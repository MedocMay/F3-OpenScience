"""沙箱强隔离 — 安全执行 agent 生成的代码。多租户云端的必备安全边界。
本地后端(hardened subprocess):环境擦除 + 资源限制 + 目录 jail + 可选网络隔离。
容器后端(生产):docker/gVisor,--network none + 内存/CPU 限制 + 只读根 + 非特权用户。
按 OPENSCI_SANDBOX 选择(local | container)。"""
from __future__ import annotations
import os, sys, subprocess, tempfile, shutil
IS_WIN = os.name == "nt"
if not IS_WIN:
    import resource

# 允许透传给沙箱的最小环境(绝不含任何 *_API_KEY / TOKEN / SECRET)
_SAFE_ENV_KEYS = {"PATH", "LANG", "LC_ALL", "TZ", "HOME", "PYTHONHASHSEED"}

def _safe_env() -> dict:
    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    if IS_WIN:
        # Windows 需保留少量系统变量,否则 Python 无法启动
        for k in ("SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC", "USERPROFILE"):
            if k in os.environ: env[k] = os.environ[k]
        env.setdefault("PATH", os.environ.get("PATH", ""))
    else:
        env.setdefault("PATH", "/usr/bin:/bin")
        env["HOME"] = tempfile.gettempdir()    # 由调用方覆写为 jail 目录
    return env

class SandboxResult:
    def __init__(self, ok, stdout, stderr, killed_reason=None):
        self.ok, self.stdout, self.stderr, self.killed_reason = ok, stdout, stderr, killed_reason

class LocalSandbox:
    """hardened subprocess。默认限制:CPU 10s、内存 512MB、进程 64、文件 50MB。"""
    def __init__(self, cpu_s=10, mem_mb=512, nproc=64, fsize_mb=50, timeout=20, isolate_net=False):
        self.cpu_s, self.mem_mb, self.nproc, self.fsize_mb = cpu_s, mem_mb, nproc, fsize_mb
        self.timeout = timeout
        self.isolate_net = isolate_net and shutil.which("unshare") is not None

    def _preexec(self):
        # 仅 POSIX。Windows 无 setrlimit,依赖超时 + 环境擦除 + jail(见 run())
        os.setsid()                                                   # 独立进程组,超时可整组杀
        resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_s, self.cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (self.mem_mb*1024*1024,)*2)      # 内存
        resource.setrlimit(resource.RLIMIT_NPROC, (self.nproc, self.nproc))     # 防 fork bomb
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.fsize_mb*1024*1024,)*2) # 文件大小

    def run(self, code: str) -> SandboxResult:
        jail = tempfile.mkdtemp(prefix="sbx_")
        try:
            script = os.path.join(jail, "run.py")
            open(script, "w").write(code)
            env = _safe_env()
            if not IS_WIN: env["HOME"] = jail
            argv = [sys.executable, "-I", "run.py"]                   # -I 隔离模式:忽略 env/用户 site
            if self.isolate_net and not IS_WIN:
                argv = ["unshare", "-n", "--"] + argv                 # 无网络命名空间
            kw = {}
            if IS_WIN:
                # Windows:新建进程组,超时可整组终止(资源限额需 Job Object,建议用容器后端)
                kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                kw["preexec_fn"] = self._preexec
            try:
                p = subprocess.run(argv, cwd=jail, env=env, capture_output=True, text=True,
                                   timeout=self.timeout, **kw)
                return SandboxResult(p.returncode == 0, p.stdout, p.stderr,
                                     None if p.returncode == 0 else f"exit={p.returncode}")
            except subprocess.TimeoutExpired:
                return SandboxResult(False, "", "", "timeout")
        finally:
            shutil.rmtree(jail, ignore_errors=True)

class ContainerSandbox:
    """生产后端 — 容器强隔离。写成同接口;需 docker/gVisor,不在此环境跑。"""
    IMAGE = os.environ.get("OPENSCI_SANDBOX_IMAGE", "python:3.11-slim")
    def run(self, code: str) -> SandboxResult:
        jail = tempfile.mkdtemp(prefix="sbx_"); open(os.path.join(jail,"run.py"),"w").write(code)
        argv = ["docker","run","--rm","--network","none","--memory","512m","--cpus","1",
                "--read-only","--tmpfs","/tmp","--user","nobody","--security-opt","no-new-privileges",
                "-v",f"{jail}:/work:ro","-w","/work", self.IMAGE, "python","-I","run.py"]
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            return SandboxResult(p.returncode==0, p.stdout, p.stderr, None if p.returncode==0 else f"exit={p.returncode}")
        except Exception as e:
            return SandboxResult(False,"",str(e),"container_error")
        finally:
            shutil.rmtree(jail, ignore_errors=True)

def get_sandbox():
    if os.environ.get("OPENSCI_SANDBOX") == "container":
        return ContainerSandbox()
    return LocalSandbox(isolate_net=os.environ.get("OPENSCI_SANDBOX_NET_ISOLATE") == "1")
