import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, Select } from "@/components/ui/card";
import { api, getConfig, addModel, getModels } from "@/lib/api";
import {
  Send, Settings, Plus, MessageSquare, GitBranch, Brain, Terminal, FileText, Zap, Logs, ChevronLeft, ChevronRight, Server, Cpu
} from "lucide-react";

type Message = { role: "user" | "assistant" | "system"; content: string };

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState("");
  const [models, setModels] = useState<{ provider: string; name: string }[]>([]);
  const [configOpen, setConfigOpen] = useState(false);
  const [sidebar, setSidebar] = useState(true);
  const [status, setStatus] = useState({ cpu: 0, mem: 0 });
  const [cf, setCf] = useState<{ provider: string; name: string; apiKeys: Record<string, string> }>({ provider: "", name: "", apiKeys: {} });
  const [newKey, setNewKey] = useState("");
  const [cfgModel, setCfgModel] = useState("");
  const [activePanel, setActivePanel] = useState("chat");
  const [memories, setMemories] = useState<string[]>([]);
  const [noKey, setNoKey] = useState(false);
  const chatsEnd = useRef<HTMLDivElement>(null);

  useEffect(() => { chatsEnd.current?.scrollIntoView(); }, [messages]);

  useEffect(() => {
    getConfig().then(c => {
      const hasKeys = Object.keys(c.api_keys).length > 0;
      setCf({ provider: c.current.provider, name: c.current.name, apiKeys: c.api_keys });
      setCfgModel(c.current.provider + "/" + c.current.name);
      if (!hasKeys) {
        setNoKey(true); setConfigOpen(true); setCfgModel("deepseek-v4-flash");
        setCf(p => ({ ...p, provider: "deepseek", name: "deepseek-v4-flash" }));
        setMessages([{ role: "assistant", content: "👋 欢迎使用 Eva Agent！\n\n首次使用需要先配一个 AI 大脑（API Key），三步搞定：\n\n① 打开浏览器，访问 platform.deepseek.com\n   用手机号注册账号（1 分钟）\n② 点顶部「API Keys」→「创建 API Key」\n   复制那一长串以 sk- 开头的字符\n③ 点右下角 ⚙️ 齿轮图标\n   粘贴 Key，点「添加模型」\n\n💡 需要充值 10 元才能用，一次问答大约 1 分钱\n💡 不想充值也可以用智谱 AI（有免费额度）\n\n配置好之后跟我说「你好」开始。" }]);
      } else {
        setMessages([{ role: "assistant", content: "你好，我是 Eva。有什么可以帮你的？" }]);
      }
    }).catch(() => {
      setNoKey(true); setConfigOpen(true);
      setMessages([{ role: "assistant", content: "⚠️ 连接后端失败，请确认 Python 服务是否在运行（cd eva-agent && python3 run.py）。\n\n首次使用还需配置 API Key：\n① 打开 platform.deepseek.com 注册\n② 创建 API Key 并复制\n③ 点击下方 ⚙️ 粘贴 Key" }]);
    });
    getModels().then(m => setModels(m)).catch(() => {});
    const t = setInterval(() => {
      api<{ cpu_percent: number; memory_percent: number }>("/status")
        .then(s => setStatus({ cpu: s.cpu_percent, mem: s.memory_percent })).catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const send = async () => {
    if (!input.trim() || loading) return;
    const msg = input;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const data = await api<{ reply: string }>("/chat", {
        method: "POST", body: JSON.stringify({ message: msg }),
      });
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: "system", content: "错误: " + e.message }]);
    }
    setLoading(false);
  };

  const [keyStatus, setKeyStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");

  const handleAddModel = async () => {
    if (!cf.provider || !cfgModel) return;
    try {
      await addModel(cf.provider, cfgModel, newKey || undefined);
    } catch {
      setMessages(prev => [...prev, { role: "system", content: "❌ 保存失败，请重试" }]);
      return;
    }
    setNewKey("");
    setKeyStatus("idle");
    const c = await getConfig();
    setCf({ provider: c.current.provider, name: c.current.name, apiKeys: c.api_keys });
    setMessages(prev => [...prev, { role: "system", content: "✅ 配置已保存，现在可以开始对话了！" }]);
    setConfigOpen(false);
  };

  const testKey = async () => {
    if (!newKey) return;
    setKeyStatus("testing");
    try {
      const r = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "hi" }),
      });
      setKeyStatus(r.status === 200 ? "ok" : "fail");
    } catch { setKeyStatus("fail"); }
  };

  return (
    <div className="flex h-screen w-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      {sidebar && (
        <div className="w-14 bg-card border-r border-border flex flex-col items-center py-3 gap-3 shrink-0">
          {[
            { icon: MessageSquare, label: "对话", id: "chat", action: () => setActivePanel("chat") },
            { icon: GitBranch, label: "任务", id: "tasks", action: () => { setActivePanel("tasks"); setMessages(prev => [...prev, { role: "system", content: "📋 任务面板 — 暂无活跃任务" }]); } },
            { icon: Brain, label: "模型", id: "models", action: () => setConfigOpen(true) },
            { icon: Zap, label: "频道", id: "channels", action: () => { setActivePanel("channels"); setMessages(prev => [...prev, { role: "system", content: "📡 频道列表：开发 / 办公助理 / 学习" }]); } },
            { icon: FileText, label: "技能", id: "skills", action: () => { setActivePanel("skills"); setMessages(prev => [...prev, { role: "system", content: "⚡ 技能 — 暂无已保存的技能" }]); } },
            { icon: Terminal, label: "记忆", id: "memory", action: () => { api("/api/memories").then(d => { const items = ((d as any).memories || []).slice(0, 8).map((m: any) => "📌 " + (m.title || "")).join("\n"); setMessages(prev => [...prev, { role: "system", content: "🧠 最近记忆：\n" + (items || "暂无记忆") }]); }).catch(() => {}); } },
            { icon: Logs, label: "日志", id: "logs", action: () => { setActivePanel("logs"); setMessages(prev => [...prev, { role: "system", content: "📝 日志面板" }]); } },
          ].map(({ icon: Icon, label, id, action }) => (
            <button key={label} onClick={action} className={`group relative w-9 h-9 flex items-center justify-center rounded-lg transition-colors ${activePanel === id ? "bg-accent/15 text-accent" : "text-muted-foreground hover:bg-accent/10 hover:text-accent"}`}>
              <Icon size={18} />
              <span className="absolute left-full ml-2 px-2 py-1 bg-card border border-border text-foreground text-xs rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">{label}</span>
            </button>
          ))}
          <div className="flex-1" />
          <button className="w-9 h-9 flex items-center justify-center rounded-lg text-muted-foreground hover:bg-accent/10 hover:text-accent" title="设置" onClick={() => setConfigOpen(true)}>
            <Settings size={18} />
          </button>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-12 border-b border-border flex items-center px-4 gap-3 shrink-0 bg-card/50">
          <button onClick={() => setSidebar(!sidebar)} className="text-muted-foreground hover:text-foreground">
            {sidebar ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
          <div className="flex items-center gap-2 text-xs text-muted-foreground ml-auto">
            <Cpu size={14} /> {status.cpu.toFixed(0)}%
            <Server size={14} className="ml-2" /> {status.mem.toFixed(0)}%
            <span className="ml-2 text-accent">{model || "deepseek/deepseek-v4-flash"}</span>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user" ? "bg-accent text-accent-foreground" :
                m.role === "system" ? "bg-muted/50 text-muted-foreground italic" :
                "bg-card border border-border"
              }`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-card border border-border rounded-xl px-4 py-2.5 text-sm text-muted-foreground">
                <span className="animate-pulse">思考中...</span>
              </div>
            </div>
          )}
          <div ref={chatsEnd} />
        </div>

        {/* Input */}
        <div className="border-t border-border p-4 bg-card/30">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <Textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="输入消息… (Shift+Enter 换行)"
              className="min-h-[44px] max-h-[120px]"
              rows={1}
            />
            <Button onClick={send} disabled={loading} size="lg" className="px-3">
              <Send size={18} />
            </Button>
          </div>
        </div>
      </div>

      {/* Config Dialog */}
      {configOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setConfigOpen(false)}>
          <Card className="w-[420px] p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-semibold">⚙️ 模型配置</h2>
            <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
              当前：<span className="text-accent font-medium">{cfgModel || "--"}</span>
            </div>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">快速添加：</p>
              <div className="flex gap-2 flex-wrap">
                {[
                  { p: "deepseek", m: "deepseek-v4-flash", u: "https://api.deepseek.com", l: "DeepSeek V4" },
                  { p: "zhipu", m: "glm-4-flash", u: "https://open.bigmodel.cn/api/paas/v4", l: "智谱 GLM" },
                  { p: "siliconflow", m: "deepseek-ai/DeepSeek-V3", u: "https://api.siliconflow.cn/v1", l: "硅基" },
                ].map(item => (
                  <Button key={item.l} variant="outline" size="sm" onClick={() => { setCf(p => ({ ...p, provider: item.p, name: item.m })); setCfgModel(item.m); }}>
                    {item.l}
                  </Button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="提供商" value={cf.provider} onChange={e => setCf(p => ({ ...p, provider: e.target.value }))} />
              <Input placeholder="模型名" value={cfgModel} onChange={e => setCfgModel(e.target.value)} />
              <div className="col-span-2 flex gap-2">
                <Input placeholder="API Key（sk-...）" type="password" value={newKey} onChange={e => { setNewKey(e.target.value); setKeyStatus("idle"); }} className="flex-1" />
                <Button variant="outline" size="sm" onClick={testKey} disabled={!newKey || keyStatus === "testing"} className="shrink-0">
                  {keyStatus === "testing" ? "..." : keyStatus === "ok" ? "✅" : keyStatus === "fail" ? "❌" : "测试"}
                </Button>
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => setConfigOpen(false)} variant="ghost" className="flex-1">取消</Button>
              <Button onClick={handleAddModel} className="flex-1">确认</Button>
            </div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {Object.entries(cf.apiKeys).map(([prov, key]) => (
                <div key={prov} className="flex items-center justify-between text-xs bg-muted/30 rounded-md px-3 py-2">
                  <span>{prov}</span>
                  <span className="text-green-500">✓ 已配置</span>
                </div>
              ))}
            </div>
            <Button variant="ghost" className="w-full" onClick={() => setConfigOpen(false)}>关闭</Button>
          </Card>
        </div>
      )}
    </div>
  );
}
