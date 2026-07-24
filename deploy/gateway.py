"""网络网关 — 把 Orchestrator 的 ipc.schema 暴露成 HTTP + SSE 网络 API。
让系统从"本地 stdio IPC"变成"可云端部署的服务"。零第三方依赖(stdlib)。

端点:
  POST /v1/runs            {direction, autonomy, contributor} -> {run_id}
  GET  /v1/runs/{id}/events   Server-Sent Events 流(run.event / gate.request / result)
  POST /v1/gates           {run_id, gate_id, decision} -> {ok}
  GET  /v1/sovereignty?contributor=.. -> {contributions}
  POST /v1/sovereignty/revoke {lesson_id} -> {ok}
  GET  /healthz

认证:Bearer token(环境 OPENSCI_TOKEN;未设=开发模式放行)。
"""
from __future__ import annotations
import os, tempfile, sys, json, threading, queue, uuid, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
from orchestrator import Orchestrator

TOKEN = os.environ.get("OPENSCI_TOKEN")            # 未设=dev 放行
DB = os.environ.get("OPENSCI_DB") or os.path.join(tempfile.gettempdir(), "opensci_gateway.db")

class RunSession:
    """一次 run 的会话:事件队列 + 待决 gate。run 在后台线程执行。"""
    def __init__(self):
        self.events: queue.Queue = queue.Queue()
        self.gate_waiters: dict[str, queue.Queue] = {}
        self.done = False
        self.result = None

    def ask(self, gate_id: str) -> str:
        q = queue.Queue(); self.gate_waiters[gate_id] = q
        self.events.put(("gate.request", {"gate_id": gate_id}))
        decision = q.get()                              # 阻塞直到 /v1/gates 到达
        self.gate_waiters.pop(gate_id, None)
        return decision

    def emit(self, stage, typ, data):
        self.events.put(("run.event", {"stage": stage, "type": typ, "data": data}))

    def resolve_gate(self, gate_id, decision) -> bool:
        q = self.gate_waiters.get(gate_id)
        if not q: return False
        q.put(decision); return True

SESSIONS: dict[str, RunSession] = {}
_orch_lock = threading.Lock()

def _run_bg(run_id, direction, autonomy, contributor):
    sess = SESSIONS[run_id]
    try:
        with _orch_lock:                                # Orchestrator 起 sidecar,单例串行(MVP)
            orch = Orchestrator(sess.ask, sess.emit, db=DB)
            try:
                res = orch.run(direction, autonomy, contributor)
            finally:
                orch.close()
        sess.result = res
        sess.events.put(("result", res))
    except Exception as e:
        sess.events.put(("error", {"message": str(e)}))
    finally:
        sess.done = True
        sess.events.put(("_end", {}))

class Handler(BaseHTTPRequestHandler):
    def _auth(self) -> bool:
        if not TOKEN: return True
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/healthz":
            return self._json(200, {"ok": True, "service": "f3-gateway"})
        if not self._auth(): return self._json(401, {"error": "unauthorized"})
        if self.path.startswith("/v1/runs/") and self.path.endswith("/events"):
            run_id = self.path.split("/")[3]
            return self._sse(run_id)
        if self.path.startswith("/v1/sovereignty"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            fp = (q.get("contributor") or [None])[0]
            rows = _mem_call("mem.list_contributions", {"contributor_fp": fp})
            return self._json(200, {"contributions": rows})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth(): return self._json(401, {"error": "unauthorized"})
        if self.path == "/v1/runs":
            b = self._body(); run_id = "run-" + uuid.uuid4().hex[:8]
            SESSIONS[run_id] = RunSession()
            threading.Thread(target=_run_bg, args=(run_id, b.get("direction", ""),
                             int(b.get("autonomy", 1)), b.get("contributor", "user")), daemon=True).start()
            return self._json(202, {"run_id": run_id})
        if self.path == "/v1/gates":
            b = self._body(); sess = SESSIONS.get(b.get("run_id", ""))
            ok = sess.resolve_gate(b.get("gate_id"), b.get("decision", "approve")) if sess else False
            return self._json(200 if ok else 404, {"ok": ok})
        if self.path == "/v1/sovereignty/revoke":
            b = self._body(); r = _mem_call("mem.revoke", {"lesson_id": b.get("lesson_id")})
            return self._json(200, r)
        self._json(404, {"error": "not found"})

    def _sse(self, run_id):
        sess = SESSIONS.get(run_id)
        if not sess: return self._json(404, {"error": "unknown run"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "keep-alive")
        self.end_headers()
        while True:
            try: kind, data = sess.events.get(timeout=90)
            except queue.Empty:
                self.wfile.write(b": keepalive\n\n"); self.wfile.flush(); continue
            if kind == "_end":
                self.wfile.write(b"event: end\ndata: {}\n\n"); self.wfile.flush(); break
            payload = json.dumps({"kind": kind, **({"data": data} if kind != "run.event" else data)})
            self.wfile.write(f"event: {kind}\ndata: {payload}\n\n".encode()); self.wfile.flush()

    def log_message(self, *a): pass

def _mem_call(method, params):
    import subprocess
    root = os.path.join(os.path.dirname(__file__), "..")
    p = subprocess.Popen([sys.executable, "-c", f"import sys;from memory.server import main;main('{DB}')"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=root)
    out, _ = p.communicate(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}) + "\n", timeout=30)
    return json.loads(out.strip().split("\n")[0]).get("result")

def main():
    port = int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"f3-gateway on :{port}  (auth={'on' if TOKEN else 'DEV-OPEN'})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
