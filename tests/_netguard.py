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


# Pin generation to the template for every suite that imports this. Subprocesses
# inherit it, so the RPC path is covered too.
# 凡是 import 本模块的套件,生成一律钉死为模板。子进程继承该变量,RPC 路径同样覆盖。
os.environ.setdefault("OPENSCI_PIPELINE_MODEL", "0")
# Layer 4 likewise: a suite must not gate differently because a key is present.
# Real-model relevance is measured in experiments/relevance/, where it belongs.
# 第 4 层同理:套件不能因为有没有 key 而门控得不一样。真实模型的相关性表现在
# experiments/relevance/ 里测,那才是它该在的地方。
os.environ.setdefault("COE_RELEVANCE", "heuristic")

_skipped: list[tuple[str, str]] = []


def _notice(name: str, what: str) -> bool:
    _skipped.append((name or "test", what))
    return True


def skip_if_missing(module: str, extra: str, name: str = "") -> bool:
    """Skip when an optional dependency is absent. 缺可选依赖时跳过。

    A dependency you did not install is a capability this environment lacks — not a
    defect in the code under test. Reporting it as a failure is the conflation this
    project exists to name, one level up: the harness mistaking its own gap for a
    fact about the subject.
    没装的依赖是「这个环境缺这项能力」,不是被测代码的缺陷。报成失败,
    就是本项目要指出的那种混同上移了一层。
    """
    try:
        __import__(module)
        return False
    except ImportError:
        return _notice(name, f"{module} not installed — pip install -e '.[{extra}]' · 未安装可选依赖")


def run_suite(tests, title: str) -> None:
    """Shared runner. ✅ = ran and passed. ⏭ = skipped, **not run**.

    共用 runner。✅ = 跑过且通过。⏭ = 跳过,**未运行**。

    A test that returned early for want of a capability must not print the same mark
    as one that actually asserted something. "We checked" and "we could not check"
    are different findings — printing ✅ for both is exactly how a suite comes to
    report green while having verified nothing.
    因缺能力提前返回的测试,不能和真正断言过的测试打同一个标记。
    「查过了」和「查不了」是两种结论 —— 两者都打 ✅,
    正是一个套件什么都没验证却报绿的方式。

    tests: [callable] or [(callable, label)]
    """
    ran = skipped = 0
    for item in tests:
        fn, label = item if isinstance(item, tuple) else (item, item.__name__)
        mark = len(_skipped)
        try:
            fn()
        except CapabilityLost as e:
            skipped += 1
            print(f"  ⏭  {label} SKIP — {e}")
            continue
        if len(_skipped) > mark:
            skipped += 1
            print(f"  ⏭  {label} SKIP — {_skipped[-1][1]}")
        else:
            ran += 1
            print(f"✅ {label}")
    tail = f" ({ran} ran · {skipped} SKIPPED, not run · 项未运行)" if skipped else ""
    print(f"\n{title} PASSED{tail}")


class CapabilityLost(Exception):
    """The capability under test disappeared mid-run. 被测能力在运行途中消失。

    Not a regression — the suite simply stopped being able to observe.
    非回归 —— 只是套件中途失去了观测能力。
    """


def assert_capable(cond, what: str, capability: str = "cite", detail: str = "") -> None:
    """Assert, but re-probe the capability before calling a failure a failure.

    Probing once at the start and trusting that answer for the rest of the run
    carries exactly the blind spot this project exists to name: a stale view of
    one's own reach, reported as a fact about the code. These suites generate
    enough traffic to rate-limit *themselves* partway through — test_integration
    runs the full chain twice — so "the assertion failed" and "the service stopped
    answering" are genuinely different findings, and only a fresh probe tells them
    apart.

    开头探测一次、其后全程信任那个答案,带着的正是本项目要指出的那种盲区:把自己
    过期的视野,报告成关于代码的事实。这些套件自身的流量足以让它们跑到一半把自己
    限流(test_integration 会跑两遍完整链路)—— 所以「断言失败」和「服务不再作答」
    是两种不同的结论,只有重新探测才分得开。

    The re-probe costs two API calls and only happens on failure, so it does not
    add to the pressure that caused the degradation.
    重新探测只在失败时发生、只花两次 API 调用,不会加重造成降级的那份压力。
    """
    if cond:
        return
    _cache.pop(capability, None)                        # force a fresh probe · 强制重探
    alive = can_judge_citations() if capability == "cite" else can_search_literature()
    if not alive:
        raise CapabilityLost(
            f"{what}: capability '{capability}' was available at start but is gone now "
            f"(rate-limited mid-run) · 开始时可用,现已失去(运行中被限流) —— NOT a regression · 非回归")
    raise AssertionError(detail or what)


def skip_if_offline(name: str = "") -> bool:
    """Skip when citation judgement is unavailable. 无法判定引用时跳过。"""
    return False if can_judge_citations() else _notice(
        name, "Citation verification unavailable (rate-limited or offline) · 引用判定不可用")


def skip_if_no_search(name: str = "") -> bool:
    """Skip when literature search is unavailable. 无法检索文献时跳过。"""
    return False if can_search_literature() else _notice(
        name, "Literature search unavailable (rate-limited or offline) · 文献检索不可用")
