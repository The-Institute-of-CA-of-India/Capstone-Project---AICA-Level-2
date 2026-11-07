; KnowTaxx AP Suite - server installer. Build with installer/build_installer.py, or:
;   makensis /DVERSION=1.0.0 /DDIST_DIR=..\dist\KnowTaxx_AP_Suite /DWINSW=vendor\WinSW-x64.exe AP_Suite_Server.nsi
Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!ifndef DIST_DIR
  !define DIST_DIR "..\dist\KnowTaxx_AP_Suite"
!endif
!ifndef WINSW
  !define WINSW "vendor\WinSW-x64.exe"
!endif
!define PRODUCT "KnowTaxx AP Suite Server"
!define SERVICE "KTAPSuiteServer"
!define FIREWALL_RULE "KnowTaxx AP Suite"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\KnowTaxxAPSuiteServer"
; With SetShellVarContext all, $APPDATA is C:\ProgramData
!define DATA_DIR "$APPDATA\KnowTaxx AP Suite"
!define START_DIR "$SMPROGRAMS\KnowTaxx AP Suite"

Name "${PRODUCT}"
OutFile "KnowTaxx_AP_Suite_Server_Setup_${VERSION}.exe"
InstallDir "$PROGRAMFILES64\KnowTaxx AP Suite"
InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show

Var Port
Var PortField

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom PortPageShow PortPageLeave
!insertmacro MUI_PAGE_INSTFILES
Page custom FinishPageShow
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  SetShellVarContext all
  StrCpy $Port "5000"
FunctionEnd

Function PortPageShow
  !insertmacro MUI_HEADER_TEXT "Network port" "Choose the port this server listens on."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 36u "Other computers and phones on your network connect to this port. Keep 5000 unless another program already uses it."
  Pop $0
  ${NSD_CreateLabel} 0 44u 40u 12u "Port:"
  Pop $0
  ${NSD_CreateNumber} 44u 42u 60u 14u "$Port"
  Pop $PortField
  nsDialogs::Show
FunctionEnd

Function PortPageLeave
  ${NSD_GetText} $PortField $Port
  ${If} $Port < 1024
  ${OrIf} $Port > 65535
    MessageBox MB_ICONEXCLAMATION "Please enter a port between 1024 and 65535."
    Abort
  ${EndIf}
FunctionEnd

Function FinishPageShow
  !insertmacro MUI_HEADER_TEXT "Installation complete" "Note your first sign-in details."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 28u "KnowTaxx AP Suite is running as a Windows service. Open it from the desktop shortcut, or from any device on your network at http://THIS-COMPUTER:$Port"
  Pop $0
  ${NSD_CreateGroupBox} 0 34u 100% 46u "First sign-in"
  Pop $0
  ${NSD_CreateLabel} 10u 48u 90% 12u "Username: admin"
  Pop $0
  ${NSD_CreateLabel} 10u 60u 90% 12u "Temporary password: Admin@123  (you must change it at first sign-in)"
  Pop $0
  ${NSD_CreateLabel} 0 88u 100% 24u "Your data is stored in ${DATA_DIR}. Install Tesseract OCR separately if this installer did not include it."
  Pop $0
  nsDialogs::Show
FunctionEnd

