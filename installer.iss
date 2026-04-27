; Inno Setup script — Processador de DTFs (Tecnosup)
; Compile com: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Ou rode build_exe.bat que já chama o ISCC automaticamente.

#define AppName        "Processador de DTFs"
#define AppPublisher   "Tecnosup"
#define AppVersion     "1.0.3"
#define AppExeName     "Processador de DTFs.exe"
#define SourceDir      "dist\Processador de DTFs"

[Setup]
AppId={{B7D3F8A2-9E4C-4A1D-9F2B-7C6E8A1D3B5F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppPublisher}\{#AppName}
DefaultGroupName={#AppPublisher}
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir=installer_output
OutputBaseFilename=Setup_{#AppPublisher}_DTF_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=assets\logo.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
; Empacota TODA a pasta dist/Processador de DTFs/ (EXE + DLLs + vendor/ImageMagick + customtkinter)
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName} agora"; Flags: nowait postinstall skipifsilent
