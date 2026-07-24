"""可达性回归(R0/R2)—— 守住「不把『我看不到』当成『世界不允许』」这条线。

本套件的断言重点不是"全部通过",而是**失败的语义正确**:
  已知有效但难校验 -> 必须 unresolved(verification_gap),绝不可 reject(fabrication)
  已知捏造        -> 必须 reject(fabrication),绝不可放行
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel import run_verify
from coe_kernel.metrics import reachability_metrics

def _net_ok():
    import urllib.request
    try:
        urllib.request.urlopen("http://export.arxiv.org/api/query?search_query=all:test&max_results=1", timeout=25).read()
        return True
    except Exception:
        return False

def _run():
    case = json.load(open(os.path.join(os.path.dirname(__file__), "golden", "reachability_case.json")))
    rep = run_verify(case["run_id"], "", case["claims"], case["run_log"])
    labels = {c["id"]: c["_label"] for c in case["claims"] if "_label" in c}
    return rep, labels

def test_index_gap_is_not_fabrication():
    """★ 核心:索引未覆盖的真实引用,不得被判为捏造。"""
    if not _net_ok(): print("  ⚠ 网络不可达,跳过"); return
    rep, _ = _run()
    by = {c["id"]: c for c in rep["claims"]}
    c = by["rc-title-only-obscure"]
    assert c["status"] != "reject", f"索引盲区被误判为捏造:{c}"
    assert c.get("failure_kind") != "fabrication"

def test_derived_number_now_verifiable():
    """★ R3:合法推导值可由日志量重算 -> pass,证据链 kind=derivation。
    可达空间因此扩张,且**仍然被检验**(不是放水)。"""
    rep, _ = _run()
    by = {c["id"]: c for c in rep["claims"]}
    c = by["rc-derived-number"]
    assert c["status"] == "pass", f"推导值未通过:{c}"
    ev = c.get("evidence_chain", {})
    assert ev.get("kind") == "derivation" and ev.get("derivation"), f"缺推导证据链:{ev}"

def test_contradicted_derivation_is_fabrication():
    """★ R3 的反面:推导式重算与声明值矛盾 = 权威否定 -> reject/fabrication。
    裁判从书目学变成计算 —— 计算说不,就是不。"""
    rep, _ = _run()
    by = {c["id"]: c for c in rep["claims"]}
    c = by["rc-contradicted-derivation"]
    assert c["status"] == "reject", f"矛盾推导未被拦:{c}"
    assert c.get("failure_kind") == "fabrication"

def test_real_fabrication_still_caught():
    """反向保证:真捏造必须仍被 reject —— 放宽语义不等于放松署名门槛。"""
    if not _net_ok(): print("  ⚠ 网络不可达,跳过"); return
    rep, _ = _run()
    by = {c["id"]: c for c in rep["claims"]}
    for cid in ("rc-fake-arxiv", "rc-fake-doi"):
        assert by[cid]["status"] == "reject", f"{cid} 未被拦截"
        assert by[cid].get("failure_kind") == "fabrication"

def test_signing_gate_unchanged():
    """署名保证不变:存在 unresolved 时不得放行。"""
    rep, _ = _run()
    assert rep["all_green"] is False

def test_metrics_expose_narrowing():
    """度量必须能报出误拒率与覆盖率。"""
    if not _net_ok(): print("  ⚠ 网络不可达,跳过"); return
    rep, labels = _run()
    m = reachability_metrics([rep], labels)
    assert m["false_rejection_rate"] == 0.0, f"存在误拒:{m['false_rejections']}"
    assert m["missed_fabrication_rate"] == 0.0, f"漏放捏造:{m['missed_fabrications']}"
    assert 0 <= m["coverage_ratio"] <= 1
    print(f"  覆盖率={m['coverage_ratio']} 误拒率={m['false_rejection_rate']} "
          f"漏放率={m['missed_fabrication_rate']} 失败构成={m['by_failure_kind']}")

if __name__ == "__main__":
    for t in [test_index_gap_is_not_fabrication, test_derived_number_now_verifiable,
              test_contradicted_derivation_is_fabrication,
              test_real_fabrication_still_caught, test_signing_gate_unchanged,
              test_metrics_expose_narrowing]:
        t(); print(f"✅ {t.__name__}")
    print("\n可达性回归 PASSED")
