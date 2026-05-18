"""Eva Agent 核心模块测试"""
import sys, json, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 配置测试 ──

def test_config_defaults():
    from queen_bee.config import DEFAULT_CONFIG
    assert "model" in DEFAULT_CONFIG
    assert "deepseek" in str(DEFAULT_CONFIG.get("models_available", {}))

def test_config_save_load():
    from queen_bee.config import get as get_cfg, load
    # 强制重新加载
    global _config
    try:
        import queen_bee.config as c
        c._config = None
    except: pass
    cfg = get_cfg()
    assert cfg is not None
    assert "model" in cfg

# ── 语义测试 ──

def test_semantic_expand():
    from queen_bee.semantic import expand, expand_tags
    r = expand("写程序")
    assert "写" in r or "程序" in r
    r2 = expand_tags("帮我写一个计算器")
    assert len(r2) > 0

def test_emotion_detection():
    from queen_bee.semantic import detect_emotion
    assert detect_emotion("真棒") == "praise"
    assert detect_emotion("糟糕") == "disapprove"
    assert detect_emotion("等等") == "hesitate"
    assert detect_emotion("好吧") == "approve"
    assert detect_emotion("谢谢") == "thanks"

def test_common_misunderstandings():
    from queen_bee.semantic import COMMON_MISUNDERSTANDINGS
    assert "看到我的桌面" in COMMON_MISUNDERSTANDINGS
    assert "帮我下载" in COMMON_MISUNDERSTANDINGS

# ── 熟练度测试 ──

def test_mastery_score():
    from queen_bee.mastery import score, record
    s = score()
    assert "score" in s
    assert "title" in s
    assert s["score"] >= 0

def test_mastery_record():
    from queen_bee.mastery import record, score
    before = score()["score"]
    record("tool_calls")
    record("conversations")
    after = score()["score"]
    assert after >= before

def test_mastery_invite():
    from queen_bee.mastery import generate_invite, get_invite
    code = generate_invite()
    assert code.startswith("EVA-")
    assert get_invite() == code

# ── 加密测试 ──

def test_encrypt_decrypt():
    from queen_bee.crypto import encrypt, decrypt
    original = "sk-test123456789"
    encrypted = encrypt(original)
    if encrypted != original:  # 有 Fernet 才测试
        assert encrypted != original
        decrypted = decrypt(encrypted)
        assert decrypted == original
