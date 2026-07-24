"""可达性度量(R0)—— 让"护城河变牢笼"可观测。

只报「拦截率下降」是危险的:它无法区分
    (A) 系统学会了不再捏造          —— 真进步
    (B) 系统学会了绕开难校验的区域  —— 可达性坍缩
因此拦截率必须与一组对偶量同时读:

    拦截率↓ + 可达率持平/上升  = 真的学会了
    拦截率↓ + 可达率↓          = 牢笼

三个核心量:
  false_rejection_rate : 在「已知有效但难校验」回归集上被判 reject(捏造)的比例。
                         这是最危险的错误 —— 把「我看不到」误判成「世界不允许」。
  coverage_ratio       : 论断中能被任一证据基质解析的比例(承认覆盖率,而非假装全知)。
  novel_claims_signed  : 署名产出中不依赖既有文献支撑的论断占比。
                         若趋于 0,系统已退化为查重器,而非发现引擎。
"""
from __future__ import annotations


def reachability_metrics(reports: list[dict], labels: dict[str, str] | None = None) -> dict:
    """labels: claim_id -> 'valid' | 'fabricated'(回归集的真值标注)。
    未标注的 claim 不计入 false_rejection_rate。"""
    labels = labels or {}
    claims = [c for r in reports for c in r.get("claims", [])]
    if not claims:
        return {"n_claims": 0}

    n = lambda **kw: sum(1 for c in claims if all(c.get(k) == v for k, v in kw.items()))
    total = len(claims)

    # 已知有效却被判"捏造" —— 把盲区当成世界的边界
    known_valid = [c for c in claims if labels.get(c["id"]) == "valid"]
    false_rej = [c for c in known_valid if c["status"] == "reject"]
    # 已知捏造却放行 —— 反向失败(署名保证被破坏)
    known_fake = [c for c in claims if labels.get(c["id"]) == "fabricated"]
    missed = [c for c in known_fake if c["status"] == "pass"]

    resolved = n(status="pass")
    unresolved = n(status="unresolved")
    novel = sum(1 for c in claims
                if c.get("status") == "pass"
                and (c.get("evidence_chain") or {}).get("kind") in ("log", "derivation"))

    return {
        "n_claims": total,
        # —— 可达性(越高越好)——
        "coverage_ratio": round(resolved / total, 3),
        "unresolved_ratio": round(unresolved / total, 3),
        "novel_claims_signed": round(novel / max(1, resolved), 3),
        # —— 误判(越低越好)——
        "false_rejection_rate": round(len(false_rej) / len(known_valid), 3) if known_valid else None,
        "missed_fabrication_rate": round(len(missed) / len(known_fake), 3) if known_fake else None,
        # —— 明细,便于定位 ——
        "false_rejections": [c["id"] for c in false_rej],
        "missed_fabrications": [c["id"] for c in missed],
        "by_failure_kind": {
            "fabrication": n(failure_kind="fabrication"),
            "verification_gap": n(failure_kind="verification_gap"),
        },
    }


def flywheel_health(interception_curve: list[int], coverage_curve: list[float],
                    exploration_curve: list[float] | None = None) -> dict:
    """三条曲线并读,判断飞轮是在学习还是在收窄。

        拦截率↓ + 可达率持平/↑ + 探索率持平/↑   = learning     真的学会了
        拦截率↓ + 可达率↓                        = narrowing    ⚠ 绕开难校验区域
        拦截率↓ + 可达率持平 + 探索率↓            = conservative ⚠ 只敢走熟路

    第三种最隐蔽:各项校验指标都好看,但系统已经不再提出低先验假设 ——
    退化成一台安全的平庸机器。只看前两条曲线是发现不了的。
    """
    if len(interception_curve) < 2 or len(coverage_curve) < 2:
        return {"verdict": "insufficient_data"}
    d_intercept = interception_curve[-1] - interception_curve[0]
    d_coverage = coverage_curve[-1] - coverage_curve[0]
    d_explore = (exploration_curve[-1] - exploration_curve[0]) if exploration_curve and len(exploration_curve) >= 2 else None

    if d_intercept >= 0:
        verdict, note = "no_progress", "拦截率未下降 —— 飞轮尚未生效"
    elif d_coverage < -0.01:
        verdict, note = "narrowing", "⚠ 拦截率下降但可达率同时下降 —— 疑似牢笼:系统可能在绕开难校验区域"
    elif d_explore is not None and d_explore < -0.05:
        verdict, note = "conservative", "⚠ 校验指标好看但探索率下降 —— 系统只敢走熟路,正在退化为平庸"
    else:
        verdict, note = "learning", "拦截率下降,可达率与探索率未收窄 —— 飞轮在真正学习"

    out = {"verdict": verdict, "note": note,
           "delta_interception": d_intercept, "delta_coverage": round(d_coverage, 3)}
    if d_explore is not None:
        out["delta_exploration"] = round(d_explore, 3)
    return out
