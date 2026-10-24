<#
注册开机自启：登录 Windows 后自动拉起局域网开考服务（守护进程）。

用法：
  pwsh -NoProfile -File scripts\install-autostart.ps1

卸载：
  pwsh -NoProfile -File scripts\uninstall-autostart.ps1
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$TaskName = 'YangsiExamLan'
$Script = Join-Path $PSScriptRoot 'supervisor-lan.ps1'

# 脚本里有中文，Windows PowerShell 5.1 按 ANSI 读会解析失败，必须用 pwsh
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell).Source }

$action = New-ScheduledTaskAction -Execute $pwsh `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

# 触发器一：登录时
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# 触发器二：每 5 分钟重复一次，兼作自愈。
# -MultipleInstances IgnoreNew 保证已经在跑时不会起第二份；
# 万一守护进程意外没了（比如被别的程序杀掉），下一次触发就把它拉回来。
# 注意：重注册任务会杀掉正在运行的实例，所以重装前先跑 stop-lan.ps1。
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName `
  -Description '杨思考试系统 - 局域网开考服务（后端 8001 / 前端 5174）' `
  -Action $action -Trigger @($triggerLogon, $triggerRepeat) `
  -Principal $principal -Settings $settings | Out-Null

Write-Host ''
Write-Host "已注册开机自启任务：$TaskName"
Write-Host "  程序    : $pwsh"
Write-Host '  触发    : 登录时 + 每 5 分钟检查一次'
Write-Host '  效果    : 登录后自动启动；考试中途服务挂了会自动拉起；守护进程意外死了也会被重新拉起'
Write-Host ''
Write-Host '现在立刻启动一次：'
Write-Host '  pwsh -NoProfile -File scripts\start-lan.ps1'
Write-Host ''
Write-Host '查看状态：  pwsh -NoProfile -File scripts\supervisor-status.ps1'
Write-Host '彻底停止：  pwsh -NoProfile -File scripts\stop-lan.ps1'
Write-Host '取消自启：  pwsh -NoProfile -File scripts\uninstall-autostart.ps1'
