"""多租户隔离 — token → 租户/用户 映射 + 每租户独立存储。
隔离策略:每租户独立 experience 库(SQLite 一租户一文件 / Postgres 一 schema),天然隔离;
global 记忆跨租户共享(飞轮的意义所在,但只存脱敏模式)。"""
from __future__ import annotations
import os, sqlite3, secrets, hashlib, threading, tempfile

class TenantRegistry:
    """管理 token ↔ (tenant_id, user_id)。生产可接 IdP/JWT;此处自管 token。"""
    def __init__(self, path: str | None = None, data_root: str = "./data/tenants"):
        path = path or os.path.join(tempfile.gettempdir(), "opensci_tenants.db")
        self.root = data_root
        for d in {os.path.dirname(path) or ".", data_root}:
            os.makedirs(d, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS tenants(
            token_hash TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL, created_at REAL)""")
        self.db.commit()
        self._lock = threading.Lock()

    @staticmethod
    def _h(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(self, tenant_id: str, user_id: str) -> str:
        """发一个 token(仅存哈希,明文只返回一次)。"""
        token = "ost_" + secrets.token_urlsafe(24)
        import time
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO tenants VALUES(?,?,?,?)",
                            (self._h(token), tenant_id, user_id, time.time())); self.db.commit()
        os.makedirs(os.path.join(self.root, tenant_id), exist_ok=True)
        return token

    def resolve(self, token: str) -> dict | None:
        r = self.db.execute("SELECT tenant_id,user_id FROM tenants WHERE token_hash=?", (self._h(token),)).fetchone()
        return {"tenant_id": r[0], "user_id": r[1]} if r else None

    def resolve_header(self, auth_header: str) -> dict | None:
        if not auth_header.startswith("Bearer "):
            return None
        return self.resolve(auth_header[7:])

    # ---- 每租户存储路径(隔离核心)----
    def experience_db(self, tenant_id: str) -> str:
        return os.path.join(self.root, tenant_id, "experience.db")

    def vault_db(self, tenant_id: str) -> str:
        return os.path.join(self.root, tenant_id, "vault.db")
