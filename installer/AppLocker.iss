; AppLocker — Inno Setup 6 installer script.
;
; Installs the single-file AppLocker.exe per-user (no administrator rights)
; into %LOCALAPPDATA%\Programs\AppLocker, adds Start Menu shortcuts and an
; uninstall entry. Protected-app policies and the encrypted master password
; live in %LOCALAPPDATA%\AppLocker and are intentionally left untouched on
; uninstall.
;
; Build:  installer\build_installer.ps1
; or:     ISCC.exe /DMyAppVersion=2.0.0 installer\AppLocker.iss

#define MyAppName "AppLocker"
#ifndef MyAppVersion
#define MyAppVersion "2.0.0"
#endif

; ---------------------------------------------------------------------------
[Setup]
AppId={{4D8A2F9E-6B2C-4A11-9C5D-3F2E9A8B7C64}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=AppLocker Contributors
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename={#MyAppName}Setup-{#MyAppVersion}
SetupIconFile=..\applocker\assets\applocker.ico
UninstallDisplayIcon={app}\AppLocker.exe
UninstallDisplayName={#MyAppName}
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=no
Compression=lzma2
SolidCompression=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} installer
RestartIfNeededByRun=no

; ---------------------------------------------------------------------------
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Run {#MyAppName} when Windows sign&s in"; GroupDescription: "Startup:"

; ---------------------------------------------------------------------------
[Files]
Source: "..\release\AppLocker.exe"; DestDir: "{app}"; Flags: ignoreversion

; ---------------------------------------------------------------------------
[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\AppLocker.exe"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\AppLocker.exe"; Tasks: desktopicon

; ---------------------------------------------------------------------------
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; \
    ValueData: """{app}\AppLocker.exe"""; Flags: uninsdeletevalue; Tasks: startup

; ---------------------------------------------------------------------------
[UninstallDelete]
Type: dirifempty; Name: "{app}"
Type: dirifempty; Name: "{localappdata}\Programs"

; ---------------------------------------------------------------------------
[Run]
Filename: "{app}\AppLocker.exe"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent