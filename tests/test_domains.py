"""领域物理可达性(R6)回归 —— 由领域规律裁决,与任何数据库无关。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline
from coe_kernel.domains import chemistry as ch, available_domains
from coe_kernel import run_verify

def test_mass_conservation():
    """★ 质量守恒定律 —— 零依赖、零查询即可判定物理不可能。"""
    assert ch.check_reaction("2H2 + O2 -> 2H2O")[0] == "plausible"
    assert ch.check_reaction("CH4 + 2O2 -> CO2 + 2H2O")[0] == "plausible"
    v, why = ch.check_reaction("H2 + O2 -> H2O")
    assert v == "impossible" and "守恒" in why

def test_degree_of_unsaturation():
    assert ch.check_formula("C6H12O6")[0] == "plausible"
    assert ch.check_formula("C6H6")[0] == "plausible"
    v, why = ch.check_formula("C2H8")
    assert v == "impossible" and "不饱和度" in why

def test_radical_is_not_impossible():
    """★ 自由基/离子真实存在 —— 半整数不饱和度不得判死。"""
    v, why = ch.check_formula("CH3")
    assert v == "plausible" and "自由基" in why

def test_out_of_scope_is_unknown():
    """★ 判据不适用时必须承认判断不了,绝不冒充物理结论。"""
    assert ch.check_formula("NaCl2Fe3")[0] == "unknown"
    assert ch.check_formula("not a formula")[0] == "unknown"
    assert ch.check_reaction("some prose without arrow")[0] == "unknown"

def test_smiles_optional_and_honest():
    """装了 RDKit 才判价键;没装则 unknown(能力缺失 ≠ 物理结论)。"""
    v, why = ch.check_smiles("C(C)(C)(C)(C)C")     # 五价碳
    if ch.rdkit_available():
        assert v == "impossible"
    else:
        assert v == "unknown" and "非物理结论" in why

def test_extraction_from_prose():
    """从自由文本抽取,不能把英文句子吞进反应式。"""
    d = "We synthesized C6H12O6 via the pathway 2H2 + O2 -> 2H2O. A side product C2H8 was proposed."
    found = ch.find_claims(d)
    exprs = {c["expr"] for c in found}
    assert "2H2 + O2 -> 2H2O" in exprs and "C6H12O6" in exprs and "C2H8" in exprs

def test_end_to_end_domain_gate():
    """物理不可能 -> fabrication -> 阻断署名。"""
    if skip_if_offline("test_end_to_end_domain_gate"): return
    d = "The unbalanced step H2 + O2 -> H2O and the species C2H8 were considered."
    r = run_verify("d1", d, [], "", domain="chemistry")
    doms = [c for c in r["claims"] if c["type"] == "domain"]
    assert len(doms) >= 2
    assert all(c["status"] == "reject" and c["failure_kind"] == "fabrication" for c in doms)
    assert r["all_green"] is False
    assert r["coverage"]["domain_checks"] == ["chemistry"]

def test_domain_off_by_default():
    """不指定 domain 时不启用领域判据 —— MVP 域(ML/CS)不受影响。"""
    r = run_verify("d2", "The species C2H8 was considered.", [], "")
    assert not [c for c in r["claims"] if c["type"] == "domain"]

if __name__ == "__main__":
    print("可用领域:", available_domains())
    for t in [test_mass_conservation, test_degree_of_unsaturation, test_radical_is_not_impossible,
              test_out_of_scope_is_unknown, test_smiles_optional_and_honest,
              test_extraction_from_prose, test_end_to_end_domain_gate, test_domain_off_by_default]:
        t(); print(f"✅ {t.__name__}")
    print("\n领域物理可达性 PASSED")
