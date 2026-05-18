#!/usr/bin/env python3
"""Eva Agent v0.11.3 — 千叶实验室"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from queen_bee.api_server import run_server

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Eva Agent v0.11.3")
    parser.add_argument("--host", default=None, help="监听地址(默认0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="端口(默认19198)")
    parser.add_argument("--cli", action="store_true", help="CLI交互模式")
    parser.add_argument("--reload", action="store_true", help="热重载（改代码自动重启）")
    args = parser.parse_args()

    if args.cli:
        from queen_bee.agent import create_agent
        agent = create_agent()
        print("Eva Agent v0.11.3 — CLI 模式")
        while True:
            try:
                msg = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if msg.lower() in ("quit", "exit", "q"):
                break
            if msg:
                print(f"\n{agent.run(msg)}")
    else:
        run_server(args.host, args.port, reload=args.reload)
