; Inno Setup script for the DJI Metadata Embedder desktop app (issue #264
; stage 3e). One installer carries everything: the Avalonia GUI (the Start
; menu entry), dji-embed.exe beside it, and pinned FFmpeg/ExifTool builds in
; tools\ — and puts both directories on the user PATH so the full CLI works
; from any terminal with no extra steps.
;
; Compiled by .github/workflows/release-installer.yml:
;   ISCC.exe /DAppVersion=1.21.0 /DStagingDir=..\staging\app installer\DjiMetadataEmbedder.iss
; StagingDir must contain the final {app} layout (GUI publish output,
; dji-embed.exe, tools\, licenses\).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef StagingDir
  #define StagingDir "..\staging\app"
#endif

#define MyAppName "DJI Metadata Embedder"
#define MyAppExeName "DjiEmbed.Gui.exe"

[Setup]
; Never change this AppId: it is how upgrades find the existing install.
AppId={{A0F2FECD-3BEB-4832-9BC6-4A57B20ED947}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=CallMarcus
AppPublisherURL=https://github.com/CallMarcus/dji-drone-metadata-embedder
AppSupportURL=https://github.com/CallMarcus/dji-drone-metadata-embedder/issues
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Per-user install: no admin prompt, and the PATH edits below stay in HKCU.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=dji-metadata-embedder-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
; Makes Windows broadcast WM_SETTINGCHANGE so new terminals see the PATH.
ChangesEnvironment=yes

[Files]
Source: "{#StagingDir}\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent

[Code]
// Append {app} and {app}\tools to the *user* PATH on install and remove
// them again on uninstall. Idempotent: re-running the installer never
// duplicates entries.

const
  UserEnvKey = 'Environment';

function SplitPath(const PathValue: string; Entries: TStringList): Boolean;
begin
  Entries.Delimiter := ';';
  Entries.StrictDelimiter := True;
  Entries.DelimitedText := PathValue;
  Result := True;
end;

function EntryIndex(Entries: TStringList; const Dir: string): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to Entries.Count - 1 do
    if CompareText(Trim(Entries[I]), Dir) = 0 then
    begin
      Result := I;
      exit;
    end;
end;

procedure AddDirToUserPath(const Dir: string);
var
  PathValue: string;
  Entries: TStringList;
begin
  if not RegQueryStringValue(HKCU, UserEnvKey, 'Path', PathValue) then
    PathValue := '';
  Entries := TStringList.Create;
  try
    SplitPath(PathValue, Entries);
    if EntryIndex(Entries, Dir) = -1 then
    begin
      if (PathValue <> '') and (Copy(PathValue, Length(PathValue), 1) <> ';') then
        PathValue := PathValue + ';';
      PathValue := PathValue + Dir;
      RegWriteExpandStringValue(HKCU, UserEnvKey, 'Path', PathValue);
    end;
  finally
    Entries.Free;
  end;
end;

procedure RemoveDirFromUserPath(const Dir: string);
var
  PathValue: string;
  Entries: TStringList;
  I: Integer;
begin
  if not RegQueryStringValue(HKCU, UserEnvKey, 'Path', PathValue) then
    exit;
  Entries := TStringList.Create;
  try
    SplitPath(PathValue, Entries);
    I := EntryIndex(Entries, Dir);
    while I <> -1 do
    begin
      Entries.Delete(I);
      I := EntryIndex(Entries, Dir);
    end;
    Entries.Delimiter := ';';
    RegWriteExpandStringValue(HKCU, UserEnvKey, 'Path', Entries.DelimitedText);
  finally
    Entries.Free;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    AddDirToUserPath(ExpandConstant('{app}'));
    AddDirToUserPath(ExpandConstant('{app}\tools'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveDirFromUserPath(ExpandConstant('{app}'));
    RemoveDirFromUserPath(ExpandConstant('{app}\tools'));
  end;
end;
