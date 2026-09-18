@echo off
setlocal EnableExtensions
title Install ODF Generator desktop shortcut

REM ============================================================
REM  Creates a double-click shortcut on your Desktop that runs
REM  Launch-ODF-Generator.bat. Run this once. Keep both .bat
REM  files together in the same folder.
REM ============================================================

set "LAUNCHER=%~dp0Launch-ODF-Generator.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\ODF Generator.lnk"
set "ICON=%ProgramFiles%\Mozilla Firefox\firefox.exe"

if not exist "%LAUNCHER%" (
    echo.
    echo  ERROR: Launch-ODF-Generator.bat was not found next to this file.
    echo  Put both .bat files in the same folder, then run this again.
    echo.
    pause
    exit /b 1
)

if not exist "%ICON%" set "ICON=%LAUNCHER%"

set "ODF_WORKDIR=%~dp0"

REM  The paths are passed through the environment, not interpolated into the
REM  PowerShell literals. Interpolating them meant a single apostrophe in any
REM  path -- C:\Users\O'Brien\... is enough -- closed the string early and the
REM  rest of the path was parsed as PowerShell code.
powershell -NoProfile -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SHORTCUT);" ^
  "$s.TargetPath = $env:LAUNCHER;" ^
  "$s.WorkingDirectory = $env:ODF_WORKDIR;" ^
  "$s.IconLocation = $env:ICON + ',0';" ^
  "$s.Description = 'Launch ODF Message Generator and open the webapp';" ^
  "$s.Save()"

if errorlevel 1 (
    echo.
    echo  Something went wrong creating the shortcut.
    pause
    exit /b 1
)

echo.
echo  Done. A shortcut named "ODF Generator" is now on your Desktop.
echo.
pause
exit /b 0
