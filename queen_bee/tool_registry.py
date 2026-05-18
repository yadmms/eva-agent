"""工具注册表 - 注册/注销/按需加载，转OpenAI function calling格式"""

import json, time
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional

_tools: Dict[str, Dict] = {}

# ── 注册函数 ──────────────────────────────────────────────

def register(name: str, description: str, parameters: Dict,
             execute: Callable, enabled: bool = True):
    """注册工具"""
    _tools[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "execute": execute,
        "enabled": enabled,
    }


def unregister(name: str):
    """注销工具"""
    _tools.pop(name, None)


def get_tool(name: str) -> Optional[Dict]:
    return _tools.get(name)


def get_all() -> Dict[str, Dict]:
    return dict(_tools)


def get_schemas(only_enabled: bool = True) -> List[Dict]:
    """转为OpenAI function calling格式"""
    schemas = []
    for name, tool in _tools.items():
        if only_enabled and not tool["enabled"]:
            continue
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
        })
    return schemas


def execute(name: str, args: Dict) -> str:
    """执行工具调用"""
    tool = _tools.get(name)
    if not tool:
        return f"错误: 未知工具 {name}"
    if not tool["enabled"]:
        return f"错误: 工具 {name} 已禁用"
    try:
        result = tool["execute"](**args)
        return str(result)
    except Exception as e:
        return f"工具执行错误: {e}"


# ── 自动化注册所有工具 ─────────────────────────────────────

