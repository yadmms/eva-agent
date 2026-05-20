// 和 Python 后端同源时用相对路径，否则用绝对路径
const API_BASE = window.location.port === "1420" ? "" : "";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function chat(message: string): Promise<string> {
  const data = await api<{ reply: string }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data.reply;
}

export async function getStatus() {
  return api<{ cpu_percent: number; memory_percent: number; model: string; version: string }>("/status");
}

export async function getModels(): Promise<{ provider: string; name: string; label: string }[]> {
  return api("/models");
}

export async function switchModel(provider: string, name: string) {
  return api("/model/switch", { method: "POST", body: JSON.stringify({ provider, name }) });
}

export async function getConfig() {
  return api<{ current: { provider: string; name: string }; models_available: Record<string, Record<string, { base_url: string }>>; api_keys: Record<string, string> }>("/config");
}

export async function addModel(provider: string, name: string, apiKey?: string, baseUrl?: string) {
  return api("/config/model", {
    method: "POST",
    body: JSON.stringify({ provider, name, api_key: apiKey, base_url: baseUrl }),
  });
}
