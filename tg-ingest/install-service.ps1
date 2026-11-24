param(
  [switch]$Remove
)

$TaskName = "tg-ingest"
$Script = "C:\Users\User\Desktop\openclaw-pilot\tg-ingest\ingest.py"
$Config = "C:\Users\User\Desktop\openclaw-pilot\tg-ingest\config.json"
$Log = "C:\Users\User\Desktop\openclaw-pilot\tg-ingest\ingest.log"

if ($Remove) {
  schtasks /Delete /TN $TaskName /F | Out-Null
  Write-Host "Removed task $TaskName"
  exit 0
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c pythonw.exe `"$Script`" --config `"$Config`" >> `"$Log`" 2>&1"
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Task $TaskName registered (at logon) and started. Log: $Log"
