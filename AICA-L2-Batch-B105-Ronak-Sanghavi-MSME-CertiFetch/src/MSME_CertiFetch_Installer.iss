; =====================================================================
;  MSME CertiFetch - Windows installer script (Inno Setup 6, free tool)
;  Build_EXE.bat compiles this automatically when Inno Setup is installed.
; =====================================================================
#ifndef SourceDir
  #define SourceDir "dist\MSME CertiFetch"
#endif

[Setup]
AppId={{A57FEBF7-DCB2-4A34-9400-F13CBC2C6B40}
AppName=MSME CertiFetch
AppVersion=1.0
AppVerName=MSME CertiFetch 1.0
AppPublisher=Ramesh Rajni & Co LLP
AppPublisherURL=https://rameshrajni.com
AppSupportURL=https://rameshrajni.com
; installs per user, so staff do NOT need admin rights
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\MSME CertiFetch
DisableProgramGroupPage=yes
OutputBaseFilename=MSME_CertiFetch_Setup_v1.0
SetupIconFile=Art\autumn_icon.ico
UninstallDisplayIcon={app}\MSME CertiFetch.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\MSME CertiFetch"; Filename: "{app}\MSME CertiFetch.exe"
Name: "{autodesktop}\MSME CertiFetch"; Filename: "{app}\MSME CertiFetch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MSME CertiFetch.exe"; Description: "Launch MSME CertiFetch now"; Flags: nowait postinstall skipifsilent

[Code]
const
  ChromeKey = 'Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe';

function ChromeInstalled: Boolean;
begin
  Result := RegKeyExists(HKCU, ChromeKey) or RegKeyExists(HKLM, ChromeKey);
  if (not Result) and IsWin64 then
    Result := RegKeyExists(HKLM64, ChromeKey);
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not ChromeInstalled then
    SuppressibleMsgBox(
      'MSME CertiFetch uses Google Chrome to open the Udyam portal, and Chrome was not found on this PC.' + #13#10#13#10 +
      'Setup will continue. Please install Chrome from google.com/chrome before using the app.',
      mbInformation, MB_OK, IDOK);
end;
