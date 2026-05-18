<div align="center">
  <h1>🦋 Eva Agent</h1>
  <p>你的第一个 AI 智能助手 — 为家人和朋友设计</p>
  <p><strong>Your first AI assistant — designed for family and friends</strong></p>
  <br>
</div>

---

## 🇨🇳 中文

### 这是什么

Eva Agent 是一个**开箱即用的桌面端 AI 助手**。下载 → 解压 → 双击启动，就能跟 AI 聊天、写代码、查资料。

专门为**不熟悉 AI 工具的普通人**设计。不需要懂命令行，不需要配环境，双击就能用。

### 快速开始

1. [注册 DeepSeek](https://platform.deepseek.com) 获取 API Key
2. 下载 [最新版 ZIP](https://lnpiao.cn/eva/)
3. 解压，双击 `启动.sh`（Linux）或 `安装启动.bat`（Windows）
4. 粘贴 Key，开始使用

### 功能

| 功能 | 说明 |
|------|------|
| 💬 智能对话 | 聊天、写文章、解数学题 |
| 🔧 工具调用 | 读文件、写代码、执行命令、搜索网页 |
| 🧠 记忆宫殿 | 自动记住对话历史，越用越聪明 |
| 🏆 熟练度 | 使用越多，解锁越多能力 |
| 🤖 子智能体 | 创建分工助手（架构师、程序员等） |
| 🎨 双模式 UI | 精简模式 / 三栏详细模式 |

### 截图

> 待添加

### 技术栈

- Python 3.10+
- FastAPI + Uvicorn（后端）
- 纯 HTML/CSS/JS（前端，单文件）

### 项目结构

```
eva-agent/
├── run.py                     # 启动入口
├── 启动.sh / 安装启动.bat      # 一键启动脚本
├── queen_bee/
│   ├── api_server.py          # API 服务
│   ├── agent.py               # Agent 主循环
│   ├── provider.py            # LLM 调用
│   ├── tool_registry.py       # 工具注册表
│   ├── palace.py              # 记忆宫殿
│   ├── semantic.py            # 语义搜索
│   ├── mastery.py             # 熟练度系统
│   ├── config.py              # 配置管理
│   ├── delegate.py            # 子智能体
│   ├── security.py            # 安全守卫
│   └── desktop/
│       └── dashboard.html     # 前端界面
└── requirements.txt
```

### 🤝 贡献

欢迎提 Issue 和 PR。

---

## 🇬🇧 English

### What is this

Eva Agent is a **ready-to-use desktop AI assistant**. Download → extract → double-click to start. Chat, code, search — all out of the box.

Designed for **people who aren't tech-savvy**. No terminal commands, no environment setup, just double-click and go.

### Quick Start

1. [Register at DeepSeek](https://platform.deepseek.com) and get an API Key
2. Download the [latest ZIP](https://lnpiao.cn/eva/)
3. Extract and double-click `启动.sh` (Linux/macOS) or `安装启动.bat` (Windows)
4. Paste your key and start chatting

### Features

| Feature | Description |
|---------|-------------|
| 💬 Chat | Talk, write, solve problems |
| 🔧 Tools | Read files, write code, run commands, search web |
| 🧠 Memory | Auto-remembers conversations, gets smarter over time |
| 🏆 Mastery | Level up as you use it |
| 🤖 Sub-agents | Create specialized assistants |
| 🎨 Dual UI | Minimal mode / Three-column detailed mode |

### Stack

- Python 3.10+ / FastAPI / Single-file HTML/CSS/JS

---

<div align="center">
  <p>🦋 Qianye Lab · 千叶实验室</p>
  <p>Made with ❤️ for everyone</p>
</div>
