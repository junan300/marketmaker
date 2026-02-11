# Create Desktop Shortcut for Market Maker
# Run this script once to create the shortcut

$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Market Maker.lnk"
$ScriptPath = $PSScriptRoot

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $ScriptPath "start-all.bat"
$Shortcut.WorkingDirectory = $ScriptPath
$Shortcut.Description = "Start Solana Market Maker (Backend + Frontend)"
$Shortcut.IconLocation = "shell32.dll,137"  # Rocket/Launch icon

try {
    $Shortcut.Save()
    Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
    Write-Host "Look for 'Market Maker' on your desktop." -ForegroundColor Green
    Write-Host "Shortcut path: $ShortcutPath" -ForegroundColor Cyan
} catch {
    Write-Host "Error creating shortcut: $_" -ForegroundColor Red
    Write-Host "You can manually create a shortcut to: $($Shortcut.TargetPath)" -ForegroundColor Yellow
}
