@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe exit /b 1
.venv\Scripts\python.exe -m streamlit run review_ui\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
if errorlevel 1 pause
