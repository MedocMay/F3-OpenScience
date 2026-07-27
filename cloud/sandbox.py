"""沙箱强隔离 — 安全执行 agent 生成的代码。多租户云端的必备安全边界。
本地后端(hardened subprocess):环境擦除 + 资源限制 + 目录 jail + 可选网络隔离。
容器后端(生产):docker/gVisor,--network none + 内存/CPU 限制 + 只读根 + 非特权用户。
按 OPENSCI_SANDBOX 选择(local | container)。"""
from __future__ import annotations
import os, sys, json, subprocess, tempfile, shutil
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
    def __init__(self, ok, stdout, stderr, killed_reason=None, limits_unavailable=None):
        self.ok, self.stdout, self.stderr, self.killed_reason = ok, stdout, stderr, killed_reason
        # Which resource limits the platform refused. Non-empty means the isolation
        # is weaker than advertised — say so rather than let the caller assume.
        # 平台拒绝设置的资源限制。非空即表示隔离弱于标称 —— 如实说明,不让调用方误以为完整。
        self.limits_unavailable = limits_unavailable or {}

class LocalSandbox:
    """hardened subprocess。默认限制:CPU 10s、内存 512MB、进程 64、文件 50MB。

    **Not every platform grants every limit.** macOS refuses RLIMIT_AS, so the memory
    ceiling does not exist there; Windows has no setrlimit at all. Call
    unsupported_limits() — or read SandboxResult.limits_unavailable — to see what this
    platform actually enforces. A non-empty result means the isolation is weaker than
    the defaults above suggest.
    **并非每个平台都给得起每一道限制。** macOS 拒绝 RLIMIT_AS,内存上限在那里并不存在;
    Windows 根本没有 setrlimit。用 unsupported_limits()(或读
    SandboxResult.limits_unavailable)查看本平台真正强制了哪些。非空即表示隔离弱于上面
    标称的默认值。

    For multi-tenant or untrusted workloads use ContainerSandbox (docker / gVisor),
    which enforces memory and CPU regardless of host platform. LocalSandbox on a
    platform with missing limits is a development convenience, not a security boundary.
    多租户或不可信负载请用 ContainerSandbox(docker / gVisor),它不依赖宿主平台即可强制
    内存与 CPU。在缺限制的平台上,LocalSandbox 是开发便利,不是安全边界。
    """
    def __init__(self, cpu_s=10, mem_mb=512, nproc=64, fsize_mb=50, timeout=20, isolate_net=False):
        self.cpu_s, self.mem_mb, self.nproc, self.fsize_mb = cpu_s, mem_mb, nproc, fsize_mb
        self.timeout = timeout
        self.isolate_net = isolate_net and shutil.which("unshare") is not None
        self._unsupported = None      # lazily probed by unsupported_limits()

    def _limit_spec(self):
        return [("RLIMIT_CPU",   (self.cpu_s, self.cpu_s)),                  # CPU 时间
                ("RLIMIT_AS",    (self.mem_mb*1024*1024,)*2),                # 内存
                ("RLIMIT_NPROC", (self.nproc, self.nproc)),                  # 防 fork bomb
                ("RLIMIT_FSIZE", (self.fsize_mb*1024*1024,)*2)]              # 文件大小

    def unsupported_limits(self) -> dict:
        """Limits this platform refuses, as {name: reason}. Empty = full isolation.

        本平台拒绝设置的限制,{名称: 原因}。空字典 = 完整隔离。

        A limit the platform will not set is a capability gap, not a fatal error —
        the same distinction this project draws between "cannot verify" and "does
        not exist". Previously RLIMIT_AS raised ValueError on macOS, _preexec died
        with it, and *every* sandbox run failed: the boundary was not weakened, it
        was absent. Now the gap is reported instead of taking the sandbox down.

        平台设不上的限制是能力缺口,不是致命错误 —— 与本项目区分「核验不了」和
        「不存在」是同一条线。此前 RLIMIT_AS 在 macOS 上抛 ValueError,_preexec
        随之中断,**每一次**沙箱执行都失败:边界不是被削弱,而是根本不存在。
        现在缺口被如实报告,而不是让沙箱整个瘫痪。

        Probed in a throwaway child so a failed probe cannot damage this process's
        own limits (lowering a hard limit is irreversible for non-root).
        在一次性子进程里探测:探测失败不会损伤本进程自己的限制(非 root 降低硬限
        不可逆)。
        """
        if IS_WIN:
            return {n: "Windows has no setrlimit · Windows 无 setrlimit"
                    for n, _ in self._limit_spec()}
        if self._unsupported is None:
            src = ("import json,resource as R,sys\n"
                   "o={}\n"
                   "for n,v in json.loads(sys.argv[1]):\n"
                   "    try: R.setrlimit(getattr(R,n),tuple(v)); o[n]=None\n"
                   "    except Exception as e: o[n]='%s: %s'%(type(e).__name__,e)\n"
                   "print(json.dumps(o))")
            spec = json.dumps([[n, list(v)] for n, v in self._limit_spec()])
            try:
                p = subprocess.run([sys.executable, "-c", src, spec],
                                   capture_output=True, text=True, timeout=15)
                probe = json.loads(p.stdout)
            except Exception as e:
                probe = {n: f"probe failed · 探测失败: {type(e).__name__}"
                         for n, _ in self._limit_spec()}
            self._unsupported = {n: r for n, r in probe.items() if r}
        return self._unsupported

    def _preexec(self):
        # 仅 POSIX。Windows 无 setrlimit,依赖超时 + 环境擦除 + jail(见 run())
        os.setsid()                                                   # 独立进程组,超时可整组杀
        for name, val in self._limit_spec():
            try:
                resource.setrlimit(getattr(resource, name), val)
            except (ValueError, OSError):
                pass          # 平台不支持 —— 由 unsupported_limits() 如实报告,不静默假装已设

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
                                     None if p.returncode == 0 else f"exit={p.returncode}",
                                     self.unsupported_limits())
            except subprocess.TimeoutExpired:
                return SandboxResult(False, "", "", "timeout", self.unsupported_limits())
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
