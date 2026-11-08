@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Install the software first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
