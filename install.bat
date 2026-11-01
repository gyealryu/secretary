@echo off
cd /d "%~dp0"
echo ==========================================
echo  AI Secretary - install
echo ==========================================

set PY=python
where py >nul 2>nul
if %errorlevel%==0 set PY=py -3

%PY% --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed. Install Python 3.10+ from python.org
  echo         and check "Add python.exe to PATH" during install.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [ERROR] venv creation failed & pause & exit /b 1 )
)

if exist wheels\ (
  echo Installing from local "wheels" folder ^(offline mode^)...
  .venv\Scripts\python -m pip install --no-index --find-links wheels -r requirements.txt
) else (
  echo Installing packages from the internet...
  .venv\Scripts\python -m pip install -r requirements.txt
)
if errorlevel 1 (
  echo [ERROR] Package install failed. See README "offline install".
  pause
  exit /b 1
)

echo.
echo Done! Double-click run.bat to start.
pause
