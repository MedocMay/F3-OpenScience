# 本地录制 Tauri 桌面壳真视频

在你自己的机器上一键启动壳 + 录屏(此仓库环境无 GUI/cargo,无法在线录)。

## 前置(一次性)
- **Rust**:https://rustup.rs  · **Node ≥18** · **Python ≥3.11**
- Linux 另需 `ffmpeg`(`sudo apt install ffmpeg`);Wayland 用 `wf-recorder`
- 脚本会自动 `cargo install tauri-cli` 和 `npm i`

## 用法
```bash
# macOS / Linux
bash scripts/record-demo.sh   my-demo.mp4

# Windows (PowerShell)
pwsh -File scripts\record-demo.ps1
```
脚本会:自检依赖 → 装前端依赖 → 校验 Python sidecar → `cargo tauri dev` 起壳 → 启动录屏。
录制时照着 [`demo-walkthrough.md`](demo-walkthrough.md) 点(~40 秒一条完整链路),按 `Ctrl-C` 结束。

## 录屏后端
- **macOS**:内置 `screencapture -v`(脚本已调用;整屏可改 `screencapture -v out.mp4`)。
- **Linux/X11**:`ffmpeg x11grab`(脚本已调用)。Wayland 改 `wf-recorder -f out.mp4`。
- **Windows**:`Win+G`(Xbox Game Bar)或 **OBS Studio**(推荐,画质可控)。

## 最有冲击力的镜头
第 7 步 `blocked_pre_signoff`(红,拒绝给不可信产出署名)→ 第 8 步 `signed`(绿,飞轮规避后一次过)。
两处各停 1–2 秒对比,就是整个产品的卖点。

> 提示:先跑一遍 `bash demo.sh`(纯终端,无需 Rust)确认后端 OK,再录桌面壳,能少踩坑。
