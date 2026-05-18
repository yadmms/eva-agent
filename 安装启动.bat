@echo off
chcp 65001 >nul
title Eva Agent — 安装启动

echo.
echo  ╔══════════════════════════════════╗
echo  ║   伊娃 Eva Agent v0.11.3       ║
echo  ║   千叶实验室 Qianye Lab        ║
echo  ╚══════════════════════════════════╝
echo.

:: 第1步：检查Python
echo [1/3] 正在检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ❌ 你的电脑还没有安装 Python。
    echo.
    echo  请按以下步骤操作：
    echo   ① 打开浏览器，地址栏输入 python.org 回车
    echo   ② 点黄色大按钮 "Download Python" 下载
    echo   ③ 双击下载的文件安装
    echo   ④ ⚠️ 安装时一定要勾选 "Add Python to PATH"
    echo   ⑤ 安装完成后，重新双击运行本文件
    echo.
    pause
    exit /b 1
)
echo    ✓ Python 已就绪

:: 第2步：安装依赖
echo.
echo [2/3] 正在安装所需组件（首次需要 1-2 分钟，请耐心等待）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠ 国内镜像安装失败，尝试官方源...
    pip install -r requirements.txt --quiet >nul 2>&1
)
echo    ✓ 组件安装完成

:: 第3步：启动
echo.
echo [3/3] 正在启动 Eva Agent...
echo.
echo  ╔══════════════════════════════════╗
echo  ║   Eva Agent 启动中...           ║
echo  ║   请稍后在浏览器打开：          ║
echo  ║   http://localhost:19198        ║
echo  ╚══════════════════════════════════╝
echo.
start http://localhost:19198
python run.py
pause
