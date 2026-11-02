' AppealIQ desktop shortcut target: runs launch_appealiq.ps1 with no console window.
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & here & "\launch_appealiq.ps1"""
CreateObject("WScript.Shell").Run cmd, 0, False
