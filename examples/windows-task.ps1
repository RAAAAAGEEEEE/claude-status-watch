# Run once in PowerShell. Adjust the path to where you cloned the repository.
# UNTESTED on Windows by the author: see docs/LIMITATIONS.md.
$script = "$env:USERPROFILE\claude-status-watch\claude_status_watch.py"
$action = New-ScheduledTaskAction -Execute "python" -Argument "-I `"$script`" check"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "claude-status-watch" -Action $action -Trigger $trigger
# Remove with: Unregister-ScheduledTask -TaskName "claude-status-watch" -Confirm:$false
