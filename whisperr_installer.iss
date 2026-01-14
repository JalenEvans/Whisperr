[Setup]
AppName=Whisperr
AppVersion=1.0.0
DefaultDirName={autopf}\Whisperr
DefaultGroupName=Whisperr
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ChangesEnvironment=yes

[Files]
Source: "dist\whisperr.exe";
DestDir:"{app}"

[Icons]
Name:"{group}\Whisperr";
Filename: "{app}\whisperr.exe"

[Registry]
Root: HKLM; 
Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment";
ValueType: expandsz; 
ValueName: "Path";
ValueData: "{olddata};{app}";
Check: NeedsAddPath('{app}')

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath) then begin
    Result := True;
    exit;
  end;
  { Look for the path with semicolons around it }
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;