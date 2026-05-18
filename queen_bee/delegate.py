"""子智能体（Delegate Sub-Agent）模块 — v0.11

用户可创建多个命名的子智能体，每个配置独立的：
  - 身份（名称 + 角色）
  - LLM 提供商 + 模型
  - API Key（独立计费）
  - 工具集（限制或全开）

子智能体配置持久化在 ~/.eva/sub_agents/{name}.json
"""
from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from .provider import chat, ProviderError
from .tool_registry import get_schemas, execute as execute_tool, register
from .config import get as get_config

logger = logging.getLogger("eva.delegate")

SUB_AGENTS_DIR = Path.home() / ".eva" / "sub_agents"

# ── 子智能体配置模板 ────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPTS = {
    "架构师": (
        "你是{name}，一个资深系统架构师。你的职责：\n"
        "- 分析需求，设计系统架构\n"
        "- 将大任务分解为小模块\n"
        "- 输出：架构图(文字)→ 模块划分 → 接口定义 → 技术选型\n"
        "简洁、结构化，不做实现细节。每次回答控制在500字以内。"
    ),
    "程序员": (
        "你是{name}，一个高效的程序员。你的职责：\n"
        "- 收到编码任务后直接写代码\n"
        "- 不解释为什么，只输出结果\n"
        "- 代码简洁精确，带必要注释"
    ),
    "审查员": (
        "你是{name}，一个严格的代码审查员。你的职责：\n"
        "- 审查代码质量、查找 bug\n"
        "- 输出结构化问题清单：[严重/重要/建议]\n"
        "- 不写修复代码，只做诊断"
    ),
    "研究员": (
        "你是{name}，一个信息研究员。你的职责：\n"
        "- 搜索、收集、整理信息\n"
        "- 输出结构化摘要\n"
        "- 标注信息来源与可信度"
    ),
    "通用助手": (
        "你是{name}，一个AI助理。简洁直接地回答用户问题。"
    ),
}

def _build_system_prompt(name: str, role: str) -> str:
    """根据角色生成 system prompt"""
    template = DEFAULT_SYSTEM_PROMPTS.get(role, DEFAULT_SYSTEM_PROMPTS["通用助手"])
    return template.format(name=name)


# ── 子智能体会话 ──────────────────────────────────────────────

class SubAgentSession:
    """子智能体的一次独立会话 — 有自己的 LLM 配置、工具、上下文"""
    
    def __init__(self, agent_config: dict):
        self.cfg = agent_config
        self.history: List[Dict] = []
        self._api_key = agent_config.get("api_key", "")
        self._provider = agent_config.get("provider", "deepseek")
        self._model = agent_config.get("model", "deepseek-v4-flash")
        self._base_url = agent_config.get("base_url", "https://api.deepseek.com/v1")
        self._allowed_tools = agent_config.get("tools", None)
    
    def run(self, task: str) -> str:
        """执行一次任务，返回最终响应"""
        system_prompt = self.cfg.get("system_prompt", 
            _build_system_prompt(self.cfg["name"], self.cfg.get("role", "通用助手")))
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": task})
        
        all_schemas = get_schemas()
        if self._allowed_tools is not None:
            tools_schema = [s for s in all_schemas 
                          if s["function"]["name"] in self._allowed_tools]
        else:
            tools_schema = all_schemas
        
        max_calls = self.cfg.get("max_tool_calls", 10)
        call_count = 0
        
        while call_count < max_calls:
            call_count += 1
            
            try:
                response = self._chat(messages, tools_schema)
            except ProviderError as e:
                return f"[{self.cfg['name']}] 模型调用失败: {e}"
            
            choice = response.get("choices", [{}])[0]
            msg = choice.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            
            if not tool_calls:
                reply = msg.get("content", "")
                self.history.append({"role": "assistant", "content": reply})
                return reply
            
            messages.append(msg)
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                
                result = execute_tool(tool_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        
        return f"[{self.cfg['name']}] 达到最大工具调用次数({max_calls})"
    
    def _chat(self, messages: List[Dict], tools_schema: List[Dict]) -> Dict:
        """子智能体使用自己的 provider/model/key 调用 LLM"""
        import httpx
        
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools_schema:
            payload["tools"] = tools_schema
            payload["tool_choice"] = "auto"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        
        client = _get_sub_client()
        
        for attempt in range(3):
            try:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 401:
                    raise ProviderError(f"API Key 无效({self._provider})")
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"[{self.cfg['name']}] 速率限制, {wait}s后重试")
                    time.sleep(wait)
                    continue
                raise ProviderError(f"API {resp.status_code}: {resp.text[:200]}")
            except ProviderError:
                raise
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError(f"网络错误: {e}")
        
        raise ProviderError("重试耗尽")


# ── 委托管理器（单例） ─────────────────────────────────────────

