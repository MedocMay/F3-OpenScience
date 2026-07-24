#!/usr/bin/env bash
# 生成三种部署方式 × 三大操作系统的安装包。
# 用法: bash packaging/build-packages.sh [输出目录]
# 产物: F3-OpenScience-{本地部署|云端部署|混合部署}-{Windows|macOS|Linux}-v<版本>.{zip|tar.gz}
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
VER="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
OUT="${1:-$ROOT/../installers}"
STAGE="$(mktemp -d)"
mkdir -p "$OUT"
trap 'rm -rf "$STAGE"' EXIT

echo "F3-OpenScience 安装包生成器  版本 $VER"
echo "输出目录: $OUT"
echo ""

# ---------- 共用核心(所有模式都要) ----------
CORE=(coe_kernel memory pipeline model orchestrator cloud contracts
      pyproject.toml README.md LICENSE INSTALL.md DEPLOY.md DEMO.md
      REACHABILITY.md CHANGELOG.md STATUS.md INNOVATION.md demo.sh Makefile)

copy_core() {                       # $1 = 目标目录
  local d="$1"
  mkdir -p "$d"
  for p in "${CORE[@]}"; do cp -r "$ROOT/$p" "$d/" 2>/dev/null || true; done
  mkdir -p "$d/tests" && cp "$ROOT"/tests/*.py "$d/tests/" 2>/dev/null || true
  cp -r "$ROOT/tests/golden" "$d/tests/" 2>/dev/null || true
  mkdir -p "$d/deploy"
  # 清理运行产物
  find "$d" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  find "$d" -name '*.pyc' -delete 2>/dev/null || true
  find "$d" -name '*.db'  -delete 2>/dev/null || true
}

# ---------- 各模式追加的文件 ----------
add_mode_files() {                  # $1=目标目录 $2=模式
  local d="$1" mode="$2"
  case "$mode" in
    local)
      cp "$ROOT/deploy/gateway.py" "$ROOT/deploy/global_service.py" "$d/deploy/"
      cp "$ROOT/deploy/run-local.sh" "$d/deploy/"
      cp "$ROOT/deploy/LOCAL.md" "$ROOT/deploy/STORAGE.md" "$d/deploy/"
      cp "$ROOT/deploy/.env.example" "$d/deploy/"
      mkdir -p "$d/deploy/docker" && cp "$ROOT/deploy/docker/compose.local.yml" \
        "$ROOT/deploy/docker/Dockerfile" "$ROOT/deploy/docker/Dockerfile.global" "$d/deploy/docker/"
      cp -r "$ROOT/apps" "$d/" 2>/dev/null || true      # 桌面壳源码(可自行构建)
      ;;
    cloud)
      cp "$ROOT/deploy/gateway_cloud.py" "$ROOT/deploy/gateway.py" \
         "$ROOT/deploy/global_service.py" "$d/deploy/"
      cp "$ROOT/deploy/CLOUD.md" "$ROOT/deploy/PROD.md" "$ROOT/deploy/STORAGE.md" "$d/deploy/"
      cp "$ROOT/deploy/.env.prod.example" "$d/deploy/"
      mkdir -p "$d/deploy/docker"
      cp "$ROOT"/deploy/docker/* "$d/deploy/docker/"
      ;;
    hybrid)
      cp "$ROOT/deploy/gateway.py" "$ROOT/deploy/global_service.py" "$d/deploy/"
      cp "$ROOT/deploy/run-local.sh" "$d/deploy/"
      cp "$ROOT/deploy/HYBRID.md" "$ROOT/deploy/LOCAL.md" "$ROOT/deploy/STORAGE.md" "$d/deploy/"
      cp "$ROOT/deploy/.env.example" "$d/deploy/"
      mkdir -p "$d/deploy/docker" && cp "$ROOT/deploy/docker/Dockerfile.global" \
        "$ROOT/deploy/docker/Dockerfile" "$d/deploy/docker/" 2>/dev/null || true
      cp -r "$ROOT/apps" "$d/" 2>/dev/null || true
      ;;
  esac
  # 预构建 wheel(免联网安装)
  if ls "$ROOT"/dist/*.whl >/dev/null 2>&1; then
    mkdir -p "$d/dist" && cp "$ROOT"/dist/*.whl "$d/dist/"
  fi
}

# ---------- 生成安装脚本(按 OS) ----------
write_unix_installer() {            # $1=目标目录 $2=模式 $3=OS名
  local d="$1" mode="$2" osname="$3"
  cat > "$d/安装.sh" <<INSTALLER
#!/usr/bin/env bash
# F3-OpenScience 安装脚本 —— ${osname}
set -euo pipefail
cd "\$(dirname "\$0")"
echo "════════════════════════════════════════════"
echo "  F3-OpenScience 安装  ·  MODE_LABEL  ·  ${osname}"
echo "════════════════════════════════════════════"

# 1) 检查 Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ 未找到 python3。请先安装 Python 3.11+:"
  echo "   macOS : brew install python@3.11   或 https://www.python.org/downloads/"
  echo "   Linux : sudo apt install python3 python3-pip"
  exit 1
fi
PYV=\$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
echo "· Python \$PYV"
python3 - <<'PYCHK'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("✗ 需要 Python 3.11 及以上")
PYCHK

# 2) 安装依赖
echo "· 安装依赖 …"
PIP_EXTRAS="EXTRA_SPEC"
if ls dist/*.whl >/dev/null 2>&1; then
  # wheel 本身不含可选依赖,须显式带上本部署模式所需的 extra
  WHL=\$(ls dist/*.whl | head -1)
  python3 -m pip install --user --quiet "\${WHL}\${PIP_EXTRAS}" 2>/dev/null \\
    || python3 -m pip install --user --quiet --break-system-packages "\${WHL}\${PIP_EXTRAS}"
else
  python3 -m pip install --user --quiet jsonschema cryptography 2>/dev/null \
    || python3 -m pip install --user --quiet --break-system-packages jsonschema cryptography
fi
echo "  ✓ 依赖就绪"

# 3) 生成配置
MODE_CONFIG

# 4) 自检
echo "· 自检核心模块 …"
python3 -c "import sys;sys.path.insert(0,'.');import coe_kernel,memory,cloud.vault;print('  ✓ 核心模块正常')"

echo ""
echo "✓ 安装完成。启动:  bash 启动.sh"
echo "  说明文档:      安装说明.md"
INSTALLER
  chmod +x "$d/安装.sh"
}

write_windows_installer() {         # $1=目标目录 $2=模式
  local d="$1" mode="$2"
  cat > "$d/安装.ps1" <<'INSTALLER'
# F3-OpenScience 安装脚本 —— Windows (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "════════════════════════════════════════════"
Write-Host "  F3-OpenScience 安装  ·  MODE_LABEL  ·  Windows"
Write-Host "════════════════════════════════════════════"

# 1) 检查 Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
  Write-Host "✗ 未找到 Python。请安装 Python 3.11+:https://www.python.org/downloads/"
  Write-Host "  安装时请勾选 Add Python to PATH"
  exit 1
}
$ver = & $py.Source -c "import sys;print('%d.%d'%sys.version_info[:2])"
Write-Host "· Python $ver"
& $py.Source -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Host "✗ 需要 Python 3.11 及以上"; exit 1 }

# 2) 安装依赖
Write-Host "· 安装依赖 …"
$extras = "EXTRA_SPEC"
if (Test-Path "dist\*.whl") {
  $whl = (Get-Item dist\*.whl).FullName
  & $py.Source -m pip install --user --quiet "$whl$extras"
} else {
  & $py.Source -m pip install --user --quiet jsonschema cryptography
}
Write-Host "  ✓ 依赖就绪"

# 3) 生成配置
MODE_CONFIG

# 4) 自检
Write-Host "· 自检核心模块 …"
& $py.Source -c "import sys;sys.path.insert(0,'.');import coe_kernel,memory,cloud.vault;print('  OK 核心模块正常')"

Write-Host ""
Write-Host "✓ 安装完成。启动:  powershell -File 启动.ps1"
Write-Host "  说明文档:      安装说明.md"
INSTALLER
}

# ---------- 生成启动脚本 ----------
write_launchers() {                 # $1=目标目录 $2=模式 $3=os(unix|win)
  local d="$1" mode="$2" ostype="$3"
  if [ "$ostype" = "unix" ]; then
    case "$mode" in
      local|hybrid)
        cat > "$d/启动.sh" <<'L'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data
[ -f deploy/.env ] && set -a && . deploy/.env && set +a || true
echo "· 启动 global 记忆服务 :8090"
OPENSCI_GLOBAL_DB="${OPENSCI_GLOBAL_DB:-./data/global.db}" PORT=8090 python3 deploy/global_service.py &
G=$!
echo "· 启动网关 :${PORT:-8080}"
OPENSCI_DB="${OPENSCI_DB:-./data/gateway.db}" PORT="${PORT:-8080}" python3 deploy/gateway.py &
W=$!
trap 'kill $G $W 2>/dev/null' EXIT
sleep 2
echo ""
echo "✓ F3-OpenScience 已启动 —— http://localhost:${PORT:-8080}"
echo "  健康检查: curl http://localhost:${PORT:-8080}/healthz"
echo "  Ctrl-C 结束"
wait
L
        chmod +x "$d/启动.sh"
        ;;
      cloud)
        cat > "$d/启动.sh" <<'L'
#!/usr/bin/env bash
# 云端启动:优先用 Docker 全栈;无 Docker 则裸跑云网关。
set -euo pipefail
cd "$(dirname "$0")"
if command -v docker >/dev/null 2>&1 && [ -f deploy/.env.prod ]; then
  echo "· 使用 Docker 全栈(Caddy+Postgres+Redis+网关)"
  cd deploy/docker && exec docker compose --env-file ../.env.prod -f compose.prod.yml up -d
fi
echo "· 未检测到 Docker 或 .env.prod,裸跑云网关(开发/内网模式)"
mkdir -p data
[ -f deploy/.env.prod ] && set -a && . deploy/.env.prod && set +a || true
: "${OPENSCI_ADMIN_TOKEN:?请先在 deploy/.env.prod 设置 OPENSCI_ADMIN_TOKEN}"
: "${OPENSCI_MASTER_KEY:?请先在 deploy/.env.prod 设置 OPENSCI_MASTER_KEY}"
OPENSCI_GLOBAL_DB=./data/global.db PORT=8090 python3 deploy/global_service.py &
G=$!
OPENSCI_DATA_ROOT=./data/tenants PORT="${PORT:-8080}" python3 deploy/gateway_cloud.py &
W=$!
trap 'kill $G $W 2>/dev/null' EXIT
sleep 2
echo "✓ 云网关已启动 —— http://localhost:${PORT:-8080}(多租户 + BYOK)"
wait
L
        chmod +x "$d/启动.sh"
        ;;
    esac
  else
    case "$mode" in
      local|hybrid)
        cat > "$d/启动.ps1" <<'L'
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force data | Out-Null
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Host "✗ 未找到 Python,请先运行 安装.ps1"; exit 1 }
$env:OPENSCI_GLOBAL_DB = ".\data\global.db"; $env:PORT = "8090"
$g = Start-Process -PassThru -NoNewWindow $py.Source "deploy\global_service.py"
$env:OPENSCI_DB = ".\data\gateway.db"; $env:PORT = "8080"
$w = Start-Process -PassThru -NoNewWindow $py.Source "deploy\gateway.py"
Start-Sleep 2
Write-Host ""
Write-Host "✓ F3-OpenScience 已启动 —— http://localhost:8080"
Write-Host "  健康检查: curl http://localhost:8080/healthz"
Write-Host "  关闭本窗口即结束"
try { Wait-Process -Id $w.Id } finally {
  Stop-Process -Id $g.Id -ErrorAction SilentlyContinue
  Stop-Process -Id $w.Id -ErrorAction SilentlyContinue
}
L
        ;;
      cloud)
        cat > "$d/启动.ps1" <<'L'
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path deploy\.env.prod)) {
  Write-Host "· 使用 Docker 全栈"
  Set-Location deploy\docker
  docker compose --env-file ..\.env.prod -f compose.prod.yml up -d
  exit 0
}
Write-Host "· 未检测到 Docker,裸跑云网关"
New-Item -ItemType Directory -Force data | Out-Null
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Host "✗ 未找到 Python,请先运行 安装.ps1"; exit 1 }
$env:OPENSCI_DATA_ROOT = ".\data\tenants"; $env:PORT = "8080"
& $py.Source deploy\gateway_cloud.py
L
        ;;
    esac
  fi
}

# ---------- 模式文档 ----------
write_mode_doc() {                  # $1=目标目录 $2=模式 $3=OS名
  local d="$1" mode="$2" osname="$3"
  local unixhint="bash 安装.sh   然后  bash 启动.sh"
  local winhint="powershell -ExecutionPolicy Bypass -File 安装.ps1   然后  powershell -File 启动.ps1"
  local hint="$unixhint"
  [ "$osname" = "Windows" ] && hint="$winhint"

  case "$mode" in
    local)
      cat > "$d/安装说明.md" <<DOC
# F3-OpenScience · 本地部署 · ${osname}

**适合**:个人 / 实验室 / 内网。数据与推理全部留在本机,合规友好。

## 安装
\`\`\`
${hint}
\`\`\`
启动后访问 http://localhost:8080

## 配模型(二选一)
- **本地模型(推荐,数据不出域)**:装 [Ollama](https://ollama.com) → \`ollama pull qwen2.5\`,
  在 \`deploy/.env\` 设 \`OPENSCI_MODEL=ollama:qwen2.5\`
- **云 API**:在 \`deploy/.env\` 设 \`OPENSCI_MODEL=anthropic:claude-haiku-4-5-20251001\` 并填 \`ANTHROPIC_API_KEY\`
  (也支持 openai / gemini / deepseek / kimi / qwen)

## 试用
\`\`\`
curl http://localhost:8080/healthz
curl -X POST http://localhost:8080/v1/runs -d '{"direction":"few-shot RL for battery health","autonomy":1}'
\`\`\`

## 桌面应用(可选)
\`apps/shell\` 是 Tauri 桌面壳源码。需 Rust + Node:
\`\`\`
cd apps/shell && npm i && npm run tauri build
\`\`\`
产出 ${osname} 原生安装包(见 packaging/PLATFORMS.md)。

## 不配模型也能验证
\`bash demo.sh\` —— 跑校验内核与飞轮,确认后端正常。

数据位置:\`./data/\`(SQLite)。备份该目录即备份全部经验库。
DOC
      ;;
    cloud)
      cat > "$d/安装说明.md" <<DOC
# F3-OpenScience · 云端部署 · ${osname}

> ⚠️ **研究原型,资源受限未全面测试。** Docker 编排层从未运行过,
> Postgres/Redis 路径未实跑,安全未经独立审计。完整边界见 STATUS.md。

**适合**:团队 / 对外 SaaS。多租户隔离 + 每用户 BYOK 密钥 + 沙箱强隔离。

## 方式一:Docker 全栈(推荐,一条命令)
自带 Caddy 自动 TLS + Postgres + Redis + 云网关。
\`\`\`
cp deploy/.env.prod.example deploy/.env.prod
#  编辑填入:DOMAIN 与四个密钥(可用 openssl rand -hex 24 生成)
${hint}
\`\`\`

## 方式二:裸跑云网关(内网 / 开发)
无 Docker 时,\`启动\` 脚本会自动降级为直接运行云网关(需先在 .env.prod 设好
OPENSCI_ADMIN_TOKEN 与 OPENSCI_MASTER_KEY)。

## 启动后
\`\`\`
# 发一个租户 token
curl -X POST http://localhost:8080/admin/tenants \\
  -H "Authorization: Bearer \$OPENSCI_ADMIN_TOKEN" \\
  -d '{"tenant_id":"acme","user_id":"alice"}'
# 用户存自己的模型 key(加密落盘)
curl -X POST http://localhost:8080/v1/keys -H "Authorization: Bearer <token>" \\
  -d '{"provider":"anthropic","api_key":"sk-..."}'
\`\`\`

## 安全须知
- \`OPENSCI_MASTER_KEY\` 生产应从 KMS / Vault 注入,不要写死在文件里。
- 公开服务建议部署在 **Linux**:沙箱资源限额(内存 / CPU / 进程数)依赖 POSIX;
  Windows 下沙箱降级为超时 + 环境擦除,建议改用容器后端。
- 详见 deploy/CLOUD.md 与 deploy/PROD.md。
DOC
      ;;
    hybrid)
      cat > "$d/安装说明.md" <<DOC
# F3-OpenScience · 混合部署 · ${osname}

> ⚠️ **研究原型,资源受限未全面测试。** 跨用户飞轮仅在单机模拟多用户下验证过。
> 完整边界见 STATUS.md。

**适合**:既要数据主权、又要跨用户飞轮复利。**推荐形态。**

研究数据、原始记忆、模型推理都留在本地;只有**脱敏后的校验模式**上传到中心
global 服务,换取"越多人用越准"的复利。

## 一、中心侧(全组织部署一次)
在一台服务器上:
\`\`\`
export OPENSCI_GLOBAL_TOKEN=\$(openssl rand -hex 24)
python3 deploy/global_service.py            # 监听 :8090
\`\`\`
或用 Docker:\`docker build -f deploy/docker/Dockerfile.global -t f3-global . && docker run -p 8090:8090 f3-global\`

## 二、每个用户 / 机构侧
\`\`\`
${hint}
\`\`\`
安装脚本会生成 \`deploy/.env\`,请填入中心地址与 token:
\`\`\`
OPENSCI_GLOBAL_URL=http://中心服务器:8090
OPENSCI_GLOBAL_TOKEN=<中心发放的 token>
OPENSCI_MODEL=ollama:qwen2.5        # 本地模型 → 推理也不出域
\`\`\`

## 数据边界(已实测)
- 上行的只有 \`NONEXISTENT_CITATION\` 这类**抽象模式**,不含研究内容、想法、原始引用。
- 需 **≥2 个不同用户**独立复现,该经验才在 global 生效(防噪声与投毒)。
- 用户可随时查看与撤回自己的贡献。

详见 deploy/HYBRID.md。
DOC
      ;;
  esac
}

# ---------- 模式配置片段 ----------
mode_config_unix() {
  case "$1" in
    local)  echo 'if [ ! -f deploy/.env ]; then cp deploy/.env.example deploy/.env; echo "  ✓ 已生成 deploy/.env(可编辑模型设置)"; fi' ;;
    hybrid) echo 'if [ ! -f deploy/.env ]; then cp deploy/.env.example deploy/.env; echo "  ⚠ 请编辑 deploy/.env 填入 OPENSCI_GLOBAL_URL 与 OPENSCI_GLOBAL_TOKEN"; fi' ;;
    cloud)  cat <<'CFG'
if [ ! -f deploy/.env.prod ]; then
  cp deploy/.env.prod.example deploy/.env.prod
  # 自动生成四个密钥(用户无需手动 openssl)
  gen() { if command -v openssl >/dev/null 2>&1; then openssl rand -hex 24; else python3 -c "import secrets;print(secrets.token_hex(24))"; fi; }
  for k in OPENSCI_ADMIN_TOKEN OPENSCI_MASTER_KEY OPENSCI_GLOBAL_TOKEN POSTGRES_PASSWORD; do
    v=$(gen)
    python3 - "$k" "$v" <<'PYGEN'
import sys, pathlib, re
k, v = sys.argv[1], sys.argv[2]
p = pathlib.Path("deploy/.env.prod")
lines = p.read_text().splitlines()
out = []
for ln in lines:
    if ln.startswith(k + "="):
        head, _, comment = ln.partition("#")
        out.append(f"{k}={v}" + (("   #" + comment) if comment else ""))
    else:
        out.append(ln)
p.write_text("\n".join(out) + "\n")
PYGEN
  done
  echo "  ✓ 已生成 deploy/.env.prod 并自动创建四个密钥"
  echo "  ⚠ 若对外服务,请编辑 DOMAIN 为你的域名(Caddy 自动签发 TLS)"
  echo "  ⚠ 生产环境建议将 OPENSCI_MASTER_KEY 改为从 KMS/Vault 注入"
fi
CFG
    ;;
  esac
}
mode_config_win() {
  case "$1" in
    local)  echo 'if (-not (Test-Path deploy\.env)) { Copy-Item deploy\.env.example deploy\.env; Write-Host "  OK 已生成 deploy\.env" }' ;;
    hybrid) echo 'if (-not (Test-Path deploy\.env)) { Copy-Item deploy\.env.example deploy\.env; Write-Host "  ! 请编辑 deploy\.env 填入 OPENSCI_GLOBAL_URL 与 TOKEN" }' ;;
    cloud)  cat <<'CFG'
if (-not (Test-Path deploy\.env.prod)) {
  Copy-Item deploy\.env.prod.example deploy\.env.prod
  $keys = @("OPENSCI_ADMIN_TOKEN","OPENSCI_MASTER_KEY","OPENSCI_GLOBAL_TOKEN","POSTGRES_PASSWORD")
  $lines = Get-Content deploy\.env.prod
  foreach ($k in $keys) {
    $v = -join ((1..48) | ForEach-Object { "0123456789abcdef"[(Get-Random -Max 16)] })
    $lines = $lines | ForEach-Object {
      if ($_ -like "$k=*") { $parts = $_ -split "#",2; if ($parts.Count -gt 1) { "$k=$v   #" + $parts[1] } else { "$k=$v" } } else { $_ }
    }
  }
  Set-Content deploy\.env.prod $lines
  Write-Host "  OK 已生成 deploy\.env.prod 并自动创建四个密钥"
  Write-Host "  ! 若对外服务,请编辑 DOMAIN 为你的域名"
}
CFG
    ;;
  esac
}

# ---------- 主循环 ----------
declare -A MODE_LABEL=( [local]="本地部署" [cloud]="云端部署" [hybrid]="混合部署" )

for mode in local cloud hybrid; do
  label="${MODE_LABEL[$mode]}"
  for osname in Windows macOS Linux; do
    pkgname="F3-OpenScience-${label}-${osname}-v${VER}"
    d="$STAGE/$pkgname"
    copy_core "$d"
    add_mode_files "$d" "$mode"
    write_mode_doc "$d" "$mode" "$osname"
    case "$mode" in
      cloud) EXTRA='[cloud]' ;;
      *)     EXTRA='' ;;
    esac

    if [ "$osname" = "Windows" ]; then
      write_windows_installer "$d" "$mode"
      write_launchers "$d" "$mode" "win"
      python3 - "$d/安装.ps1" "$label" "$(mode_config_win "$mode")" "$EXTRA" <<'PYX'
import sys, pathlib
p, label, cfg, extra = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
p.write_text(p.read_text().replace("MODE_LABEL", label).replace("MODE_CONFIG", cfg).replace("EXTRA_SPEC", extra), encoding="utf-8")
PYX
    else
      write_unix_installer "$d" "$mode" "$osname"
      write_launchers "$d" "$mode" "unix"
      python3 - "$d/安装.sh" "$label" "$(mode_config_unix "$mode")" "$EXTRA" <<'PYX'
import sys, pathlib
p, label, cfg, extra = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
p.write_text(p.read_text().replace("MODE_LABEL", label).replace("MODE_CONFIG", cfg).replace("EXTRA_SPEC", extra), encoding="utf-8")
PYX
    fi

    # 打包:Windows 用 zip,其余用 tar.gz
    ( cd "$STAGE"
      if [ "$osname" = "Windows" ]; then
        # 用 Python zipfile 打包:正确设置 UTF-8 标志位,避免 Windows 解压出现中文乱码文件名
        python3 - "$OUT/${pkgname}.zip" "$pkgname" <<'PYZIP'
import sys, os, zipfile
out, root = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            zi = zipfile.ZipInfo.from_file(p, os.path.relpath(p, "."))
            zi.flag_bits |= 0x800          # UTF-8 文件名标志
            zi.compress_type = zipfile.ZIP_DEFLATED
            if os.access(p, os.X_OK):
                zi.external_attr = (0o755 << 16)
            with open(p, "rb") as src, z.open(zi, "w") as dst:
                dst.write(src.read())
PYZIP
        echo "  ✓ ${pkgname}.zip"
      else
        tar czf "$OUT/${pkgname}.tar.gz" "$pkgname"
        echo "  ✓ ${pkgname}.tar.gz"
      fi )
  done
done

echo ""
echo "全部生成完毕 → $OUT"
ls -1 "$OUT"
