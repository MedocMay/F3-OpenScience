"""云端多租户网关 — 在 gateway 基础上加:多租户隔离 + 每用户 BYOK 密管。
- 认证:token -> 租户/用户(TenantRegistry)
- 隔离:每租户独立 experience 库
- BYOK:每用户模型 key 加密存 KeyVault,run 时按用户解密注入(明文不落盘/不进日志)
- global:跨租户共享(仅脱敏模式)
"""
from __future__ import annotations
import os, sys, json, threading, queue, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
from orchestrator import Orchestrator
from cloud.tenancy import TenantRegistry
from cloud.vault import KeyVault
from cloud.sessions import get_sessions

ADMIN = os.environ.get("OPENSCI_ADMIN_TOKEN", "dev-admin")
DATA_ROOT = os.environ.get("OPENSCI_DATA_ROOT", "./data/tenants")
reg = TenantRegistry(os.path.join(DATA_ROOT, "_tenants.db"), data_root=DATA_ROOT)
_PROVIDER_ENV = {"anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY","deepseek":"DEEPSEEK_API_KEY",
                 "moonshot":"MOONSHOT_API_KEY","dashscope":"DASHSCOPE_API_KEY","gemini":"GEMINI_API_KEY"}
SESSIONS: dict = {}
_run_lock = threading.Lock()
_store = get_sessions()   # 会话元数据外置(Redis/内存)

class Sess:
    def __init__(self): self.events=queue.Queue(); self.waiters={}; self.result=None
    def ask(self,g): q=queue.Queue(); self.waiters[g]=q; self.events.put(("gate.request",{"gate_id":g})); d=q.get(); self.waiters.pop(g,None); return d
    def emit(self,s,t,d): self.events.put(("run.event",{"stage":s,"type":t,"data":d}))
    def resolve(self,g,d):
        q=self.waiters.get(g)
        if q: q.put(d); return True
        return False

def _run_bg(run_id, ctx, direction, autonomy):
    sess = SESSIONS[run_id]
    exp_db = reg.experience_db(ctx["tenant_id"])                 # 租户隔离:各自经验库
    vault = KeyVault(reg.vault_db(ctx["tenant_id"]))
    with _run_lock:                                             # 串行(MVP);env 注入需独占
        saved = {}
        try:
            # BYOK:把该用户的 key 从密管解密注入 env(sidecar 继承)
            for prov in vault.providers(ctx["user_id"]):
                ev = _PROVIDER_ENV.get(prov)
                if ev:
                    saved[ev] = os.environ.get(ev)
                    os.environ[ev] = vault.get(ctx["user_id"], prov)
            orch = Orchestrator(sess.ask, sess.emit, db=exp_db)
            try: res = orch.run(direction, autonomy, ctx["user_id"])
            finally: orch.close()
            sess.result = res; sess.events.put(("result", res))
        except Exception as e:
            sess.events.put(("error", {"message": str(e)}))
        finally:
            for k, v in saved.items():                          # 还原 env,明文不驻留
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
            sess.events.put(("_end", {}))

class H(BaseHTTPRequestHandler):
    def _send(self,code,obj):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _body(self): n=int(self.headers.get("Content-Length",0)); return json.loads(self.rfile.read(n) or b"{}")
    def _ctx(self): return reg.resolve_header(self.headers.get("Authorization",""))

    def do_GET(self):
        if self.path=="/healthz": return self._send(200,{"ok":True,"service":"opensci-cloud-gateway"})
        ctx=self._ctx()
        if not ctx: return self._send(401,{"error":"unauthorized"})
        if self.path.startswith("/v1/runs/") and self.path.endswith("/events"):
            return self._sse(self.path.split("/")[3])
        if self.path=="/v1/keys":
            return self._send(200, {"providers": KeyVault(reg.vault_db(ctx["tenant_id"])).providers(ctx["user_id"])})
        self._send(404,{"error":"not found"})

    def do_POST(self):
        # 管理端:发 token(仅 admin)
        if self.path=="/admin/tenants":
            if self.headers.get("Authorization","")!=f"Bearer {ADMIN}": return self._send(403,{"error":"forbidden"})
            b=self._body(); tok=reg.issue(b["tenant_id"], b["user_id"])
            return self._send(201,{"token":tok,"tenant_id":b["tenant_id"],"user_id":b["user_id"]})
        ctx=self._ctx()
        if not ctx: return self._send(401,{"error":"unauthorized"})
        if self.path=="/v1/keys":                               # 存 BYOK
            b=self._body(); KeyVault(reg.vault_db(ctx["tenant_id"])).put(ctx["user_id"], b["provider"], b["api_key"])
            return self._send(201,{"ok":True,"provider":b["provider"]})
        if self.path=="/v1/runs":
            b=self._body(); rid="run-"+uuid.uuid4().hex[:8]; SESSIONS[rid]=Sess()
            _store.put(rid, {"tenant_id": ctx["tenant_id"], "user_id": ctx["user_id"]})
            threading.Thread(target=_run_bg, args=(rid, ctx, b.get("direction",""), int(b.get("autonomy",1))), daemon=True).start()
            return self._send(202,{"run_id":rid,"tenant":ctx["tenant_id"]})
        if self.path=="/v1/gates":
            b=self._body(); s=SESSIONS.get(b.get("run_id","")); ok=s.resolve(b.get("gate_id"),b.get("decision","approve")) if s else False
            return self._send(200 if ok else 404,{"ok":ok})
        self._send(404,{"error":"not found"})

    def _sse(self, rid):
        s=SESSIONS.get(rid)
        if not s: return self._send(404,{"error":"unknown run"})
        self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.end_headers()
        while True:
            k,d=s.events.get()
            if k=="_end": self.wfile.write(b"event: end\ndata: {}\n\n"); self.wfile.flush(); break
            pl=json.dumps({"kind":k, **({"data":d} if k!="run.event" else d)})
            self.wfile.write(f"event: {k}\ndata: {pl}\n\n".encode()); self.wfile.flush()
    def log_message(self,*a): pass

def main():
    port=int(os.environ.get("PORT","8080"))
    print(f"opensci-cloud-gateway on :{port}  (multi-tenant + BYOK)", flush=True)
    ThreadingHTTPServer(("0.0.0.0",port), H).serve_forever()
if __name__=="__main__": main()
