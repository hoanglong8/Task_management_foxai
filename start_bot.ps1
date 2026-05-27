# FOXAI Bot Launcher
$botDir = $PSScriptRoot
$venvPython = Join-Path $botDir "venv\Scripts\python.exe"
$botScript = Join-Path $botDir "foxai_task_bot.py"
$pidFile = Join-Path $botDir "bot.pid"
$logFile = Join-Path $botDir "bot.log"
$errFile = Join-Path $botDir "bot_error.log"

Write-Host "FOXAI Telegram Bot Launcher" -ForegroundColor Cyan

# Dung bot cu neu dang chay
if (Test-Path $pidFile) {
    $storedPid = [int](Get-Content $pidFile -ErrorAction SilentlyContinue)
    if ($storedPid) {
        $existing = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "Dung bot cu (PID $storedPid)..." -ForegroundColor Yellow
            Stop-Process -Id $storedPid -Force
            Start-Sleep -Seconds 2
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Kill stray python processes
Get-WmiObject Win32_Process | Where-Object {
    $_.Name -like "*python*" -and $_.CommandLine -like "*foxai_task_bot*"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1
Write-Host "Khoi dong bot (background)..." -ForegroundColor Green

# Chay background - khong chet khi dong terminal
# Quote bot script path de xu ly space trong duong dan
$proc = Start-Process -FilePath $venvPython -ArgumentList "`"$botScript`"" -PassThru -WindowStyle Hidden -RedirectStandardOutput $logFile -RedirectStandardError $errFile

# Python bot tu quan ly bot.pid -- khong ghi o day
Write-Host "Bot started - PID $($proc.Id)" -ForegroundColor Green
Write-Host "Log: $logFile" -ForegroundColor Gray
