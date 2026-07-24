"""探索预算与新颖论断署名(R5)回归。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel.exploration import allocate, measure
from coe_kernel.novelty import extract_mechanism_claims, required_substrate, evidence_satisfies
from coe_kernel.verify import verify_mechanism
from coe_kernel.metrics import flywheel_health

def test_mechanism_claims_are_extracted():
    """★ 补上反向缺口:机制性命题此前完全不进校验。"""
    d = ("We propose that sparse attention leads to lower memory usage. "
         "The dataset contains 5000 samples. "
         "Our method improves convergence because gradient variance is reduced.")
    cs = extract_mechanism_claims(d)
    assert len(cs) >= 2 and all(c["type"] == "mechanism" for c in cs)
    assert not any("dataset contains" in c["text"] for c in cs)   # 描述句不算主张

def test_substrate_depends_on_support_not_pass_fail():
    """新颖度决定所需证据基质,而非能否通过。"""
    assert required_substrate("supported") == "citation_or_computational"
    assert required_substrate("unestablished_in_index") == "computational"
    assert not evidence_satisfies({"kind": "citation"}, "computational")
    assert evidence_satisfies({"kind": "code+data"}, "computational")
    assert evidence_satisfies({"kind": "derivation"}, "computational")

def test_novel_claim_signable_on_computational_evidence():
    """★ 索引中无支撑的命题,可凭可复现包署名 —— 系统敢主张新东西。"""
    c = {"id": "m1", "type": "mechanism",
         "text": "We propose that this regime is driven by a rarely-observed pathway."}
    r = verify_mechanism(c, artifacts={"reproducible_package": "/pkg/run-abc"})
    assert r["status"] == "pass"
    assert r["evidence_chain"]["kind"] == "code+data"

def test_claim_without_any_evidence_blocked():
    """没有任何证据的主张不得放行 —— 放宽的是基质,不是证明责任。"""
    c = {"id": "m2", "type": "mechanism", "text": "We propose that X leads to Y."}
    r = verify_mechanism(c, artifacts={})
    assert r["status"] == "unresolved" and r["failure_kind"] == "verification_gap"

def test_exploration_budget_enforced_and_honest():
    cands = [{"prior": "high"} for _ in range(6)] + [{"prior": "low"} for _ in range(3)]
    m = measure(allocate(cands, ratio=0.3))
    assert m["met"] and m["exploration_rate"] >= 0.3
    # 候选池不足时如实报告未达成,不伪造探索项
    poor = [{"prior": "high"} for _ in range(5)]
    m2 = measure(allocate(poor, ratio=0.5))
    assert m2["met"] is False and m2["exploration_rate"] == 0.0

def test_flywheel_detects_conservatism():
    """★ 最隐蔽的退化:校验指标好看,但探索率下降。"""
    ok = flywheel_health([2, 1, 0], [0.5, 0.5, 0.51], [0.35, 0.34, 0.35])
    assert ok["verdict"] == "learning"
    cons = flywheel_health([2, 1, 0], [0.5, 0.5, 0.51], [0.40, 0.25, 0.10])
    assert cons["verdict"] == "conservative"
    narrow = flywheel_health([2, 1, 0], [0.5, 0.35, 0.20], [0.4, 0.4, 0.4])
    assert narrow["verdict"] == "narrowing"

if __name__ == "__main__":
    for t in [test_mechanism_claims_are_extracted, test_substrate_depends_on_support_not_pass_fail,
              test_novel_claim_signable_on_computational_evidence, test_claim_without_any_evidence_blocked,
              test_exploration_budget_enforced_and_honest, test_flywheel_detects_conservatism]:
        t(); print(f"✅ {t.__name__}")
    print("\n探索预算与新颖论断 PASSED")
