@echo off
chcp 65001 >nul
title Eva Agent — 一键启动
setlocal enabledelayedexpansion

:: 获取当前目录
set DIR=%~dp0
cd /d "%DIR%"

echo.
echo  ╔══════════════════════════════════╗
echo  ║   伊娃 Eva Agent v0.11.3       ║
echo  ║   千叶实验室 Qianye Lab        ║
echo  ╚══════════════════════════════════╝
echo.

:: ── 第1步：检查 Python ──
echo [1/3] 正在检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ❌ 你的电脑还没有安装 Python。
    echo  请从 python.org 下载安装，安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo    ✓ %%i

:: ── 第2步：安装依赖 ──
echo.
echo [2/3] 正在安装所需组件（首次需要 1-2 分钟）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet 2>nul
if %errorlevel% neq 0 (
    pip install -r requirements.txt --quiet 2>nul
)
echo    ✓ 组件安装完成

:: ── 第3步：关闭旧进程 ──
echo.
echo [3/3] 正在启动 Eva Agent...
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: ── 后台启动服务 ──
start /b python run.py

:: ── 等待服务就绪 ──
echo   等待服务启动...
:waitloop
timeout /t 2 /nobreak >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:19198' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
if %errorlevel% neq 0 goto waitloop

:: ── 打开浏览器 ──
start http://localhost:19198

echo.
echo  ╔══════════════════════════════════╗
echo  ║   Eva Agent 已启动              ║
echo  ║   浏览器窗口已自动打开           ║
echo  ║   关闭命令行窗口即可停止服务     ║
echo  ╚══════════════════════════════════╝
echo.

:: ── 保持窗口（关闭时停服务） ──
echo 按任意键停止服务...
pause >nul

:: ── 清理 ──
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
exit
