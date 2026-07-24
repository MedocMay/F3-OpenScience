#!/usr/bin/env bash
# 构建各平台安装产物。在目标 OS 上运行(交叉编译桌面壳不可靠)。
# 用法: bash packaging/build-installers.sh [backend|desktop|all]
set -euo pipefail
cd "$(dirname "$0")/.."
WHAT="${1:-all}"
OS="$(uname -s 2>/dev/null || echo Windows)"
mkdir -p dist

build_backend() {
  echo "▶ 后端:构建 Python wheel + sdist(跨平台通用)"
  python3 -m pip install --quiet build >/dev/null 2>&1 || true
  python3 -m build
  echo "✓ dist/ 下已生成 wheel 与 sdist —— 任何 OS 上 pip install 即用"
  echo "▶ 后端:构建独立可执行(免装 Python,可选)"
  if command -v pyinstaller >/dev/null 2>&1; then
    # 冻结后 sys.path 失效 -> 必须显式 hidden-import + 收集子模块(已实测)
    SEP=":"; [ "$OS" = "Windows" ] && SEP=";"
    pyinstaller --onefile --name f3-gateway \
      --add-data "$(pwd)/contracts${SEP}contracts" \
      --paths "$(pwd)" --paths "$(pwd)/orchestrator" \
      --hidden-import orchestrator --hidden-import rpc --hidden-import state_machine --hidden-import packager \
      --collect-submodules coe_kernel --collect-submodules memory --collect-submodules pipeline \
      --collect-submodules cloud --collect-submodules model \
      deploy/gateway.py --distpath dist/bin --workpath "${TMPDIR:-/tmp}/pyi" --specpath "${TMPDIR:-/tmp}/pyi_spec" --clean -y
    echo "✓ dist/bin/f3-gateway(免装 Python 的单文件,实测可运行)"
  else
    echo "· 未装 pyinstaller,跳过(pip install pyinstaller 后可生成免 Python 运行的单文件)"
  fi
}

build_desktop() {
  echo "▶ 桌面壳:Tauri 打包(需 Rust 工具链)"
  command -v cargo >/dev/null || { echo "✗ 需要 Rust: https://rustup.rs"; return 1; }
  (cd apps/shell && npm i && npm run tauri build)
  echo "✓ 安装包在 apps/shell/src-tauri/target/release/bundle/"
  case "$OS" in
    Darwin) echo "   → .dmg / .app(分发前请签名+公证)";;
    Linux)  echo "   → .AppImage / .deb / .rpm";;
    *)      echo "   → .msi / .exe";;
  esac
}

case "$WHAT" in
  backend) build_backend;;
  desktop) build_desktop;;
  all)     build_backend; build_desktop || echo "(桌面壳跳过)";;
esac
echo "完成。平台矩阵见 packaging/PLATFORMS.md"
