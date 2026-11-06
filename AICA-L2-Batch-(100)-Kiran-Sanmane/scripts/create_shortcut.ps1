# Creates the "AppealIQ" desktop shortcut (SPEC section 14, CR-001 (c)). Run by setup.bat.
# The shortcut runs launch_appealiq.vbs through wscript.exe, so no console window appears.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$Link = Join-Path $Desktop "AppealIQ.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($Link)
$shortcut.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$shortcut.Arguments = "`"" + (Join-Path $Root "scripts\launch_appealiq.vbs") + "`""
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation = (Join-Path $Root "assets\appealiq.ico") + ",0"
$shortcut.Description = "AppealIQ - ITAT Appeal Readiness Analyser"
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output "Desktop shortcut created: $Link"
