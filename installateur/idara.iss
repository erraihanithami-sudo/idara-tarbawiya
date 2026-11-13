; ملف تثبيت «الشامل في الإدارة التربوية بالمغرب» (Inno Setup 6)
; يُثبَّت للمستخدم الحالي دون صلاحيات المسؤول. البيانات لا تُمس عند التحديث أو الإزالة.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6E1E5C2A-4B7D-4E3F-9A51-2D0C7A1B8F33}
AppName=الشامل في الإدارة التربوية بالمغرب
AppVersion={#Version}
AppPublisher=الشامل في الإدارة التربوية بالمغرب
DefaultDirName={localappdata}\Programs\IdaraTarbawiya
DefaultGroupName=الشامل في الإدارة التربوية بالمغرب
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

[InstallDelete]
; الاختصارات القديمة باسم «الإدارة التربوية» (قبل تغيير الاسم 2026-11-13)
Type: files; Name: "{autodesktop}\الإدارة التربوية.lnk"
Type: files; Name: "{userprograms}\الإدارة التربوية\الإدارة التربوية.lnk"
Type: dirifempty; Name: "{userprograms}\الإدارة التربوية"

[Icons]
Name: "{group}\الشامل في الإدارة التربوية بالمغرب"; Filename: "{app}\Idara.exe"
Name: "{autodesktop}\الشامل في الإدارة التربوية بالمغرب"; Filename: "{app}\Idara.exe"; Tasks: bureau

[Run]
Filename: "{app}\Idara.exe"; Description: "تشغيل الشامل في الإدارة التربوية بالمغرب"; Flags: nowait postinstall skipifsilent
