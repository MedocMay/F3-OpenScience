"""M3 集成测试:真实多进程(orchestrator + 3 sidecars over stdio JSON-RPC)。
断言飞轮跨 IPC 生效:RUN1 blocked -> RUN2 signed。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import Orchestrator
from _netguard import skip_if_no_search

def test_multiprocess_flywheel():
    # the full chain runs literature search · 完整链路会走文献检索
    if skip_if_no_search("test_multiprocess_flywheel"): return
    db = "/tmp/test_orch.db"
    if os.path.exists(db): os.remove(db)
    logs = []
    orch = Orchestrator(lambda g: "approve", lambda s,t,d: logs.append((s,d)), db=db)
    try:
        r1 = orch.run("x", autonomy=1, contributor="userA")
        r2 = orch.run("x", autonomy=1, contributor="userB")
    finally:
        orch.close()
    assert r1["status"] == "blocked_pre_signoff", r1["status"]     # 首次假引用被拦
    assert r2["status"] == "signed", r2["status"]                  # 飞轮跨 IPC 规避 -> 署名
    assert r1["report"]["stats"]["hallucinated_citations"] == 1
    assert r2["report"]["stats"]["hallucinated_citations"] == 0

if __name__ == "__main__":
    test_multiprocess_flywheel(); print("✅ test_multiprocess_flywheel PASSED (real IPC)")
