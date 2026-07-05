# Start-Hermes.ps1 — Hermes startup wrapper.
# 1. Syncs ~/.claude/skills/ → .skills-index.txt
# 2. Launches Hermes gateway
#
# Usage: Run as desktop shortcut or manually.

$ErrorActionPreference = 'Continue'
$WORKSPACE = $PSScriptRoot | Split-Path -Parent

Write-Host "🔄 Syncing skills index..." -ForegroundColor Cyan
try {
    $nodeArgs = @('--use-system-ca', "$WORKSPACE\scripts\sync-skills.js")
    $result = & node @nodeArgs 2>&1
    Write-Host $result -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Skills sync skipped: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 Starting Hermes Gateway..." -ForegroundColor Cyan
$hermesCmd = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"

if (-not (Test-Path $hermesCmd)) {
    Write-Host "ERROR: Hermes not installed at $hermesCmd" -ForegroundColor Red
    Write-Host "Run: pip install hermes-agent && hermes gateway install" -ForegroundColor Yellow
    exit 1
}

& $hermesCmd
