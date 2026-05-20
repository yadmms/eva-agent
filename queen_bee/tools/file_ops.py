from pathlib import Path
def read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    p = Path(path).expanduser()
    if not p.exists(): return f"文件不存在: {path}"
    lines = p.read_text(errors="replace").split("\n")
    end = min(offset + limit - 1, len(lines))
    return "\n".join(f"{i+1}|{lines[i]}" for i in range(offset - 1, end))

def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"已写入 {path}"

def search_files(pattern: str, path: str = ".", glob: str = None, max_results: int = 50) -> str:
    import re, os
    base = Path(path).expanduser()
    results = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            fp = Path(root) / f
            try:
                for i, line in enumerate(fp.read_text(errors="replace").split("\n"), 1):
                    if re.search(pattern, line):
                        rel = fp.relative_to(base)
                        results.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(results) >= max_results: break
            except: continue
    return "\n".join(results) if results else "未找到匹配"
