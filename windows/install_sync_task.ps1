param(
    [string]$TaskName = "WB SERP curl to Google Drive"
)

$ErrorActionPreference = "Stop"
$syncScript = Join-Path $PSScriptRoot "sync_wb_curl_to_drive.ps1"
$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$syncScript`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