Section "Install"
  SetShellVarContext all
  ; Upgrading: stop the running service first, or its files stay locked
  IfFileExists "$INSTDIR\KTAPSuiteServer.exe" 0 +3
    nsExec::Exec '"$INSTDIR\KTAPSuiteServer.exe" stop'
    nsExec::Exec '"$INSTDIR\KTAPSuiteServer.exe" uninstall'

  SetOutPath "$INSTDIR\KnowTaxx_AP_Suite"
  File /r "${DIST_DIR}\*.*"

  SetOutPath "$INSTDIR"
  File /oname=KTAPSuiteServer.exe "${WINSW}"
  File /oname=KTAPSuiteServer.xml "service.xml"
  CreateDirectory "${DATA_DIR}"
  CreateDirectory "${DATA_DIR}\logs"

  ; Fill in the port and data folder chosen for this machine
  nsExec::ExecToLog `powershell -NoProfile -ExecutionPolicy Bypass -Command "$$p='$INSTDIR\KTAPSuiteServer.xml'; (Get-Content -LiteralPath $$p -Raw).Replace('@PORT@','$Port').Replace('@DATA_DIR@','${DATA_DIR}') | Set-Content -LiteralPath $$p -Encoding UTF8"`

  ; Start and stop helpers (each asks for admin rights)
  FileOpen $0 "$INSTDIR\Start Service.cmd" w
  FileWrite $0 `@powershell -NoProfile -Command "Start-Process sc.exe -ArgumentList 'start ${SERVICE}' -Verb RunAs -WindowStyle Hidden"$\r$\n`
  FileClose $0
  FileOpen $0 "$INSTDIR\Stop Service.cmd" w
  FileWrite $0 `@powershell -NoProfile -Command "Start-Process sc.exe -ArgumentList 'stop ${SERVICE}' -Verb RunAs -WindowStyle Hidden"$\r$\n`
  FileClose $0

  nsExec::ExecToLog '"$INSTDIR\KTAPSuiteServer.exe" install'
  nsExec::ExecToLog `netsh advfirewall firewall add rule name="${FIREWALL_RULE}" dir=in action=allow protocol=TCP localport=$Port profile=private,domain`
  nsExec::ExecToLog '"$INSTDIR\KTAPSuiteServer.exe" start'

  WriteINIStr "$INSTDIR\KnowTaxx AP Suite.url" "InternetShortcut" "URL" "http://localhost:$Port"
  CreateShortcut "$DESKTOP\KnowTaxx AP Suite.lnk" "$INSTDIR\KnowTaxx AP Suite.url" "" "$INSTDIR\KnowTaxx_AP_Suite\_internal\app\static\icons\favicon.ico"
  CreateDirectory "${START_DIR}"
  CreateShortcut "${START_DIR}\Open AP Suite.lnk" "$INSTDIR\KnowTaxx AP Suite.url" "" "$INSTDIR\KnowTaxx_AP_Suite\_internal\app\static\icons\favicon.ico"
  CreateShortcut "${START_DIR}\Stop Service.lnk" "$INSTDIR\Stop Service.cmd"
  CreateShortcut "${START_DIR}\Start Service.lnk" "$INSTDIR\Start Service.cmd"
  CreateShortcut "${START_DIR}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${PRODUCT}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "KnowTaxx Consultancy"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  nsExec::ExecToLog '"$INSTDIR\KTAPSuiteServer.exe" stop'
  nsExec::ExecToLog '"$INSTDIR\KTAPSuiteServer.exe" uninstall'
  nsExec::ExecToLog `netsh advfirewall firewall delete rule name="${FIREWALL_RULE}"`

  RMDir /r "$INSTDIR\KnowTaxx_AP_Suite"
  Delete "$INSTDIR\KTAPSuiteServer.exe"
  Delete "$INSTDIR\KTAPSuiteServer.xml"
  Delete "$INSTDIR\KTAPSuiteServer.wrapper.log"
  Delete "$INSTDIR\KnowTaxx AP Suite.url"
  Delete "$INSTDIR\Start Service.cmd"
  Delete "$INSTDIR\Stop Service.cmd"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\KnowTaxx AP Suite.lnk"
  RMDir /r "${START_DIR}"
  DeleteRegKey HKLM "${UNINST_KEY}"

  ; Keep financial data unless the user clearly says otherwise. Default answer: keep.
  MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "Also delete ALL data (database, invoices, backups) in:$\r$\n${DATA_DIR}$\r$\n$\r$\nThis cannot be undone. Choose No to keep it." IDYES 0 IDNO keep_data
  RMDir /r "${DATA_DIR}"
  keep_data:
SectionEnd
