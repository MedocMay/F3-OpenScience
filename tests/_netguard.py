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

_PROBE = "http://export.arxiv.org/api/query?search_query=all:test&max_results=1"
_cached: bool | None = None


def net_ok(timeout: int = 25) -> bool:
    """Is the academic-API network reachable? Result cached per process."""
    global _cached
    if _cached is not None:
        return _cached
    if os.environ.get("OPENSCI_SKIP_NETWORK_TESTS") == "1":
        _cached = False
        return _cached
    try:
        urllib.request.urlopen(_PROBE, timeout=timeout).read()
        _cached = True
    except Exception:
        _cached = False
    return _cached


def skip_if_offline(name: str = "") -> bool:
    """Return True (and print a notice) when the suite should be skipped."""
    if net_ok():
        return False
    print(f"  ⚠️  Academic APIs unreachable — skipping {name or 'network-dependent test'} "
          f"(NOT a regression · 非回归)")
    return True
