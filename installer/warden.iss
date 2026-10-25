#define AppName "Warden"
#define AppVersion "1.0.1"
#define AppExe "Warden.exe"

[Setup]
AppId={{6F1C3B52-5A0E-4C59-9C3D-1D7E1B7A2E41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Svandik42
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Warden-{#AppVersion}-setup
SetupIconFile=..\resources\warden.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
czech.Shortcuts=Zástupci:
english.Shortcuts=Shortcuts:
czech.DesktopIcon=Vytvořit zástupce na ploše
english.DesktopIcon=Create a desktop shortcut
czech.Startup=Spouštění:
english.Startup=Startup:
czech.AutoStart=Spouštět Warden po přihlášení do Windows
english.AutoStart=Start Warden when I sign in to Windows
czech.Uninstall=Odinstalovat Warden
english.Uninstall=Uninstall Warden
czech.RunNow=Spustit Warden
english.RunNow=Launch Warden

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:Startup}"

[Files]
Source: "..\dist\Warden\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Warden"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Warden"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent
