; ملف تثبيت تطبيق الإدارة التربوية (Inno Setup 6)
; يُثبَّت للمستخدم الحالي دون صلاحيات المسؤول. البيانات لا تُمس عند التحديث أو الإزالة.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6E1E5C2A-4B7D-4E3F-9A51-2D0C7A1B8F33}
AppName=الإدارة التربوية
AppVersion={#Version}
AppPublisher=الإدارة التربوية
DefaultDirName={localappdata}\Programs\IdaraTarbawiya
DefaultGroupName=الإدارة التربوية
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist-installateur
OutputBaseFilename=Idara-Installation-{#Version}
SetupIconFile=..\idara\resources\icone.ico
UninstallDisplayIcon={app}\Idara.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
#if FileExists(AddBackslash(CompilerPath) + "Languages\Arabic.isl")
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
#endif
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات:"

[Files]
Source: "..\dist\Idara\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\الإدارة التربوية"; Filename: "{app}\Idara.exe"
Name: "{autodesktop}\الإدارة التربوية"; Filename: "{app}\Idara.exe"; Tasks: bureau

[Run]
Filename: "{app}\Idara.exe"; Description: "تشغيل الإدارة التربوية"; Flags: nowait postinstall skipifsilent
