;; ═══════════════════════════════════════════════════════════════════════════════
;; YouTube Downloader - Inno Setup Installer Script
;; ═══════════════════════════════════════════════════════════════════════════════

#define MyAppName "YouTube Downloader"

; Versao pode ser sobrescrita via linha de comando do ISCC:
;   ISCC.exe /DMyAppVersion=1.2.0 installer.iss
; (usado pelo pipeline release.py). Sem o parametro, usa o padrao abaixo.
#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif

#define MyAppPublisher "Freebuff"
#define MyAppURL "https://freebuff.com"
#define MyAppExeName "YouTube Downloader.exe"
#define MyAppExeCLI "YouTube Downloader CLI.exe"

[Setup]
; Configuracoes basicas
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Diretorio padrao de instalacao
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Configuracoes do instalador
OutputDir=installer
OutputBaseFilename=YouTube-Downloader-Setup-{#MyAppVersion}
SetupIconFile=youtube_icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120,100

; Permissoes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Desinstalacao
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
CreateUninstallRegKey=yes

; Idioma - detecta automaticamente o idioma do usuario
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
portuguese.WizardSelectDir=Selecione o Diretorio de Instalacao
portuguese.WizardSelectDirLabel=O instalador ira instalar {#MyAppName} no seguinte diretorio.
portuguese.WizardSelectProgramGroup=Selecione a Pasta do Menu Iniciar
portuguese.SelectStartMenuFolderUpLabel=&Pasta do Menu Iniciar:
portuguese.UninstallAppFullTitle=Desinstalar {#MyAppName}
portuguese.WizardReady=O instalador esta pronto para instalar {#MyAppName} no seu computador.

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
; Executavel principal (GUI)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Executavel CLI (incluido apenas se existir)
#if FileExists(AddBackslash(SourcePath) + "dist\" + MyAppExeCLI)
  Source: "dist\{#MyAppExeCLI}"; DestDir: "{app}"; Flags: ignoreversion
#endif

; Arquivos auxiliares
Source: "YouTube Downloader.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "youtube_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Binarios ffmpeg (processamento de audio/video) - essenciais para mesclar e converter
Source: "ffmpeg\ffmpeg.exe"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion
Source: "ffmpeg\ffprobe.exe"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion

; Scripts Python (para usuarios que querem modificar ou rebuildar)
Source: "yt-downloader-gui.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "yt-downloader.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "downloader.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "config_manager.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "download_queue_manager.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "platforms.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "drop_handler.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "updater.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "signing.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "update_public_key.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "gerar_icone.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "build_exe.py"; DestDir: "{app}\src"; Flags: ignoreversion

[Icons]
; Menu Iniciar
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\youtube_icon.ico"; Comment: "Baixe videos e musicos do YouTube e outras plataformas"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\youtube_icon.ico"

; Area de Trabalho (opcional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\youtube_icon.ico"; Tasks: desktopicon

[Run]
; Opcao de executar apos instalacao
Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: postinstall nowait skipifsilent unchecked; WorkingDir: "{app}"

[Code]
function GetUninstallString: string;
begin
  Result := '';
  if not RegQueryStringValue(
    HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1',
    'UninstallString', Result) then
    RegQueryStringValue(
      HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1',
      'UninstallString', Result);
end;

function IsUpgrade: Boolean;
begin
  Result := (GetUninstallString <> '');
end;

function UnInstallOldVersion: Boolean;
var
  sUnInstallPath: String;
  iResultCode: Integer;
begin
  if RegQueryStringValue(
    HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1',
    'UninstallString', sUnInstallPath) then
  begin
    sUnInstallPath := RemoveQuotes(sUnInstallPath);
    Result := Exec(sUnInstallPath, '/SILENT /NORESTART /SUPPRESSMSGBOXES',
      '', SW_HIDE, ewWaitUntilTerminated, iResultCode);
  end
  else
  begin
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if IsUpgrade then
    begin
      UnInstallOldVersion;
    end;
  end;
end;
