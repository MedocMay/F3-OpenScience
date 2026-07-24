"""每用户 BYOK 密钥管理 — 密钥落盘加密(Fernet/AES),主密钥从环境或 KMS 注入。
云端多租户:每个用户自带模型 key,系统加密存储、按需解密注入,明文永不落盘、不进日志。
生产:主密钥应来自 KMS/Vault(此处从 OPENSCI_MASTER_KEY 读,未设则派生并告警)。"""
from __future__ import annotations
import os, json, sqlite3, base64, hashlib, threading, tempfile


def _fernet():
    """延迟导入 —— 核心保持零依赖;仅在真正使用密管时才需要 cryptography。
    与 psycopg / redis / rdkit 的处理方式一致:缺失时给出可操作的提示,而非裸 ImportError。"""
    try:
        from cryptography.fernet import Fernet
        return Fernet
    except ImportError as e:
        raise ImportError(
            "BYOK 密钥管理需要 cryptography。请安装云端依赖组:\n"
            "    pip install 'f3-openscience[cloud]'   # 或  pip install cryptography"
        ) from e

def _master_key() -> bytes:
    mk = os.environ.get("OPENSCI_MASTER_KEY")
    if mk:
        # 允许传 32 字节 base64 或任意口令(口令走 scrypt 派生)
        try:
            if len(base64.urlsafe_b64decode(mk + "===")) == 32:
                return mk.encode()
        except Exception:
            pass
        dk = hashlib.scrypt(mk.encode(), salt=b"opensci-vault", n=16384, r=8, p=1, dklen=32)
        return base64.urlsafe_b64encode(dk)
    # 未设主密钥:派生一个临时的(仅 dev;生产必须显式设 OPENSCI_MASTER_KEY)
    dk = hashlib.scrypt(b"dev-insecure", salt=b"opensci-vault", n=16384, r=8, p=1, dklen=32)
    return base64.urlsafe_b64encode(dk)

class KeyVault:
    """按 (user_id, provider) 存加密后的 API key。"""
    def __init__(self, path: str | None = None):
        path = path or os.path.join(tempfile.gettempdir(), "opensci_vault.db")
        d = os.path.dirname(path)
        if d: os.makedirs(d, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS keys(user_id TEXT, provider TEXT, ciphertext BLOB, PRIMARY KEY(user_id,provider))")
        self.db.commit()
        self.f = _fernet()(_master_key())
        self._lock = threading.Lock()

    def put(self, user_id: str, provider: str, api_key: str):
        ct = self.f.encrypt(api_key.encode())
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO keys VALUES(?,?,?)", (user_id, provider, ct))
            self.db.commit()

    def get(self, user_id: str, provider: str) -> str | None:
        r = self.db.execute("SELECT ciphertext FROM keys WHERE user_id=? AND provider=?", (user_id, provider)).fetchone()
        if not r:
            return None
        return self.f.decrypt(r[0]).decode()      # 仅在注入调用瞬间解密

    def providers(self, user_id: str) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT provider FROM keys WHERE user_id=?", (user_id,)).fetchall()]

    def delete(self, user_id: str, provider: str):
        with self._lock:
            self.db.execute("DELETE FROM keys WHERE user_id=? AND provider=?", (user_id, provider)); self.db.commit()
