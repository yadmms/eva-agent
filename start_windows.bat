@echo off
title Eva Agent

set LOGFILE=eva-startup.log
call :log "=== Eva Agent v0.11.3 ==="
call :log "OS: Windows"
call :log "Time: %date% %time%"

echo.
echo ====================================
echo   Eva Agent v0.11.3 - Qianye Lab
echo ====================================
echo.

:: Step 1: Check Python
echo [1/3] Checking Python...
call :log "[1/3] Checking Python..."
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Python not found!
    call :log "ERROR: Python not found"
    echo Please download from:
    echo https://www.python.org/downloads/windows/
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
    echo    OK: %%i
    call :log "Python: %%i"
)

:: Step 2: Install dependencies
echo.
echo [2/3] Installing dependencies (first time may take 1-2 mins)...
call :log "[2/3] Installing dependencies..."
echo    Running: pip install -r requirements.txt
pip install -r requirements.txt >>%LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo    Retrying with mirror...
    call :log "pip failed, retrying with mirror..."
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >>%LOGFILE% 2>&1
)
call :log "Dependencies installed"

:: Step 3: Start
echo.
echo [3/3] Starting Eva Agent...
call :log "[3/3] Starting server..."

:: Kill old process
call :log "Killing old python.exe..."
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Start server in background
call :log "Starting server..."
start /b python run.py >>%LOGFILE% 2>&1

:: Wait for server
echo    Waiting for server...
:waitloop
timeout /t 2 /nobreak >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:19198' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    call :log "Waiting... (attempt %attempt%)"
    goto waitloop
)
call :log "Server ready"

:: Open browser
start http://localhost:19198

echo.
echo ====================================
echo   Eva Agent is running!
echo   Browser opened at localhost:19198
echo   Close this window to stop the server
echo ====================================
echo.
call :log "Startup complete"
pause
goto :eof

:log
echo %* >>%LOGFILE%
echo %date% %time% - %* >>%LOGFILE%
goto :eof
