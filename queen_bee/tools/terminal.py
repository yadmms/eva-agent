"""终端执行工具 — 安全执行shell命令，30秒超时，返回结构化的stdout+stderr+exit_code"""

import subprocess
import shlex
import json
from typing import Optional

# 危险命令黑名单（大小写不敏感匹配）
DANGEROUS_PATTERNS = [
    # 递归强制删除根目录
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+/\*",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\$HOME",
    # 格式化磁盘
    r"mkfs",
    r"dd\s+if=/dev/zero\s+of=/dev/sd",
    # fork炸弹
    r":\(\)\s*\{",
    # 修改关键系统文件权限
    r"chmod\s+-R\s+777\s+/",
    r"chown\s+-R\s+\S+\s+/",
    # 危险重定向覆盖关键设备
    r">\s*/dev/sda",
    # 移动/替换系统目录
    r"mv\s+\S+\s+/bin",
    r"mv\s+\S+\s+/etc",
    r"mv\s+\S+\s+/usr",
    # 危险的关机/重启（容易误操作）
    r"shutdown\s+-h\s+now",
    r"reboot\s+-f",
    r"halt\s+-f",
    # 强制杀死系统关键进程
    r"kill\s+-9\s+1\b",
    r"killall\s+-9\s+init",
    # curl/wget管道到shell执行可疑脚本（过于危险的模式）
    r"curl\s+\S+\s*\|\s*(ba)?sh",
    r"wget\s+\S+\s+-O\s*-\s*\|\s*(ba)?sh",
]

import re
_DANGEROUS_RE = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def _is_dangerous(command: str) -> Optional[str]:
    """检查命令是否包含危险操作，返回匹配到的危险模式描述"""
    for pattern_re, pattern_str in zip(_DANGEROUS_RE, DANGEROUS_PATTERNS):
        if pattern_re.search(command):
            return f"检测到危险命令模式: {pattern_str}"
    return None


def execute(
    command: str,
    timeout: int = 30,
    cwd: Optional[str] = None,
) -> str:
    """执行shell命令，30秒超时，返回stdout+stderr+exit_code的JSON字符串

    Args:
        command: 要执行的shell命令
        timeout: 超时秒数（默认30）
        cwd: 工作目录（可选）

    Returns:
        JSON字符串，包含 stdout, stderr, exit_code, success 字段
    """
    # 安全扫描
    danger = _is_dangerous(command)
    if danger:
        return json.dumps({
            "stdout": "",
            "stderr": danger,
            "exit_code": -1,
            "success": False,
        }, ensure_ascii=False)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "success": result.returncode == 0,
        }, ensure_ascii=False)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "stdout": "",
            "stderr": f"命令超时（{timeout}秒）",
            "exit_code": -1,
            "success": False,
        }, ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({
            "stdout": "",
            "stderr": f"命令未找到: {command.split()[0] if command.strip() else '(空命令)'}",
            "exit_code": -1,
            "success": False,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "stdout": "",
            "stderr": f"执行错误: {e}",
            "exit_code": -1,
            "success": False,
        }, ensure_ascii=False)
