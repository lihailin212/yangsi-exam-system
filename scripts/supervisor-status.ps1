<#
查看局域网开考服务状态。

用法：
  pwsh -NoProfile -File scripts\supervisor-status.ps1
#>
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot 'logs'
$log = Join-Path $LogDir 'supervisor.log'

function Get-PortPid([int]$Port) {
  $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
       Select-Object -First 1
  if ($c) { return $c.OwningProcess } else { return $null }
}

# 后端启动要连远端库、跑一遍建表补列，实测 40~60 秒。
# 端口还没绑上时要说清是"启动中"还是"挂了"，否则每次看都是一头雾水。
function Get-State([int]$Port, [string]$Label) {
  $pidOnPort = Get-PortPid $Port
  if ($pidOnPort) { return "运行中 (PID $pidOnPort)" }

  if (-not (Test-Path $log)) { return '未运行' }

  $line = Get-Content $log -Tail 40 -Encoding UTF8 |
          Where-Object { $_ -match "$Label PID (\d+)" } |
          Select-Object -Last 1
  if (-not $line) { return '未运行' }

  $m = [regex]::Match($line, '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(\d+)（等待就绪')
  if (-not $m) { return '未运行' }

  $startedAt = [datetime]::ParseExact($m.Groups[1].Value, 'yyyy-MM-dd HH:mm:ss', $null)
  $waited = [int]((Get-Date) - $startedAt).TotalSeconds
  if (Get-Process -Id ([int]$m.Groups[2].Value) -ErrorAction SilentlyContinue) {
    if ($waited -lt 120) { return "启动中（已等待 ${waited}s / 上限 120s）" }
    return "启动超时（已等待 ${waited}s），看 logs\lan-backend.err.log"
  }
  return "进程 $($m.Groups[2].Value) 已退出，等待守护进程重拉"
}

$be = Get-PortPid 8001
$ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
  Select-Object -First 1 -ExpandProperty IPAddress

Write-Host ''
Write-Host '局域网开考服务'
Write-Host ('  后端 8001 : ' + (Get-State 8001 'backend'))
Write-Host ('  前端 5174 : ' + (Get-State 5174 'frontend'))
Write-Host '  管理入口 : http://127.0.0.1:5174/#/login'
Write-Host ('  手机入口 : http://' + $ip + ':5174/#/exam-login/<考试ID>')

if ($be) {
  try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/exam-login/7' -TimeoutSec 8
    Write-Host '  接口自检 : 通过'
  } catch {
    Write-Host '  接口自检 : 失败（端口在监听但接口没响应）'
  }
}

$task = Get-ScheduledTask -TaskName 'YangsiExamLan' -ErrorAction SilentlyContinue
Write-Host ('  开机自启 : ' + $(if ($task) { '已开启' } else { '未开启' }))
Write-Host ''

if (Test-Path $log) {
  Write-Host '守护进程日志（最后 5 行）：'
  Get-Content $log -Tail 5 -Encoding UTF8 | ForEach-Object { '  ' + $_ }
  Write-Host ''
}
