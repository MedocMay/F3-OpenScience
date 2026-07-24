"""External-API capability guards · 外部 API 能力守卫

Several suites depend on live academic APIs. CI runners are frequently
rate-limited by them. 有几个套件依赖真实学术 API,CI runner 常被限流。

★ Probe the EXACT capability a test uses — not an adjacent one.
★ 探测测试**实际使用**的那一项能力,而不是相邻的一项。

  This has bitten us three times, each time the same way:

    1st  probed "can I reach arxiv.org?" — but a generic query can succeed
         while a *nonexistent-ID* lookup is throttled and degrades to unknown.
    2nd  probed check_arxiv(id) — but the ID endpoint (`id_list`) and the
         search endpoint (`search_query`) fail independently under rate limits.
         ID lookup returned True while search returned zero papers.
    3rd  ...is what this file is trying to prevent.

  这个坑我们踩了三次,每次形态相同:
    第一次 探测「能否连上 arxiv」—— 但普通查询成功,查**不存在的 ID** 却被限流降级为未知
    第二次 探测 check_arxiv(id) —— 但 ID 端点(id_list)与搜索端点(search_query)
           在限流下独立失效。ID 查询返回 True,搜索却返回 0 篇。
    第三次 …正是这个文件想避免的

  The lesson is the project's own thesis applied to its test harness:
  treating "I can do X" as "I can do Y" is the same error as treating
  "I cannot find it" as "it does not exist."

  教训就是本项目自身论点在测试装置上的应用:
  把「我能做 X」当成「我能做 Y」,和把「我查不到」当成「它不存在」,是同一个错误。

★ SKIP, never weaken the assertion. 跳过,绝不放宽断言。
  Turning `assert status == "reject"` into `in ("reject","manual")` would let a
  genuine missed-fabrication bug pass unnoticed.
"""
from __future__ import annotations
import os

_REAL_ID = "1706.03762"     # certainly exists · 确定存在
_FAKE_ID = "2099.99999"     # certainly does not · 确定不存在
_cache: dict[str, bool] = {}


def _forced_off() -> bool:
    return os.environ.get("OPENSCI_SKIP_NETWORK_TESTS") == "1"


def can_judge_citations() -> bool:
    """Can we tell a real citation from a fabricated one?
    我们能区分真引用与捏造引用吗?

    Requires BOTH directions: a known-real ID must resolve, and a known-fake ID
    must be *definitively denied* (False, not None/unknown).
    需要双向成立:真 ID 必须解析成功,假 ID 必须被**明确否定**。
    """
    if "cite" in _cache:
        return _cache["cite"]
    if _forced_off():
        _cache["cite"] = False
        return False
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from coe_kernel import apis
        real_ok, _ = apis.check_arxiv(_REAL_ID)
        fake_ok, _ = apis.check_arxiv(_FAKE_ID)
        _cache["cite"] = (real_ok is True) and (fake_ok is False)
    except Exception:
        _cache["cite"] = False
    return _cache["cite"]


def can_search_literature() -> bool:
    """Can we retrieve papers by topic?  我们能按主题检索到论文吗?

    This is a DIFFERENT capability from can_judge_citations(). arXiv's
    `search_query` endpoint and its `id_list` endpoint fail independently under
    rate limiting — an ID lookup can succeed while a search returns nothing.
    这与 can_judge_citations() 是**不同的**能力。arXiv 的 search_query 与
    id_list 两个端点在限流下独立失效 —— ID 查得到,搜索却可能返回空。
    """
    if "search" in _cache:
        return _cache["search"]
    if _forced_off():
        _cache["search"] = False
        return False
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from pipeline.pipeline import literature
        _cache["search"] = len(literature("neural networks", n=2)) >= 1
    except Exception:
        _cache["search"] = False
    return _cache["search"]


def net_ok() -> bool:
    """Back-compat alias for citation judgement. 向后兼容别名。"""
    return can_judge_citations()


def _notice(name: str, what: str) -> bool:
    print(f"  ⚠️  {what} unavailable (rate-limited or offline) — skipping "
          f"{name or 'test'} (NOT a regression · 非回归)")
    return True


def skip_if_offline(name: str = "") -> bool:
    """Skip when citation judgement is unavailable. 无法判定引用时跳过。"""
    return False if can_judge_citations() else _notice(name, "Citation verification")


def skip_if_no_search(name: str = "") -> bool:
    """Skip when literature search is unavailable. 无法检索文献时跳过。"""
    return False if can_search_literature() else _notice(name, "Literature search")
