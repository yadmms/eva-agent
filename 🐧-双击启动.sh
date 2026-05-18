#!/bin/bash
# Eva Agent — 桌面端启动（无终端窗口）
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PYTHON=""
for cmd in python3 python; do command -v $cmd &>/dev/null && { PYTHON=$cmd; break; } done
[ -z "$PYTHON" ] && { echo "未找到 Python"; exit 1; }

$PYTHON -m pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null || true

kill $(lsof -t -i:19198 2>/dev/null) 2>/dev/null

# 后台启动，完全脱离终端
nohup $PYTHON run.py > /dev/null 2>&1 &
disown

# 等待服务就绪
for i in $(seq 1 15); do
    curl -s http://localhost:19198 >/dev/null 2>&1 && break
    sleep 1
done

# 打开默认浏览器
xdg-open "http://localhost:19198" 2>/dev/null

# 脚本结束，终端自动关闭
