import sys

if sys.version_info < (3, 11):
    # The package uses PEP 604 annotations (`list | None`) evaluated at import
    # time, so this fails on the first import rather than at first use. Say so
    # plainly instead of surfacing a TypeError about the `|` operator.
    # 本包使用 PEP 604 注解(`list | None`),在导入时求值,因此第一次 import 就会
    # 失败,而非用到才失败。直接说清楚,而不是抛一个关于 `|` 运算符的 TypeError。
    sys.exit(
        f"F3-OpenScience requires Python 3.11+, but this is "
        f"{sys.version.split()[0]} at {sys.executable}\n"
        f"需要 Python 3.11 以上,当前为 {sys.version.split()[0]}\n"
        f"\n"
        f"  python3 -m venv .venv && source .venv/bin/activate\n"
        f"  python3 scripts/doctor.py     # full environment check · 完整体检\n"
    )

from .kernel import run_verify
