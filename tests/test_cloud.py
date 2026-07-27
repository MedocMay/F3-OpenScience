"""云端多租户 + BYOK 密管 + 存储抽象 回归。"""
import sys, os, sqlite3, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import run_suite, skip_if_missing
os.environ["OPENSCI_MASTER_KEY"] = "test-master-key"
from cloud.vault import KeyVault
from cloud.tenancy import TenantRegistry
from cloud.db import open_db

def _clean(p): shutil.rmtree(p, ignore_errors=True); os.path.exists(p) and os.remove(p)

def test_vault_byok():
    # BYOK needs `cryptography`, an optional extra. Absent, this environment cannot
    # exercise the vault at all — that is a capability gap, not a defect.
    # BYOK 需要可选依赖 cryptography。没装就根本无法验证密管 ——
    # 这是能力缺口,不是缺陷。
    if skip_if_missing("cryptography", "cloud", "test_vault_byok"): return
    p = "/tmp/t_vault.db"; _clean(p)
    v = KeyVault(p)
    v.put("alice", "anthropic", "sk-ALICE"); v.put("bob", "anthropic", "sk-BOB")
    assert v.get("alice", "anthropic") == "sk-ALICE"
    assert v.get("bob", "anthropic") == "sk-BOB"          # 每用户隔离
    assert v.get("alice", "openai") is None
    raw = sqlite3.connect(p).execute("SELECT ciphertext FROM keys LIMIT 1").fetchone()[0]
    assert b"ALICE" not in raw and b"sk-" not in raw       # 明文不落盘

def test_tenant_isolation():
    root = "/tmp/t_tenants"; shutil.rmtree(root, ignore_errors=True)
    reg = TenantRegistry(os.path.join(root, "_t.db"), data_root=root)
    tA = reg.issue("acme", "alice"); tB = reg.issue("globex", "bob")
    assert reg.resolve(tA)["tenant_id"] == "acme"
    assert reg.resolve(tB)["tenant_id"] == "globex"
    assert reg.resolve("bogus") is None                    # 无效 token
    assert reg.experience_db("acme") != reg.experience_db("globex")   # 路径隔离

def test_db_abstraction():
    p = "/tmp/t_abs.db"; _clean(p)
    db = open_db(p)                                        # 裸路径 = sqlite
    db.executescript("CREATE TABLE t(k TEXT PRIMARY KEY, v INTEGER)")
    db.execute("INSERT OR REPLACE INTO t VALUES(?,?)", ("a", 1)); db.commit()
    assert dict(db.execute("SELECT k,v FROM t WHERE k=?", ("a",)).fetchone())["v"] == 1
    assert db.dialect == "sqlite"
    assert open_db("sqlite:////tmp/t_abs.db").dialect == "sqlite"
    # postgres 后端:open_db("postgresql://...") 同接口(需 psycopg,不在此环境跑)

if __name__ == "__main__":
    run_suite([test_vault_byok, test_tenant_isolation, test_db_abstraction],
              "云端(多租户 + BYOK + 存储抽象)测试")
