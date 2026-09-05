# Extraction daemon watchdog — relaunches the daemon if it died.
# Registered as a Windows Scheduled Task (every 30 min). Stops relaunching once
# the batch is complete (log contains BOTH BATCHES COMPLETE).

$log = "D:\Capstone\logs\extract_daemon.log"
$errlog = "D:\Capstone\logs\extract_daemon.err.log"
$wdlog = "D:\Capstone\logs\watchdog.log"

function Log($msg) {
    Add-Content -Path $wdlog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
}

if ((Test-Path $log) -and (Select-String -Path $log -Pattern "BOTH BATCHES COMPLETE" -Quiet)) {
    Log "batch complete - nothing to do"
    exit 0
}

# ollama is the extraction floor — make sure it's alive too (doesn't auto-start on boot)
$ollamaUp = try { (Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 8 -UseBasicParsing).StatusCode -eq 200 } catch { $false }
if (-not $ollamaUp) {
    Log "ollama down - starting"
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 15
}

$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'extract_daemon' }

if ($running) {
    Log "daemon alive (PID $($running.ProcessId))"
    exit 0
}

Log "daemon NOT running - relaunching"
Start-Process -FilePath "python" -ArgumentList "scripts/extract_daemon.py" `
    -WorkingDirectory "D:\Capstone" -WindowStyle Hidden `
    -RedirectStandardOutput $log -RedirectStandardError $errlog
Log "relaunched"