def _get_sub_client():
    """复用 provider 的共享 HTTP 客户端"""
    from .provider import get_shared_client
    return get_shared_client()


class DelegateManager:
    """管理所有子智能体的生命周期"""
    
    def __init__(self):
        SUB_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all()
    
    def _load_all(self):
        """从磁盘加载所有已保存的子智能体配置"""
        self._agents: Dict[str, dict] = {}
        for f in SUB_AGENTS_DIR.glob("*.json"):
            try:
                cfg = json.loads(f.read_text())
                name = cfg.get("name", f.stem)
                self._agents[name] = cfg
            except Exception:
                pass
    
    def spawn(self, name: str, role: str = "通用助手",
              provider: str = None, model: str = None,
              api_key: str = "", base_url: str = "",
              tools: List[str] = None,
              system_prompt: str = "") -> dict:
        main_cfg = get_config()
        provider = provider or main_cfg.get("model", {}).get("provider", "deepseek")
        model = model or main_cfg.get("model", {}).get("name", "deepseek-v4-flash")
        
        if not api_key:
            api_key = main_cfg.get("model", {}).get("api_key", "")
        
        if not base_url:
            avail = main_cfg.get("models_available", {})
            base_url = avail.get(provider, {}).get(model, {}).get(
                "base_url", "https://api.deepseek.com/v1")
        
        if not system_prompt:
            system_prompt = _build_system_prompt(name, role)
        
        cfg = {
            "name": name,
            "role": role,
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "tools": tools,
            "system_prompt": system_prompt,
            "max_tool_calls": 10,
            "created_at": time.time(),
        }
        
        self._agents[name] = cfg
        self._save(name, cfg)
        
        return {
            "status": "spawned",
            "name": name,
            "role": role,
            "provider": provider,
            "model": model,
            "has_api_key": bool(api_key),
        }
    
    def delegate(self, agent_name: str, task: str) -> str:
        """委托任务给子智能体。支持按名称或角色匹配。"""
        # 1. 精确名称匹配
        if agent_name in self._agents:
            return self._run_delegate(agent_name, task)
        
        # 2. 按角色模糊匹配
        matches = []
        for name, cfg in self._agents.items():
            role = cfg.get("role", "")
            if agent_name in name or agent_name in role or name in agent_name or role in agent_name:
                matches.append(name)
        
        if len(matches) == 1:
            return self._run_delegate(matches[0], task)
        
        if len(matches) > 1:
            return (f"找到多个匹配的子智能体: {matches}。请指定确切名称。")
        
        # 3. 只有一个子智能体时自动匹配
        if len(self._agents) == 1:
            only_name = list(self._agents.keys())[0]
            return self._run_delegate(only_name, task)
        
        return f"错误: 子智能体 '{agent_name}' 不存在。可用: {self.list_names()}"
    
    def _run_delegate(self, agent_name: str, task: str) -> str:
        """内部：执行委托"""
        cfg = self._agents[agent_name]
        
        if not cfg.get("api_key"):
            return (f"错误: 子智能体 '{agent_name}' 缺少 API Key。\n"
                    f"请先用 spawn_agent 重新创建并指定 api_key。")
        
        logger.info(f"委派任务给 [{agent_name}]({cfg['provider']}/{cfg['model']}): "
                    f"{task[:80]}...")
        
        session = SubAgentSession(cfg)
        start = time.time()
        result = session.run(task)
        elapsed = time.time() - start
        
        return (f"── [{agent_name}]({cfg['provider']}/{cfg['model']}) "
                f"· {elapsed:.1f}s ──\n{result}")
    
    def kill(self, name: str) -> dict:
        if name not in self._agents:
            return {"status": "not_found", "name": name}
        
        del self._agents[name]
        cfg_file = SUB_AGENTS_DIR / f"{name}.json"
        if cfg_file.exists():
            cfg_file.unlink()
        
        return {"status": "killed", "name": name}
    
    def list_agents(self) -> List[dict]:
        return [
            {
                "name": c["name"],
                "role": c["role"],
                "provider": c["provider"],
                "model": c["model"],
                "has_key": bool(c.get("api_key")),
            }
            for c in self._agents.values()
        ]
    
    def list_names(self) -> List[str]:
        return list(self._agents.keys())
    
    def get_agent(self, name: str) -> Optional[dict]:
        return self._agents.get(name)
    
    def _save(self, name: str, cfg: dict):
        cfg_file = SUB_AGENTS_DIR / f"{name}.json"
        safe = dict(cfg)
        cfg_file.write_text(json.dumps(safe, ensure_ascii=False, indent=2))


# ── 全局单例 ──────────────────────────────────────────────────

_manager: Optional[DelegateManager] = None

def get_manager() -> DelegateManager:
    global _manager
    if _manager is None:
        _manager = DelegateManager()
    return _manager


# ── 工具执行函数 ────────────────────────────────────────────

