# AppealIQ desktop launcher (SPEC section 14, CR-001 (c)). Started hidden by launch_appealiq.vbs.
#
# 1. Starts Streamlit on 127.0.0.1:8501 with no console window (or reuses a running instance).
# 2. Opens the app in a Microsoft Edge app window (--app=...) with its own profile folder.
# 3. When that window is closed, stops the Streamlit process it started.
# If Edge is not installed, the default browser is opened and the app keeps running until the
# hidden process is stopped (sign out, or end "python" in Task Manager).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Url = "http://127.0.0.1:8501"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "data\logs"
$EdgeProfile = Join-Path $env:LOCALAPPDATA "AppealIQ\EdgeAppProfile"

function Test-AppUp {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$Url/_stcore/health"
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Find-Edge {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

if (-not (Test-Path $Python)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("AppealIQ is not set up yet. Run setup.bat first.", "AppealIQ") | Out-Null
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$server = $null
if (-not (Test-AppUp)) {
    $server = Start-Process -FilePath $Python -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
        -ArgumentList "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", `
                      "--server.port", "8501", "--server.headless", "true" `
        -RedirectStandardOutput (Join-Path $LogDir "launcher_stdout.log") `
        -RedirectStandardError (Join-Path $LogDir "launcher_stderr.log")
    $deadline = (Get-Date).AddSeconds(90)
    while (-not (Test-AppUp)) {
        if ($server.HasExited -or (Get-Date) -gt $deadline) {
            Add-Type -AssemblyName PresentationFramework
            [System.Windows.MessageBox]::Show("AppealIQ could not start. See data\logs\launcher_stderr.log.", "AppealIQ") | Out-Null
            if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
            exit 1
        }
        Start-Sleep -Milliseconds 500
    }
}

$edge = Find-Edge
if ($null -eq $edge) {
    Start-Process $Url
    exit 0
}

New-Item -ItemType Directory -Force -Path $EdgeProfile | Out-Null
Start-Process -FilePath $edge -ArgumentList "--app=$Url", "--user-data-dir=`"$EdgeProfile`"", `
    "--no-first-run", "--window-size=1440,900" | Out-Null

# Wait until every Edge process using the AppealIQ profile has closed (Edge may hand the window
# to a child process, so the launched process alone is not a reliable signal).
$needle = "*AppealIQ\EdgeAppProfile*"
Start-Sleep -Seconds 3
do {
    Start-Sleep -Seconds 2
    $open = Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" |
        Where-Object { $_.CommandLine -like $needle }
} while ($open)

if ($null -ne $server -and -not $server.HasExited) {
    Stop-Process -Id $server.Id -Force
}
