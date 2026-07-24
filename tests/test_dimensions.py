"""量纲一致性(R4)回归 —— 第一个与索引无关的物理约束。

核心断言分两类:
  1. 物理不可能的东西必须被判 fabrication(不查任何数据库)
  2. ★ 语义无法辨识时必须承认判断不了,绝不武断否定
     —— 否则就是在新的地方重犯"把自己的命名习惯当成物理定律"的错误
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel.dimensions import check_expression, check_value, infer_semantic
from coe_kernel.verify import verify_number

LOG = "epoch 10 | baseline_acc 0.520 | improved_acc 0.597 | train_time_s 120.0 | mem_mb 512.0"
SYMS = {"baseline_acc": 0.520, "improved_acc": 0.597, "epoch": 10.0,
        "train_time_s": 120.0, "mem_mb": 512.0, "mystery_z": 7.0}

def test_semantic_inference():
    assert infer_semantic("baseline_acc") == "probability"
    assert infer_semantic("train_time_s") == "duration"
    assert infer_semantic("epoch") == "count"
    assert infer_semantic("mem_mb") == "memory"
    assert infer_semantic("mystery_z") == "unknown"      # 不硬猜

def test_incompatible_dimensions_rejected():
    """准确率 + 耗时:物理上不可加。"""
    ok, why = check_expression("improved_acc + train_time_s", SYMS)
    assert not ok and "不可加减" in why

def test_compatible_dimensions_pass():
    for e in ["improved_acc - baseline_acc",
              "(improved_acc - baseline_acc) / baseline_acc * 100",
              "train_time_s / epoch",              # 秒/步 —— 合法复合量纲
              "mem_mb * 2"]:
        ok, why = check_expression(e, SYMS)
        assert ok, f"{e} 被误判:{why}"

def test_unknown_never_asserts_violation():
    """★ 未知语义参与时不得宣告物理违反 —— 承认判断不了,而非假装无量纲。"""
    ok, _ = check_expression("mystery_z + train_time_s", SYMS)
    assert ok, "对未知量纲武断下了否定结论"
    ok2, _ = check_value("mystery_z", -999.0)
    assert ok2, "对未知语义的取值武断否定"

def test_value_bounds():
    assert not check_value("final accuracy", 1.35)[0]     # 概率 > 1
    assert not check_value("final accuracy", -0.1)[0]
    assert not check_value("epoch count", -3)[0]
    assert not check_value("training time seconds", -5)[0]
    assert check_value("final accuracy", 0.95)[0]
    assert check_value("improvement", -12.0)[0]           # 变化率可为负

def test_physical_violation_is_fabrication():
    """物理不可能 -> fabrication(与索引无关的权威否定),不是 verification_gap。"""
    r = verify_number({"id": "x", "type": "number", "value": "1.35", "text": "final accuracy"}, LOG)
    assert r["status"] == "reject" and r["failure_kind"] == "fabrication"

    r2 = verify_number({"id": "y", "type": "number", "value": "0.6", "text": "z",
                        "derivation": "improved_acc + train_time_s"}, LOG)
    assert r2["status"] == "reject" and r2["failure_kind"] == "fabrication"

def test_dimension_prunes_discovery():
    """量纲剪枝应发生在求值之前:合法推导仍能被发现。"""
    r = verify_number({"id": "z", "type": "number", "value": "0.077", "text": "absolute gain"}, LOG)
    assert r["status"] == "pass" and r["evidence_chain"]["kind"] == "derivation"

if __name__ == "__main__":
    for t in [test_semantic_inference, test_incompatible_dimensions_rejected,
              test_compatible_dimensions_pass, test_unknown_never_asserts_violation,
              test_value_bounds, test_physical_violation_is_fabrication,
              test_dimension_prunes_discovery]:
        t(); print(f"✅ {t.__name__}")
    print("\n量纲一致性 PASSED")
