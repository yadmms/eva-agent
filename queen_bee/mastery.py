"""熟练度追踪 — 用户成长系统"""
import json, time
from pathlib import Path

DATA_DIR = Path.home() / ".eva"
MASTERY_FILE = DATA_DIR / "mastery.json"

_DEFAULTS = {
    "tool_calls": 0,      # 工具调用次数
    "conversations": 0,   # 对话轮次
    "memory_count": 0,    # 记忆条数
    "projects": 0,        # 项目数
    "skills_shared": 0,   # 技能分享
    "web_searches": 0,    # 搜索次数
    "code_execs": 0,      # 代码执行
}

def _load() -> dict:
    if MASTERY_FILE.exists():
        try: return json.loads(MASTERY_FILE.read_text())
        except: pass
    return dict(_DEFAULTS)

def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MASTERY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def get() -> dict:
    return _load()

def record(action: str):
    data = _load()
    if action in data:
        data[action] += 1
    _save(data)

def generate_invite() -> str:
    """生成一次性邀请码（达到掌控者时触发）"""
    import hashlib, socket
    seed = f"{socket.gethostname()}-{time.time()}-eva-master"
    code = "EVA-" + hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
    data = _load()
    data["_invite_code"] = code
    data["_invite_used"] = False
    _save(data)
    return code

def get_invite() -> str:
    """获取已有邀请码"""
    return _load().get("_invite_code", "")

def score() -> dict:
    data = _load()
    total = 0
    weights = {"tool_calls": 25, "conversations": 10, "memory_count": 15,
               "projects": 15, "skills_shared": 20, "web_searches": 10, "code_execs": 5}
    details = {}
    for k, w in weights.items():
        val = min(data.get(k, 0) / max(w, 1), 1.0)
        details[k] = {"value": data.get(k, 0), "pct": round(val * 100)}
        total += val * w
    total_pct = min(round(total / sum(weights.values()) * 100), 100)
    title = "初识者"
    if total_pct >= 100:
        title = "掌控者"
        if not data.get("_invite_code"):
            generate_invite()
    elif total_pct >= 80: title = "近道者"
    elif total_pct >= 60: title = "知己"
    elif total_pct >= 40: title = "同行者"
    elif total_pct >= 20: title = "探索者"
    invite = get_invite() if total_pct >= 100 else ""
    return {"score": total_pct, "title": title, "invite": invite, "details": details}
