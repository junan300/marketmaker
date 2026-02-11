# Restart Market Maker Server Script
# This script stops any running instances and helps you restart with new config

Write-Host "=== Market Maker Server Restart ===" -ForegroundColor Cyan
Write-Host ""

# Check for running Python processes (likely uvicorn)
$pythonProcs = Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.Path -like "*Python*"}
if ($pythonProcs) {
    Write-Host "Found running Python processes:" -ForegroundColor Yellow
    $pythonProcs | ForEach-Object { Write-Host "  PID: $($_.Id) - $($_.Path)" }
    Write-Host ""
    $kill = Read-Host "Kill these processes? (y/n)"
    if ($kill -eq "y") {
        $pythonProcs | ForEach-Object {
            Write-Host "Stopping PID $($_.Id)..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force
        }
        Start-Sleep -Seconds 2
        Write-Host "Processes stopped." -ForegroundColor Green
    }
} else {
    Write-Host "No Python processes found running." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Checking .env Configuration ===" -ForegroundColor Cyan
if (Test-Path .env) {
    $envContent = Get-Content .env
    $network = ($envContent | Select-String "SOLANA_NETWORK=").ToString().Split("=")[1]
    $passphrase = ($envContent | Select-String "MM_KEYSTORE_PASSPHRASE=").ToString().Split("=")[1]
    
    Write-Host "Network: $network" -ForegroundColor $(if ($network -eq "mainnet-beta") { "Green" } else { "Red" })
    Write-Host "Passphrase: $($passphrase.Substring(0, [Math]::Min(10, $passphrase.Length)))..." -ForegroundColor Gray
} else {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Start the backend server:" -ForegroundColor Yellow
Write-Host "   python -m uvicorn backend.main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "2. In another terminal, start the frontend:" -ForegroundColor Yellow
Write-Host "   npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "3. Access the UI at: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "4. Import your new wallet:" -ForegroundColor Yellow
Write-Host "   - Use the 'Import Wallet' button in the UI" -ForegroundColor White
Write-Host "   - Or use the API: POST /api/wallet/import" -ForegroundColor White
Write-Host ""
