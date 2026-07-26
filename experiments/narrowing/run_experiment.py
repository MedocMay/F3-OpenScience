#!/usr/bin/env python3
"""Does conflating "cannot verify" with "wrong" narrow the reachable space?

把「无法核验」等同于「错误」,是否会收窄可达空间?

────────────────────────────────────────────────────────────────────────
WHAT THIS TESTS · 测什么
────────────────────────────────────────────────────────────────────────
Two arms, identical except for one line of policy:

    ARM A  (conflating)   every verification failure becomes a generation
                          constraint — the prevailing practice
    ARM B  (separated)    only *confirmed fabrication* becomes a constraint;
                          coverage gaps become a capability backlog

两组,除一行策略外完全相同:
    A 组(混同)   所有校验失败都写回生成约束 —— 主流做法
    B 组(分离)   只有「确证捏造」写回;覆盖缺口转为能力待办

We measure three curves per round: interception rate, reachability, and
retention of valid-but-hard-to-verify claims.

────────────────────────────────────────────────────────────────────────
WHAT IS REAL, WHAT IS MODELLED · 什么是真的,什么是建模的
────────────────────────────────────────────────────────────────────────
REAL      Verification. Every claim is checked against live arXiv /
          CrossRef / DataCite / OpenAlex through the project's own kernel.
          Which claims are "hard to verify" is determined by those services,
          not by our labels.
          校验是真的。哪些论断难以核验由真实服务决定,不是我们标的。

MODELLED  The generator. It is a stand-in with exactly one modelled
          property: it does not propose claims matching its constraint set.
          This mirrors `pipeline.hypothesize(guard=True)`, which pre-verifies
          and drops claims that would fail.
          生成器是替身,只建模一个属性:不提出匹配约束集的论断。
          这与 pipeline.hypothesize(guard=True) 的行为一致。

────────────────────────────────────────────────────────────────────────
WHAT THIS DOES **NOT** SHOW · 这个实验**不能**证明什么
────────────────────────────────────────────────────────────────────────
It does not show that a real LLM behaves this way. The generator here has
no learning dynamics, no distributional shift, no in-context effects.

它不能证明真实 LLM 会这样。这里的生成器没有学习动力学、没有分布漂移、
没有上下文效应。

What it does show is the *mechanism* and its *magnitude under a stated
model*: how much reachable space is lost when the constraint set is drawn
from all failures rather than from confirmed fabrication only — and,
importantly, that the interception-rate curve looks the same either way.

它展示的是**机制**及其**在给定生成器模型下的量级**:
当约束集取自「所有失败」而非「仅确证捏造」时,可达空间损失多少 ——
以及,拦截率曲线在两种情况下长得一模一样。

To make the stronger empirical claim, swap the stand-in for a real model
(see --generator llm, requires an API key) and re-run.
要做更强的实证主张,请把替身换成真实模型(--generator llm)后重跑。

────────────────────────────────────────────────────────────────────────
Usage
    python3 experiments/narrowing/run_experiment.py
    python3 experiments/narrowing/run_experiment.py --rounds 8 --k 6
    python3 experiments/narrowing/run_experiment.py --granularity fine
"""
from __future__ import annotations
import argparse, json, os, random, sys, csv
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from coe_kernel import verify as V           # real verifier · 真实校验器


# ── policy: which failures may constrain generation ──────────────────
ARMS = {
    "A_conflating": {
        "label": "ARM A · conflating (prevailing practice)",
        "label_zh": "A 组 · 混同(主流做法)",
        # every failure writes back
        "constrains": lambda failure_kind: True,
    },
    "B_separated": {
        "label": "ARM B · separated (only fabrication constrains)",
        "label_zh": "B 组 · 分离(只有捏造约束生成)",
        # only confirmed fabrication writes back
        "constrains": lambda failure_kind: failure_kind == "fabrication",
    },
}


