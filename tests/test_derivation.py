"""推导式证据链(R3)回归 —— 安全性 + 正确性 + 保守性。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel.derivation import (parse_log_symbols, safe_eval, verify_explicit,
                                   discover, UnsafeExpression)
from coe_kernel.verify import verify_number

LOG = "epoch 10 | baseline_acc 0.520 | improved_acc 0.597 | improvement 14.8%\nseed 42"

def test_symbol_parsing():
    s = parse_log_symbols(LOG)
    assert s["baseline_acc"] == 0.520 and s["improved_acc"] == 0.597
    assert s["improvement"] == 14.8 and s["seed"] == 42

def test_safe_eval_blocks_code_execution():
    """★ 安全底线:推导式绝不能变成任意代码执行入口。"""
    s = parse_log_symbols(LOG)
    for bad in ['__import__("os").system("ls")', 'open("/etc/passwd")',
                'baseline_acc.__class__', '[x for x in range(10)]',
                'unknown_var + 1', '(lambda: 1)()', 'globals()']:
        try:
            safe_eval(bad, s)
            assert False, f"未拦截危险表达式:{bad}"
        except (UnsafeExpression, SyntaxError):
            pass

def test_explicit_derivation():
    s = parse_log_symbols(LOG)
    ok, got, _ = verify_explicit("improved_acc - baseline_acc", "0.077", s)
    assert ok and abs(got - 0.077) < 1e-9

def test_discovery_is_conservative():
    """精度不足的数不接受自动发现 —— 防巧合命中。"""
    s = parse_log_symbols(LOG)
    assert discover("0.077", s) is not None          # 3 位小数,可发现
    assert discover("0.5", s) is None                # 1 位小数,拒绝
    assert discover("42", s) is None                 # 整数,拒绝

def test_verify_number_paths():
    lit = verify_number({"id": "a", "type": "number", "value": "14.8"}, LOG)
    assert lit["status"] == "pass" and lit["evidence_chain"]["kind"] == "log"

    auto = verify_number({"id": "b", "type": "number", "value": "0.077"}, LOG)
    assert auto["status"] == "pass" and auto["evidence_chain"]["kind"] == "derivation"

    exp = verify_number({"id": "c", "type": "number", "value": "0.077",
                         "derivation": "improved_acc - baseline_acc"}, LOG)
    assert exp["status"] == "pass" and exp["evidence_chain"]["derivation"]

    bad = verify_number({"id": "d", "type": "number", "value": "0.999",
                         "derivation": "improved_acc - baseline_acc"}, LOG)
    assert bad["status"] == "reject" and bad["failure_kind"] == "fabrication"

    none = verify_number({"id": "e", "type": "number", "value": "88.8"}, LOG)
    assert none["status"] == "unresolved" and none["failure_kind"] == "verification_gap"

def test_unknown_symbol_rejected():
    """推导式只能引用日志中真实存在的量,不得凭空引入符号。"""
    s = parse_log_symbols(LOG)
    ok, got, why = verify_explicit("nonexistent_metric * 2", "1.0", s)
    assert not ok and "未知符号" in why

if __name__ == "__main__":
    for t in [test_symbol_parsing, test_safe_eval_blocks_code_execution, test_explicit_derivation,
              test_discovery_is_conservative, test_verify_number_paths, test_unknown_symbol_rejected]:
        t(); print(f"✅ {t.__name__}")
    print("\n推导式证据链 PASSED")
