@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run INSTALL_WINDOWS.bat first.
 pause
 exit /b 1
)
start "Crystal Cleaning Billing Worker" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m app.scheduler"
start "" "http://localhost:8000"
echo.
echo Crystal Cleaning Operations Hub is starting.
echo Web address: http://localhost:8000
echo Press Ctrl+C to stop the web server. Also close the Billing Worker window.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
