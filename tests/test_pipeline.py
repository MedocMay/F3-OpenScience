"""M5 回归:真实 Pipeline 主线(literature 真检索 + code 真执行 + 数字可溯源)。需网络。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline
from pipeline.pipeline import run_pipeline
from coe_kernel import run_verify

def test_real_literature_and_execution():
    if skip_if_offline(): return
    r = run_pipeline("few-shot reinforcement learning battery health", injected=[])
    assert r["n_papers"] >= 1                         # 真实检索到论文
    assert "improvement" in r["run_log"]              # 真实沙箱执行出日志
    # 真实论文引用应通过 CoE;幻觉引用应被拒;真实数字应溯源
    rep = run_verify("m5", r["draft"], r["claims"], r["run_log"])
    cites = [c for c in rep["claims"] if c["type"] == "citation"]
    nums = [c for c in rep["claims"] if c["type"] == "number"]
    assert any(c["status"] == "pass" for c in cites)          # 真实论文过
    assert any(c["status"] == "reject" for c in cites)        # 幻觉被拦
    assert all(c["status"] == "pass" for c in nums)           # 真实数字溯源
    assert rep["stats"]["hallucinated_citations"] >= 1

def test_guard_drops_hallucination():
    if skip_if_offline(): return
    r = run_pipeline("graph neural networks molecules", injected=[{"kind": "fake_cite", "pattern": "NONEXISTENT_CITATION"}])
    rep = run_verify("m5g", r["draft"], r["claims"], r["run_log"])
    assert rep["stats"]["hallucinated_citations"] == 0        # guard 开:幻觉在生成前被丢弃
    assert rep["all_green"] is True

if __name__ == "__main__":
    test_real_literature_and_execution(); print("✅ real literature + execution")
    test_guard_drops_hallucination(); print("✅ guard drops hallucination")
    print("\nM5 pipeline 测试 PASSED")
