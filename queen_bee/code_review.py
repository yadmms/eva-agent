"""代码审查模块 — 对标OpenCode静态分析与代码质量审查

提供：
1. review_file(path) — 单文件静态分析：语法、复杂度、风格
2. review_directory(path) — 目录级别批量审查
3. 检查维度：语法错误、过长函数(>80行)、未使用导入、缺少文档字符串
"""

import ast
import re
import sys
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════
# 审查结果数据结构
# ═══════════════════════════════════════════

class Issue:
    """单个代码问题"""

    def __init__(self, file: str, line: int, severity: str,
                 category: str, message: str, suggestion: str = ""):
        self.file = file
        self.line = line
        self.severity = severity   # error / warning / info
        self.category = category   # syntax / complexity / style / security / doc
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
        }

    def format(self) -> str:
        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[self.severity]
        line = f"{icon} [{self.severity.upper()}] {self.file}:{self.line} — {self.message}"
        if self.suggestion:
            line += f"\n   💡 {self.suggestion}"
        return line


class ReviewResult:
    """审查结果集"""

    def __init__(self):
        self.issues: list[Issue] = []
        self.files_checked: int = 0
        self.files_skipped: int = 0

    def add(self, file: str, line: int, severity: str,
            category: str, message: str, suggestion: str = ""):
        self.issues.append(Issue(file, line, severity, category, message, suggestion))

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    def report(self, max_issues: int = 50) -> str:
        """生成 Markdown 审查报告"""
        lines = [
            "# 📋 代码审查报告",
            "",
            f"**文件**: {self.files_checked} 已检查"
            + (f", {self.files_skipped} 跳过" if self.files_skipped else ""),
            f"**问题**: ❌ {self.error_count} 错误"
            + f" | ⚠️ {self.warning_count} 警告"
            + f" | ℹ️ {self.info_count} 建议",
            f"**总计**: {len(self.issues)} 个问题",
            "",
        ]

        if not self.issues:
            lines.append("✅ **未发现问题，代码质量良好！**")
            return "\n".join(lines)

        # 按严重程度分组
        for sev, label in [("error", "❌ 错误"), ("warning", "⚠️ 警告"), ("info", "ℹ️ 建议")]:
            group = [i for i in self.issues if i.severity == sev]
            if not group:
                continue
            lines.append(f"## {label} ({len(group)}项)")
            lines.append("")
            for i, issue in enumerate(group[:max_issues]):
                lines.append(issue.format())
                lines.append("")
            if len(group) > max_issues:
                lines.append(f"... 还有 {len(group) - max_issues} 项")
                lines.append("")

        # 按类别统计
        lines.append("## 📊 类别分布")
        cats: dict[str, int] = {}
        for i in self.issues:
            cats[i.category] = cats.get(i.category, 0) + 1
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat}: {count}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """导出为 JSON"""
        import json
        return json.dumps({
            "files_checked": self.files_checked,
            "files_skipped": self.files_skipped,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
        }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════
# 审查检查器
# ═══════════════════════════════════════════

# 标准库导入列表（用于检测"可能未使用"的标准库导入）
STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop", "base64", "bdb", "binascii", "bisect",
    "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "doctest",
    "email", "encodings", "enum", "errno", "faulthandler", "fcntl",
    "filecmp", "fileinput", "fnmatch", "formatter", "fractions", "ftplib",
    "functools", "gc", "getopt", "getpass", "gettext", "glob", "grp",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib",
    "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib", "numbers",
    "operator", "optparse", "os", "ossaudiodev", "parser", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue",
    "quopri", "random", "re", "readline", "reprlib", "resource",
    "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
    "sndhdr", "socket", "socketserver", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
    "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    # 特殊: __future__
    "__future__",
}


def _is_python_file(path: Path) -> bool:
    """判断是否为 Python 源文件"""
    return path.suffix.lower() in (".py", ".pyw", ".pyi")


def _should_skip(path: Path) -> bool:
    """跳过非代码文件"""
    name = path.name
    if name.startswith("."):
        return True
    if name in ("__pycache__",):
        return True
    if "__pycache__" in path.parts:
        return True
    if name == "__init__.py" and path.stat().st_size < 100:
        return True  # 跳过空/极简 __init__.py
    return False


# ═══════════════════════════════════════════
# 单文件审查
# ═══════════════════════════════════════════