def verdict_of(claim: dict, cache: dict) -> tuple[str, str | None]:
    """Verify a claim for real. Cached so repeated rounds don't hammer the APIs.
    真实校验。带缓存,避免多轮打爆外部 API。"""
    cid = claim["id"]
    if cid not in cache:
        r = V.verify_citation(claim)
        cache[cid] = (r["status"], r.get("failure_kind"))
    return cache[cid]


def pattern_of(claim: dict, status: str, failure_kind: str | None) -> str | None:
    """Abstract a failure into a reusable pattern — mirrors memory.store.distill().

    把失败抽象成可复用模式 —— 与 memory.store.distill() 一致。

    One pattern per failure class — this is what the real distill() produces.
    每个失败类别一个模式 —— 这是真实 distill() 的行为。
    """
    if status == "pass":
        return None
    if status == "manual":
        # transport failure: no conclusion at all. Not a claim about the world,
        # not an index gap. 传输失败:根本没结论。既非世界判断,也非索引缺口。
        return None
    return "NONEXISTENT_CITATION" if failure_kind == "fabrication" else "UNINDEXED_CITATION"


def matches_constraint(claim: dict, constraints: set[str], cache: dict) -> bool:
    """Would the guard suppress this claim? Mirrors hypothesize(guard=True):
    pre-verify, and drop anything whose resulting pattern is already known-bad.

    guard 会不会压掉这条论断?与 hypothesize(guard=True) 一致:
    先预核验,若得到的模式已在约束集中则丢弃。
    """
    if not constraints:
        return False
    status, fk = verdict_of(claim, cache)
    pat = pattern_of(claim, status, fk)
    return pat is not None and pat in constraints


