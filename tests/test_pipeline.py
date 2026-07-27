"""M5 回归:真实 Pipeline 主线(literature 真检索 + code 真执行 + 数字可溯源)。需网络。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline, skip_if_no_search, assert_capable, run_suite
from pipeline.pipeline import run_pipeline
from coe_kernel import run_verify

def test_real_literature_and_execution():
    # needs the SEARCH endpoint, not the ID endpoint · 需要搜索端点而非 ID 端点
    if skip_if_no_search("test_real_literature_and_execution"): return
    r = run_pipeline("few-shot reinforcement learning battery health", injected=[])
    # A full pipeline run is heavy enough to rate-limit this process partway, so the
    # capability checked at line 1 may be gone by now. assert_capable re-probes before
    # declaring a failure — search capability for retrieval, judgement for the verdicts.
    # 一次完整 pipeline 足以把本进程打到限流,开头确认过的能力此刻可能已经没了。
    # assert_capable 在判定失败之前重探:检索类断言探检索能力,判定类断言探判定能力。
    assert_capable(r["n_papers"] >= 1, "retrieved >=1 paper", "search", f"n_papers={r['n_papers']}")
    assert "improvement" in r["run_log"]              # 真实沙箱执行出日志(本地,不依赖网络)
    # 真实论文引用应通过 CoE;幻觉引用应被拒;真实数字应溯源
    rep = run_verify("m5", r["draft"], r["claims"], r["run_log"])
    cites = [c for c in rep["claims"] if c["type"] == "citation"]
    nums = [c for c in rep["claims"] if c["type"] == "number"]
    assert_capable(any(c["status"] == "pass" for c in cites), "a real paper passed", "cite")
    assert_capable(any(c["status"] == "reject" for c in cites), "a fabricated cite rejected", "cite")
    assert all(c["status"] == "pass" for c in nums)           # 真实数字溯源(本地重算)
    assert_capable(rep["stats"]["hallucinated_citations"] >= 1, "counted >=1 hallucination", "cite")

def test_guard_drops_hallucination():
    if skip_if_no_search("test_guard_drops_hallucination"): return
    r = run_pipeline("graph neural networks molecules", injected=[{"kind": "fake_cite", "pattern": "NONEXISTENT_CITATION"}])
    rep = run_verify("m5g", r["draft"], r["claims"], r["run_log"])
    assert rep["stats"]["hallucinated_citations"] == 0        # guard 开:幻觉在生成前被丢弃
    assert_capable(rep["all_green"] is True, "all claims green", "cite")

if __name__ == "__main__":
    run_suite([(test_real_literature_and_execution, "real literature + execution"),
               (test_guard_drops_hallucination, "guard drops hallucination")],
              "M5 pipeline 测试")
