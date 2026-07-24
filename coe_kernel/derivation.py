"""推导式证据链(R3)—— 把证据从「字面命中」升级为「可重算」。

动机(可达性):要求数字字面出现在运行日志里,会把可声称的科学压缩成
「我的沙箱恰好打印过的东西」。相对提升、绝对增益、单位换算、由两个日志值算出的第三个值,
全都是合法且可检验的科学论断,却会被字面匹配一律拒绝。

R3 的立场:**放宽的是证据形式,不是证明责任。**
数字仍必须可被独立重算 —— 只是「重算」不再等同于「字符串出现过」。

两条路径:
  1) 显式推导:claim 携带 derivation 表达式,引用日志中的具名量,重新求值比对。
  2) 推导发现:在**有界的**算子空间内搜索能复现该值的表达式(差、比、相对变化…)。
     搜索命中不等于自动放行 —— 见 _MIN_PRECISION 与容差守则。

安全:表达式用 AST 白名单求值,不使用 eval;禁止函数调用、属性访问、下标、推导式。
"""
from __future__ import annotations
import ast, re, math, hashlib
from itertools import permutations
from . import dimensions as dims

# ---- 日志符号表 ----
# 形如 "baseline_acc 0.520" / "improved_acc=0.597" / "improvement 14.8%"
_SYM = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*[=:]?\s*(-?\d+(?:\.\d+)?)\s*%?")

def parse_log_symbols(run_log: str) -> dict[str, float]:
    """从运行日志抽出具名数值,作为推导的基底。后出现的同名量覆盖先前的。"""
    syms: dict[str, float] = {}
    for name, val in _SYM.findall(run_log or ""):
        try:
            syms[name] = float(val)
        except ValueError:
            pass
    return syms

# ---- 安全求值(AST 白名单)----
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load,
                  ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
                  ast.USub, ast.UAdd, ast.Mod)

class UnsafeExpression(ValueError):
    pass

def safe_eval(expr: str, symbols: dict[str, float]) -> float:
    """只允许四则运算 / 幂 / 取模 + 具名量与字面量。任何调用、属性、下标一律拒绝。"""
    if len(expr) > 200:
        raise UnsafeExpression("表达式过长")
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpression(f"不允许的语法节点:{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in symbols:
            raise UnsafeExpression(f"未知符号:{node.id}(不在运行日志中)")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise UnsafeExpression("只允许数值常量")
    return float(eval(compile(tree, "<derivation>", "eval"), {"__builtins__": {}}, dict(symbols)))

# ---- 比对 ----
def _close(a: float, b: float, rel: float = 1e-3, abs_: float = 1e-9) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)

def _round_trip(claimed_str: str, computed: float) -> bool:
    """按 claim 的书写精度比对:声明 0.077,则比到小数点后 3 位。
    避免因四舍五入导致的假阴性,也避免用过松的容差放过捏造。"""
    if "." in claimed_str:
        nd = len(claimed_str.split(".")[1])
        return abs(round(computed, nd) - float(claimed_str)) < 10 ** (-nd) / 2 + 1e-12
    return _close(float(claimed_str), computed)

def verify_explicit(derivation: str, claimed: str, symbols: dict[str, float]) -> tuple[bool, float | None, str]:
    """校验显式推导式。返回 (是否成立, 计算值, 说明)。"""
    try:
        got = safe_eval(derivation, symbols)
    except UnsafeExpression as e:
        return False, None, f"推导式被拒:{e}"
    except Exception as e:
        return False, None, f"推导式求值失败:{type(e).__name__}"
    return (_round_trip(claimed, got), got, "")

# ---- 有界推导发现 ----
# 只搜索**科学上有意义**的算子,不做通用符号回归 —— 后者会把噪声拟合成"证据"。
_BINARY = [
    ("{a} - {b}",              lambda a, b: a - b),
    ("{a} + {b}",              lambda a, b: a + b),
    ("{a} / {b}",              lambda a, b: a / b if b else float("nan")),
    ("{a} * {b}",              lambda a, b: a * b),
    ("({a} - {b}) / {b} * 100", lambda a, b: (a - b) / b * 100 if b else float("nan")),  # 相对提升 %
    ("({a} - {b}) / {b}",      lambda a, b: (a - b) / b if b else float("nan")),
    ("{a} / {b} * 100",        lambda a, b: a / b * 100 if b else float("nan")),
]
# 精度守则:位数太少的数(如 "2"、"0.5")容易被巧合命中,不接受自动发现的推导。
_MIN_PRECISION = 2   # 小数点后至少 2 位

def discover(claimed: str, symbols: dict[str, float]) -> tuple[str, float] | None:
    """在有界算子空间里找能复现该值的推导式。返回 (表达式, 计算值) 或 None。

    刻意保守:
      - 只用上面 7 个有物理/统计意义的算子,不做通用符号回归;
      - 只在日志具名量之间搜索(不引入任意常数);
      - 声明值精度不足(< _MIN_PRECISION 位小数)时直接放弃,避免巧合命中。
    """
    if "." not in claimed or len(claimed.split(".")[1]) < _MIN_PRECISION:
        return None
    names = list(symbols)
    if len(names) < 2:
        return None
    for na, nb in permutations(names, 2):
        a, b = symbols[na], symbols[nb]
        for tmpl, fn in _BINARY:
            expr = tmpl.format(a=na, b=nb)
            # ★ R4:量纲先剪枝 —— 物理上不可能的组合根本不进入候选,
            #    而不是先自由拟合再事后过滤。这就是"用物理硬约束重塑偏好"。
            ok, _ = dims.check_expression(expr, symbols)
            if not ok:
                continue
            try:
                got = fn(a, b)
            except Exception:
                continue
            if got != got or math.isinf(got):     # NaN / inf
                continue
            if _round_trip(claimed, got):
                return expr, got
    return None

def fingerprint(expr: str, value: float) -> str:
    return "sha256:" + hashlib.sha256(f"{expr}={value}".encode()).hexdigest()[:16]
