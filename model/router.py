"""统一模型路由层(provider-agnostic)。
一个接口 complete(messages, model) -> text;按 model 前缀路由到对应 provider。
云:anthropic / openai / gemini / deepseek / moonshot(kimi) / dashscope(qwen)。
本地/自托管:ollama / 任意 OpenAI-compatible endpoint(openai_compat)。
BYOK:各 provider 的 key 从环境变量读;本地无需 key。per-request 切换 + 回退链。"""
from __future__ import annotations
import os, json, urllib.request, urllib.error

# ---------- provider 适配器:各自把 (messages, model) 变成一次 HTTP 调用,统一返回 text ----------
def _post(url, headers, body, timeout=40):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

def _anthropic(messages, model, key, temperature=None):
    r = _post("https://api.anthropic.com/v1/messages",
              {"x-api-key": key, "anthropic-version": "2023-06-01"},
              {"model": model, "max_tokens": 1024, "messages": messages,
               **({"temperature": temperature} if temperature is not None else {})})
    return "".join(b.get("text", "") for b in r.get("content", []))

def _openai_style(base, messages, model, key, temperature=None):
    """OpenAI 兼容(OpenAI / DeepSeek / Moonshot / DashScope-compat / 本地 vLLM 等共用)。"""
    hdr = {"authorization": f"Bearer {key}"} if key else {}
    r = _post(base.rstrip("/") + "/chat/completions", hdr,
              {"model": model, "messages": messages,
               **({"temperature": temperature} if temperature is not None else {})})
    return r["choices"][0]["message"]["content"]

def _gemini(messages, model, key):
    contents = [{"role": "user" if m["role"] != "assistant" else "model",
                 "parts": [{"text": m["content"]}]} for m in messages]
    r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
              {}, {"contents": contents})
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])

def _ollama(base, messages, model, key=None):
    r = _post(base.rstrip("/") + "/api/chat", {}, {"model": model, "messages": messages, "stream": False})
    return r["message"]["content"]

# ---------- provider 注册表:前缀 -> (endpoint 构造, key 环境变量) ----------
PROVIDERS = {
    "anthropic": lambda m, model, k, t=None: _anthropic(m, model, k or os.environ.get("ANTHROPIC_API_KEY", ""), t),
    "openai":    lambda m, model, k, t=None: _openai_style("https://api.openai.com/v1", m, model, k or os.environ.get("OPENAI_API_KEY", ""), t),
    "deepseek":  lambda m, model, k, t=None: _openai_style("https://api.deepseek.com/v1", m, model, k or os.environ.get("DEEPSEEK_API_KEY", ""), t),
    "moonshot":  lambda m, model, k, t=None: _openai_style("https://api.moonshot.cn/v1", m, model, k or os.environ.get("MOONSHOT_API_KEY", ""), t),   # Kimi
    "dashscope": lambda m, model, k, t=None: _openai_style("https://dashscope.aliyuncs.com/compatible-mode/v1", m, model, k or os.environ.get("DASHSCOPE_API_KEY", ""), t),  # Qwen
    "gemini":    lambda m, model, k, t=None: _gemini(m, model, k or os.environ.get("GEMINI_API_KEY", ""), t),
    "ollama":    lambda m, model, k, t=None: _ollama(os.environ.get("OLLAMA_HOST", "http://localhost:11434"), m, model),
    "openai_compat": lambda m, model, k, t=None: _openai_style(os.environ.get("LOCAL_LLM_BASE", "http://localhost:8000/v1"), m, model, k or os.environ.get("LOCAL_LLM_KEY", "")),
}

# 模型别名:kimi -> moonshot, qwen -> dashscope, local -> openai_compat
ALIASES = {"kimi": "moonshot", "qwen": "dashscope", "local": "openai_compat", "vllm": "openai_compat"}

class ModelRouter:
    """per-request 路由 + 回退链。model 形如 'anthropic:claude-haiku-4-5' / 'ollama:qwen2.5' / 'kimi:moonshot-v1-8k'。"""
    def __init__(self, default: str | None = None, fallbacks: list[str] | None = None):
        self.default = default or os.environ.get("OPENSCI_MODEL", "anthropic:claude-haiku-4-5-20251001")
        self.fallbacks = fallbacks or []

    def _route(self, spec: str):
        if ":" not in spec:
            raise ValueError(f"model spec 需 'provider:model',得到 {spec!r}")
        prov, model = spec.split(":", 1)
        prov = ALIASES.get(prov, prov)
        if prov not in PROVIDERS:
            raise ValueError(f"未知 provider: {prov};支持 {list(PROVIDERS)+list(ALIASES)}")
        return PROVIDERS[prov], model

    def complete(self, messages: list[dict], model: str | None = None, api_key: str | None = None,
                 temperature: float | None = None) -> dict:
        """返回 {text, model_used, provider, ok}。主模型失败 -> 回退链。"""
        chain = [model or self.default] + self.fallbacks
        last_err = None
        for spec in chain:
            try:
                fn, m = self._route(spec)
                text = fn(messages, m, api_key, temperature)
                return {"ok": True, "text": text, "model_used": spec, "provider": spec.split(":")[0]}
            except Exception as e:
                last_err = f"{spec}: {type(e).__name__}: {str(e)[:80]}"
                continue
        return {"ok": False, "text": "", "model_used": None, "error": last_err}

    @staticmethod
    def available() -> dict:
        """哪些 provider 当前有凭据/可达(用于 UI 展示与选择)。"""
        env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
               "moonshot": "MOONSHOT_API_KEY", "dashscope": "DASHSCOPE_API_KEY", "gemini": "GEMINI_API_KEY"}
        out = {p: bool(os.environ.get(v)) for p, v in env.items()}
        out["ollama"] = bool(os.environ.get("OLLAMA_HOST"))
        out["openai_compat"] = bool(os.environ.get("LOCAL_LLM_BASE"))
        return out
