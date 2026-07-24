"""JSON-RPC 2.0 over stdio 客户端。拉起一个 sidecar 子进程,按 contracts 调方法。
语言无关:sidecar 换成 TS/Rust 只要同样读 stdin 一行 JSON、写 stdout 一行 JSON。"""
from __future__ import annotations
import subprocess, json, itertools, sys, os

class RpcClient:
    def __init__(self, name: str, argv: list[str], cwd: str | None = None):
        self.name = name
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1, cwd=cwd)
        self._id = itertools.count(1)

    def call(self, method: str, params: dict, timeout: float = 40.0):
        rid = next(self._id)
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            err = self.p.stderr.read()
            raise RuntimeError(f"[{self.name}] no response. stderr: {err[:500]}")
        resp = json.loads(line)
        if "error" in resp and resp["error"]:
            raise RuntimeError(f"[{self.name}] rpc error: {resp['error']}")
        return resp.get("result")

    def close(self):
        try:
            self.p.stdin.close(); self.p.terminate(); self.p.wait(timeout=5)
        except Exception:
            self.p.kill()
