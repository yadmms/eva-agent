# Eva Agent v0.11.5 开发文档

## 项目结构

```
eva-agent/
├── run.py                       # 启动入口
├── start_windows.bat            # Windows 启动
├── start_linux.sh               # Linux 启动
├── start_windows.ps1            # PowerShell 启动
├── start_windows.vbs            # 静默启动器
├── requirements.txt             # Python 依赖
├── queen_bee/                   # Python 后端
│   ├── api_server.py            # FastAPI 服务 (473行)
│   ├── agent.py                 # LLM 对话循环
│   ├── provider.py              # LLM 调用
│   ├── config.py                # 配置管理
│   ├── tool_registry.py         # 工具注册表
│   ├── palace.py                # 记忆宫殿
│   ├── semantic.py              # 语义搜索
│   ├── mastery.py               # 熟练度系统
│   ├── delegate.py              # 子智能体
│   ├── crypto.py                # 密钥加密
│   ├── models.py                # Pydantic 模型
│   └── tools/                   # 内置工具
├── desktop-ui/                  # React 桌面端
│   ├── src/
│   │   ├── App.tsx              # 主界面
│   │   ├── components/ui/       # shadcn/ui 组件
│   │   └── lib/api.ts           # 后端 API 封装
│   ├── src-tauri/               # Tauri 打包配置
│   └── package.json
└── tests/                       # 测试
```

## 启动方式

### 开发模式（浏览器）
1. 启动后端：`python3 run.py`
2. 启动前端：`cd desktop-ui && npm run dev`
3. 浏览器打开 `http://localhost:1420`

### 生产模式（Python 服务 React 构建）
1. 构建前端：`cd desktop-ui && npm run build`
2. 启动后端：`python3 run.py`
3. 浏览器打开 `http://localhost:19198`

### 桌面端（Tauri）
1. 构建 + 打包：`cd desktop-ui && npm run tauri:build`
2. 安装：`sudo dpkg -i src-tauri/target/release/bundle/deb/eva-agent_*.deb`
3. 应用菜单搜索 "eva-agent"

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | 对话（body: {message}） |
| `/status` | GET | 系统状态 |
| `/models` | GET | 模型列表 |
| `/model/switch` | POST | 切换模型 |
| `/config` | GET | 配置信息 |
| `/config/model` | POST | 添加模型 |
| `/config/model/delete` | POST | 删除模型 |
| `/config/set` | POST | 保存配置 |
| `/agents` | GET | 子智能体列表 |
| `/mastery` | GET | 熟练度 |
| `/api/memories` | GET | 记忆列表 |
| `/api/tools` | GET | 工具列表 |
| `/api/files` | GET | 文件列表 |
| `/api/files/read` | GET | 读取文件 |
| `/api/dirs` | GET | 目录列表 |
| `/api/sessions` | GET/POST | 会话管理 |
| `/api/version/check` | GET | 版本检查 |

## 主要依赖

- Python: FastAPI, uvicorn, httpx, pyyaml, psutil
- Node: React, Tailwind CSS, shadcn/ui, Lucide, Tauri

## 版本历史

- v0.11.5 — 重构：React 前端替代旧 HTML，清理死代码
- v0.11.4 — Tauri 桌面端打包
- v0.11.3 — 语义搜索 + 记忆宫殿 + 熟练度系统
