# Start the CashSense local API (127.0.0.1:8765, or CASHSENSE_PORT) that the dashboard and n8n call.
# Run from the cashsense folder:  powershell -ExecutionPolicy Bypass -File scripts\start_cashsense.ps1
Set-Location (Split-Path $PSScriptRoot -Parent)
$port = 8765
if ($env:CASHSENSE_PORT) { $port = [int]$env:CASHSENSE_PORT }
python -m cashsense.cli serve --port $port
