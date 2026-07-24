"""量纲与取值域一致性(R4)—— 第一个**与索引无关**的物理约束。

前三层校验(arXiv / DOI / OpenAlex / 推导重算)都依赖外部证据基质:
要么查登记处,要么读运行日志。它们回答的是「有没有人记录过」。

量纲不同。它回答的是「这在物理上可能吗」——不查任何数据库:
    准确率 + 耗时        量纲不可加     -> 世界不允许
    准确率 = 1.35        超出取值域     -> 世界不允许
    步数 = -3            计数为负       -> 世界不允许

因此量纲违反属于 **fabrication(确证矛盾)**,而非 verification_gap(我看不到)。
这是「可达性回归物理」的第一步:裁判第一次完全不依赖书目学。

同时它反向重塑提议器:推导发现的搜索空间先被量纲剪枝,
不合量纲的组合根本不会被提出 —— 即「用物理硬约束重塑偏好」,
而不是先自由拟合、再事后过滤。
"""
from __future__ import annotations
import ast, re

# ---- 基本量纲:指数向量 (time, bytes, count) ----
# 无量纲 = 全零。ML/CS 场景足够;扩到化学/生物时再加 (length, mass, amount…)。
BASE = ("time", "bytes", "count")
DIMENSIONLESS = (0, 0, 0)
TIME  = (1, 0, 0)
BYTES = (0, 1, 0)
COUNT = (0, 0, 1)

# ---- 取值域语义(比量纲更细,但同样是物理约束)----
# bounded: (下界, 上界) 或 None
_SEMANTICS = {
    "probability": {"dim": DIMENSIONLESS, "bounds": (0.0, 1.0)},
    "percentage":  {"dim": DIMENSIONLESS, "bounds": (None, None)},   # 变化率可为负/超百
    "count":       {"dim": COUNT,         "bounds": (0.0, None)},
    "duration":    {"dim": TIME,          "bounds": (0.0, None)},
    "memory":      {"dim": BYTES,         "bounds": (0.0, None)},
    "loss":        {"dim": DIMENSIONLESS, "bounds": (0.0, None)},
    "plain":       {"dim": DIMENSIONLESS, "bounds": (None, None)},
    # ★ 未知 ≠ 无量纲。命名无法辨识时必须承认"我不知道",
    #   而不是默认它无量纲 —— 后者会把推断错误伪装成物理结论。
    "unknown":     {"dim": None,          "bounds": (None, None)},
}

# ---- 由符号名推断语义(命名约定;未知则退化为 plain,不做武断判定)----
_B0, _B1 = r"(?:^|[\s_])", r"(?:$|[\s_])"
_RULES = [
    (_B0 + r"(accuracy|precision|recall|auc|f1|probability|ratio|fraction|acc|prob|frac)" + _B1, "probability"),
    (_B0 + r"(pct|percent|percentage|improvement|gain)" + _B1, "percentage"),
    (_B0 + r"(epoch|epochs|step|steps|iter|iters|iteration|count|num|seed|batch|samples)" + _B1, "count"),
    (_B0 + r"(s|sec|secs|second|seconds|ms|latency|duration|time|elapsed|runtime)" + _B1, "duration"),
    (_B0 + r"(mb|gb|kb|bytes|mem|memory|vram|ram)" + _B1, "memory"),
    (_B0 + r"(loss|nll|mse|rmse|mae|perplexity|ppl)" + _B1, "loss"),
]

def infer_semantic(name: str) -> str:
    """由名称/文本推断语义。

    ★ 歧义即未知。若命中多个互不相同的语义(如 "accuracy improvement of 12.4%"
    同时命中 probability 与 percentage),必须返回 unknown —— 因为我们**确实**
    分不清这个数说的是哪一个。武断选一个,就会把合法的 12.4% 提升判成
    「概率超过 1,物理不可能」—— 把"我误解了"当成"世界不允许"。

    唯一的消歧信号是显式单位标记(如紧跟的 %),那是作者写下的事实,不是我们的猜测。
    """
    n = name.lower()
    hits = {sem for pat, sem in _RULES if re.search(pat, n)}
    if not hits:
        return "unknown"
    if len(hits) == 1:
        return hits.pop()
    # 多语义命中 = 歧义。仅当存在显式单位标记时才消歧。
    if "%" in n and "percentage" in hits:
        return "percentage"
    return "unknown"

