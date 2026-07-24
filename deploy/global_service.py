"""global 记忆网络服务 — 把 GlobalMemory 暴露成 HTTP。混合/云端多用户的共享层。
只接收脱敏后的模式(脱敏门在 GlobalMemory 内),原始研究内容永不上行。零第三方依赖。

  POST /v1/global/promote   {lesson, contributor_fp, consent} -> {ok,status,distinct_contributors}
  POST /v1/global/query     {kinds} -> [lessons]
  POST /v1/global/status    {signature, contributor_fp} -> {..}
  POST /v1/global/revoke    {signature, contributor_fp} -> {ok}
  GET  /healthz
认证:Bearer OPENSCI_GLOBAL_TOKEN(未设=dev 放行)。
"""
import os, tempfile, sys, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from memory.global_store import GlobalMemory

TOKEN = os.environ.get("OPENSCI_GLOBAL_TOKEN")
DB = os.environ.get("OPENSCI_GLOBAL_DSN") or os.environ.get("OPENSCI_GLOBAL_DB") or os.path.join(tempfile.gettempdir(), "opensci_global.db")
G = GlobalMemory(DB)   # DSN=postgres:// 时走 Postgres
import threading; _lock = threading.Lock()

class H(BaseHTTPRequestHandler):
    def _auth(self): return (not TOKEN) or self.headers.get("Authorization","")==f"Bearer {TOKEN}"
    def _send(self, code, obj):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _body(self):
        n=int(self.headers.get("Content-Length",0)); return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        if self.path=="/healthz": return self._send(200,{"ok":True,"service":"f3-global"})
        self._send(404,{"error":"not found"})
    def do_POST(self):
        if not self._auth(): return self._send(401,{"error":"unauthorized"})
        b=self._body()
        with _lock:
            if self.path=="/v1/global/promote":
                return self._send(200, G.promote(b["lesson"], b["contributor_fp"], b.get("consent",False)))
            if self.path=="/v1/global/query":
                return self._send(200, G.query(b.get("kinds",[])))
            if self.path=="/v1/global/status":
                return self._send(200, G.status_for(b["signature"], b["contributor_fp"]) or {"in_global":False})
            if self.path=="/v1/global/revoke":
                return self._send(200, G.revoke(b["signature"], b["contributor_fp"]))
        self._send(404,{"error":"not found"})
    def log_message(self,*a): pass

def main():
    port=int(os.environ.get("PORT","8090"))
    print(f"f3-global on :{port}  (auth={'on' if TOKEN else 'DEV-OPEN'})", flush=True)
    ThreadingHTTPServer(("0.0.0.0",port), H).serve_forever()

if __name__=="__main__": main()