def _auto_register():
    """自动发现并注册tools子模块中的工具函数"""
    from queen_bee.tools.terminal import execute as terminal_execute
    from queen_bee.tools.file_ops import read_file, write_file, search_files
    from queen_bee.tools.web_search import fetch_url
    from queen_bee.web_inspector import fetch_and_analyze as web_fetch_and_analyze, check_links as web_check_links

    # ─── terminal.execute ─────────────────────────────────
    register(
        name="terminal",
        description="在Linux环境中执行shell命令。返回stdout、stderr和exit_code。"
                    "命令有30秒超时限制。危险命令（如rm -rf /等）会被阻止。"
                    "适用于：安装软件包、运行脚本、git操作、进程管理、网络诊断等。",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的shell命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认30，最大300）",
                    "default": 30,
                },
                "cwd": {
                    "type": "string",
                    "description": "工作目录（绝对路径），可选",
                },
            },
            "required": ["command"],
        },
        execute=terminal_execute,
    )

    # ─── file_ops.read_file ───────────────────────────────
    register(
        name="read_file",
        description="读取文件内容，带行号显示。支持分页（offset/limit）。"
                    "适用于：查看代码、配置文件、日志等文本文件。"
                    "输出格式: 'LINE_NUM|CONTENT'",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（支持 ~ 展开）",
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（1-indexed，默认1）",
                    "default": 1,
                    "minimum": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回行数（默认500，最大2000）",
                    "default": 500,
                    "minimum": 1,
                    "maximum": 2000,
                },
            },
            "required": ["path"],
        },
        execute=read_file,
    )

    # ─── file_ops.write_file ──────────────────────────────
    register(
        name="write_file",
        description="写入文件内容，自动创建父目录。完全覆盖已有内容。"
                    "适用于：创建新文件、保存生成的内容。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（支持 ~ 展开）",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的完整内容",
                },
            },
            "required": ["path", "content"],
        },
        execute=write_file,
    )

    # ─── file_ops.search_files ────────────────────────────
    register(
        name="search_files",
        description="纯Python实现的递归文件内容搜索，类似grep。"
                    "支持正则表达式和glob文件名过滤。"
                    "跳过二进制文件和常见忽略目录（node_modules/.git/__pycache__等）。"
                    "适用于：在代码库中查找函数定义、配置项、错误信息等。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索模式：正则表达式或纯文本",
                },
                "path": {
                    "type": "string",
                    "description": "搜索起始目录（默认当前目录 '.'）",
                    "default": ".",
                },
                "glob": {
                    "type": "string",
                    "description": "文件名过滤glob（如 '*.py'），可选",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数（默认50）",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
        execute=search_files,
    )

    # ─── web_search.fetch_url ─────────────────────────────
    register(
        name="fetch_url",
        description="使用Python内置urllib抓取网页内容，无需外部依赖。"
                    "支持GET请求，提取纯文本。自动处理gzip、字符编码、HTML标签清理。"
                    "适用于：获取API响应、抓取文档页面、检查网站状态。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "目标URL（http/https）",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP方法，默认GET",
                    "default": "GET",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认15）",
                    "default": 15,
                },
                "headers": {
                    "type": "object",
                    "description": "额外的请求头（可选）",
                },
            },
            "required": ["url"],
        },
        execute=fetch_url,
    )

    # ─── web_inspector.fetch_and_analyze ─────────────────
    register(
        name="web_inspect",
        description="抓取网页并进行全面分析。检测HTTP状态码、响应时间、页面大小、"
                    "SEO问题（缺title/description/h1/viewport）、"
                    "链接/图片/脚本/css/表单/iframe数量、"
                    "是否gzip压缩。返回结构化JSON分析报告。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "目标URL（http/https）",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认15）",
                    "default": 15,
                },
            },
            "required": ["url"],
        },
        execute=web_fetch_and_analyze,
    )

    # ─── web_inspector.check_links ───────────────────────
    register(
        name="check_links",
        description="检测网页中所有链接的有效性。提取所有<a href>链接，"
                    "并发检查前20个唯一链接的HTTP状态，"
                    "返回断链列表（含状态码和错误信息）。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "目标URL（http/https）",
                },
                "timeout": {
                    "type": "integer",
                    "description": "抓取页面超时秒数（默认15）",
                    "default": 15,
                },
            },
            "required": ["url"],
        },
        execute=web_check_links,
    )

    # ─── palace.recall ─────────────────────────────────────
    def _search_memory(query: str = "", limit: int = 5) -> str:
        """搜索记忆宫殿，返回匹配的历史记录"""
        from queen_bee.palace import get_palace
        palace = get_palace()
        matched = palace.recall(query)[:limit] if query else []
        # 语义扩展二次搜索 — 如果没结果，用扩展词再搜
        if not matched and query:
            from queen_bee.semantic import expand
            for term in sorted(expand(query), key=len, reverse=True)[:5]:
                matched = palace.recall(term)[:limit]
                if matched:
                    break
        recent = palace.recall("")[:3]
        lines = []
        if matched:
            lines.append("📌 相关记忆：")
            for r in matched:
                lines.append(f"- [{r['type']}] {r['title']}: {r['preview']}")
        if recent:
            lines.append("\n📋 近期对话：")
            for r in recent:
                lines.append(f"- {r['title']}")
        return "\n".join(lines) if lines else "暂无记忆"

    register(
        name="search_memory",
        description="搜索记忆宫殿，查找过去的对话、任务和决策记录。当用户问'还记得吗''之前做过什么'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，描述要找的内容",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回条数（默认5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        execute=_search_memory,
    )

    # ─── save_skill ─────────────────────────────────────────────────
    def _save_skill(name: str = "", description: str = "", content: str = "", tags: str = "") -> str:
        """保存技能到本地，若已加入实验室则同步到织网者"""
        skill = {"name": name, "description": description, "content": content, "tags": tags, "created": time.time()}
        skill_dir = Path.home() / ".eva" / "skills"
        skill_dir.mkdir(parents=True, exist_ok=True)
        slug = "".join(c for c in name if c.isalnum() or c in "_-. ")[:40].strip().replace(" ", "_")
        fpath = skill_dir / f"{slug}.json"
        fpath.write_text(json.dumps(skill, ensure_ascii=False, indent=2))
        from queen_bee.mastery import record
        record("skills_shared")
        return f"技能已保存: {name}"

    register(
        name="save_skill",
        description="保存解决问题的经验为技能。当用户说'好了''可以了''谢谢'表示满意时调用，或你完成了一个有价值的任务后调用。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称，简短描述做了什么"},
                "description": {"type": "string", "description": "简短描述"},
                "content": {"type": "string", "description": "完整内容（问题+解决方案+步骤）"},
                "tags": {"type": "string", "description": "逗号分隔的标签"},
            },
            "required": ["name", "content"],
        },
        execute=_save_skill,
    )

    # ─── git tools ──────────────────────────────────────────────
    def _git_exec(args: str = "") -> str:
        import subprocess, os
        try:
            r = subprocess.run(["git"] + args.split(), capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr)[:2000]
            return out or "(无输出)"
        except FileNotFoundError:
            return "未找到 git，请先安装 git"
        except Exception as e:
            return f"git 错误: {e}"

    register(name="git_status", description="查看当前仓库的 git status — 修改、新增、删除的文件列表",
             parameters={"type": "object", "properties": {}, "required": []}, execute=lambda: _git_exec("status --short"))

    register(name="git_diff", description="查看未暂存的 diff — 具体改了哪些内容",
             parameters={"type": "object", "properties": {}, "required": []}, execute=lambda: _git_exec("diff"))

    register(name="git_log", description="查看最近提交历史",
             parameters={"type": "object", "properties": {}, "required": []}, execute=lambda: _git_exec("log --oneline -10"))

    register(name="git_commit", description="提交当前暂存区的更改",
             parameters={"type": "object", "properties": {"message": {"type": "string", "description": "提交信息"}},
                          "required": ["message"]},
             execute=lambda message: _git_exec(f'commit -m "{message}"'))

    # ─── pip_install ───────────────────────────────────────────
    def _pip_install(package: str = "") -> str:
        import subprocess, sys
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                               "--break-system-packages", package],
                             capture_output=True, text=True, timeout=60)
            return f"✅ {package} 安装成功" if r.returncode == 0 else f"❌ 安装失败: {r.stderr[:200]}"
        except Exception as e:
            return f"❌ 安装出错: {e}"

    register(
        name="pip_install",
        description="安装 Python 依赖包。当需要读取 PDF/Word/Excel 时自动调用，或用户说'装一下'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "包名如 pdfminer.six python-docx openpyxl，多个用空格分隔"},
            },
            "required": ["package"],
        },
        execute=_pip_install,
    )

_auto_register()
