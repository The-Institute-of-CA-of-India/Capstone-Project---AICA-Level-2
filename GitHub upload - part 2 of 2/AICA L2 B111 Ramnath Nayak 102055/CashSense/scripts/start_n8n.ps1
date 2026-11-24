# Start n8n Community Edition locally (http://localhost:5678) for CashSense.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\start_n8n.ps1   (-CheckOnly: exit 0 if n8n is installed)
param([switch]$CheckOnly)
$root = Split-Path $PSScriptRoot -Parent

# Reload the saved Windows PATH (a window opened by an older program may carry an out-of-date copy) and make sure
# the npm global folder (where n8n is installed) and the Node.js folder are on it.
$paths = @([Environment]::GetEnvironmentVariable("Path", "Machine"), [Environment]::GetEnvironmentVariable("Path", "User"))
# n8n is installed in "n8n-runtime" next to the project folder (on D:), because an install made from inside the
# Claude desktop app lands in that app's private copy of AppData, which normal windows cannot see.
$runtime = Join-Path (Split-Path $root -Parent) "n8n-runtime"
$extra = @($runtime)
if ($env:APPDATA) { $extra += (Join-Path $env:APPDATA "npm") }
$nodeDir = (Get-ItemProperty "HKLM:\SOFTWARE\Node.js" -ErrorAction SilentlyContinue).InstallPath
if ($nodeDir) { $extra += $nodeDir }
$env:Path = (($extra + $paths) -join ";")       # n8n-runtime first
$n8n = (Get-Command n8n.cmd -ErrorAction SilentlyContinue).Source
if ($CheckOnly) { if ($n8n) { exit 0 } else { exit 1 } }
if (-not $n8n) {
    Write-Host "n8n was not found (optional - CashSense works without it). To add it, install Node.js 20+ and run once" -ForegroundColor Yellow
    Write-Host "(takes 5-10 minutes):" -ForegroundColor Yellow
    Write-Host ('    $env:NODE_USE_SYSTEM_CA = "1"; npm.cmd install -g n8n --prefix "' + $runtime + '"') -ForegroundColor Yellow
    exit 1
}
$drop = Join-Path $root "data\inbox\drop"
New-Item -ItemType Directory -Force $drop | Out-Null

$env:NODE_USE_SYSTEM_CA = "1"                      # trust the Windows certificate store (antivirus HTTPS scanning)
$env:GENERIC_TIMEZONE = "Asia/Kolkata"
$env:TZ = "Asia/Kolkata"
$env:N8N_HOST = "localhost"
$env:N8N_PORT = "5678"
$env:N8N_LISTEN_ADDRESS = "127.0.0.1"              # not reachable from other machines
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_PERSONALIZATION_ENABLED = "false"
$env:N8N_RESTRICT_FILE_ACCESS_TO = $drop           # the drop-folder trigger may only read this folder
# make sure the CashSense workflows are published (they can come back unpublished after an abrupt shutdown)
python (Join-Path $PSScriptRoot "setup_n8n.py") --publish-only | Out-Null
& $n8n start
