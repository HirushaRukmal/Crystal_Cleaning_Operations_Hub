@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==============================================================
echo   CRYSTAL CLEANING OPERATIONS HUB - INSTALL / REPAIR
echo ==============================================================
echo.
echo Repair: Uvicorn runs without optional PyYAML compiler extras.
echo This installer will NOT delete your company database or .env.
echo.

if not exist "requirements.txt" (
    echo ERROR: requirements.txt was not found in this folder.
    echo Put this installer in the Crystal_Cleaning_Operations_Hub folder.
    goto failure
)

set "VENV_PY=.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; assert sys.version_info[0] == 3 and sys.version_info[1] in (10,11,12,13,14,15)" >nul 2>nul
    if errorlevel 1 call :backup_venv
)

if not exist "%VENV_PY%" goto create_venv
goto install_packages

:create_venv
if exist ".venv" call :backup_venv
set "PY_CMD="
call :check_python "py -3.12"
call :check_python "py -3.13"
call :check_python "py -3.11"
call :check_python "py -3.14"
call :check_python "py -3.15"
call :check_python "py -3.10"
call :check_python "python"
if not defined PY_CMD (
    echo ERROR: Python 3.10 - 3.15 was not detected.
    echo Install Python 3.12 for best compatibility:
    echo https://www.python.org/downloads/release/python-31210/
    goto failure
)
echo Creating a virtual environment with: %PY_CMD%
%PY_CMD% -m venv ".venv"
if errorlevel 1 goto failure
if not exist "%VENV_PY%" (
    echo ERROR: Python did not create the virtual environment.
    goto failure
)

:install_packages
echo.
echo Virtual environment Python version:
"%VENV_PY%" --version
if errorlevel 1 goto failure

rem If the old requirements file is present, automatically remove the optional
rem Uvicorn extras that install PyYAML and require a compiler on Python 3.15.
findstr /L /C:"uvicorn[standard]" "requirements.txt" >nul 2>nul
if not errorlevel 1 (
    echo Updating requirements.txt to avoid unnecessary PyYAML compilation...
    if not exist "requirements_before_pyyaml_fix.bak" copy "requirements.txt" "requirements_before_pyyaml_fix.bak" >nul
    "%VENV_PY%" -c "from pathlib import Path; p=Path('requirements.txt'); s=p.read_text(encoding='utf-8-sig'); p.write_text(s.replace('uvicorn[standard]', 'uvicorn'), encoding='utf-8')"
    if errorlevel 1 goto failure
)

echo.
echo Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto failure

echo.
echo Installing Crystal Cleaning dependencies (no PyYAML required)...
"%VENV_PY%" -m pip install -r "requirements.txt"
if errorlevel 1 goto failure

echo.
echo Checking essential imports...
"%VENV_PY%" -c "import uvicorn, fastapi, sqlalchemy, reportlab, qrcode, alembic; print('Web server and required dependencies loaded successfully')"
if errorlevel 1 goto failure

if not exist ".env" copy ".env.example" ".env" >nul
if not exist ".env" (
    echo ERROR: .env configuration could not be created.
    goto failure
)

echo.
echo Applying database migrations (preserving existing company data)...
"%VENV_PY%" -m alembic upgrade head
if errorlevel 1 goto failure

echo.
echo ==============================================================
echo  INSTALLATION SUCCESSFUL - Run START_WINDOWS.bat next
echo ==============================================================
pause
exit /b 0

:check_python
if defined PY_CMD exit /b 0
%~1 -c "import sys; assert sys.version_info[0] == 3 and sys.version_info[1] in (10,11,12,13,14,15)" >nul 2>nul
if not errorlevel 1 set "PY_CMD=%~1"
exit /b 0

:backup_venv
if not exist ".venv" exit /b 0
set "BACKUP_VENV=.venv_before_repair_backup"
if exist "%BACKUP_VENV%" set "BACKUP_VENV=.venv_before_repair_%RANDOM%"
echo Existing virtual environment is incompatible; preserving as %BACKUP_VENV%
move ".venv" "%BACKUP_VENV%" >nul
if errorlevel 1 (
    echo ERROR: Could not move .venv. Close all Crystal Cleaning windows.
    goto failure
)
exit /b 0

:failure
echo.
echo INSTALLATION FAILED. Send the FIRST error above this line.
pause
exit /b 1
