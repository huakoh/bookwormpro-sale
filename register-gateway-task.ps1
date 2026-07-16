$action = New-ScheduledTaskAction `
    -Execute "C:\Users\leesu\AppData\Local\Programs\Python\Python312\python.exe" `
    -Argument "gateway\run.py" `
    -WorkingDirectory "C:\Users\leesu\BookwormPRO"

$trigger = New-ScheduledTaskTrigger -AtLogOn -User "leesu"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "BookwormProGateway" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "BookwormPRO Gateway - wecom/weixin/webhook" `
    -Force

Write-Host "[OK] BookwormProGateway task registered (auto-start at logon, 3x restart on failure)"
