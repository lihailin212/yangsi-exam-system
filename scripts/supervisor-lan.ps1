<#
局域网开考常驻守护进程。

用法：
  pwsh -NoProfile -File scripts\supervisor-lan.ps1

做什么：
  1. 载入 .env.local（生产库 Neon + Blob 令牌），避免回落到本地 SQLite 题库
  2. 拉起后端 8001 和前端 5174
  3. 一直盯着：哪个服务掉了就重新拉起（考试中途后端挂掉不用人管）
  4. logs\lan.stop 存在时不启动（stop-lan.ps1 写这个文件，start-lan.ps1 负责清）

由计划任务 YangsiExamLan 托管（登录时 + 每 5 分钟触发一次）。
注意：重装计划任务会杀掉正在运行的实例，要重启请先 stop-lan.ps1 再 install-autostart.ps1。

日志：logs\supervisor.log
#>
param(
  [int]$BackendPort = 8001,
  [int]$FrontendPort = 5174,
  [int]$PollSeconds = 10,
  # 后端启动时要连 Neon 并跑一遍建表/补列/校序列，实测要 40~60 秒，
  # 这段时间内端口还没绑上属于正常，不能判定为失败。
  [int]$BootGraceSeconds = 120
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$LogDir = Join-Path $RepoRoot 'logs'
$StopFlag = Join-Path $LogDir 'lan.stop'
$LogFile = Join-Path $LogDir 'supervisor.log'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# 停止标记由“人”来清（start-lan.ps1），守护进程自己不清。
# 有标记说明用户明确喊停：计划任务的重复触发也会被这一行挡住，
# 否则"停止"最多维持到下一次触发，等于停不住。
if (Test-Path $StopFlag) {
  Add-Content -LiteralPath $LogFile -Encoding utf8 -Value (
    '{0} 检测到停止标记，不启动。要恢复请跑 scripts\start-lan.ps1' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  )
  exit 0
}

function Write-Log([string]$Message) {
  $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
  Add-Content -LiteralPath $LogFile -Value $line -Encoding utf8
}

# 只允许一个守护进程，否则两个会互相抢端口
$mutex = New-Object System.Threading.Mutex($false, 'Global\YangsiExamLanSupervisor')
if (-not $mutex.WaitOne(0)) {
  Write-Log '已有守护进程在运行，退出。'
  exit 0
}

# ---- 载入 .env.local（关键：没有 DATABASE_URL 会静默用本地 exam.db 题库）----
$envFile = Join-Path $RepoRoot '.env.local'
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile -Encoding UTF8) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith('#') -or -not $t.Contains('=')) { continue }
    $k, $v = $t.Split('=', 2)
    $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
    if ($k -and -not (Test-Path "env:$k")) { Set-Item -Path "env:$k" -Value $v }
  }
}

$ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Sort-Object { if ($_.InterfaceAlias -match 'Wi-Fi|WLAN|无线') { 0 } else { 1 } } |
  Select-Object -First 1 -ExpandProperty IPAddress
if (-not $ip) { Write-Log '未找到局域网 IP，退出。'; exit 1 }

$env:FRONTEND_BASE_URL = "http://${ip}:$FrontendPort"
$env:LAN_API = "http://127.0.0.1:$BackendPort"
$env:LAN_PORT = "$FrontendPort"

function Test-Port([int]$Port) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $t = $c.ConnectAsync('127.0.0.1', $Port)
    if (-not $t.Wait(1500)) { $c.Close(); return $false }
    $c.Close(); return $true
  } catch { return $false }
}

function Start-Backend {
  Write-Log "启动后端 :$BackendPort"
  $p = Start-Process -FilePath 'python' `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', "$BackendPort" `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput (Join-Path $LogDir 'lan-backend.out.log') `
    -RedirectStandardError  (Join-Path $LogDir 'lan-backend.err.log') `
    -WindowStyle Hidden -PassThru
  return $p.Id
}

function Start-Frontend {
  Write-Log "启动前端 :$FrontendPort"
  $vite = Join-Path $RepoRoot 'node_modules\vite\bin\vite.js'
  $p = Start-Process -FilePath 'node' `
    -ArgumentList $vite, '--config', (Join-Path $RepoRoot 'vite.lan.config.js') `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput (Join-Path $LogDir 'lan-frontend.out.log') `
    -RedirectStandardError  (Join-Path $LogDir 'lan-frontend.err.log') `
    -WindowStyle Hidden -PassThru
  return $p.Id
}

# 每个服务的"正在启动"记录：pid + 拉起时刻
$pending = @{}

function Ensure-Service([string]$Name, [int]$Port, [scriptblock]$Starter) {
  if (Test-Port $Port) {
    if ($pending.ContainsKey($Name)) { $pending.Remove($Name) }
    return
  }

  $state = $pending[$Name]
  if ($state) {
    $alive = $null -ne (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)
    $age = ((Get-Date) - $state.at).TotalSeconds
    if ($alive -and $age -lt $BootGraceSeconds) { return }   # 还在启动，等下一轮
    if ($alive) {
      Write-Log "$Name 进程 $($state.pid) 存活但 ${int}$age 秒仍未监听 :$Port，判定为卡死，重启"
      Stop-Process -Id $state.pid -Force -ErrorAction SilentlyContinue
    } else {
      Write-Log "$Name 进程 $($state.pid) 已退出但 :$Port 仍未监听，重新拉起"
    }
  }

  $newPid = & $Starter
  $pending[$Name] = @{ pid = $newPid; at = (Get-Date) }
  Write-Log "$Name PID $newPid（等待就绪，最长 $BootGraceSeconds 秒）"
}

Write-Log "=== 守护进程启动 ip=$ip 后端=$BackendPort 前端=$FrontendPort ==="

while ($true) {
  if (Test-Path $StopFlag) {
    Write-Log '收到停止标记，守护进程退出。'
    break
  }

  Ensure-Service 'backend'  $BackendPort  { Start-Backend }
  Ensure-Service 'frontend' $FrontendPort { Start-Frontend }

  @{ ip = $ip; backendPort = $BackendPort; frontendPort = $FrontendPort; supervised = $true
     backend = $pending['backend'].pid; frontend = $pending['frontend'].pid } | ConvertTo-Json |
    Set-Content -Encoding UTF8 (Join-Path $LogDir 'lan.pid.json')

  Start-Sleep -Seconds $PollSeconds
}

$mutex.ReleaseMutex()
