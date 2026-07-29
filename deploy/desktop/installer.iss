; Inno Setup script — wraps the built KER exe into a Windows installer.
; Compiled in CI:  ISCC /Odist deploy/desktop/installer.iss
; The exe path and version come from environment variables set by the workflow.

#define AppName "KER"
#define AppPublisher "KER"
#define AppExe GetEnv("JARVIS_EXE")
#define AppVersion GetEnv("JARVIS_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{9E5D2A2C-7A1B-4E9F-9C1E-J4RV1S000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\KER
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=KER-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
UninstallDisplayName={#AppName}
; The app's mark, for the installer window and the Add/Remove Programs entry.
SetupIconFile={#SourcePath}\..\..\jarvis\desktop_app\assets\ker.ico
UninstallDisplayIcon={app}\KER.exe

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#AppExe}"; DestDir: "{app}"; DestName: "KER.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\KER.exe"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\KER.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KER.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
