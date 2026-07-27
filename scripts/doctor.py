#!/usr/bin/env python3
"""Environment doctor · 环境体检

Checks whether this machine can actually run F3-OpenScience, and — where a
check involves an external service — whether it has the *capability* the code
depends on, not merely a connection.

检查本机能否真正运行 F3-OpenScience。凡涉及外部服务的检查,查的是代码所依赖的
**能力**,而不只是「能不能连上」。

That distinction is the project's own discipline, and this file exists because
we got it wrong once: a CI guard probed "can I reach arXiv?" when the capability
the tests actually needed was "can I get a definitive negative for an ID that
does not exist?". Reachable and able-to-decide are different properties.

这个区分正是本项目自己的纪律。写这个文件是因为我们犯过一次:CI 守卫探测的是
「能否连上 arXiv」,而测试真正依赖的能力是「能否对一个不存在的 ID 得到明确否定」。
「连得上」和「判得了」是两回事。

Usage · 用法:
    python3 scripts/doctor.py            # full check · 完整体检
    python3 scripts/doctor.py --offline  # skip network checks · 跳过网络检查

Exit code 0 if everything required passes. 全部必需项通过则退出码为 0。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import ssl
import subprocess
import time
import sys
import urllib.error
import urllib.request

MIN_PY = (3, 11)
TIMEOUT = 20
_ARXIV_MIN_INTERVAL = 3.0   # matches apis.py 与 apis.py 一致
UA = {"User-Agent": "F3-OpenScience-doctor/1.0 (+https://github.com/MedocMay/F3-OpenScience)"}

# ── tiny reporter ────────────────────────────────────────────────────────────

class Report:
    def __init__(self) -> None:
        self.failures: list[tuple[str, list[str]]] = []
        self.degraded: list[tuple[str, list[str]]] = []
        self.warnings: list[str] = []

    def ok(self, label: str, detail: str = "") -> None:
        print(f"  \033[32m✓\033[0m {label}" + (f"  {detail}" if detail else ""))

    def warn(self, label: str, detail: str = "") -> None:
        print(f"  \033[33m!\033[0m {label}" + (f"  {detail}" if detail else ""))
        self.warnings.append(label)

    def fail(self, label: str, detail: str = "", fix: list[str] | None = None) -> None:
        print(f"  \033[31m✗\033[0m {label}" + (f"  {detail}" if detail else ""))
        self.failures.append((label, fix or []))

    def degrade(self, label: str, detail: str = "", fix: list[str] | None = None) -> None:
        """Runnable, but some measurement will be untrustworthy.

        能跑,但某些测量结果不可信。Deliberately NOT a failure: reporting
        "cannot run" when the truth is "cannot see clearly right now" is the
        exact conflation this project exists to name.
        刻意不算失败:把「现在看不清」报成「不能运行」,正是本项目要指出的那种混同。
        """
        print(f"  \033[33m~\033[0m {label}" + (f"  {detail}" if detail else ""))
        self.degraded.append((label, fix or []))

    def skip(self, label: str, why: str) -> None:
        print(f"  \033[90m·\033[0m {label}  ({why})")


def get(url: str) -> tuple[int, bytes | None, str | None]:
    """Return (status, body, error). Never raises. 不抛异常。"""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(), None
    except urllib.error.HTTPError as e:
        return e.code, None, None
    except Exception as e:  # noqa: BLE001 — doctor must survive anything
        return 0, None, f"{type(e).__name__}: {e}"


# ── checks ───────────────────────────────────────────────────────────────────

def check_python(r: Report) -> None:
    print("\nPython")
    v = sys.version_info
    got = f"{v.major}.{v.minor}.{v.micro}"
    if v[:2] < MIN_PY:
        r.fail(
            f"version {got}",
            f"need ≥ {MIN_PY[0]}.{MIN_PY[1]} · 需要 {MIN_PY[0]}.{MIN_PY[1]} 以上",
            fix=[
                "The code uses PEP 604 annotations (`list | None`), evaluated at",
                "import time — so this fails immediately, not lazily.",
                "代码使用 PEP 604 注解(`list | None`),在导入时求值,所以是立即失败。",
                "",
                "  macOS (no Homebrew · 没有 brew):",
                "    download the universal2 .pkg from https://www.python.org/downloads/macos/",
                "    then run: open '/Applications/Python 3.13/Install Certificates.command'",
                "    装完必须跑上面那行证书脚本,否则所有 HTTPS 都会失败。",
                "",
                "  then · 然后:",
                "    python3.13 -m venv .venv && source .venv/bin/activate",
            ],
        )
    else:
        r.ok(f"version {got}", f"{platform.system()} {platform.machine()}")

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        r.ok("virtualenv active · 虚拟环境已激活", sys.prefix)
    else:
        r.warn(
            "not in a virtualenv · 未使用虚拟环境",
            "recommended: python3 -m venv .venv && source .venv/bin/activate",
        )


def check_imports(r: Report) -> None:
    print("\nPackage · 包")
    sys.path.insert(0, os.getcwd())
    try:
        import coe_kernel  # noqa: F401

        r.ok("import coe_kernel")
    except Exception as e:  # noqa: BLE001
        r.fail(
            "import coe_kernel",
            f"{type(e).__name__}: {e}",
            fix=[
                "Run from the repository root · 必须在仓库根目录下运行:",
                "  cd /path/to/F3-OpenScience && python3 scripts/doctor.py",
            ],
        )

    try:
        import jsonschema  # noqa: F401

        r.ok("jsonschema (test extra · 测试依赖)")
    except ImportError:
        r.fail("jsonschema (test extra · 测试依赖)", "not installed · 未安装",
               fix=["make test 会在 test_coe 崩掉,而那正是覆盖校验内核的套件。",
                    "", "  pip install -e '.[test]'"])

    try:
        import rdkit  # noqa: F401

        r.ok("rdkit (optional · 可选)", "valence checks available · 价键判据可用")
    except ImportError:
        r.skip(
            "rdkit (optional · 可选)",
            "not installed — valence checks report capability-missing, "
            "not a physical conclusion · 未安装,价键判据会报「能力缺失」而非物理结论",
        )


def check_tls(r: Report) -> None:
    print("\nTLS")
    status, _, err = get("https://export.arxiv.org/api/query?id_list=1706.03762")
    if err and "CERTIFICATE_VERIFY_FAILED" in err:
        r.fail(
            "certificate verification · 证书验证",
            "CERTIFICATE_VERIFY_FAILED",
            fix=[
                "The python.org build does not use the macOS keychain.",
                "python.org 的构建不使用 macOS 钥匙串,必须手动装证书:",
                "",
                f"  open '/Applications/Python {sys.version_info.major}."
                f"{sys.version_info.minor}/Install Certificates.command'",
                "",
                "Wait for 'update complete', then re-run this doctor.",
                "等它打印 update complete,再重跑本体检。",
            ],
        )
    elif err:
        r.warn("certificate verification · 证书验证", f"inconclusive · 无法判定 ({err})")
    else:
        r.ok("certificate verification · 证书验证", f"cafile: {ssl.get_default_verify_paths().openssl_cafile}")


def check_toolchains(r: Report) -> None:
    """Non-Python toolchains, reported as advisory only. 非 Python 工具链,仅作提醒。

    Quick start steps 5 and 6 need Node and Rust. Nothing in the verification core
    does, and STATUS.md lists both the TS orchestrator and the desktop shell as
    never having been run — so a missing toolchain is a smaller world, not a broken
    one. Reporting it as blocking would repeat the mistake this file already made
    once with rate limiting: telling someone they cannot run when they can.
    Quick start 第 5、6 步需要 Node 与 Rust。校验内核一概不需要,而 STATUS.md 把
    TS orchestrator 和桌面壳都列为「从未运行」—— 所以缺工具链是「能做的事少一些」,
    不是「坏了」。把它报成阻塞,等于重犯本文件在限流上已经犯过的那个错:
    告诉一个明明能跑的人他不能跑。
    """
    print("\nOptional toolchains · 可选工具链")
    for cmd, args, what in [("node", ["--version"], "orchestrator-ts (Quick start 5)"),
                            ("npm", ["--version"], "orchestrator-ts / apps/shell"),
                            ("cargo", ["--version"], "desktop shell (Quick start 6)")]:
        exe = shutil.which(cmd)
        if not exe:
            r.skip(f"{cmd} · {what}", "not installed — that step is unavailable · 未安装,该步骤不可用")
            continue
        try:
            out = subprocess.run([exe] + args, capture_output=True, text=True, timeout=15)
            r.ok(f"{cmd} · {what}", out.stdout.strip().splitlines()[0] if out.stdout.strip() else "")
        except Exception as e:  # noqa: BLE001
            r.warn(f"{cmd} · {what}", f"{type(e).__name__}: {e}")


def check_verifier_capability(r: Report, offline: bool) -> None:
    """Probe through the project's own code path, not around it.

    走项目自己的代码路径,而不是绕过它。

    An earlier version of this file issued its own urllib requests. It therefore
    checked whether *this machine* could reach arXiv — not whether *this project's
    verifier* could. Those came apart in practice: doctor reported all green while
    coe_kernel.apis was failing every arXiv lookup, because apis was still using a
    plaintext http:// URL that timed out. A doctor that does not exercise the real
    call path can certify an environment the code cannot actually work in.
    本文件早先版本自己发 urllib 请求,于是它检查的是「这台机器能不能连上 arXiv」,
    而不是「这个项目的校验器能不能」。两者真的分开过:doctor 全绿,而 coe_kernel.apis
    的每一次 arXiv 查询都在失败 —— 因为 apis 还在用会超时的明文 http:// 地址。
    不走真实调用路径的体检,会给一个代码根本跑不通的环境发合格证。

    Going through apis also inherits its throttling, circuit breaker and on-disk
    cache. The cache means a repeat run may answer from a stored authoritative
    denial rather than the network — which is the honest answer to "can the verifier
    judge this?", since a cached denial is a real capability.
    走 apis 也就继承了它的限速、熔断与磁盘缓存。缓存意味着重复运行可能由已存的权威
    否定作答而非网络 —— 对「校验器判得了吗」这个问题,这正是诚实的答案:缓存里的
    权威否定就是一种真实能力。
    """
    print("\nVerification services · 校验服务")
    print("  \033[90m(through coe_kernel.apis — the real call path · 走 coe_kernel.apis 真实调用路径)\033[0m")

    if offline:
        r.skip("all network checks · 全部网络检查", "--offline")
        return

    try:
        sys.path.insert(0, os.getcwd())
        from coe_kernel import apis
    except Exception as e:  # noqa: BLE001
        r.fail("import coe_kernel.apis", f"{type(e).__name__}: {e}",
               fix=["Run from the repository root · 必须在仓库根目录下运行。"])
        return

    def probe(label, fn, want, detail, fix=None):
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001
            r.degrade(label, f"{type(e).__name__}: {e}", fix=fix)
            return
        if got is want:
            r.ok(label, detail)
        elif got is None:
            r.degrade(label, "verifier returned unknown · 校验器返回未知", fix=fix)
        else:
            r.warn(label, f"unexpected verdict {got!r} — investigate · 判定异常,需排查")

    rate_fix = [
        "Reachable but unable to decide. Fabricated citations come back 'manual'",
        "(transport failure) instead of 'reject', and the narrowing experiment will",
        "report NOT ELIGIBLE. The repo still runs and the tests still pass.",
        "连得上但判不了。捏造引用会返回 manual(传输失败)而非 reject,narrowing",
        "实验会被判为不适格。仓库照常运行,测试照常通过。",
        "",
        "Usually rate limiting — wait, or run from another network.",
        "通常是限流 —— 等一会儿,或换网络重试。",
    ]

    probe("arXiv · confirm an existing ID · 确认已有 ID",
          lambda: apis.check_arxiv("1706.03762")[0], True, "1706.03762", rate_fix)
    probe("arXiv · definitive negative for a fake ID · 对捏造 ID 给出明确否定",
          lambda: apis.check_arxiv("2099.99999")[0], False, "2099.99999 → absent", rate_fix)
    probe("CrossRef · confirm a real DOI · 确认真实 DOI",
          lambda: apis.check_doi("10.1038/s41586-021-03819-2")[0], True,
          "10.1038/s41586-021-03819-2", rate_fix)
    probe("CrossRef · definitive negative · 明确否定",
          lambda: apis.check_doi("10.9999/fake.nonexistent.2099")[0], False,
          "authoritative absence · 权威否定", rate_fix)

    try:
        matched, _, _ = apis.match_openalex("Attention Is All You Need")
    except Exception as e:  # noqa: BLE001
        matched = None
        r.degrade("OpenAlex · index lookup · 索引查询", f"{type(e).__name__}: {e}")
    else:
        if matched is None:
            r.degrade("OpenAlex · index lookup · 索引查询",
                      "index unreachable · 索引不可达",
                      fix=["Add a mailto to enter the polite pool · 加 mailto 进 polite pool:",
                           "  export OPENALEX_MAILTO=you@example.com"])
        else:
            r.ok("OpenAlex · index lookup · 索引查询",
                 "confirms only, never refutes · 只确认,不证伪")

    breaker = {k: v for k, v in apis._fails.items() if v}
    if breaker:
        r.warn("circuit breaker · 熔断计数", f"{breaker} (opens at {apis._BREAK} · 阈值)")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="F3-OpenScience environment doctor · 环境体检")
    ap.add_argument("--offline", action="store_true",
                    help="skip all network checks · 跳过全部网络检查")
    args = ap.parse_args()

    print("F3-OpenScience · environment doctor · 环境体检")
    print("=" * 66)

    r = Report()
    check_python(r)
    if sys.version_info[:2] >= MIN_PY:
        check_imports(r)
        check_tls(r)
    else:
        print("\n  \033[90m(remaining checks skipped until Python is upgraded ·"
              " 升级 Python 前跳过后续检查)\033[0m")
        _summarise(r)
        return 1
    check_verifier_capability(r, args.offline)
    check_toolchains(r)

    return _summarise(r)


def _summarise(r: Report) -> int:
    print("\n" + "=" * 66)
    if not r.failures:
        if r.degraded:
            print(f"  \033[33mRUNNABLE, MEASUREMENT DEGRADED · 可运行,但测量能力受损"
                  f" ({len(r.degraded)})\033[0m")
            for label, fix in r.degraded:
                print(f"\n  ~~ {label}")
                for line in fix:
                    print(f"     {line}" if line else "")
            print("\n  You can run everything. Expect the narrowing experiment to")
            print("  report NOT ELIGIBLE until this clears.")
            print("  一切照常可跑。在此之前 narrowing 实验会报不适格。")
        else:
            msg = "READY · 可以运行"
            if r.warnings:
                msg += f"   ({len(r.warnings)} warning(s) · 项提醒)"
            print(f"  \033[32m{msg}\033[0m")
        print("\n  Next · 下一步:")
        print("    python3 experiments/narrowing/run_experiment.py")
        return 0

    print(f"  \033[31mNOT READY · 尚不可运行 ({len(r.failures)} blocking · 项阻塞)\033[0m")
    for label, fix in r.failures:
        print(f"\n  ── {label}")
        for line in fix:
            print(f"     {line}" if line else "")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
