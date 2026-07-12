# Start-Hermes.ps1 — Hermes startup wrapper.
# Reads .telegram-config for pre_scripts, post_scripts — fully dynamic.
#
# Usage: Run as desktop shortcut or manually.

$ErrorActionPreference = 'Continue'
$WORKSPACE = $PSScriptRoot | Split-Path -Parent
$configFile = "$WORKSPACE\.telegram-config"

function Run-Scripts($label, $scripts) {
    if (-not $scripts) { return }
    foreach ($script in $scripts) {
        # Expand $env:LOCALAPPDATA and $WORKSPACE inside the script string
        $expanded = $script `
            -replace '\$env:LOCALAPPDATA', $env:LOCALAPPDATA `
            -replace '\$WORKSPACE', $WORKSPACE
        Write-Host "  ▶ $label`: $expanded" -ForegroundColor Cyan
        try { Invoke-Expression $expanded } catch { Write-Host "  ⚠ Failed: $_" -ForegroundColor Yellow }
    }
}

# Load config
$cfg = $null
if (Test-Path $configFile) {
    try { $cfg = Get-Content $configFile -Raw | ConvertFrom-Json }
    catch { Write-Host "⚠ Could not read .telegram-config: $_" -ForegroundColor Yellow }
}

# Pre-scripts
Write-Host "🔄 Running pre-scripts..." -ForegroundColor Cyan
Run-Scripts "pre" $cfg.pre_scripts

# Launch Hermes Gateway
Write-Host ""
Write-Host "🚀 Starting Hermes Gateway..." -ForegroundColor Cyan
$hermesCmd = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"
if (-not (Test-Path $hermesCmd)) {
    Write-Host "ERROR: Hermes not installed at $hermesCmd" -ForegroundColor Red
    exit 1
}
& $hermesCmd

# Post-scripts
Write-Host "🔧 Running post-scripts..." -ForegroundColor Cyan
Run-Scripts "post" $cfg.post_scripts
