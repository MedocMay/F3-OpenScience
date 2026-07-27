"""M3 集成测试:真实多进程(orchestrator + 3 sidecars over stdio JSON-RPC)。
断言飞轮跨 IPC 生效:RUN1 blocked -> RUN2 signed。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import Orchestrator
from _netguard import skip_if_no_search, skip_if_offline, assert_capable, run_suite

def test_multiprocess_flywheel():
    # the full chain runs literature search · 完整链路会走文献检索
    # The chain needs BOTH capabilities: search to find papers, judgement to reject
    # the fabricated one. They fail independently under rate limiting, so guarding on
    # search alone leaves the hallucinated_citations assertions naked.
    # 这条链路需要**两种**能力:检索找到论文,判定拒绝捏造引用。两者在限流下独立失效,
    # 只守检索会让 hallucinated_citations 的断言裸奔。
    if skip_if_no_search("test_multiprocess_flywheel"): return
    if skip_if_offline("test_multiprocess_flywheel"): return
    db = "/tmp/test_orch.db"
    if os.path.exists(db): os.remove(db)
    logs = []
    orch = Orchestrator(lambda g: "approve", lambda s,t,d: logs.append((s,d)), db=db)
    try:
        r1 = orch.run("x", autonomy=1, contributor="userA")
        r2 = orch.run("x", autonomy=1, contributor="userB")
    finally:
        orch.close()
    # Two full chain runs happen above; they are heavy enough to rate-limit this
    # process partway. assert_capable re-probes before declaring any of these a failure.
    # 上面跑了两遍完整链路,足以把本进程打到限流。assert_capable 在判定失败之前重探能力。
    assert_capable(r1["status"] == "blocked_pre_signoff", "RUN1 blocked", "cite", r1["status"])
    assert_capable(r2["status"] == "signed", "RUN2 signed", "cite", r2["status"])
    assert_capable(r1["report"]["stats"]["hallucinated_citations"] == 1, "RUN1 caught 1", "cite")
    assert_capable(r2["report"]["stats"]["hallucinated_citations"] == 0, "RUN2 caught 0", "cite")

if __name__ == "__main__":
    run_suite([(test_multiprocess_flywheel, "test_multiprocess_flywheel (real IPC)")],
              "M3 多进程集成")
