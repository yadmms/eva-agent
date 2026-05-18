"""配置管理 - YAML配置文件读取，支持默认值+用户覆盖"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG = {
    "model": {
        "provider": "deepseek",
        "name": "deepseek-v4-flash",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com/v1",
    },
    "models_available": {
        "deepseek": {
            "deepseek-v4-flash": {"base_url": "https://api.deepseek.com/v1"},
            "deepseek-v4-pro": {"base_url": "https://api.deepseek.com/v1"},
        },
        "openai": {
            "gpt-4o": {"base_url": "https://api.openai.com/v1"},
            "gpt-4o-mini": {"base_url": "https://api.openai.com/v1"},
            "gpt-4.1": {"base_url": "https://api.openai.com/v1"},
        },
        "openrouter": {
            "claude-sonnet-4": {"base_url": "https://openrouter.ai/api/v1"},
            "claude-opus-4": {"base_url": "https://openrouter.ai/api/v1"},
            "gemini-2.5-flash": {"base_url": "https://openrouter.ai/api/v1"},
        },
        "zhipu": {
            "glm-4-flash": {"base_url": "https://open.bigmodel.cn/api/paas/v4"},
            "glm-4-plus": {"base_url": "https://open.bigmodel.cn/api/paas/v4"},
        },
        "moonshot": {
            "moonshot-v1-8k": {"base_url": "https://api.moonshot.cn/v1"},
            "moonshot-v1-32k": {"base_url": "https://api.moonshot.cn/v1"},
        },
        "groq": {
            "llama-3.3-70b": {"base_url": "https://api.groq.com/openai/v1"},
        },
        "siliconflow": {
            "deepseek-ai/DeepSeek-V3": {"base_url": "https://api.siliconflow.cn/v1"},
            "deepseek-ai/DeepSeek-R1": {"base_url": "https://api.siliconflow.cn/v1"},
            "Qwen/Qwen2.5-7B-Instruct": {"base_url": "https://api.siliconflow.cn/v1"},
        },
    },
    "agent": {
        "max_tool_calls": 20,
        "system_prompt": (
            "你是伊娃(Eva Agent)，来自千叶实验室的 AI 智能助手。\n\n"
            "这是连续对话，你已经介绍过自己了，每次直接回答用户的问题，不要重复自我介绍。\n\n"
            "## 规则\n"
            "- 先看用户问了什么，直接回答\n"
            "- 需要调工具就调，调完用结果回答\n"
            "- 工具调用次数有限，一次尽量完成多个操作\n"
            "- 不要自我介绍，不要寒暄，直接回答问题\n"
            "- 用户问之前的事，先看 system prompt 里的「近期对话记忆」，那里有最近聊过的内容\n"
            "- 解决了有价值的问题后，用 save_skill 保存为技能（用户说'谢谢'可以了'时自动调用）\n"
            "- 缺少依赖时自动用 pip_install 安装，不要让用户手动操作"
        ),
    },
    "tools": {
        "terminal": True,
        "file_ops": True,
        "web_search": True,
    },
    "server": {
        "host": "0.0.0.0",
        "port": 19198,
    },
    "api_keys": {},
    "eva_name": "",
    "lab_joined": False,
    "data_dir": "~/eva-data",
    "assets_dir": "",
    "palace": {
        "base_dir": "~/.eva_palace",
        "max_history": 200,
        "auto_summary": True,
    },
    "memory": {
        "sanctum_url": "",
        "agent_token": "",
        "agent_id": "",
    },
}

_config: Optional[Dict] = None

def load(config_path: str = None) -> Dict[str, Any]:
    global _config
    if _config is not None:
        return _config
    
    _config = dict(DEFAULT_CONFIG)
    
    if config_path is None:
        config_path = os.environ.get("QUEEN_BEE_CONFIG", 
                     str(Path.home() / ".queen_bee.yaml"))
    
    if Path(config_path).exists():
        with open(config_path) as f:
            user = yaml.safe_load(f) or {}
        _deep_merge(_config, user)
        # 解密 API Key
        from .crypto import decrypt
        raw_key = _config.get("model", {}).get("api_key", "")
        if raw_key:
            _config["model"]["api_key"] = decrypt(raw_key)
        for prov in _config.get("api_keys", {}):
            raw = _config["api_keys"][prov]
            if raw:
                _config["api_keys"][prov] = decrypt(raw)
    
    return _config

def get() -> Dict[str, Any]:
    return _config or load()

def set_model(provider: str, name: str):
    """运行时切换模型"""
    cfg = get()
    avail = cfg.get("models_available", {})
    if provider not in avail or name not in avail[provider]:
        raise ValueError(f"未知模型: {provider}/{name}")
    cfg["model"]["provider"] = provider
    cfg["model"]["name"] = name

def list_models() -> list:
    """列出所有可用模型"""
    cfg = get()
    models = []
    for prov, ms in cfg.get("models_available", {}).items():
        for m in ms:
            models.append({"provider": prov, "name": m, "label": f"{prov}/{m}"})
    return models

def save_config():
    """持久化当前配置到YAML文件（自动加密 API Key）"""
    import yaml
    from .crypto import encrypt
    cfg = get()
    # 加密密钥
    api_key = cfg.get("model", {}).get("api_key", "")
    if api_key and not api_key.startswith("gAAAAA"):
        cfg["model"]["api_key"] = encrypt(api_key)
    for prov, key in cfg.get("api_keys", {}).items():
        if key and not key.startswith("gAAAAA"):
            cfg["api_keys"][prov] = encrypt(key)
    config_path = Path.home() / ".queen_bee.yaml"
    out = {"model": cfg.get("model", {}), "models_available": cfg.get("models_available", {}), "api_keys": cfg.get("api_keys", {})}
    config_path.write_text(yaml.dump(out, allow_unicode=True, default_flow_style=False))

def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
