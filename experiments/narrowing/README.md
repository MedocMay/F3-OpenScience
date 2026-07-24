# Experiment · Does conflating "cannot verify" with "wrong" narrow the reachable space?

**实验 · 把「无法核验」等同于「错误」,是否会收窄可达空间?**

```bash
python3 experiments/narrowing/run_experiment.py            # main condition · 主条件
python3 experiments/narrowing/run_experiment.py --control  # control · 对照条件
```

---

## The two arms · 两组

Identical in every respect except one line of policy.
除一行策略外完全相同。

| | Policy · 策略 |
|---|---|
| **ARM A** · conflating<br>混同 | Every verification failure becomes a generation constraint.<br>所有校验失败都写回生成约束。**这是主流做法。** |
| **ARM B** · separated<br>分离 | Only *confirmed fabrication* constrains generation. Coverage gaps become a capability backlog.<br>只有**确证捏造**约束生成;覆盖缺口转为能力待办。 |

## Result · 结果

Six rounds, 15-claim pool (5 easily-verified real, 5 real-but-hard-to-verify, 5 fabricated):

```
                              ARM A        ARM B
  reachability vs baseline    -0.50        +0.00
  hard-claim retention         0.00         1.00
  interception rate (final)    0.00         0.50
```

**ARM A's interception rate went to zero — and it looks better for it.**
It achieved that by no longer proposing anything hard to verify, losing every
real-but-hard-to-verify claim in the pool. ARM B's interception rate stayed at
0.50 precisely *because* it kept attempting those claims.

**A 组拦截率归零 —— 而且指标因此更好看。**
它做到这一点的方式,是不再提出任何难以核验的东西,丢掉了池中全部
「真实但难核验」的论断。B 组拦截率停在 0.50,恰恰**因为**它还在尝试那些论断。

> If your dashboard has one curve, ARM A is the winner.
> 如果你的仪表盘只有一条曲线,A 组是赢家。

## Control condition · 对照条件

```bash
python3 experiments/narrowing/run_experiment.py --control
```

Removes all `valid_hard` claims from the pool. With nothing valid that is hard
to verify, ARM A has nothing to lose:

剔除全部 `valid_hard`。没有「真实但难核验」的东西时,A 组无可失去:

```
  reachability vs baseline    ARM A +0.00    ARM B +0.00
```

**No narrowing.** This is what makes the main result meaningful rather than
tautological — the harness does not manufacture the effect.

**不收窄。** 这一点让主结果不至于流于同义反复 —— 装置不会凭空制造效应。

---

## What is real, what is modelled · 什么是真的,什么是建模的

**REAL · 真实的**

Verification. Every claim is checked against live arXiv / CrossRef / DataCite /
OpenAlex through `coe_kernel`. Which claims turn out hard to verify is decided
by those services, not by our labels.

校验是真的。哪些论断难以核验由真实服务决定,不是我们标注的。

**MODELLED · 建模的**

The generator. It is a stand-in with exactly one modelled property: it does not
propose claims matching its constraint set. This mirrors
`pipeline.hypothesize(guard=True)`, which pre-verifies and drops claims that
would fail.

生成器是替身,只建模一个属性:不提出匹配约束集的论断。
这与 `pipeline.hypothesize(guard=True)` 的实际行为一致。

---

## What this does **not** show · **不能**证明什么

**It does not show that a real LLM behaves this way.**
The stand-in generator has no learning dynamics, no distributional shift, no
in-context effects. It demonstrates and quantifies a *mechanism* under a stated
model — not the behaviour of any deployed system.

**不能证明真实 LLM 会这样。** 替身生成器没有学习动力学、没有分布漂移、
没有上下文效应。它在给定模型下展示并量化一个**机制**,而非任何真实系统的行为。

To make the stronger empirical claim, replace the stand-in with a real model and
re-run. That is the experiment that would turn the argument into a finding.

要做更强的实证主张,请把替身换成真实模型后重跑。**那才是把论点变成发现的实验。**

---

## Environment eligibility · 环境适格性

The harness checks whether the environment can produce clean verdicts, and
refuses to present results as meaningful when it cannot.

装置会检查环境能否给出干净判定,不能时拒绝把结果当作有意义。

A `valid_hard` claim should come back **`unresolved`** — the index searched and
found no match. If it comes back **`manual`** instead, the verifier could not
reach a conclusion at all, typically because the index API rate-limited the host
(HTTP 429). Those are different kinds of "I cannot see": one is an index gap,
the other a transport failure.

`valid_hard` 应当返回 **`unresolved`**(索引查过、没匹配上)。
若返回 **`manual`**,说明校验器根本无法得出结论 —— 通常是索引 API 对本机限流(429)。
两者是**不同的**「我看不到」:一个是索引缺口,一个是传输失败。

When fewer than 3 `valid_hard` claims resolve cleanly, the run is marked
**NOT ELIGIBLE**. Results are still printed, but should not be cited.

少于 3 条 `valid_hard` 得到干净判定时,该次运行标记为**不适格**,结果不应被引用。

> The development environment where this was written is rate-limited by OpenAlex,
> so the recorded runs are NOT ELIGIBLE. The effect is visible anyway — but a
> clean replication needs a network the index API does not throttle, or an
> OpenAlex API key.
>
> 编写本实验的开发环境被 OpenAlex 限流,因此已记录的运行**不适格**。
> 效应依然可见,但干净的复现需要不被限流的网络或 OpenAlex API key。

---

## Files · 文件

| | |
|---|---|
| `run_experiment.py` | Harness · 实验主体 |
| `claim_pool.json` | 15 claims with ground truth · 带真值的论断池 |
| `results.csv` | Per-round metrics for both arms · 两组逐轮指标 |

## Background · 背景

The argument this tests: [docs/REACHABILITY.md](../../docs/REACHABILITY.md) ·
[INNOVATION.md](../../INNOVATION.md)

Honest account of what the whole project has and has not verified:
[STATUS.md](../../STATUS.md)
