@echo off
title File Buddy setup
cd /d "%~dp0"
echo === File Buddy setup (Windows) ===
set "PY="

rem 1) Already have Python 3.10-3.12?
for %%V in (3.11 3.12 3.10) do (
  if not defined PY ( py -%%V -c "print()" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

rem 2) No Python -> install it automatically (no admin needed)
if not defined PY (
  echo Python not found - installing Python 3.11 for you...
  winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
  if not exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    echo Downloading the installer from python.org...
    powershell -NoProfile -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile $env:TEMP\py311.exe"
    "%TEMP%\py311.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
  )
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined PY (
  echo Couldn't install Python automatically. Get Python 3.11 from https://www.python.org/downloads/ then run this again.
  pause & exit /b 1
)

echo Using %PY%
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv || (echo Could not create virtual env & pause & exit /b 1)
)
.venv\Scripts\python -m pip install --upgrade pip setuptools wheel
.venv\Scripts\python -m pip install -r requirements.txt || (echo Install failed & pause & exit /b 1)

rem Desktop shortcut
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\File Buddy.lnk');$s.TargetPath='%~dp0.venv\Scripts\pythonw.exe';$s.Arguments='\"%~dp0FileBuddy.pyw\"';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0assets\icon.ico';$s.Save()"
echo.
echo Done! Open "File Buddy" from your desktop.
echo For the free local AI 3D engine, run install_ai_engine.bat next.
pause
