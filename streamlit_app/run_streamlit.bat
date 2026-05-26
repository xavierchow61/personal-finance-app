@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo   Personal Finance - Streamlit Web UI
echo ============================================
echo.
echo Working dir: %CD%
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found
    echo Please run 'run.bat' once first to setup the venv
    pause
    exit /b 1
)

echo [1/2] Checking streamlit...
"venv\Scripts\python.exe" -c "import streamlit" 1>nul 2>nul
if errorlevel 1 (
    echo Streamlit not installed. Installing now ^(2-3 min^)...
    "venv\Scripts\python.exe" -m pip install streamlit pandas plotly
    if errorlevel 1 (
        echo [ERROR] pip install failed
        pause
        exit /b 1
    )
)
echo [OK] streamlit ready
echo.

echo [2/2] Starting Streamlit server on http://localhost:8501
echo.
echo === Mobile / tablet access ===
echo 1. Find your PC IP: open cmd, type ipconfig, look at IPv4
echo 2. On phone same wifi, open http://YOUR-PC-IP:8501
echo.
echo Press Ctrl+C in this window to stop the server.
echo Browser will open automatically in 5 seconds...
echo.

REM Background: wait 5 seconds, then open browser
start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 5; Start-Process 'http://localhost:8501'"

REM Run streamlit (blocking)
"venv\Scripts\python.exe" -m streamlit run "streamlit_app\Home.py" --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false

echo.
echo ============================================
echo  Streamlit stopped
echo ============================================
pause
