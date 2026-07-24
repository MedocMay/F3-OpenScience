# model/ — 模型无关路由层(provider-agnostic)

一个接口 `complete(messages, model)`,`model` 形如 `provider:name`,按前缀路由。CoE 相关性、Pipeline 生成都走它。

## 支持的 provider
| 前缀 | 服务 | key 环境变量 |
|---|---|---|
| `anthropic:` | Claude | `ANTHROPIC_API_KEY` |
| `openai:` | GPT | `OPENAI_API_KEY` |
| `gemini:` | Gemini | `GEMINI_API_KEY` |
| `deepseek:` | DeepSeek | `DEEPSEEK_API_KEY` |
| `kimi:` → moonshot | Kimi(月之暗面) | `MOONSHOT_API_KEY` |
| `qwen:` → dashscope | 通义千问 | `DASHSCOPE_API_KEY` |
| `ollama:` | 本地 Ollama | `OLLAMA_HOST`(默认 localhost:11434) |
| `local:` / `vllm:` → openai_compat | 任意 OpenAI-兼容(vLLM/LMStudio/自建) | `LOCAL_LLM_BASE`(+ 可选 `LOCAL_LLM_KEY`) |

## 用法
```python
from model.router import ModelRouter
r = ModelRouter(default="anthropic:claude-haiku-4-5-20251001", fallbacks=["deepseek:deepseek-chat", "ollama:qwen2.5"])
out = r.complete([{"role":"user","content":"hi"}], model="qwen:qwen-max")   # per-request 切换
# out = {ok, text, model_used, provider}
```

## 设计
- **BYOK**:各 provider key 从环境读;本地模型无需 key。
- **per-request 路由**:同一次运行可对不同阶段用不同模型。
- **回退链**:主模型不可达 → 依次尝试 fallbacks(照 ARC model fallback)。
- **本地优先可选**:把 default 设为 `ollama:` 或 `local:` 即全本地、数据不出域(对齐推理主权)。
- `ModelRouter.available()` 供 UI 展示当前可用 provider。
