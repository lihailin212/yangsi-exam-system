<#
取消开机自启（后端/前端如果正在跑不会被停掉，需要停请另跑 stop-lan.ps1）。

用法：
  pwsh -NoProfile -File scripts\uninstall-autostart.ps1
#>
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$TaskName = 'YangsiExamLan'
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "已取消自启任务：$TaskName"
} else {
  Write-Host "自启任务不存在：$TaskName"
}
