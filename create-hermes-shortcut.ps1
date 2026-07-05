# Creates a "Hermes Gateway (Start)" shortcut on the Desktop.
# Runs Start-Hermes.ps1 which:
#   1. Syncs ~/.claude/skills/ → .skills-index.txt
#   2. Launches Hermes Gateway
# Works with or without OneDrive — detects automatically.

$desktop   = if ($env:OneDrive) { "$env:OneDrive\Desktop" } else { "$env:USERPROFILE\Desktop" }
$workspace = $PSScriptRoot
$wrapper   = "$workspace\scripts\Start-Hermes.ps1"
$hermesCmd = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"

if (-not (Test-Path $hermesCmd)) {
    Write-Host "ERROR: Hermes not installed at $hermesCmd" -ForegroundColor Red
    Write-Host "Run: pip install hermes-agent && hermes gateway install" -ForegroundColor Yellow
    exit 1
}

$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$desktop\Hermes Gateway (Start).lnk")
$lnk.TargetPath       = "pwsh.exe"
$lnk.Arguments        = "-NoProfile -WindowStyle Hidden -File `"$wrapper`""
$lnk.WorkingDirectory = $workspace
$lnk.WindowStyle      = 7   # minimised / hidden — no console window
$lnk.Description      = "Start Hermes Gateway (syncs skills + starts bot)"
$lnk.Save()

Write-Host "✓ Shortcut created: $desktop\Hermes Gateway (Start).lnk" -ForegroundColor Green
Write-Host "  → Syncs skills index on every startup" -ForegroundColor Cyan
