@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe exit /b 1
set "SESSION=%~1"
if "%SESSION%"=="" set "SESSION=data\screenshots\session01"
set "WORK=%~2"
if "%WORK%"=="" set "WORK=data\intermediate\session01"
.venv\Scripts\python.exe -m processing.pipeline process --session "%SESSION%" --work "%WORK%"
if errorlevel 1 (
 echo Processing stopped. Check errors; existing checkpoints are retained.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m processing.pipeline export --work "%WORK%" --output data\output\session01
if errorlevel 1 exit /b 1
pause
