# PyInstaller spec — 单文件后端(免装 Python)。用法:pyinstaller packaging/opensci.spec
# 关键:冻结后 sys.path 失效,必须显式声明 hiddenimports + 收集子模块。
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.getcwd())
hidden = (["orchestrator", "rpc", "state_machine", "packager"]
          + collect_submodules("coe_kernel") + collect_submodules("memory")
          + collect_submodules("pipeline") + collect_submodules("cloud")
          + collect_submodules("model"))

a = Analysis(
    ["../deploy/gateway.py"],
    pathex=[ROOT, os.path.join(ROOT, "orchestrator")],
    datas=[(os.path.join(ROOT, "contracts"), "contracts")],
    hiddenimports=hidden,
    hookspath=[], runtime_hooks=[], excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="f3-gateway",
          console=True, upx=False, onefile=True)
