@echo off
setlocal EnableExtensions
title ODF Message Generator launcher

REM ============================================================
REM  Starts the ODF Message Generator service (uvicorn) and
REM  opens the webapp in the default browser.
REM
REM  The project folder is wherever this script lives (%~dp0),
REM  so the whole project can be moved or cloned to another
REM  machine without editing anything here.
REM ============================================================

set "PROJECT_DIR=%~dp0"
set "APP_URL=http://127.0.0.1:8000"

REM --- Go to the project folder ---------------------------------
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo.
    echo  ERROR: Could not find the project folder:
    echo  %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

REM --- Start the service in its own window ----------------------
REM  A virtual environment is activated automatically if one of
REM  the common folder names is present. The child window keeps
REM  running so you can see the server logs and close it later.
REM  KEEP THAT WINDOW OPEN: it is the service, and it is also
REM  where a generation error prints its traceback.
if exist ".venv\Scripts\activate.bat" (
    start "ODF service" cmd /k "call .venv\Scripts\activate.bat & uvicorn api.app:app --host 127.0.0.1 --port 8000"
) else if exist "venv\Scripts\activate.bat" (
    start "ODF service" cmd /k "call venv\Scripts\activate.bat & uvicorn api.app:app --host 127.0.0.1 --port 8000"
) else (
    start "ODF service" cmd /k "uvicorn api.app:app --host 127.0.0.1 --port 8000"
)

REM --- Wait for the service to answer before opening browser ----
echo Waiting for the service to start...
set /a tries=0
:waitloop
set /a tries+=1
curl -s -o nul "%APP_URL%"
if not errorlevel 1 goto ready
if %tries% geq 30 goto timeout
timeout /t 1 /nobreak >nul
goto waitloop

:timeout
echo.
echo  The service did not answer within 30 seconds.
echo  Opening the browser anyway - if the page fails to load, check the
echo  "ODF service" window for the startup error (a missing rule pack or
echo  an unimportable odf_validator are the usual causes).
echo.

:ready
REM --- Open the webapp ------------------------------------------
REM  Deliberately the default browser rather than a named one: the
REM  previous "start Chrome" resolved unqualified, so it searched the
REM  current directory before PATH (anything that could drop a
REM  Chrome.exe into the project folder got code execution here), and
REM  it silently did nothing when Chrome was not installed while the
REM  comments and README-shortcut.md both said Firefox.
start "" "%APP_URL%"

exit /b 0
