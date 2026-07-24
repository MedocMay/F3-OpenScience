"""External-API availability guard · 外部 API 可达性守卫

Several suites verify against live academic APIs (arXiv / CrossRef / OpenAlex).
CI runners are frequently rate-limited or blocked by these services, which makes
those suites fail for reasons that have nothing to do with the code.

有几个套件要打真实学术 API。CI 环境经常被这些站点限流或封禁,
导致测试因与代码无关的原因失败。

★ The right response is to SKIP, never to weaken the assertion.
★ 正确做法是**跳过**,绝不是放宽断言。

  Weakening `assert status == "reject"` into `assert status in ("reject", "manual")`
  would hide a real regression: it would let a genuine "we failed to detect
  fabrication" bug pass unnoticed.

  把 `assert status == "reject"` 放宽成 `in ("reject","manual")` 会掩盖真实回归 ——
  真的漏放了捏造引用也会被判为通过。

Note this mirrors the project's own principle: unreachable ≠ nonexistent.
When the verifier cannot reach a registry it reports `manual`, not `reject`.
The tests must respect the same distinction.

这与项目自身原则同构:连不上 ≠ 不存在。
校验器连不上登记处时报 `manual` 而非 `reject`,测试也必须尊重同一区分。
"""
from __future__ import annotations
import os, urllib.request

_cached: bool | None = None

# Known-good and known-bad arXiv IDs used to probe the registry.
# 用于探测登记处的一真一假 arXiv ID。
_REAL_ID = "1706.03762"      # Attention Is All You Need
_FAKE_ID = "2099.99999"      # well-formed but nonexistent · 格式合法但不存在


def net_ok() -> bool:
    """Can the arXiv registry give a DEFINITIVE existence verdict right now?

    ★ We probe the capability, not mere connectivity.

    A plain reachability check is not enough. arXiv rate-limits CI runners, and a
    throttled response makes `check_arxiv` return None (unknown) — at which point
    the verifier correctly reports `manual` rather than `reject`. A test asserting
    `reject` would then fail for reasons unrelated to the code.

    ★ 我们探测的是**能力**,不是连通性。

    只探测"能不能连上"是不够的。arXiv 会限流 CI runner,被限流时 `check_arxiv`
    返回 None(未知),校验器据此正确地报 `manual` 而非 `reject` ——
    此时断言 `reject` 的测试会因与代码无关的原因失败。

    So: require a definitive True for a real ID *and* a definitive False for a
    fake one. Anything less (None / unknown) means the registry cannot be trusted
    to answer right now, and citation-existence tests must skip.

    因此:真 ID 必须确定为 True,假 ID 必须确定为 False。
    只要有一个是 None,就说明登记处此刻给不出确定答案,存在性测试必须跳过。
    """
    global _cached
    if _cached is not None:
        return _cached
    if os.environ.get("OPENSCI_SKIP_NETWORK_TESTS") == "1":
        _cached = False
        return _cached
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from coe_kernel import apis
        real, _ = apis.check_arxiv(_REAL_ID)
        fake, _ = apis.check_arxiv(_FAKE_ID)
        _cached = (real is True) and (fake is False)
    except Exception:
        _cached = False
    return _cached


def skip_if_offline(name: str = "") -> bool:
    """Return True (and print a notice) when the suite should be skipped."""
    if net_ok():
        return False
    print(f"  ⚠️  arXiv cannot give a definitive verdict right now (unreachable or "
          f"rate-limited) — skipping {name or 'network-dependent test'} "
          f"(NOT a regression · 非回归)")
    return True
