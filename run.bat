@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   Invoice Extractor
echo ============================================
echo.
echo Working directory: %CD%
echo.

REM === Find Python ===
set PY_CMD=
where py >nul 2>&1
if not errorlevel 1 (
    set PY_CMD=py -3
    echo [OK] Using py launcher
    py -3 --version
    goto have_python
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] python.exe is a Microsoft Store stub, not real Python.
        echo Please install Python 3.10+ from python.org
        echo Remember to tick "Add Python to PATH" during install.
        echo.
        pause
        exit /b 1
    )
    set PY_CMD=python
    echo [OK] Using python
    python --version
    goto have_python
)

echo.
echo [ERROR] Python not found.
echo Please install Python 3.10+ from python.org
echo.
pause
exit /b 1

:have_python
echo.

REM === Setup venv if missing ===
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERROR] venv creation failed
        pause
        exit /b 1
    )

    echo [2/3] Upgrading pip...
    "venv\Scripts\python.exe" -m pip install --upgrade pip

    echo [3/3] Installing packages...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] package install failed
        pause
        exit /b 1
    )
    echo [OK] Setup done.
    echo.
) else (
    echo [OK] venv ready
    echo.
)

REM === Check .env ===
if not exist ".env" (
    echo.
    echo [WARN] No .env file found.
    echo You need to set GEMINI_API_KEY before extraction works.
    echo Get a free key at: https://aistudio.google.com/apikey
    echo Then copy .env.example to .env and fill in the key.
    echo.
    pause
)

echo.
echo Launching GUI...
echo.
"venv\Scripts\python.exe" gui.py

echo.
echo ============================================
echo  GUI closed
echo ============================================
pause
