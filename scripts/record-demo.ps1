# 一键录制 F3-OpenScience Tauri 桌面壳真视频(Windows / PowerShell)。
# 用法:  pwsh -File scripts\record-demo.ps1
# 依赖:  Rust + cargo-tauri、Node>=18、Python>=3.11。录屏用 Win+G(Xbox Game Bar)或 OBS。
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # -> opensci\

Write-Host "═══ F3-OpenScience 桌面壳录制 (Windows) ═══"

function Need($cmd,$hint){ if(-not (Get-Command $cmd -ErrorAction SilentlyContinue)){ Write-Host "✗ 缺 $cmd : $hint"; $script:miss=$true } }
$miss=$false
Need node "https://nodejs.org (>=18)"
Need python "https://python.org (>=3.11)"
Need cargo "https://rustup.rs"
if($miss){ Write-Host "请先装齐缺失项。"; exit 1 }
if(-not (Get-Command cargo-tauri -ErrorAction SilentlyContinue)){ Write-Host "· 安装 tauri-cli …"; cargo install tauri-cli --locked }

Write-Host "· 安装依赖 …"
Push-Location apps\shell;      npm i --silent; Pop-Location
Push-Location orchestrator-ts; npm i --silent; Pop-Location
python -c "import sys; sys.path.insert(0,'.'); import coe_kernel, memory.server, pipeline.server; print('  OK sidecars')"

Write-Host "· 启动 Tauri 壳(cargo tauri dev)… 首次编译数分钟"
Push-Location apps\shell
$shell = Start-Process -PassThru -NoNewWindow cargo -ArgumentList "tauri","dev"
Pop-Location

Write-Host ""
Write-Host "▶▶ 窗口出现后开始录屏:"
Write-Host "   录屏方式一(内置):按 Win+G 打开 Xbox Game Bar → 点录制。"
Write-Host "   录屏方式二(推荐):用 OBS Studio 录 F3-OpenScience 窗口,画质可控。"
Write-Host "   在窗口里:输入方向 → 选模型 → 运行 → GATE 确认 → 看事件流/主权面板。"
Write-Host ""
Write-Host "录完后关闭本窗口或按 Ctrl-C;将自动结束壳进程。"
try { Wait-Process -Id $shell.Id } finally {
  Stop-Process -Id $shell.Id -ErrorAction SilentlyContinue
  Get-Process | Where-Object { $_.Path -like "*tsx*" } | Stop-Process -ErrorAction SilentlyContinue
}
