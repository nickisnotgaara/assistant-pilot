param(
  [string]$Workspace = "$env:USERPROFILE\.openclaw\workspace",
  [switch]$SkipAutomations
)

$ErrorActionPreference = "Stop"
$PilotRoot = Split-Path -Parent $PSScriptRoot

Write-Host "== OpenClaw pilot install ==" -ForegroundColor Cyan
Write-Host "Workspace: $Workspace"

New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
New-Item -ItemType Directory -Force -Path "$Workspace\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "$Workspace\ledger\docs" | Out-Null

Copy-Item -Recurse -Force "$PilotRoot\skills\*" "$Workspace\skills\"
Write-Host "Skills -> $Workspace\skills"

if (-not (Test-Path "$Workspace\ledger\objects.json")) {
  Copy-Item -Recurse -Force "$PilotRoot\ledger\*" "$Workspace\ledger\"
  Write-Host "Ledger seeds -> $Workspace\ledger"
} else {
  Write-Host "Ledger already exists, keeping current data" -ForegroundColor Yellow
}

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
  Write-Host "openclaw CLI not found. Install first: npm install -g openclaw@latest --allow-scripts=openclaw" -ForegroundColor Red
  exit 1
}

if (-not $SkipAutomations) {
  openclaw automations create "0 8 * * *" `
    "Запусти скилл morning-digest и отправь владельцу утренний дайджест." `
    --name "morning-digest" --session isolated

  openclaw automations create "0 9,17 * * *" `
    "Запусти скилл deadline-monitor: проверь просрочные и горящие договорённости, пришли готовые тексты напоминаний." `
    --name "deadline-check" --session isolated

  openclaw automations create "0 18 * * *" `
    "Запусти скилл morning-digest в вечернем режиме и пришли дайджест владельцу." `
    --name "evening-digest" --session isolated

  Write-Host "Automations registered: morning-digest (08:00), deadline-check (09:00/17:00), evening-digest (18:00)"
}

Write-Host ""
Write-Host "Done. Next steps (see README-PILOT.md):" -ForegroundColor Green
Write-Host "  1. openclaw onboard          # модель + workspace"
Write-Host "  2. openclaw channels add --channel whatsapp   # QR linked device"
Write-Host "  3. openclaw channels add --channel telegram   # токен бота"
Write-Host "  4. \$env:AMOCRM_SUBDOMAIN / \$env:AMOCRM_ACCESS_TOKEN"
Write-Host "  5. openclaw gateway status ; openclaw dashboard"
