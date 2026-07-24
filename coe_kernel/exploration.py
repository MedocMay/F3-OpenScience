"""探索预算(R5)—— 主动探测「世界允许但模型不喜欢」的区域。

问题:生成器天然走高概率路径。飞轮(即使已按 R2 只注入捏造类)仍会强化这一倾向,
因为通过校验的模式会被反复复用。长期结果是产出越来越安全、也越来越平庸 ——
低概率但物理上允许的稀有事件(相变成核、罕见构象、全新骨架)恰恰是突破所在,
却系统性地不被提出。

对策:**给探索留出强制配额**,并把它变成可测量的量。

设计要点:
  1. 配额是**下限**而非上限:低先验假设至少占 EXPLORATION_RATIO。
  2. 探索不降低证据标准 —— 低先验假设同样要过 R3/R4 的计算与物理裁判。
     鼓励探索而不设物理裁判,只会放大噪声。
  3. 探索率与拦截率、可达率并读:三者共同判断飞轮是在学习还是在收窄。
"""
from __future__ import annotations
import os

def budget() -> float:
    """低先验假设的最低占比。可由 OPENSCI_EXPLORATION_RATIO 调整。"""
    try:
        v = float(os.environ.get("OPENSCI_EXPLORATION_RATIO", "0.3"))
    except ValueError:
        v = 0.3
    return min(max(v, 0.0), 1.0)

def allocate(candidates: list[dict], ratio: float | None = None) -> list[dict]:
    """按探索预算挑选候选。candidates 每项需带 prior: 'high' | 'low'。

    返回的列表满足:低先验项占比 >= ratio(若候选池中有足够的低先验项)。
    不足时**不伪造**探索项,只如实返回并由 measure() 报告实际达成率。
    """
    ratio = budget() if ratio is None else ratio
    if not candidates:
        return []
    low = [c for c in candidates if c.get("prior") == "low"]
    high = [c for c in candidates if c.get("prior") != "low"]
    n = len(candidates)
    need_low = int(round(n * ratio))
    take_low = low[:need_low]
    take_high = high[: n - len(take_low)]
    out = take_high + take_low
    for c in out:
        c["exploration_selected"] = c.get("prior") == "low"
    return out

def measure(selected: list[dict]) -> dict:
    """实际达成的探索率,以及是否满足预算。"""
    if not selected:
        return {"exploration_rate": 0.0, "budget": budget(), "met": False, "n": 0}
    low = sum(1 for c in selected if c.get("prior") == "low")
    rate = round(low / len(selected), 3)
    return {"exploration_rate": rate, "budget": budget(),
            "met": rate + 1e-9 >= budget(), "n": len(selected), "n_low_prior": low}
