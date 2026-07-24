"""化学领域物理可达性(R6)。

R4 的量纲检查是**跨领域**的浅层物理约束。R6 要的是**领域内的深层约束**:
一个分子式是否可能存在、一个反应是否守恒 —— 这些由化学规律决定,
与任何数据库是否收录过它无关。

本模块分两层:
  零依赖层(始终可用):分子式解析、原子守恒(质量守恒定律)、不饱和度
  可选层(装了 RDKit 才有):SMILES 解析、价键合法性、结构可净化性

★ 纪律不变:装不了解析器 = **判断不了**,不是"不可能"。
  能力缺失绝不冒充物理结论 —— 否则又回到「把我看不见的当成世界不允许的」。
"""
from __future__ import annotations
import re
from collections import Counter

# ---- 零依赖:分子式 ----
_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)")
_FORMULA_OK = re.compile(r"^([A-Z][a-z]?\d*)+$")

def parse_formula(f: str) -> Counter | None:
    """解析分子式 C6H12O6 -> {C:6, H:12, O:6}。无法解析返回 None(不是"非法")。"""
    f = (f or "").strip()
    if not f or not _FORMULA_OK.match(f):
        return None
    atoms = Counter()
    for el, n in _TOKEN.findall(f):
        if el:
            atoms[el] += int(n) if n else 1
    return atoms or None

# 标准价态(仅用于不饱和度判据;超出此集合则不下断言)
_DOU_ELEMENTS = {"C", "H", "N", "O", "F", "Cl", "Br", "I"}
_HALOGENS = {"F", "Cl", "Br", "I"}

def degree_of_unsaturation(atoms: Counter) -> float | None:
    """不饱和度 DoU = (2C + 2 + N - H - X) / 2。
    仅当分子式只含 C/H/N/O/卤素时适用;否则返回 None(判断不了)。"""
    if not atoms or not set(atoms) <= _DOU_ELEMENTS:
        return None
    c = atoms.get("C", 0); h = atoms.get("H", 0); n = atoms.get("N", 0)
    x = sum(atoms.get(e, 0) for e in _HALOGENS)
    return (2 * c + 2 + n - h - x) / 2

def check_formula(f: str) -> tuple[str, str]:
    """返回 (verdict, why)。verdict ∈ impossible | plausible | unknown。

    DoU < 0  -> 氢原子多于骨架所能承载 —— 物理上不可能,任何数据库都改变不了。
    DoU 非整 -> 自由基/离子,**不判为不可能**(它们真实存在),标记待人工确认。
    """
    atoms = parse_formula(f)
    if atoms is None:
        return "unknown", "无法解析为分子式"
    dou = degree_of_unsaturation(atoms)
    if dou is None:
        return "unknown", "含非 C/H/N/O/卤素元素,不饱和度判据不适用"
    if dou < 0:
        return "impossible", f"不饱和度 {dou} < 0:氢原子数超过骨架承载上限 —— 物理上不可能"
    if dou != int(dou):
        return "plausible", f"不饱和度 {dou} 为半整数,提示自由基或离子(非不可能,建议人工确认)"
    return "plausible", f"不饱和度 {int(dou)},分子式自洽"

# ---- 零依赖:反应原子守恒(质量守恒定律)----
_ARROW = re.compile(r"->|=>|→|⟶|=")

def parse_reaction(eq: str) -> tuple[Counter, Counter] | None:
    """解析 '2H2 + O2 -> 2H2O',返回 (左侧原子计数, 右侧原子计数)。"""
    if not eq or not _ARROW.search(eq):
        return None
    left, right = _ARROW.split(eq, 1)

    def side(s: str) -> Counter | None:
        total = Counter()
        for term in s.split("+"):
            term = term.strip()
            if not term:
                return None
            m = re.match(r"^(\d+)?\s*([A-Za-z0-9]+)$", term)
            if not m:
                return None
            coef = int(m.group(1)) if m.group(1) else 1
            atoms = parse_formula(m.group(2))
            if atoms is None:
                return None
            for el, n in atoms.items():
                total[el] += coef * n
        return total

    l, r = side(left), side(right)
    if l is None or r is None:
        return None
    return l, r

