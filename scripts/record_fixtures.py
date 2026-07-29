#!/usr/bin/env python3
"""Record live API responses into a committed fixture, for offline test runs.

把真实 API 响应录进可提交的 fixture,供离线跑测试用。

WHY THIS EXISTS · 为什么需要它
------------------------------
Whether the tests run at all currently depends on how arXiv feels today. On
2026-07-27, `make test` reported fourteen suites PASSED while two of them
executed zero tests — the services were rate-limiting and the suites correctly
skipped. CI went red on one commit and green on the next with no relevant code
change in between.
测试能不能跑,现在取决于 arXiv 今天心情如何。2026-07-27 那天 `make test` 报告
十四个套件 PASSED,而其中两个一个测试都没执行 —— 服务在限流,套件正确地跳过了。
CI 在相邻两个 commit 上一红一绿,中间没有任何相关代码改动。

A recorded fixture separates two questions that were tangled together:
录制的 fixture 把两个纠缠在一起的问题分开:

    offline run  →  did a code change break something?   (deterministic)
    live run     →  did the world change?                (may legitimately degrade)
    离线跑       →  代码改动有没有弄坏东西?              (确定性的)
    联网跑       →  世界有没有变?                        (可以合理地降级)

WHAT IS RECORDED · 录的是什么
------------------------------
The replay point is the **network boundary**, not the verdict. This file records
`url -> raw response`; it does NOT record `claim -> verdict`. Every layer of the
verifier still executes on replay — the four-layer citation check, authoritative
denial, threshold matching, all of it. Caching verdicts instead would replace the
thing under test with its own past output.
复放点在**网络边界**,不在判定层。本文件录的是 `URL -> 原始响应`,**不是**
`claim -> verdict`。复放时校验器每一层照常执行 —— 四层引用校验、权威否定、阈值
匹配,一个不少。缓存 verdict 等于把被测对象换成了它自己的历史输出。

SHELF LIFE · 保质期
-------------------
A recorded fixture goes stale silently. If arXiv changes its response shape, or
OpenAlex indexes the papers that are currently invisible to it, the offline run
stays green — it is replaying the world as of the capture date. That is what the
live CI job is for, and why MANIFEST.json records when this was captured.
录下来的 fixture 会**无声地过期**。如果 arXiv 改了响应格式,或者 OpenAlex 收录了
目前对它不可见的那些论文,离线跑照样绿 —— 它复放的是采集当天的世界。这正是联网
CI job 存在的理由,也是 MANIFEST.json 要记采集日期的理由。

USAGE · 用法
------------
    python3 scripts/record_fixtures.py               # record every suite
    python3 scripts/record_fixtures.py test_coe ...  # record named suites only
    python3 scripts/record_fixtures.py --fresh       # discard and re-record all
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "api_cache"
MANIFEST = FIXTURE / "MANIFEST.json"
STAGING = FIXTURE.parent / "api_cache.staging"
SUITES_FILE = ROOT / "tests" / "SUITES"


def suites() -> list[str]:
    """Read the same list make test and CI read. 读 make test 与 CI 同一份清单。"""
    out = []
    for line in SUITES_FILE.read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if name:
            out.append(name)
    return out


def size_of(d: pathlib.Path) -> tuple[int, int]:
    files = [f for f in d.glob("*.json") if f.name != "MANIFEST.json"]
    return len(files), sum(f.stat().st_size for f in files)


def verify_offline(target: pathlib.Path, names: list[str]) -> list[tuple[str, str]]:
    """Replay every suite against the fixture with the network closed off.

    在网络关闭的前提下,用 fixture 复放每一个套件。

    Counting skips was not a completeness check, only a proxy for one — and it
    missed the case that actually happened: a suite that ran to completion while
    every request failed. test_reachability recorded ONE response for 21 claims and
    was marked ok, because under rate limiting every lookup degraded to unknown and
    the suite's expectations for hard claims are precisely "unresolved". It passed
    for the wrong reason and recorded almost nothing.
    数跳过次数不是完整性检查,只是它的一个代理指标 —— 而且恰好漏掉了真正发生的
    那种情况:套件跑完了,但每一个请求都失败了。test_reachability 为 21 条论断只录到
    1 个响应却被标为 ok,因为限流下每次查询都降级为未知,而该套件对难核验论断的
    期望恰恰就是 unresolved。它因为错误的理由通过,同时几乎什么都没录到。

    So stop inferring completeness and measure it: if the fixture can carry every
    suite with COE_OFFLINE set, it is complete. If it cannot, FixtureMiss names the
    exact URL that is missing. This is the same discipline the project applies to
    its verifier — do not report a conclusion you have not actually reached.
    所以不再推断完整性,直接测量它:如果这份 fixture 能在 COE_OFFLINE 下带动全部
    套件,它就是完整的;带不动的话,FixtureMiss 会精确点出缺哪个 URL。这与本项目
    对校验器的要求是同一条纪律 —— 别报告一个你并没有真正得出的结论。
    """
    print("\nverifying offline · 离线验证 (COE_OFFLINE=1, network closed · 网络关闭)")
    env = dict(os.environ)
    env["COE_CACHE"] = str(target)
    env["COE_OFFLINE"] = "1"
    bad = []
    for n in names:
        print(f"  {n:20s} ", end="", flush=True)
        p = subprocess.run([sys.executable, f"tests/{n}.py"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        out = p.stdout + p.stderr
        if p.returncode != 0:
            why = "FixtureMiss" if "FixtureMiss" in out else f"exit={p.returncode}"
            bad.append((n, out.strip().splitlines()[-1] if out.strip() else why))
            print(f"MISS  {why}")
        elif "SKIPPED, not run" in p.stdout:
            bad.append((n, "skipped on replay — its responses were never recorded "
                           "· 复放时跳过,说明它的响应从未被录到"))
            print("SKIP  replayed but ran nothing · 复放了但一个测试没跑")
        else:
            print("ok")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("suites", nargs="*", help="suite names; default = all in tests/SUITES")
    ap.add_argument("--fresh", action="store_true",
                    help="discard the existing fixture first · 先清空现有 fixture")
    args = ap.parse_args()

    targets = args.suites or suites()
    unknown = [s for s in targets if not (ROOT / "tests" / f"{s}.py").exists()]
    if unknown:
        print(f"unknown suite(s) · 未知套件: {', '.join(unknown)}", file=sys.stderr)
        return 2

    # --fresh used to delete first and record second. That put an irreversible
    # action ahead of an unverified assumption: that the new recording would be at
    # least as good. It was not — a run during rate limiting produced 20 responses
    # where the previous one had 51, and the good fixture was already gone. Record
    # into staging, compare, and promote only if the new one is complete.
    # --fresh 原先先删后录,把一个不可逆的动作放在了一个未经验证的假设前面:
    # 新录制至少不会更差。事实是会 —— 限流期间的一次录制只得到 20 个响应,
    # 而上一次有 51 个,且那份好的已经被删了。改为先录到暂存区,比较后再决定是否替换。
    target = STAGING if args.fresh else FIXTURE
    if args.fresh and STAGING.exists():
        shutil.rmtree(STAGING)
    target.mkdir(parents=True, exist_ok=True)
    FIXTURE.mkdir(parents=True, exist_ok=True)

    before_n, before_b = size_of(target)
    kept_n, _ = size_of(FIXTURE)
    print(f"fixture · {target.relative_to(ROOT)}"
          + ("   (staging; promoted only if complete · 暂存区,录完整才替换)" if args.fresh else ""))
    print(f"before   {before_n} files, {before_b/1024:.0f} KB")
    print(f"recording {len(targets)} suite(s) against LIVE services · 对真实服务录制\n")

    env = dict(os.environ)
    env["COE_CACHE"] = str(target)
    env.pop("COE_OFFLINE", None)          # recording must reach the network · 录制必须走网络

    failed, skipped = [], []
    for s in targets:
        n0, _ = size_of(target)
        print(f"  {s:20s} ", end="", flush=True)
        p = subprocess.run([sys.executable, f"tests/{s}.py"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        n1, _ = size_of(target)
        tail = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
        # A suite that skipped exits 0 and looks recorded. It is not: it made no
        # requests, so its fixture is empty and the offline run will hit FixtureMiss.
        # Exit code alone cannot tell "ran and recorded" from "skipped, recorded
        # nothing" — the same conflation the suites themselves were fixed for.
        # 跳过的套件退出码是 0,看起来像录好了。并没有:它没发任何请求,fixture 是空的,
        # 离线跑到那里会撞 FixtureMiss。只看退出码分不出「跑过并录到」和「跳过所以
        # 没录到」—— 正是套件本身刚修掉的那种混同。
        was_skipped = "SKIPPED, not run" in p.stdout
        if p.returncode != 0:
            mark = "FAIL"
            failed.append((s, p.stdout, p.stderr))
        elif was_skipped:
            mark = "SKIP"
            skipped.append(s)
        else:
            mark = "ok "
        print(f"{mark}  +{n1-n0:3d} responses   {tail[:52]}")

    after_n, after_b = size_of(target)
    print(f"\nafter    {after_n} files, {after_b/1024:.0f} KB  (+{after_n-before_n})")

    if skipped:
        print(f"\n  ⚠️  {len(skipped)} suite(s) SKIPPED — their fixture is EMPTY · "
              f"项跳过,其 fixture 为空")
        print(f"      {', '.join(skipped)}")
        print("      They needed a capability that was unavailable (usually arXiv topic")
        print("      search under rate limiting). An offline run will raise FixtureMiss")
        print("      here. Check `make doctor`, wait for the capability, and re-record.")
        print("      它们需要的能力当时不可用(通常是限流下的 arXiv 主题检索)。离线跑到")
        print("      这里会抛 FixtureMiss。先看 make doctor,等能力恢复后重录。")

    if failed:
        print(f"\n  ⚠️  {len(failed)} suite(s) failed while recording · 录制期间失败")
        print("      A suite that skipped or failed contributes nothing to the fixture,")
        print("      so the offline run would then hit missing responses.")
        print("      跳过或失败的套件不会给 fixture 贡献任何东西,离线跑到那里就会缺响应。")
        for s, out, err in failed:
            print(f"\n      ── {s}")
            for line in (out + err).strip().splitlines()[-6:]:
                print(f"         {line}")

    # Completeness is now decided by replay, not by counting what looked wrong.
    # 完整性现在由复放判定,而不是靠数「看起来不对的东西」。
    unreplayable = verify_offline(target, targets)
    complete = not failed and not unreplayable
    if unreplayable:
        print(f"\n  ⚠️  {len(unreplayable)} suite(s) cannot be replayed offline · 项无法离线复放")
        for n, why in unreplayable:
            print(f"      {n}: {why[:96]}")

    if args.fresh:
        if complete:
            if FIXTURE.exists():
                shutil.rmtree(FIXTURE)
            STAGING.rename(FIXTURE)
            print(f"\n  ✓ recording complete — promoted over the old fixture "
                  f"({kept_n} → {after_n} responses) · 录制完整,已替换旧 fixture")
        else:
            print(f"\n  ✗ recording INCOMPLETE — old fixture kept untouched "
                  f"({kept_n} responses) · 录制不完整,旧 fixture 原样保留")
            print(f"      staging left at {STAGING.relative_to(ROOT)} for inspection; "
                  f"delete it or re-run when the capability is back.")
            print(f"      暂存区留在 {STAGING.relative_to(ROOT)} 供查看;能力恢复后重跑,或直接删除。")
            return 1

    MANIFEST.write_text(json.dumps({
        "captured_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "suites_recorded": targets,
        "suites_failed": [s for s, _, _ in failed],
        "suites_skipped_empty": skipped,
        "suites_not_replayable": [n for n, _ in unreplayable],
        "complete": complete,
        "responses": after_n,
        "bytes": after_b,
        "note": ("Replay is at the network boundary: url -> raw response. All verifier "
                 "logic still runs. This fixture goes stale silently — the live CI job "
                 "exists to catch that. "
                 "复放点在网络边界(URL -> 原始响应),校验逻辑照常执行。本 fixture 会无声"
                 "过期,联网 CI job 就是为抓这件事而存在。"),
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"\nmanifest · {MANIFEST.relative_to(ROOT)}")

    return 1 if (failed or unreplayable) else 0


if __name__ == "__main__":
    sys.exit(main())
