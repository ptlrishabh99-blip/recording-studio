; Inno Setup script for HLS Capture Studio.
;
; Packages the PyInstaller onedir build (dist/HLS Capture Studio/) into a
; single double-click Setup.exe that installs the app, ffmpeg (already
; bundled inside that folder by packaging/hls_recorder.spec), a Start Menu
; entry, and an optional desktop shortcut. No separate Python or ffmpeg
; install step for the end user.
;
; Build with (from the repo root, after `pyinstaller ... packaging/hls_recorder.spec`):
;   iscc packaging\windows\setup.iss /DMyAppVersion=1.0.0
; (the GitHub Actions workflow does this automatically on every tagged
; release — see .github/workflows/release.yml)

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "HLS Capture Studio"
#define MyAppPublisher "HLS Capture Studio"
#define MyAppExeName "HLS Capture Studio.exe"
#define MyAppSourceDir "..\..\dist\HLS Capture Studio"

[Setup]
AppId={{4C6F5372-8F6B-4B0A-9A3F-6C1E9C0B7A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
; Per-user install directory -> no admin/UAC prompt needed, true "click
; and it just installs" experience.
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=HLS-Capture-Studio-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
