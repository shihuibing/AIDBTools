; AI数据库工具 Windows 安装包脚本
; 直接用 Inno Setup 编译即可
[Setup]
AppName=AI数据库工具
AppVersion=8.0
AppPublisher=AI工具箱
DefaultDirName={pf}\AI数据库工具
DefaultGroupName=AI数据库工具
UninstallDisplayIcon={app}\icon.ico
Compression=lzma2
SolidCompression=yes
OutputDir=.\Setup
OutputBaseFilename=AI数据库工具_Setup
SetupIconFile=.\icon.ico
WizardStyle=modern

[Files]
Source: ".\dist\AI数据库工具.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AI数据库工具"; Filename: "{app}\AI数据库工具.exe"
Name: "{group}\卸载"; Filename: "{uninstallexe}"
Name: "{desktop}\AI数据库工具"; Filename: "{app}\AI数据库工具.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce

[Run]
Filename: "{app}\AI数据库工具.exe"; Description: "立即运行"; Flags: nowait postinstall skipifsilent