@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
 echo Please run scripts\install_windows.bat first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m capture.capture_windows %*
if errorlevel 1 pause