def run_arm(arm_key: str, pool: list[dict], rounds: int, k: int,
            seed: int, cache: dict) -> list[dict]:
    arm = ARMS[arm_key]
    rng = random.Random(seed)
    constraints: set[str] = set()
    backlog: set[str] = set()
    history = []

    valid_ids = {c["id"] for c in pool if c["class"].startswith("valid")}
    hard_ids = {c["id"] for c in pool if c["class"] == "valid_hard"}

    # round 0 — the unconstrained baseline. Narrowing must be measured against
    # THIS, not against round 1: the constraint set is already populated by the
    # time round 1 is scored, so a round-1→N delta hides the entire effect.
    # 第 0 轮 —— 无约束基线。收窄必须相对它来量,而不是相对第 1 轮:
    # 第 1 轮记分时约束集已经建立,用 1→N 的差值会把整个效应藏起来。
    history.append({
        "round": 0, "proposed": 0, "intercepted": 0, "interception_rate": 0.0,
        "reachability": 1.0, "hard_retained": 1.0, "constraints": 0, "backlog": 0,
    })

    for rnd in range(1, rounds + 1):
        # generator proposes k claims it is not forbidden from proposing
        # 生成器提出 k 条未被禁止的论断
        allowed = [c for c in pool if not matches_constraint(c, constraints, cache)]
        proposed = rng.sample(allowed, min(k, len(allowed))) if allowed else []

        intercepted = 0
        passed_valid, passed_hard = set(), set()
        for c in proposed:
            status, fk = verdict_of(c, cache)
            if status == "pass":
                if c["id"] in valid_ids: passed_valid.add(c["id"])
                if c["id"] in hard_ids: passed_hard.add(c["id"])
                continue
            if status == "manual":
                continue          # unreachable · 不可触达,不构成观测
            intercepted += 1
            pat = pattern_of(c, status, fk)
            if pat is None:
                continue
            if arm["constrains"](fk):
                constraints.add(pat)          # becomes a generation constraint
            else:
                backlog.add(pat)              # becomes a capability-building need

        # reachability: of all legitimate claims, how many can the system still
        # both propose and get through?  可达率:合法论断中仍能被提出并通过的比例
        reachable = [c for c in pool
                     if c["class"].startswith("valid")
                     and not matches_constraint(c, constraints, cache)]
        reach_hard = [c for c in reachable if c["class"] == "valid_hard"]

        history.append({
            "round": rnd,
            "proposed": len(proposed),
            "intercepted": intercepted,
            "interception_rate": round(intercepted / len(proposed), 3) if proposed else 0.0,
            "reachability": round(len(reachable) / len(valid_ids), 3),
            "hard_retained": round(len(reach_hard) / len(hard_ids), 3) if hard_ids else 0.0,
            "constraints": len(constraints),
            "backlog": len(backlog),
        })
    return history


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--k", type=int, default=8, help="claims proposed per round")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--control", action="store_true",
                    help="CONTROL CONDITION: drop all valid_hard claims from the pool. "
                         "With nothing valid that is hard to verify, ARM A has nothing to "
                         "lose and must NOT narrow. If it still does, the harness is broken. "
                         "对照条件:剔除全部 valid_hard。此时 A 组无可失去,不应收窄。")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.out is None:
        args.out = os.path.join(HERE, "results_control.csv" if args.control
                                else "results_main.csv")

    pool = json.load(open(os.path.join(HERE, "claim_pool.json")))["claims"]
    if args.control:
        pool = [c for c in pool if c["class"] != "valid_hard"]
        print("CONTROL CONDITION · 对照条件: valid_hard removed from the pool.")
        print("ARM A should show no narrowing. 若 A 组仍收窄,说明装置有问题。\n")

    # ── verify the pool once, and report what the REAL services said ──
    print("Verifying the claim pool against live APIs … 用真实 API 核验论断池 …\n")
    cache: dict = {}
    obs = Counter()
    for c in pool:
        status, fk = verdict_of(c, cache)
        obs[(c["class"], status)] += 1
    print("  ground-truth class → verdict the real services returned")
    print("  真值类别 → 真实服务给出的判定")
    for (cls, status), n in sorted(obs.items()):
        print(f"    {cls:12s} → {status:11s} ×{n}")

    hard_unresolved = obs[("valid_hard", "unresolved")]
    hard_manual = obs[("valid_hard", "manual")]
    fab_reject = obs[("fabricated", "reject")]
    fab_total = sum(n for (c, _), n in obs.items() if c == "fabricated")
    easy_unres = obs[("valid_easy", "unresolved")]
    problems = []
    if not args.control and hard_unresolved < 3:
        problems.append(f"valid_hard->unresolved x{hard_unresolved} (need >=3), "
                        f"manual x{hard_manual}: transport failure, not index gap. "
                        f"\u4f20\u8f93\u5931\u8d25\u975e\u7d22\u5f15\u7f3a\u53e3")
    if fab_reject < fab_total:
        problems.append(f"fabricated->reject x{fab_reject} of {fab_total}: the rest "
                        f"were never confirmed as fabrication. "
                        f"\u5176\u4f59\u637f\u9020\u672a\u88ab\u786e\u8ba4")
    if easy_unres:
        problems.append(f"valid_easy->unresolved x{easy_unres}: flaky index or wrong "
                        f"pool label. \u7d22\u5f15\u4e0d\u7a33\u6216\u6c60\u5b50\u6807\u9519")
    eligible = not problems
    if not eligible:
        for _p in problems:
            print(f"      . {_p}")
        print(f"\n  ⚠️  ENVIRONMENT NOT ELIGIBLE · 环境不适格")
        print(f"      valid_hard → unresolved ×{hard_unresolved}, manual ×{hard_manual}")
        print("      'manual' means the verifier could not reach a conclusion at all —")
        print("      typically the index API rate-limited this IP (HTTP 429). That is")
        print("      'I cannot see' of a *different kind*: not an index gap but a")
        print("      transport failure. The arms cannot be cleanly distinguished here.")
        print("      'manual' 表示校验器根本无法得出结论 —— 通常是索引 API 对本机限流。")
        print("      这是**另一种**「我看不到」:不是索引缺口,而是传输失败。")
        print("      此环境下两组无法干净区分。")
        print()
        print("      Fix: run from a network the index API does not throttle, or")
        print("      supply an OpenAlex mailto/API key. 换一个不被限流的网络重跑。")
        print("      Results below are reported anyway, marked NOT ELIGIBLE.")
        print("      下方结果照常输出,但标记为不适格。")

    # ── run both arms ────────────────────────────────────────────────
    print(f"\nRunning {args.rounds} rounds × {args.k} claims\n")
    results = {}
    for key in ARMS:
        results[key] = run_arm(key, pool, args.rounds, args.k, args.seed, cache)

    # ── report ───────────────────────────────────────────────────────
    for key, hist in results.items():
        print(f"── {ARMS[key]['label']}")
        print(f"   {ARMS[key]['label_zh']}")
        print(f"   {'round':>5} {'intercept':>10} {'reachability':>13} {'hard kept':>10} "
              f"{'constraints':>12} {'backlog':>8}")
        for h in hist:
            print(f"   {h['round']:>5} {h['interception_rate']:>10.2f} {h['reachability']:>13.2f} "
                  f"{h['hard_retained']:>10.2f} {h['constraints']:>12} {h['backlog']:>8}")
        print()

    # ── verdict ──────────────────────────────────────────────────────
    a, b = results["A_conflating"], results["B_separated"]
    # measure against the round-0 baseline · 相对第 0 轮基线测量
    d_reach_a = a[-1]["reachability"] - a[0]["reachability"]
    d_reach_b = b[-1]["reachability"] - b[0]["reachability"]
    # interception is compared between arms at steady state, not over time
    # 拦截率在稳态下做**组间**比较,而非随时间比较
    _t = max(1, (len(a) - 1) // 2)          # trailing half · 后半程均值
    d_int_a = sum(h["interception_rate"] for h in a[-_t:]) / _t
    d_int_b = sum(h["interception_rate"] for h in b[-_t:]) / _t

    print("═" * 74)
    print("  RESULT · 结果" + ("" if eligible else "   ⚠ NOT ELIGIBLE · 不适格"))
    print("═" * 74)
    print(f"  interception rate (final)  ARM A {d_int_a:.2f}     ARM B {d_int_b:.2f}")
    print(f"  reachability  vs baseline  ARM A {d_reach_a:+.2f}    ARM B {d_reach_b:+.2f}")
    print(f"  hard-claim retention  ARM A {a[-1]['hard_retained']:.2f}  "
          f"ARM B {b[-1]['hard_retained']:.2f}")
    print()

    narrowed = d_reach_a < -0.01 and d_reach_b >= -0.01
    invisible = abs(d_int_a - d_int_b) < 0.05

    if narrowed and args.control:
        print("  ✗ HARNESS FAILURE · 装置失败")
        print("    ARM A narrowed in the CONTROL condition - nothing to lose, yet it")
        print("    lost. Do NOT report the main result from this run.")
        print("    对照条件下 A 组仍收窄。本次主结果不可采信。")
    elif narrowed:
        print("  ✓ ARM A lost reachable space; ARM B did not.")
        print("    A 组丢失了可达空间,B 组没有。")
        if invisible:
            print("  ✓ And the interception curves are indistinguishable —")
            print("    the loss is invisible to that metric alone.")
            print("    而拦截率曲线难以区分 —— 单看这个指标发现不了损失。")
    else:
        print("  ✗ No narrowing observed under these settings.")
        print("    在当前设置下未观察到收窄。")
        if args.control:
            print("    (Expected — this is the control condition. 符合预期,这是对照条件。)")
        else:
            print("    This is a null result and should be reported as such.")
            print("    这是零结果,应如实报告。")

    print()
    print("  Reminder: the generator here is a stand-in. This quantifies a")
    print("  mechanism; it is not evidence about real LLM behaviour.")
    print("  提醒:此处生成器是替身。本实验量化机制,不构成对真实 LLM 行为的证据。")

    # ── write CSV ────────────────────────────────────────────────────
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "round", "proposed", "intercepted", "interception_rate",
                    "reachability", "hard_retained", "constraints", "backlog"])
        for key, hist in results.items():
            for h in hist:
                w.writerow([key] + [h[c] for c in ["round", "proposed", "intercepted",
                                                   "interception_rate", "reachability",
                                                   "hard_retained", "constraints", "backlog"]])
    print(f"\n  → {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    main()
