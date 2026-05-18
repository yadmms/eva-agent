#!/bin/bash
# Start both backend and Electron
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/../.."
python3 run.py --host 0.0.0.0 --port 19198 &
sleep 2
cd "$DIR"
npm start