def dim_of(name: str) -> tuple[int, int, int]:
    return _SEMANTICS[infer_semantic(name)]["dim"]

def _fmt(d) -> str:
    if d is None:
        return "未知量纲"
    if d == DIMENSIONLESS:
        return "无量纲"
    parts = [f"{b}^{e}" for b, e in zip(BASE, d) if e]
    return "·".join(parts)

class DimensionError(ValueError):
    pass

# ---- 表达式量纲传播 ----
def dim_of_expr(expr: str, symbols: dict[str, float]) -> tuple[int, int, int]:
    """沿 AST 传播量纲。加减要求同量纲;乘除做指数加减;幂只允许常数指数。
    违反即抛 DimensionError —— 这是物理否定,不是「查不到」。"""
    tree = ast.parse(expr, mode="eval")

    def walk(n) -> tuple[int, int, int]:
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant):
            return DIMENSIONLESS                      # 纯数字无量纲
        if isinstance(n, ast.Name):
            if n.id not in symbols:
                raise DimensionError(f"未知符号 {n.id}")
            return dim_of(n.id)   # 可能是 None(语义无法辨识)
        if isinstance(n, ast.UnaryOp):
            return walk(n.operand)
        if isinstance(n, ast.BinOp):
            l, r = walk(n.left), walk(n.right)
            if isinstance(n.op, (ast.Add, ast.Sub)):
                # ★ 只有两侧都能被自信辨识、且确实不同,才宣告物理违反。
                #   任一侧未知 -> 承认判断不了,返回未知,而不是假装它无量纲。
                if l is None or r is None:
                    return None
                if l != r:
                    raise DimensionError(
                        f"量纲不可加减:{_fmt(l)} 与 {_fmt(r)} —— 物理上不允许")
                return l
            if l is None or r is None:
                return None
            if isinstance(n.op, ast.Mult):
                return tuple(a + b for a, b in zip(l, r))
            if isinstance(n.op, ast.Div):
                return tuple(a - b for a, b in zip(l, r))
            if isinstance(n.op, ast.Pow):
                if not isinstance(n.right, ast.Constant):
                    raise DimensionError("幂指数必须是常数")
                e = int(n.right.value)
                return tuple(a * e for a in l)
            if isinstance(n.op, ast.Mod):
                return l
        raise DimensionError(f"不支持的语法节点 {type(n).__name__}")

    return walk(tree)

def check_expression(expr: str, symbols: dict[str, float]) -> tuple[bool, str]:
    """返回 (是否量纲自洽, 说明)。"""
    try:
        dim_of_expr(expr, symbols)
        return True, ""
    except DimensionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"量纲分析失败:{type(e).__name__}"

# ---- 取值域检查 ----
def check_value(name_or_text: str, value: float) -> tuple[bool, str]:
    """按语义检查取值域。只标记**物理上不可能**的值。
    语义无法辨识时返回 (True, "") —— 承认判断不了,而非默许或武断否定。"""
    sem = infer_semantic(name_or_text)
    if sem == "unknown":
        return True, ""
    lo, hi = _SEMANTICS[sem]["bounds"]
    if lo is not None and value < lo:
        return False, f"{sem} 不能为 {value}(下界 {lo})—— 物理上不可能"
    if hi is not None and value > hi:
        return False, f"{sem} 不能为 {value}(上界 {hi})—— 物理上不可能"
    return True, ""

def describe(name: str) -> str:
    sem = infer_semantic(name)
    return f"{name}: {sem} [{_fmt(_SEMANTICS[sem]['dim'])}]"
