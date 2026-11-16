; Inno Setup script for PDF Redactor PRO. Compiled by packaging/build.py.
; AppId must NEVER change: it lets every new version install over the old one
; (settings in %APPDATA%\PDF Redactor PRO are kept).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\PDF Redactor PRO"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "PDF Redactor PRO"
#define AppExe "PDF Redactor PRO.exe"
#define Publisher "CA Lucika Mehta"

[Setup]
AppId={{2D5D3F33-F59C-431A-B147-A0F7C9FBDCC0}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppContact=orsshah@gmail.com
AppSupportPhone=+91 90190 79090
AppPublisherURL=mailto:orsshah@gmail.com
AppComments=Redacts client documents on this computer before they are shared with AI tools.
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; installs for the current user without administrator rights (can be changed in the first dialog)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutputDir}
OutputBaseFilename=PDF-Redactor-PRO-Setup-{#AppVersion}
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; remove files of the previous version so nothing stale is left behind
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; the app window's private browser profile (no client documents are kept there)
Type: filesandordirs; Name: "{localappdata}\{#AppName}\window"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent runasoriginaluser
