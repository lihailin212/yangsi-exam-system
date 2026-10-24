$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stopFlag = Join-Path $LogDir 'lan.stop'

# 先写停止标记：launcher 和 5 分钟重复触发看到它就不会再把服务拉起来
Set-Content -LiteralPath $stopFlag -Value 'stop' -Encoding ascii

# 停守护进程本身（按命令行认，别只按端口）
Get-CimInstance Win32_Process -Filter "Name='pwsh.exe'" |
  Where-Object { $_.CommandLine -like '*supervisor-lan.ps1*' -and $_.CommandLine -notlike '*Get-CimInstance*' } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "已停止守护进程 PID $($_.ProcessId)"
  }

# 再按端口停后端/前端
foreach ($port in 8001, 5174) {
  $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p -and ($p.ProcessName -in 'python', 'node')) {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      Write-Host "已停止 :$port (PID $($p.Id) $($p.ProcessName))"
    }
  }
}

Remove-Item -LiteralPath (Join-Path $LogDir 'lan.pid.json') -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '局域网服务已停止（会保持停止，开机自启也不会再拉起）'
Write-Host '要恢复： pwsh -NoProfile -File scripts\start-lan.ps1'
