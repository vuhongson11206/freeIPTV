# Register a Windows Scheduled Task that refreshes the IPTV stream URLs every 3 hours.
# Run this from an elevated PowerShell only if your policy requires it.
#
#   powershell -ExecutionPolicy Bypass -File .\setup_refresh_task.ps1
#
# Remove with:
#   Unregister-ScheduledTask -TaskName "MultiPlatformIPTVRefresh" -Confirm:$false

$ErrorActionPreference = "Stop"

$TaskName = "MultiPlatformIPTVRefresh"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $ProjectDir "refresh_multi_playlists.py"
$Python = (Get-Command python.exe).Source

if (-not (Test-Path $Script)) {
    throw "Missing $Script"
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Hours 3) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "Refresh free/public Vietnamese IPTV stream URLs and SCTV playlist" -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Runs every 3 hours, starting in 2 minutes."
Write-Host "Playlists: $ProjectDir\output\all_free_channels.m3u"