def check_reaction(eq: str) -> tuple[str, str]:
    """原子守恒检查 —— 这是**质量守恒定律**,不是统计偏好,也不需要查任何数据库。"""
    parsed = parse_reaction(eq)
    if parsed is None:
        return "unknown", "无法解析为化学反应式"
    l, r = parsed
    if l == r:
        return "plausible", "原子守恒成立"
    diff = {el: l.get(el, 0) - r.get(el, 0) for el in set(l) | set(r) if l.get(el, 0) != r.get(el, 0)}
    return "impossible", f"原子不守恒 {diff} —— 违反质量守恒定律,物理上不可能"

# ---- 可选层:RDKit ----
def _rdkit():
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        return Chem
    except Exception:
        return None

def rdkit_available() -> bool:
    return _rdkit() is not None

def check_smiles(smiles: str) -> tuple[str, str]:
    """SMILES 价键合法性。未装 RDKit 时返回 unknown —— 能力缺失不冒充物理结论。"""
    Chem = _rdkit()
    if Chem is None:
        return "unknown", "未安装 RDKit,无法判定价键合法性(能力缺失,非物理结论)"
    if not smiles or not smiles.strip():
        return "unknown", "空 SMILES"
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return "unknown", "SMILES 语法无法解析(可能是书写问题,非必然不可能)"
    try:
        Chem.SanitizeMol(mol)
    except Exception as e:
        return "impossible", f"价键不合法:{str(e)[:80]} —— 该结构不可能存在"
    return "plausible", f"价键合法,原子数 {mol.GetNumAtoms()}"

# ---- 从自由文本中发现化学对象 ----
_FORMULA_IN_TEXT = re.compile(r"\b((?:[A-Z][a-z]?\d*){2,})\b")
_ARROW_IN_TEXT = re.compile(r"->|=>|→|⟶")
_SPECIES = re.compile(r"^\d*[A-Z][A-Za-z0-9]*$")

def _collect_side(tokens: list[str], reverse: bool = False) -> list[str]:
    """从箭头向一侧收集连续的化学物种 token(用 + 连接),遇到非化学词即停。
    这样 'the pathway 2H2 + O2 -> 2H2O' 只取到 '2H2 + O2',不会把英文吞进来。"""
    seq = list(reversed(tokens)) if reverse else tokens
    picked, expect_species = [], True
    for raw in seq:
        tok = raw.strip(".,;:!?()[]{}\u3002\uff0c\uff1b\uff1a")   # 剥离中英标点,否则 "2H2O." 会漏判
        if not tok:
            break
        if expect_species:
            if not _SPECIES.match(tok) or parse_formula(re.sub(r"^\d+", "", tok)) is None:
                break
            picked.append(tok); expect_species = False
        else:
            if tok != "+":
                break
            picked.append(tok); expect_species = True
    if picked and picked[-1] == "+":
        picked.pop()
    return list(reversed(picked)) if reverse else picked

def find_claims(text: str) -> list[dict]:
    """从文本中找出可判定的化学对象。保守:宁可漏,不可把普通词当分子式。"""
    out = []
    txt = text or ""
    for m in _ARROW_IN_TEXT.finditer(txt):
        left_toks = txt[:m.start()].replace("+", " + ").split()
        right_toks = txt[m.end():].replace("+", " + ").split()
        lhs = _collect_side(left_toks, reverse=True)
        rhs = _collect_side(right_toks, reverse=False)
        if not lhs or not rhs:
            continue
        eq = " ".join(lhs) + " -> " + " ".join(rhs)
        if parse_reaction(eq):
            out.append({"kind": "reaction", "expr": eq})
    seen_in_rx = " ".join(o["expr"] for o in out)
    for m in _FORMULA_IN_TEXT.finditer(txt):
        f = m.group(1)
        if len(f) >= 3 and parse_formula(f) and any(ch.isdigit() for ch in f):
            if f not in seen_in_rx and not any(f == o["expr"] for o in out):
                out.append({"kind": "formula", "expr": f})
    return out
