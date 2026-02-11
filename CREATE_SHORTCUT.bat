@echo off
echo Creating Desktop Shortcut...
echo.

powershell -ExecutionPolicy Bypass -Command ^
"$WshShell = New-Object -ComObject WScript.Shell; ^
$Desktop = [Environment]::GetFolderPath('Desktop'); ^
$Shortcut = $WshShell.CreateShortcut((Join-Path $Desktop 'Market Maker.lnk')); ^
$Shortcut.TargetPath = '%CD%\start-all.bat'; ^
$Shortcut.WorkingDirectory = '%CD%'; ^
$Shortcut.Description = 'Start Solana Market Maker'; ^
$Shortcut.IconLocation = 'shell32.dll,137'; ^
$Shortcut.Save(); ^
Write-Host 'Shortcut created on Desktop!' -ForegroundColor Green"

echo.
echo Done! Check your Desktop for "Market Maker" shortcut.
echo.
pause
