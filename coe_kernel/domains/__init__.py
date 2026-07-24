"""领域物理可达性(R6)—— 可插拔的领域约束层。

设计:核心保持零依赖;领域约束按需启用,缺失时**承认判断不了**。
当前实现 chemistry;biology / materials 可按同一接口扩展。
"""
from . import chemistry

REGISTRY = {"chemistry": chemistry}

def available_domains() -> dict[str, bool]:
    return {"chemistry": True, "chemistry_smiles": chemistry.rdkit_available()}

def check(domain: str, text: str) -> list[dict]:
    """对文本做领域物理检查,返回逐项判定。"""
    mod = REGISTRY.get(domain)
    if mod is None:
        return []
    results = []
    for c in mod.find_claims(text):
        if c["kind"] == "reaction":
            v, why = mod.check_reaction(c["expr"])
        else:
            v, why = mod.check_formula(c["expr"])
        results.append({**c, "verdict": v, "why": why})
    return results
