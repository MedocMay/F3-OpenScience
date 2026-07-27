"""沙箱强隔离回归 — 多租户云端执行 agent 生成代码的安全边界。
注:不在共享 CI 跑 fork bomb —— 它会拖垮共享 runner。NPROC 限制的有效性由 setrlimit 保证。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cloud.sandbox import LocalSandbox


class Unsupported(Exception):
    """This platform cannot provide the capability under test.

    本平台无法提供被测能力。

    Not a failure. "I cannot test this here" and "this is broken" are different
    findings, and collapsing them is the same mistake this project exists to name —
    a verifier reporting its own blind spot as a fact about the world.
    这不是失败。「我在这儿测不了」和「这东西是坏的」是两种不同的结论,把它们合并
    正是本项目要指出的那个错误 —— 校验器把自己的盲区报告成关于世界的事实。
    """

def test_normal_runs():
    r = LocalSandbox().run("print('improvement 14.8%')")
    assert r.ok and "14.8%" in r.stdout

def test_secret_scrubbed():
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-SECRET-XYZ"
    r = LocalSandbox().run("import os;print(os.environ.get('ANTHROPIC_API_KEY','none'))")
    assert "SECRET" not in r.stdout                 # BYOK 密钥对生成代码不可见

def test_no_env_leak_beyond_safe():
    os.environ["OPENSCI_MASTER_KEY"] = "master-secret"
    r = LocalSandbox().run("import os;print(list(os.environ.keys()))")
    assert "OPENSCI_MASTER_KEY" not in r.stdout and "ANTHROPIC_API_KEY" not in r.stdout

def test_memory_limit_contained():
    # 64MB 上限,尝试分配 ~200MB -> RLIMIT_AS 快速拦截(MemoryError),不拖垮宿主
    sb = LocalSandbox(mem_mb=64, timeout=8)
    gap = sb.unsupported_limits().get("RLIMIT_AS")
    if gap:
        # macOS refuses RLIMIT_AS. The memory ceiling genuinely does not exist here,
        # so this assertion has nothing to assert against — see the sandbox docstring
        # and SandboxResult.limits_unavailable, which report the gap at runtime.
        # macOS 拒绝 RLIMIT_AS。此处内存上限确实不存在,该断言无从断起 ——
        # 缺口由 SandboxResult.limits_unavailable 在运行时如实报告。
        raise Unsupported(f"RLIMIT_AS unsettable on this platform · 本平台不可设 ({gap})")
    r = sb.run("x = bytearray(200*1024*1024)")
    assert not r.ok

def test_timeout():
    r = LocalSandbox(cpu_s=2, timeout=4).run("while True: pass")
    # Linux escalates RLIMIT_CPU to SIGKILL (exit=-9); macOS sends SIGXCPU (exit=-24).
    # The invariant is that the sandbox stopped it, not which signal did the stopping.
    # Linux 把 RLIMIT_CPU 升级为 SIGKILL(exit=-9),macOS 送 SIGXCPU(exit=-24)。
    # 不变量是「被沙箱终止」,而非某个平台的信号编号 —— 原断言把局部观测当成了普遍规律。
    assert not r.ok
    assert r.killed_reason == "timeout" or r.killed_reason.startswith("exit=-")

if __name__ == "__main__":
    skipped = []
    for t in [test_normal_runs, test_secret_scrubbed, test_no_env_leak_beyond_safe, test_memory_limit_contained, test_timeout]:
        try:
            t(); print(f"✅ {t.__name__}")
        except Unsupported as e:
            skipped.append(t.__name__); print(f"⏭  {t.__name__} SKIP — {e}")
    tail = f" ({len(skipped)} skipped · 项因平台能力缺失跳过)" if skipped else ""
    print(f"\n沙箱强隔离测试 PASSED{tail}")