def review_file(path: str) -> str:
    """审查单个文件，返回 Markdown 报告

    检查维度：
    1. 语法错误
    2. 过长函数 (>80行)
    3. 未使用导入
    4. 缺少文档字符串
    5. 潜在安全问题 (eval/exec/shell=True)
    6. 空 except 块

    Args:
        path: 文件路径

    Returns:
        Markdown 格式的审查报告
    """
    fp = Path(path).expanduser().resolve()
    result = ReviewResult()
    result.files_checked = 1

    if not fp.exists():
        return f"❌ 文件不存在: {fp}"

    if not _is_python_file(fp):
        return f"ℹ️ 非 Python 文件，仅支持 .py 审查: {fp.name}"

    rel_path = str(fp)

    try:
        source = fp.read_text(encoding="utf-8")
    except Exception as e:
        result.add(rel_path, 0, "error", "syntax", f"无法读取文件: {e}")
        return result.report()

    lines = source.split("\n")

    # ── 1. 语法检查 ──
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result.add(rel_path, e.lineno or 0, "error", "syntax",
                   f"语法错误: {e.msg}", "修复语法错误后重新审查")
        return result.report()

    # ── 2. 函数长度检查 ──
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno:
                func_lines = node.end_lineno - node.lineno + 1
                if func_lines > 80:
                    result.add(
                        rel_path, node.lineno, "warning", "complexity",
                        f"函数 `{node.name}()` 过长 ({func_lines}行)",
                        f"建议拆分 `{node.name}()` 为多个小函数，每个 ≤ 50 行"
                    )
                elif func_lines > 50:
                    result.add(
                        rel_path, node.lineno, "info", "complexity",
                        f"函数 `{node.name}()` 较长 ({func_lines}行)",
                        f"考虑拆分 `{node.name}()` 以提升可读性"
                    )

    # ── 3. 导入分析 ──
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.asname, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                imports.append((full, alias.asname, node.lineno))

    # 收集代码中使用的名称
    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # 对于 obj.method, 收集顶层名
            parts = []
            curr = node
            while isinstance(curr, ast.Attribute):
                parts.insert(0, curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                used_names.add(curr.id)
                used_names.add(f"{curr.id}.{'.'.join(parts)}")

    # 检测可能未使用的导入
    for imp_name, imp_alias, imp_line in imports:
        name_to_check = imp_alias or imp_name.split(".")[0]
        if name_to_check.startswith("_"):
            continue  # 私有导入可能用于 re-export

        # 特殊豁免
        if imp_name in STDLIB_MODULES and name_to_check not in used_names:
            # 标准库导入在某些上下文中是合理的（类型标注、配置等）
            pass
        elif name_to_check not in used_names:
            # 检查是否在字符串中使用 (如 getattr, __import__)
            name_in_str = name_to_check in source
            if not name_in_str:
                result.add(
                    rel_path, imp_line, "info", "style",
                    f"导入 `{imp_name}` 可能未使用",
                    "移除未使用的导入以保持代码整洁"
                )

    # ── 4. 文档字符串检查 ──
    # 模块级文档
    module_doc = ast.get_docstring(tree)
    if not module_doc or len(module_doc) < 10:
        result.add(
            rel_path, 1, "info", "doc",
            "模块缺少文档字符串",
            "添加模块级 docstring 描述文件用途"
        )

    # 函数/类文档
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 跳过私有函数和魔术方法
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue
            if node.name in ("__init__", "__repr__", "__str__", "__call__"):
                continue
            doc = ast.get_docstring(node)
            if not doc or len(doc) < 5:
                result.add(
                    rel_path, node.lineno, "info", "doc",
                    f"函数 `{node.name}()` 缺少文档字符串",
                    f"为 `{node.name}()` 添加简要的 docstring"
                )
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc or len(doc) < 5:
                result.add(
                    rel_path, node.lineno, "info", "doc",
                    f"类 `{node.name}` 缺少文档字符串",
                    f"为类 `{node.name}` 添加描述性的 docstring"
                )

    # ── 5. 安全检查 ──
    unsafe_patterns = [
        (r'\beval\s*\(', "eval() 调用"),
        (r'\bexec\s*\(', "exec() 调用"),
        (r'subprocess\.[a-zA-Z]*\([^)]*shell\s*=\s*True', "shell=True 子进程调用"),
        (r'\bos\.system\s*\(', "os.system() 调用"),
        (r'__import__\s*\(', "动态 __import__()"),
        (r'(?<!re\.)\bcompile\b\s*\(', "compile() 调用 (非 re.compile)"),
    ]
    for pattern, desc in unsafe_patterns:
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                result.add(
                    rel_path, i, "warning", "security",
                    f"潜在不安全调用: {desc}",
                    "使用更安全的替代方案或严格校验输入"
                )

    # ── 6. 空 except 块 ──
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if (node.type is None or
                (isinstance(node.type, ast.Name) and node.type.id == "Exception")):
                # 检查 except 体是否为空
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    result.add(
                        rel_path, node.lineno, "warning", "style",
                        "空的 except 块 — 静默吞异常",
                        "至少记录日志或显式处理异常"
                    )

    # ── 7. 行长度检查 ──
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            result.add(
                rel_path, i, "info", "style",
                f"行过长 ({len(line)}字符)",
                "拆分长行为多行以提升可读性"
            )
            if sum(1 for _ in result.issues if _.category == "style" and "行过长" in _.message) > 5:
                break  # 避免过多同类问题

    return result.report()


# ═══════════════════════════════════════════
# 目录审查
# ═══════════════════════════════════════════

def review_directory(path: str = ".", recursive: bool = True,
                     file_limit: int = 100) -> str:
    """审查目录下所有 Python 文件

    Args:
        path: 目录路径
        recursive: 是否递归子目录
        file_limit: 最多审查文件数

    Returns:
        Markdown 格式的汇总报告
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        return f"❌ 路径不是目录: {root}"

    result = ReviewResult()

    if recursive:
        py_files = [
            p for p in root.rglob("*.py")
            if not _should_skip(p) and "__pycache__" not in str(p)
        ]
    else:
        py_files = [
            p for p in root.glob("*.py")
            if not _should_skip(p)
        ]

    if len(py_files) > file_limit:
        result.files_skipped = len(py_files) - file_limit
        py_files = sorted(py_files)[:file_limit]

    for fp in py_files:
        try:
            single_result = _review_file_internal(fp)
            result.issues.extend(single_result.issues)
            result.files_checked += 1
        except Exception:
            result.files_skipped += 1

    return result.report()


def _review_file_internal(fp: Path) -> ReviewResult:
    """内部审查函数，返回 ReviewResult 对象"""
    result = ReviewResult()
    result.files_checked = 1
    rel_path = str(fp)

    try:
        source = fp.read_text(encoding="utf-8")
    except Exception:
        result.files_checked = 0
        result.files_skipped = 1
        return result

    lines = source.split("\n")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result.add(rel_path, e.lineno or 0, "error", "syntax",
                   f"语法错误: {e.msg}")
        return result

    # 函数长度
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno:
                func_lines = node.end_lineno - node.lineno + 1
                if func_lines > 80:
                    result.add(rel_path, node.lineno, "warning", "complexity",
                               f"函数 `{node.name}()` 过长 ({func_lines}行)")

    # 文档字符串
    module_doc = ast.get_docstring(tree)
    if not module_doc or len(module_doc) < 10:
        result.add(rel_path, 1, "info", "doc", "模块缺少文档字符串")

    # 安全
    for i, line in enumerate(lines, 1):
        if re.search(r'\beval\s*\(|\bexec\s*\(|shell\s*=\s*True', line):
            result.add(rel_path, i, "warning", "security", "潜在不安全调用")

    return result


# ═══════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════

def quick_check(path: str) -> str:
    """快速检查单个文件，返回简要结果（适合工具调用）"""
    fp = Path(path).expanduser().resolve()
    if not fp.exists():
        return f"❌ 文件不存在: {path}"
    if not _is_python_file(fp):
        return f"ℹ️ 仅支持 .py: {fp.name}"

    result = _review_file_internal(fp)
    if not result.issues:
        return f"✅ {fp.name}: 未发现问题"

    lines = [f"📋 {fp.name}: {len(result.issues)} 个问题"]
    for issue in result.issues[:10]:
        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[issue.severity]
        lines.append(f"  {icon} L{issue.line}: {issue.message}")
    if len(result.issues) > 10:
        lines.append(f"  ... 还有 {len(result.issues) - 10} 个")
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 自测入口
# ═══════════════════════════════════════════
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    import argparse
    parser = argparse.ArgumentParser(description="代码审查工具")
    parser.add_argument("path", nargs="?", default=".", help="文件或目录路径")
    parser.add_argument("-r", "--recursive", action="store_true",
                        default=True, help="递归审查目录")
    parser.add_argument("-j", "--json", action="store_true",
                        help="以 JSON 格式输出")
    args = parser.parse_args()

    p = Path(args.path).expanduser()
    if p.is_file():
        output = review_file(str(p))
    else:
        output = review_directory(str(p), recursive=args.recursive)

    if args.json and p.is_dir():
        result = ReviewResult()
        py_files = list(p.rglob("*.py"))[:50]
        for fp in py_files:
            result.issues.extend(_review_file_internal(fp).issues)
        print(result.to_json())
    elif args.json and p.is_file():
        result = _review_file_internal(p)
        print(result.to_json())
    else:
        print(output)
