# Creates a "Hermes Gateway (Start)" shortcut on the Desktop.
# Works with or without OneDrive — detects automatically.

$desktop = if ($env:OneDrive) { "$env:OneDrive\Desktop" } else { "$env:USERPROFILE\Desktop" }
$target  = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"

if (-not (Test-Path $target)) {
    Write-Host "ERROR: Hermes not installed at $target" -ForegroundColor Red
    Write-Host "Run: pip install hermes-agent && hermes gateway install" -ForegroundColor Yellow
    exit 1
}

$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$desktop\Hermes Gateway (Start).lnk")
$lnk.TargetPath       = $target
$lnk.WorkingDirectory = "$env:LOCALAPPDATA\hermes\hermes-agent"
$lnk.WindowStyle      = 7   # minimised / hidden — no console window
$lnk.Description      = "Start Hermes Gateway (Telegram bot)"
$lnk.Save()

Write-Host "✓ Shortcut created: $desktop\Hermes Gateway (Start).lnk" -ForegroundColor Green