def _spawn_agent(name: str, role: str = "通用助手",
                provider: str = "", model: str = "",
                api_key: str = "") -> str:
    mgr = get_manager()
    result = mgr.spawn(
        name=name, role=role,
        provider=provider or None,
        model=model or None,
        api_key=api_key,
    )
    if result["status"] == "spawned":
        key_note = "✓ 已配置独立Key" if result["has_api_key"] else "⚠ 继承主Key"
        return (f"✅ 子智能体 '{name}' 已创建\n"
                f"   角色: {result['role']}\n"
                f"   模型: {result['provider']}/{result['model']}\n"
                f"   API: {key_note}")
    return json.dumps(result, ensure_ascii=False)


def _list_agents() -> str:
    mgr = get_manager()
    agents = mgr.list_agents()
    if not agents:
        return "暂无子智能体。使用 spawn_agent 创建。"
    lines = [f"🤖 子智能体 ({len(agents)}个):"]
    for a in agents:
        key_mark = "🔑" if a["has_key"] else "⚠️"
        lines.append(f"  {key_mark} {a['name']} — {a['role']} ({a['provider']}/{a['model']})")
    return "\n".join(lines)


def _delegate_to(agent_name: str, task: str) -> str:
    mgr = get_manager()
    return mgr.delegate(agent_name, task)


def _kill_agent(name: str) -> str:
    mgr = get_manager()
    result = mgr.kill(name)
    if result["status"] == "killed":
        return f"🗑️ 子智能体 '{name}' 已删除"
    return f"⚠️ 子智能体 '{name}' 不存在"


# ── 工具注册（模块加载时自动执行） ──────────────────────────

def _register_delegate_tools():
    register(
        name="spawn_agent",
        description="创建一个命名的子智能体，可配置独立身份和模型。"
                    "用户需要先创建子智能体，再用 delegate_to 给它派任务。\n"
                    "参数：name(名称)、role(角色身份)、"
                    "provider(可选)、model(可选)、api_key(可选，不填则继承主配置)。\n\n"
                    "### 常用角色身份及其适用范围（供用户选择）\n"
                    "• 架构师 — 系统设计、技术选型、模块划分、接口定义\n"
                    "• 前端开发 — 页面组件、样式布局、交互逻辑、UI实现\n"
                    "• 后端开发 — API接口、数据库设计、服务端逻辑、中间件\n"
                    "• 代码审查 — 代码质量检查、Bug查找、性能分析、重构建议\n"
                    "• 安全审计 — 安全漏洞扫描、权限检查、注入防护、加密方案\n"
                    "• 测试工程师 — 单元测试、集成测试、测试用例编写、自动化测试\n"
                    "• 文档撰写 — API文档、README、技术说明、用户手册\n"
                    "• 数据分析 — 数据处理、统计分析、可视化、报表生成\n"
                    "• DevOps — 部署配置、CI/CD流水线、容器化、监控告警\n"
                    "• 通用助手 — 日常问答、信息查询、通用任务处理\n\n"
                    "用户说\"创建子智能体\"但未指定角色时，列出上述选项让用户选择。"
                    "角色身份由用户自由定义，以上仅为建议。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "子智能体名称，如'托尼'、'大卫'"},
                "role": {
                    "type": "string",
                    "description": "子智能体角色身份（如：架构师、前端开发、后端开发、代码审查、安全审计、文档撰写、测试工程师等）。用户自由定义。",
                    "default": "通用助手",
                },
                "provider": {
                    "type": "string",
                    "description": "LLM提供商（deepseek/openai/openrouter/zhipu/moonshot/groq），默认继承主配置",
                    "default": "",
                },
                "model": {
                    "type": "string",
                    "description": "模型名，默认继承主配置",
                    "default": "",
                },
                "api_key": {
                    "type": "string",
                    "description": "独立的API Key。不填则继承主配置的Key",
                    "default": "",
                },
            },
            "required": ["name"],
        },
        execute=_spawn_agent,
    )

    register(
        name="list_agents",
        description="列出所有已创建的子智能体及其配置信息",
        parameters={"type": "object", "properties": {}, "required": []},
        execute=_list_agents,
    )

    register(
        name="delegate_to",
        description="将任务委托给指定子智能体执行。子智能体独立运行自己的工具循环，"
                    "完成后返回结果。必须先用 spawn_agent 创建子智能体。\n"
                    "参数：agent_name(目标子智能体名称)、task(要执行的任务描述)。",
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "目标子智能体名称"},
                "task": {"type": "string", "description": "要委托的任务描述"},
            },
            "required": ["agent_name", "task"],
        },
        execute=_delegate_to,
    )

    register(
        name="kill_agent",
        description="删除一个子智能体及其配置",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "要删除的子智能体名称"},
            },
            "required": ["name"],
        },
        execute=_kill_agent,
    )


# 模块加载时自动注册
_register_delegate_tools()
