"""P2 回归:模型无关路由层。路由解析 + 别名 + 回退链 + 本地 endpoint 实调。"""
import sys, os, threading, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from model.router import ModelRouter, PROVIDERS, ALIASES

def test_routing_and_aliases():
    r = ModelRouter()
    for spec in ["anthropic:claude-haiku-4-5","openai:gpt-5","gemini:gemini-2.0","deepseek:deepseek-chat",
                 "kimi:moonshot-v1-8k","qwen:qwen-max","ollama:qwen2.5","local:m","vllm:m"]:
        fn, m = r._route(spec)                      # 不抛错即路由成功
    assert ALIASES["kimi"] == "moonshot" and ALIASES["qwen"] == "dashscope"

def test_fallback_chain():
    # 主模型指向死端口 -> 回退到本地 mock
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n=int(self.headers.get('content-length',0)); self.rfile.read(n)
            self.send_response(200); self.send_header('content-type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"choices":[{"message":{"content":"0.7"}}]}).encode())
        def log_message(self,*a): pass
    srv = HTTPServer(('127.0.0.1',8918),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
    os.environ["LOCAL_LLM_BASE"]="http://127.0.0.1:8918/v1"
    r = ModelRouter(default="openai_compat:dead", fallbacks=["local:mock"])
    # 主 openai_compat 指向 dead 端口... 实际上 default 也用 LOCAL_LLM_BASE。改测:主用不可达 provider
    r = ModelRouter(default="ollama:none", fallbacks=["local:mock"])
    os.environ["OLLAMA_HOST"]="http://127.0.0.1:1"     # 不可达
    res = r.complete([{"role":"user","content":"hi"}])
    srv.shutdown()
    assert res["ok"] and res["model_used"]=="local:mock", res   # 回退成功
    assert res["text"]=="0.7"

if __name__ == "__main__":
    test_routing_and_aliases(); print("✅ routing + aliases")
    test_fallback_chain(); print("✅ fallback chain (主不可达 -> 本地回退)")
    print("\nP2 model router 测试 PASSED")
