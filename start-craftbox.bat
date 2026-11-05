@echo off
rem Starts Craftbox using ITS OWN virtual environment (.venv in this folder).
rem Default: http://127.0.0.1:8099   Override with: set CRAFTBOX_PORT=8100
rem Never stops or touches other servers (e.g. Dreambox on port 8000).
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Craftbox virtual environment...
    py -3 -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)

".venv\Scripts\python.exe" -m app.run %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Craftbox did not start. See the message above.
if not defined CRAFTBOX_NOPAUSE pause
exit /b 1
