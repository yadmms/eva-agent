@echo off
title Eva Agent
set STARTUP_LOG=eva-startup.log
set SERVER_LOG=eva-server.log

echo. >%STARTUP_LOG%
echo === Eva Agent v0.11.3 === >>%STARTUP_LOG%
echo Time: %date% %time% >>%STARTUP_LOG%

echo.
echo ====================================
echo   Eva Agent v0.11.3 - Qianye Lab
echo ====================================
echo.

:: Step 1: Check Python
echo [1/3] Checking Python...
echo [1/3] Checking Python... >>%STARTUP_LOG%
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Python not found!
    echo Python not found >>%STARTUP_LOG%
    echo Please download from:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
    echo    OK: %%i
    echo Python: %%i >>%STARTUP_LOG%
)

:: Step 2: Install dependencies
echo.
echo [2/3] Installing dependencies...
echo [2/3] Installing dependencies... >>%STARTUP_LOG%
echo    Running: pip install -r requirements.txt
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo    Retrying with mirror...
    echo pip failed, retrying mirror >>%STARTUP_LOG%
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo Dependencies OK >>%STARTUP_LOG%

:: Step 3: Start
echo.
echo [3/3] Starting Eva Agent...
echo [3/3] Starting... >>%STARTUP_LOG%

:: Kill old process
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo Old python processes killed >>%STARTUP_LOG%

:: Start server
start /b python run.py >%SERVER_LOG% 2>&1
echo Server process started >>%STARTUP_LOG%

:: Wait for server (max 30 seconds)
echo    Waiting for server...
set WAIT_COUNT=0
:waitloop
timeout /t 3 /nobreak >nul
set /a WAIT_COUNT+=1
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:19198' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Server ready >>%STARTUP_LOG%
    goto server_ready
)
if %WAIT_COUNT% LSS 10 goto waitloop
echo Server may still be starting... >>%STARTUP_LOG%

:server_ready

:: Open browser
start http://localhost:19198
echo Browser launched >>%STARTUP_LOG%

echo.
echo ====================================
echo   Eva Agent is running!
echo   Browser opened at localhost:19198
echo   Close this window to stop the server
echo ====================================
echo.
echo Log: %SERVER_LOG%
pause
