#!/usr/bin/env bash
# 一键录制 F3-OpenScience Tauri 桌面壳真视频(macOS / Linux)。
# 用法:  bash scripts/record-demo.sh [输出文件名.mp4]
# 依赖:  Rust 工具链 + cargo-tauri、Node>=18、Python>=3.11、ffmpeg(Linux)/自带(mac)
set -euo pipefail
cd "$(dirname "$0")/.."                       # -> opensci/
OUT="${1:-opensci-demo-$(date +%Y%m%d-%H%M%S).mp4}"
OS="$(uname -s)"

echo "═══ F3-OpenScience 桌面壳录制 ═══"

# ---------- 0) 环境自检 ----------
need(){ command -v "$1" >/dev/null 2>&1 || { echo "✗ 缺 $1:$2"; MISS=1; }; }
MISS=0
need node   "https://nodejs.org (>=18)"
need python3 "https://python.org (>=3.11)"
need cargo  "https://rustup.rs"
need npx    "随 node 安装"
if [ "$OS" = "Linux" ]; then need ffmpeg "sudo apt install ffmpeg"; fi
[ "$MISS" = "1" ] && { echo "请先装齐上面缺失项再重试。"; exit 1; }
command -v cargo-tauri >/dev/null 2>&1 || { echo "· 安装 tauri-cli …"; cargo install tauri-cli --locked; }

# ---------- 1) 装依赖 ----------
echo "· 安装前端依赖 …"
( cd apps/shell && npm i --silent )
( cd orchestrator-ts && npm i --silent )
echo "· 自检 Python sidecar 可导入 …"
python3 -c "import sys; sys.path.insert(0,'.'); import coe_kernel, memory.server, pipeline.server; print('  ✓ sidecars OK')"

# ---------- 2) 启动壳(后台)----------
echo "· 启动 Tauri 壳(cargo tauri dev)…首次编译 Rust 可能数分钟"
( cd apps/shell && cargo tauri dev >/tmp/f3-openscience-shell.log 2>&1 ) &
SHELL_PID=$!
cleanup(){ kill $SHELL_PID 2>/dev/null || true; pkill -f "tsx .*server.ts" 2>/dev/null || true; }
trap cleanup EXIT
echo "· 等待窗口出现(最多 180s)…"
for i in $(seq 1 180); do grep -q "Running\|app listening\|Built application" /tmp/f3-openscience-shell.log 2>/dev/null && break; sleep 1; done
sleep 5

# ---------- 3) 录屏 ----------
echo ""
echo "▶▶ 开始录制。请在弹出的 F3-OpenScience 窗口里操作:"
echo "   输入研究方向 → 选模型 → 点【运行】→ 在 GATE 弹窗点【确认】→ 看事件流/主权面板"
echo "   录完按 Ctrl-C 结束。输出:$OUT"
echo ""
if [ "$OS" = "Darwin" ]; then
  # macOS:交互式框选录制(含窗口)。也可换成整屏:screencapture -v "$OUT"
  echo "(macOS:即将用 screencapture 交互录制,按提示框选 F3-OpenScience 窗口区域;结束按 Ctrl-C)"
  screencapture -v -R"$(python3 - <<'PY'
print("0,0,1100,760")  # 默认区域=壳窗口尺寸;可手动改
PY
)" "$OUT" || true
else
  # Linux:ffmpeg 录 X11 屏幕。Wayland 用 wf-recorder 替代(见下方注释)。
  RES="$(xdpyinfo 2>/dev/null | awk '/dimensions/{print $2}')"; RES="${RES:-1280x800}"
  ffmpeg -y -f x11grab -framerate 30 -video_size "$RES" -i "${DISPLAY:-:0}" \
         -c:v libx264 -pix_fmt yuv420p -preset veryfast "$OUT"
  # Wayland 替代:  wf-recorder -f "$OUT"
fi
echo "✓ 完成:$OUT"
