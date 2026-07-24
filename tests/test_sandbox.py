"""沙箱强隔离回归 — 多租户云端执行 agent 生成代码的安全边界。
注:不在共享 CI 跑 fork bomb —— 它会拖垮共享 runner。NPROC 限制的有效性由 setrlimit 保证。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cloud.sandbox import LocalSandbox

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
    r = LocalSandbox(mem_mb=64, timeout=8).run("x = bytearray(200*1024*1024)")
    assert not r.ok

def test_timeout():
    r = LocalSandbox(cpu_s=2, timeout=4).run("while True: pass")
    assert not r.ok and r.killed_reason in ("timeout", "exit=-9")

if __name__ == "__main__":
    for t in [test_normal_runs, test_secret_scrubbed, test_no_env_leak_beyond_safe, test_memory_limit_contained, test_timeout]:
        t(); print(f"✅ {t.__name__}")
    print("\n沙箱强隔离测试 PASSED")
