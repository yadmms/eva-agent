"""LLM Provider — DeepSeek V4 优化版"""
import os, json, time, logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger("eva.provider")

# ── API Key ──

def _load_api_key(provider: str) -> str:
    key = os.environ.get(f"{provider.upper()}_API_KEY", "")
    if key: return key
    try:
        from .config import get as get_config
        cfg = get_config()
        key = cfg.get("api_keys", {}).get(provider, "")
        if key: return key
        return cfg.get("model", {}).get("api_key", "")
    except Exception:
        return ""

# ── HTTP 客户端 ──

_client: Optional[httpx.Client] = None

def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
    return _client

def get_shared_client() -> httpx.Client:
    return _get_client()

class ProviderError(Exception):
    pass

# ── 重试 ──

def _retry_with_backoff(fn, max_retries=3):
    last_error = None
    for attempt in range(max_retries):
        try:
            return fn()
        except ProviderError as e:
            last_error = e
            if "429" in str(e) or "rate" in str(e).lower():
                wait = 2 ** attempt
                logger.warning(f"限频，{wait}s后重试({attempt+1}/{max_retries})")
                time.sleep(wait)
            elif "5" in str(e)[:20]:
                wait = 2 ** attempt
                logger.warning(f"服务端错误，{wait}s后重试({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(f"网络错误: {e}, {wait}s后重试({attempt+1}/{max_retries})")
            time.sleep(wait)
    raise last_error

# ── 核心调用 ──

def chat(messages: List[Dict], tools: Optional[List[Dict]] = None,
         provider: str = None, model: str = None, stream: bool = False) -> Dict:
    try:
        from .config import get as get_config
        config = get_config()
    except Exception:
        config = {}

    provider = provider or config.get("model", {}).get("provider", "deepseek")
    model = model or config.get("model", {}).get("name", "deepseek-chat")

    models_avail = config.get("models_available", {})
    model_info = models_avail.get(provider, {}).get(model, {})
    base_url = model_info.get("base_url", "https://api.deepseek.com/v1")

    api_key = _load_api_key(provider)
    if not api_key:
        raise ProviderError(f"缺少 {provider.upper()} API Key")

    # DeepSeek V4: 思考模式控制
    is_v4_pro = "v4-pro" in model or model == "deepseek-reasoner"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    if is_v4_pro:
        # V4 Pro: 思考模式 + 高质量
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = "high"
    else:
        # V4 Flash: 非思考模式（快速响应）
        payload["thinking"] = {"type": "disabled"}
        payload["temperature"] = 0.1

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    if stream:
        payload["stream"] = True

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    client = _get_client()

    def _do_request():
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise ProviderError(f"API {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    return _retry_with_backoff(_do_request)
