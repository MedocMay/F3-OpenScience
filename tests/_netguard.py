"""External-API capability guard · 外部 API 能力守卫

Several suites verify against live academic APIs (arXiv / CrossRef / OpenAlex).
CI runners are frequently rate-limited by these services.

有几个套件要打真实学术 API。CI runner 经常被这些站点限流。

★ Probe the CAPABILITY the tests need, not merely connectivity.
★ 探测测试真正需要的**能力**,而不只是连通性。

  A naive "can I reach arxiv.org?" probe is not enough: a generic query may
  succeed while a lookup of a *nonexistent* ID gets throttled (403/429) and
  degrades to "unknown". The verifier then correctly reports `manual` rather
  than `reject` — and a test asserting `reject` fails for reasons unrelated
  to the code.

  简单探测「能否连上 arxiv」是不够的:普通查询可能成功,而查一个**不存在**的 ID
  却被限流(403/429)、降级为「未知」。此时校验器正确地报 `manual` 而非 `reject`,
  于是断言 `reject` 的测试因与代码无关的原因失败。

  So we probe both directions: a known-real ID must resolve, and a known-fake
  ID must be definitively denied. Only then are citation assertions meaningful.

  因此我们双向探测:已知真 ID 必须解析成功,已知假 ID 必须被明确否定。
  两者都成立,引用类断言才有意义。

★ The right response is to SKIP, never to weaken the assertion.
★ 正确做法是**跳过**,绝不是放宽断言。

  Turning `assert status == "reject"` into `assert status in ("reject","manual")`
  would let a genuine missed-fabrication bug pass unnoticed.

  把断言放宽会让「真的漏放了捏造引用」这种回归悄悄通过。

This mirrors the project's own principle: unreachable ≠ nonexistent.
这与项目自身原则同构:连不上 ≠ 不存在。
"""
from __future__ import annotations
import os

# A paper that certainly exists (Attention Is All You Need) and an ID that
# certainly does not. 一个确定存在、一个确定不存在。
_REAL_ID = "1706.03762"
_FAKE_ID = "2099.99999"

_cached: bool | None = None


def net_ok() -> bool:
    """Can we actually distinguish a real citation from a fabricated one?

    我们真的能区分真引用与捏造引用吗?

    Returns False when the academic APIs are unreachable OR rate-limited to the
    point where a nonexistent ID no longer yields a definitive denial.
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
        real_ok, _ = apis.check_arxiv(_REAL_ID)
        fake_ok, _ = apis.check_arxiv(_FAKE_ID)
        # real must resolve True; fake must be a definitive False (not None/unknown)
        _cached = (real_ok is True) and (fake_ok is False)
    except Exception:
        _cached = False
    return _cached


def skip_if_offline(name: str = "") -> bool:
    """Return True (and print a notice) when the suite should be skipped."""
    if net_ok():
        return False
    print(f"  ⚠️  Academic APIs unreachable or rate-limited — skipping "
          f"{name or 'network-dependent test'} (NOT a regression · 非回归)")
    return True
