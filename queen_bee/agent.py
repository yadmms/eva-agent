"""Agent主循环 - 接收指令→调用LLM→解析tool calls→执行→返回"""
import json
import traceback
from typing import List, Dict, Optional
from .provider import chat, ProviderError
from .tool_registry import get_schemas, execute as execute_tool
from .config import get as get_config
from .palace import get_palace

class Agent:
    def __init__(self):
        self.config = get_config()
        self.history: List[Dict] = []
        self.palace = get_palace()
        self.ctx = self.palace._load_map()
    
    MAX_HISTORY = 60

    def run(self, user_message: str) -> str:
        """执行用户指令，返回最终响应"""
        msg_title = user_message[:80] + ("…" if len(user_message) > 80 else "")
        from .semantic import expand_tags, detect_emotion, EMOTION_PROMPTS
        tags = expand_tags(user_message)[:12] + ["conversation", "user"]

        # 情绪检测 — 将情绪标签加入记忆
        emotion = detect_emotion(user_message)
        if emotion:
            tags.append(f"emotion:{emotion}")

        self.palace.remember("task", msg_title, user_message[:1000], tags=tags)
        self.history.append({"role": "user", "content": user_message})
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]
        
        messages = self._build_messages(user_message)
        tools_schema = get_schemas()
        
        max_calls = self.config["agent"]["max_tool_calls"]
        call_count = 0
        
        while call_count < max_calls:
            call_count += 1
            
            try:
                response = chat(messages, tools_schema if tools_schema else None)
            except ProviderError as e:
                reply = f"模型调用失败: {e}"
                self._save_context(user_message, reply)
                return reply
            
            choice = response["choices"][0]
            msg = choice["message"]
            reasoning = msg.get("reasoning_content") or ""
            
            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                reply = msg.get("content", "")
                stored = {"role": "assistant", "content": reply}
                self.history.append(stored)
                reply_title = reply[:80] + ("…" if len(reply) > 80 else "")
                from .semantic import expand_tags
                reply_tags = expand_tags(reply)[:12] + ["conversation", "assistant"]
                self.palace.remember("reply", reply_title, reply[:1000], tags=reply_tags)
                self._save_context(user_message, reply)
                return reply
            
            stored = {"role": "assistant", "content": msg.get("content", "") or None}
            if reasoning:
                stored["reasoning_content"] = reasoning
            stored["tool_calls"] = msg["tool_calls"]
            self.history.append(stored)
            messages.append(stored)
            
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    args = json.loads(func["arguments"])
                except json.JSONDecodeError:
                    args = {}
                
                result = execute_tool(tool_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        
        messages.append({"role": "user", "content": "工具调用已达上限，请根据已有结果直接总结回答，不要再调用任何工具。"})
        try:
            response = chat(messages, tools=None)
            reply = response["choices"][0]["message"].get("content", "已达最大工具调用次数，请简化请求后重试。")
        except Exception:
            reply = "已达最大工具调用次数，请简化请求后重试。"
        self.history.append({"role": "assistant", "content": reply})
        self._save_context(user_message, reply)
        return reply
    
    def _build_messages(self, user_message: str = "") -> List[Dict]:
        base_prompt = self.config["agent"]["system_prompt"]
        from .semantic import COMMON_MISUNDERSTANDINGS
        for phrase, guide in COMMON_MISUNDERSTANDINGS.items():
            if phrase in user_message:
                base_prompt += f"\n\n用户说「{phrase}」，你的回复思路：{guide}"
                break
        parts = [base_prompt]

        # 1. 注入近期记忆（让 LLM 知道之前聊过什么）
        recent = self.palace.recall("")[:6]
        if recent:
            lines = ["\n## 近期对话记忆"]
            for r in recent:
                lines.append(f"- {r['title']}")
            parts.append("\n".join(lines))

        # 2. 锚点
        anchor = self._load_anchors()
        if anchor:
            parts.append(anchor)

        # 3. 按需检索
        tide = self.palace.context_for(user_message) if user_message else ""
        if tide:
            parts.append(tide)

        system_prompt = "\n\n".join(parts)

        from .semantic import detect_emotion, EMOTION_PROMPTS
        em = detect_emotion(user_message)
        if em:
            system_prompt += "\n\n" + EMOTION_PROMPTS.get(em, "")

        messages = [{"role": "system", "content": system_prompt}]
        
        # 只保留 user 和纯文本 assistant 消息，过滤 tool_calls 残留
        clean = []
        for h in self.history[-30:]:
            if h["role"] == "user":
                clean.append(h)
            elif h["role"] == "assistant" and "tool_calls" not in h:
                clean.append(h)
        messages.extend(clean)
        return messages
    
    def _save_context(self, user_msg: str, reply: str):
        """对话结束后自动保存上下文"""
        self.palace.context_snapshot({
            "project": "eva-agent",
            "version": "0.11.3",
            "last_task": user_msg[:200],
            "last_summary": reply[:300],
            "conversation_count": self.ctx.get("conversation_count", 0) + 1,
            "current_state": "就绪"
        })

    def _load_anchors(self) -> str:
        """加载潮汐记忆锚点 — 锚点文件始终注入 system prompt（带 st_mtime 缓存）"""
        from .palace import _load_anchors_cached
        anchor_path = self.palace.base_dir / "anchors" / "identity.md"
        content = _load_anchors_cached(anchor_path)
        if content:
            return f"--- 锚点（常驻基石） ---\n{content}"
        return ""

    def reset(self):
        """清空对话历史"""
        self.history = []
        self.palace.context_snapshot(self.ctx)

    @classmethod
    def with_avatar(cls, avatar_name: str):
        """Create an Agent configured for a specific avatar."""
        from .avatars import get_avatar
        cfg = get_avatar(avatar_name)
        if not cfg:
            return None
        agent = cls()
        agent.config = dict(agent.config)
        agent.config["agent"] = dict(agent.config.get("agent", {}))
        agent.config["agent"]["system_prompt"] = cfg["system_prompt"]
        agent.config["agent"]["max_tool_calls"] = min(agent.config["agent"]["max_tool_calls"], 10)
        agent._avatar = avatar_name
        return agent

def create_agent() -> Agent:
    """创建Agent实例 — 自动注册工具和子智能体委托"""
    from .tool_registry import _auto_register
    _auto_register()
    from .delegate import _register_delegate_tools
    _register_delegate_tools()
    return Agent()
