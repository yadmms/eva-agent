#!/bin/bash
# Eva Agent — 桌面端启动（无终端窗口）
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
LOGFILE="eva-startup.log"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOGFILE"; }

log "=== Eva Agent v0.11.3 ==="
log "OS: $(uname -s)"
log "Startup"

PYTHON=""
for cmd in python3 python; do command -v $cmd &>/dev/null && { PYTHON=$cmd; break; } done
if [ -z "$PYTHON" ]; then
    log "ERROR: Python not found"
    echo "请先安装 Python 3.10+"
    exit 1
fi
log "Python: $($PYTHON --version 2>&1)"

log "Installing dependencies..."
$PYTHON -m pip install -r requirements.txt --break-system-packages 2>>"$LOGFILE" || true
log "Dependencies done"

kill $(lsof -t -i:19198 2>/dev/null) 2>/dev/null
log "Old server killed"

log "Starting server..."
nohup $PYTHON run.py > "$LOGFILE.server" 2>&1 &
disown

for i in $(seq 1 15); do
    curl -s http://localhost:19198 >/dev/null 2>&1 && break
    log "Waiting... ($i)"
    sleep 1
done
log "Server ready"

xdg-open "http://localhost:19198" 2>/dev/null
log "Browser opened"
