"""CoE 金标集回归测试(ENGINEERING.md §6)。断言:0 幻觉引用漏放。
需要网络(真实 arXiv/CrossRef/OpenAlex)。CI 可用 COE_CACHE 固化响应离线跑。"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel import run_verify

def test_golden():
    case = json.load(open(os.path.join(os.path.dirname(__file__), "golden", "draft_case.json")))
    rep = run_verify(case["run_id"], case["draft"], case["claims"], case["run_log"])
    by = {c["id"]: c["status"] for c in rep["claims"]}
    assert by["c-attn"] == "pass"          # 真 arXiv
    assert by["c-af"] == "pass"            # 真 DOI
    assert by["c-fake1"] == "reject"       # 假 arXiv
    assert by["c-fake2"] == "reject"       # 假 DOI
    assert by["n-acc"] == "pass"           # 有源数字
    # 语义变更(R2):无源数字 = unresolved(可能是推导值),不再武断判为捏造。
    # 署名门槛不变 —— all_green 仍为 False。
    assert by["n-energy"] == "unresolved"
    fk = {c["id"]: c.get("failure_kind") for c in rep["claims"]}
    assert fk["n-energy"] == "verification_gap"
    assert fk["c-fake1"] == "fabrication" and fk["c-fake2"] == "fabrication"
    assert rep["stats"]["hallucinated_citations"] == 2
    assert rep["stats"]["citations_rejected"] == 2   # 只数引用,不含数字
    assert rep["all_green"] is False
    # schema 合规
    from jsonschema import Draft202012Validator
    schema = json.load(open(os.path.join(os.path.dirname(__file__), "..", "contracts", "verification_report.schema.json")))
    assert not list(Draft202012Validator(schema).iter_errors(rep))

if __name__ == "__main__":
    test_golden(); print("✅ test_golden PASSED")
