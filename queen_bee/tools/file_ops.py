"""文件操作工具 — 纯Python实现的读取、写入、递归搜索"""

import fnmatch
import os
from pathlib import Path
from typing import Optional


def read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    """读取文件内容，带行号显示，支持分页

    Args:
        path: 文件路径（支持 ~ 展开）
        offset: 起始行号（1-indexed，默认第1行）
        limit: 最大返回行数（默认500，最大2000）

    Returns:
        带行号的文件内容，格式: "LINE_NUM|CONTENT"
    """
    p = Path(path).expanduser().resolve()

    if not p.exists():
        return f"错误: 文件不存在: {path}"
    if not p.is_file():
        return f"错误: 路径不是文件: {path}"
    if p.stat().st_size > 10 * 1024 * 1024:  # 10MB 上限
        return f"错误: 文件过大 ({p.stat().st_size / 1024 / 1024:.1f}MB)，超过10MB上限"

    limit = max(1, min(limit, 2000))
    offset = max(1, offset)

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"错误: 无法读取文件: {e}"

    lines = content.split("\n")
    total_lines = len(lines)

    if offset > total_lines:
        return f"错误: offset ({offset}) 超过总行数 ({total_lines})"

    end = min(offset + limit - 1, total_lines)
    result_lines = []
    for i in range(offset - 1, end):
        result_lines.append(f"{i + 1}|{lines[i]}")

    output = "\n".join(result_lines)

    if end < total_lines:
        output += f"\n...(共{total_lines}行，已显示{offset}-{end}行，剩余{total_lines - end}行)"

    return output


def write_file(path: str, content: str) -> str:
    """写入文件内容，自动创建父目录

    Args:
        path: 文件路径（支持 ~ 展开）
        content: 要写入的内容

    Returns:
        操作结果描述
    """
    p = Path(path).expanduser().resolve()

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        return f"✓ 已写入: {path} ({size} 字节)"
    except PermissionError:
        return f"错误: 权限不足，无法写入 {path}"
    except IsADirectoryError:
        return f"错误: 路径是目录，无法写入: {path}"
    except Exception as e:
        return f"错误: 写入失败: {e}"


def search_files(
    pattern: str,
    path: str = ".",
    glob: Optional[str] = None,
    max_results: int = 50,
) -> str:
    """纯Python递归搜索文件内容

    Args:
        pattern: 搜索的正则表达式或纯文本
        path: 搜索起始目录（默认当前目录）
        glob: 文件名过滤glob（如 "*.py"），可选
        max_results: 最大返回结果数（默认50）

    Returns:
        搜索结果，格式: "file_path:line_num: 匹配行内容"
    """
    import re

    try:
        pattern_re = re.compile(pattern)
    except re.error:
        # 不是有效正则，按纯文本搜索
        pattern_re = re.compile(re.escape(pattern))

    base = Path(path).expanduser().resolve()

    if not base.exists():
        return f"错误: 目录不存在: {path}"
    if not base.is_dir():
        return f"错误: 路径不是目录: {path}"

    results = []
    # 二进制文件扩展名（跳过这些）
    BINARY_EXTS = {
        ".pyc", ".pyo", ".so", ".o", ".a", ".dll", ".exe", ".bin",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
        ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
        ".db", ".sqlite", ".sqlite3",
        ".DS_Store", ".class",
    }

    try:
        for dirpath, dirnames, filenames in os.walk(base):
            # 跳过隐藏目录和常见忽略目录
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", "venv", ".venv",
                              ".git", ".svn", "dist", "build", "target", ".tox")
            ]

            if len(results) >= max_results:
                break

            for fname in filenames:
                if len(results) >= max_results:
                    break

                # glob 过滤
                if glob and not fnmatch.fnmatch(fname, glob):
                    continue

                # 跳过二进制文件
                ext = os.path.splitext(fname)[1].lower()
                if ext in BINARY_EXTS:
                    continue

                fpath = os.path.join(dirpath, fname)
                try:
                    # 跳过太大的文件 (>2MB)
                    if os.path.getsize(fpath) > 2 * 1024 * 1024:
                        continue

                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        for line_no, line in enumerate(f, 1):
                            if pattern_re.search(line):
                                rel_path = os.path.relpath(fpath, base)
                                results.append(f"{rel_path}:{line_no}: {line.rstrip()}")
                                if len(results) >= max_results:
                                    break
                except (PermissionError, OSError):
                    continue

    except Exception as e:
        return f"搜索错误: {e}"

    if not results:
        return f"未找到匹配 '{pattern}'" + (f" (glob: {glob})" if glob else "")

    output = "\n".join(results)
    if len(results) >= max_results:
        output += f"\n...(已达上限{max_results}条，结果可能不完整)"
    else:
        output += f"\n(共{len(results)}条匹配)"

    return output
