"""Nova main brain router – analyses user intent and selects the right avatar."""

from __future__ import annotations

from typing import Optional


class NovaRouter:
    """Routes user messages to the appropriate avatar based on keywords."""

    def __init__(self) -> None:
        self._keywords: dict[str, list[str]] = {
            "smith": [
                "写", "创建", "实现", "编码", "开发", "新建", "生成",
                "create", "implement", "build", "code", "make",
            ],
            "reviewer": [
                "审查", "检查", "review", "评审", "检查代码",
                "code review", "看看这段", "有没有问题",
            ],
            "debugger": [
                "bug", "错误", "修复", "调试", "debug", "报错",
                "异常", "error", "fix", "崩溃",
            ],
            "architect": [
                "设计", "架构", "规划", "design", "architect",
                "方案", "怎么实现", "整体",
            ],
            "keeper": [
                "记得", "上次", "回忆", "历史", "之前",
                "memory", "搜索记忆",
            ],
        }

    def route(self, user_message: str) -> Optional[str]:
        """Route *user_message* to an avatar.

        Returns the avatar name (e.g. ``"smith"``) or ``None`` when the
        main brain should handle the message directly.
        """
        msg_lower = user_message.lower()

        # 1. Explicit @mention takes precedence.
        for name in ("smith", "reviewer", "debugger", "architect", "keeper"):
            if f"@{name}" in msg_lower:
                return name

        # 2. Keyword scoring.
        scores: dict[str, int] = {}
        for avatar, keywords in self._keywords.items():
            score = sum(1 for kw in keywords if kw in msg_lower)
            if score > 0:
                scores[avatar] = score

        if scores:
            return max(scores, key=scores.get)
        return None


router: NovaRouter = NovaRouter()
