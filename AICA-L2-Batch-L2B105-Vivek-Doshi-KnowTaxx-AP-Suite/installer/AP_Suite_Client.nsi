; KnowTaxx AP Suite - client installer. Only creates shortcuts: the app runs on the server.
;   makensis /DVERSION=1.0.0 AP_Suite_Client.nsi
Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!define PRODUCT "KnowTaxx AP Suite"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\KnowTaxxAPSuiteClient"

Name "${PRODUCT} Client"
OutFile "KnowTaxx_AP_Suite_Client_Setup_${VERSION}.exe"
InstallDir "$LOCALAPPDATA\KnowTaxx AP Suite Client"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

Var Server
Var Port
Var ServerField
Var PortField
Var AppUrl
Var Browser

!insertmacro MUI_PAGE_WELCOME
Page custom ServerPageShow ServerPageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  StrCpy $Port "5000"
FunctionEnd

Function ServerPageShow
  !insertmacro MUI_HEADER_TEXT "Connect to the server" "Enter the address of the computer running the AP Suite server."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 12u "Server IP address or computer name (example: 192.168.1.20):"
  Pop $0
  ${NSD_CreateText} 0 14u 100% 14u "$Server"
  Pop $ServerField
  ${NSD_CreateLabel} 0 36u 100% 12u "Port:"
  Pop $0
  ${NSD_CreateNumber} 0 50u 60u 14u "$Port"
  Pop $PortField
  nsDialogs::Show
FunctionEnd

Function ServerPageLeave
  ${NSD_GetText} $ServerField $Server
  ${NSD_GetText} $PortField $Port
  ${If} $Server == ""
    MessageBox MB_ICONEXCLAMATION "Please enter the server address."
    Abort
  ${EndIf}
  StrCpy $AppUrl "http://$Server:$Port"

  ; Test the connection against the health endpoint before creating anything
  Banner::show /NOUNLOAD "Testing the connection to $AppUrl ..."
  nsExec::ExecToStack `powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $$r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri '$AppUrl/api/health'; if ($$r.Content -match '\"status\"\s*:\s*\"ok\"') { exit 0 } else { exit 2 } } catch { exit 1 }"`
  Pop $0
  Pop $1
  Banner::destroy
  ${If} $0 != 0
    MessageBox MB_YESNO|MB_ICONEXCLAMATION "Could not reach the AP Suite server at $AppUrl.$\r$\n$\r$\nCheck the address, that the server is running, and that its firewall allows this port.$\r$\n$\r$\nCreate the shortcuts anyway?" IDYES +2
    Abort
  ${EndIf}
FunctionEnd

Function FindBrowser
  StrCpy $Browser ""
  ${If} ${FileExists} "$PROGRAMFILES32\Microsoft\Edge\Application\msedge.exe"
    StrCpy $Browser "$PROGRAMFILES32\Microsoft\Edge\Application\msedge.exe"
  ${ElseIf} ${FileExists} "$PROGRAMFILES64\Microsoft\Edge\Application\msedge.exe"
    StrCpy $Browser "$PROGRAMFILES64\Microsoft\Edge\Application\msedge.exe"
  ${ElseIf} ${FileExists} "$PROGRAMFILES64\Google\Chrome\Application\chrome.exe"
    StrCpy $Browser "$PROGRAMFILES64\Google\Chrome\Application\chrome.exe"
  ${ElseIf} ${FileExists} "$PROGRAMFILES32\Google\Chrome\Application\chrome.exe"
    StrCpy $Browser "$PROGRAMFILES32\Google\Chrome\Application\chrome.exe"
  ${ElseIf} ${FileExists} "$LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    StrCpy $Browser "$LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  ${EndIf}
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  WriteINIStr "$INSTDIR\KnowTaxx AP Suite.url" "InternetShortcut" "URL" "$AppUrl"
  Call FindBrowser
  CreateDirectory "$SMPROGRAMS\KnowTaxx AP Suite"
  ${If} $Browser != ""
    CreateShortcut "$DESKTOP\KnowTaxx AP Suite.lnk" "$Browser" "--app=$AppUrl"
    CreateShortcut "$SMPROGRAMS\KnowTaxx AP Suite\KnowTaxx AP Suite.lnk" "$Browser" "--app=$AppUrl"
  ${Else}
    CreateShortcut "$DESKTOP\KnowTaxx AP Suite.lnk" "$INSTDIR\KnowTaxx AP Suite.url"
    CreateShortcut "$SMPROGRAMS\KnowTaxx AP Suite\KnowTaxx AP Suite.lnk" "$INSTDIR\KnowTaxx AP Suite.url"
  ${EndIf}
  CreateShortcut "$SMPROGRAMS\KnowTaxx AP Suite\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${PRODUCT} Client"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "KnowTaxx Consultancy"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\KnowTaxx AP Suite.lnk"
  RMDir /r "$SMPROGRAMS\KnowTaxx AP Suite"
  Delete "$INSTDIR\KnowTaxx AP Suite.url"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
