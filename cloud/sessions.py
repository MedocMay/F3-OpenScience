"""会话存储 — 多实例网关的会话外置。默认内存(单实例);设 OPENSCI_REDIS_URL 走 Redis(多实例共享)。
只存会话元数据与事件游标,不存密钥。Redis 不可达时自动回退内存并告警。"""
from __future__ import annotations
import os, json, time, threading

class MemorySessions:
    backend = "memory"
    def __init__(self): self._d = {}; self._lock = threading.Lock()
    def put(self, run_id, meta):
        with self._lock: self._d[run_id] = {"meta": meta, "ts": time.time()}
    def get(self, run_id):
        v = self._d.get(run_id); return v["meta"] if v else None
    def delete(self, run_id):
        with self._lock: self._d.pop(run_id, None)

class RedisSessions:
    backend = "redis"
    def __init__(self, url, ttl=3600):
        import redis  # 仅在启用时依赖
        self.r = redis.Redis.from_url(url, decode_responses=True); self.ttl = ttl
        self.r.ping()
    def put(self, run_id, meta): self.r.setex(f"sess:{run_id}", self.ttl, json.dumps(meta))
    def get(self, run_id):
        v = self.r.get(f"sess:{run_id}"); return json.loads(v) if v else None
    def delete(self, run_id): self.r.delete(f"sess:{run_id}")

def get_sessions():
    url = os.environ.get("OPENSCI_REDIS_URL")
    if url:
        try:
            s = RedisSessions(url); print(f"[sessions] redis @ {url}", flush=True); return s
        except Exception as e:
            print(f"[sessions] redis 不可达({e}),回退内存(单实例)", flush=True)
    return MemorySessions()
