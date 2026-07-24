# 构建各平台安装产物(Windows / PowerShell)。用法: pwsh -File packaging\build-installers.ps1 [backend|desktop|all]
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$What = if ($args.Count -gt 0) { $args[0] } else { "all" }
New-Item -ItemType Directory -Force dist | Out-Null

function Build-Backend {
  Write-Host "▶ 后端:wheel + sdist"
  python -m pip install --quiet build
  python -m build
  Write-Host "✓ dist\ 下已生成 wheel 与 sdist"
  if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    pyinstaller --onefile --name f3-gateway `
      --add-data "$PWD\contracts;contracts" --paths "$PWD" --paths "$PWD\orchestrator" `
      --hidden-import orchestrator --hidden-import rpc --hidden-import state_machine --hidden-import packager `
      --collect-submodules coe_kernel --collect-submodules memory --collect-submodules pipeline `
      --collect-submodules cloud --collect-submodules model `
      deploy\gateway.py --distpath dist\bin --clean -y
    Write-Host "✓ dist\bin\f3-gateway.exe"
  } else { Write-Host "· 未装 pyinstaller,跳过单文件构建" }
}
function Build-Desktop {
  Write-Host "▶ 桌面壳:Tauri 打包(需 Rust + MSVC Build Tools)"
  if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { Write-Host "✗ 需要 Rust: https://rustup.rs"; return }
  Push-Location apps\shell; npm i; npm run tauri build; Pop-Location
  Write-Host "✓ 安装包(.msi/.exe)在 apps\shell\src-tauri\target\release\bundle\"
}
switch ($What) {
  "backend" { Build-Backend }
  "desktop" { Build-Desktop }
  default   { Build-Backend; Build-Desktop }
}
Write-Host "完成。平台矩阵见 packaging\PLATFORMS.md"
