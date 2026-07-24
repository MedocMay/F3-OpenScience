# 安装与部署(一页上手)

## 先决条件(按模式)
| 模式 | 必需 | 可选 |
|---|---|---|
| 本地 / 混合 | Python 3.11+ | Ollama(本地模型) |
| 云端 | Docker + Docker Compose | 域名(自动 TLS) |
| 桌面 App | Rust 工具链 + Node ≥18 | — |

> **核心零第三方依赖**(纯标准库)。可选依赖按需安装:
>
> | 依赖组 | 装法 | 用于 |
> |---|---|---|
> | 核心 | 无需安装 | 校验内核、飞轮、量纲、化学守恒判据 |
> | `[cloud]` | `pip install 'f3-openscience[cloud]'` | 云端多租户:BYOK 密管 / Postgres / Redis |
> | `[chem]` | `pip install 'f3-openscience[chem]'` | 化学价键判据(RDKit;守恒与不饱和度无需它) |
> | `[test]` | `pip install 'f3-openscience[test]'` | 跑测试套件(jsonschema) |
>
> 安装脚本会按部署模式自动装对应依赖组 —— 云端包自动带 `[cloud]`。

---

## 第 0 步:冒烟(强烈建议,只需 Python,不用 Docker)
```bash
tar xzf opensci-deploy-0.1.0.tar.gz && cd opensci
pip install jsonschema
bash demo.sh        # 跑 CoE 校验 + 飞轮 + 多进程链路;全绿即后端 OK
```

---

## 第 1 步:配模型(任何 AI Agent 都绕不开)
agent 要连一个模型才能"生成研究"。二选一:

**A. 本地模型(免费、数据不出域)**
```bash
# 装 Ollama: https://ollama.com ,然后
ollama pull qwen2.5
export OPENSCI_MODEL=ollama:qwen2.5
```
**B. 云 API(填一个即可)**
```bash
export OPENSCI_MODEL=anthropic:claude-haiku-4-5-20251001
export ANTHROPIC_API_KEY=sk-...        # 或 OPENAI_API_KEY / DEEPSEEK_API_KEY / MOONSHOT_API_KEY(Kimi)/ DASHSCOPE_API_KEY(Qwen)/ GEMINI_API_KEY
```
> 不配模型:校验层与飞轮仍可跑(用于验证),但"生成研究"这步不可用。

---

## 第 2 步:选一种模式部署

### 本地(有 Python 即可)
```bash
cp deploy/.env.example deploy/.env      # 按需改;OPENSCI_MODEL 已在上一步设
bash deploy/run-local.sh                # 网关 :8080 + global :8090,数据落 ./data/
curl localhost:8080/healthz             # 验证
```

### 混合(数据主权 + 跨用户飞轮)
```bash
# 中心机(部署一次):
OPENSCI_GLOBAL_TOKEN=$(openssl rand -hex 24) python3 deploy/global_service.py
# 各用户机:.env 里填 OPENSCI_GLOBAL_URL=http://中心:8090 和同一 token,然后
bash deploy/run-local.sh
```

### 云端(有 Docker 即可)
```bash
cp deploy/.env.prod.example deploy/.env.prod    # 填 DOMAIN 和 4 个密钥(openssl rand -hex 24)
cd deploy/docker
docker compose --env-file ../.env.prod -f compose.prod.yml up -d
# 自带 Caddy(自动 TLS)+ Postgres + Redis + 多租户 + BYOK + 沙箱
```

### 桌面 App(给非技术用户)
```bash
cd apps/shell && npm i && npm run tauri build    # 产出 .dmg/.msi/.AppImage(需 Rust)
```

---

## 用起来(网络 API,三模式统一)
```bash
# 开始一次研究
curl -X POST localhost:8080/v1/runs -d '{"direction":"few-shot RL for battery health","autonomy":1}'
# 用返回的 run_id 订阅事件流(会推送 gate 请求)
curl -N localhost:8080/v1/runs/<run_id>/events
# 确认某个 gate
curl -X POST localhost:8080/v1/gates -d '{"run_id":"<id>","gate_id":"topic_confirm","decision":"approve"}'
```
云端另有:`POST /admin/tenants`(发 token)、`POST /v1/keys`(存 BYOK)。

---

## 常见问题
- **端口占用**:`PORT=9090 bash deploy/run-local.sh`。
- **只想验证不配模型**:跳过第 1 步,直接 `bash demo.sh`。
- **依赖缺失时**:代码会给出可操作提示(如「请安装 `pip install 'f3-openscience[cloud]'`」),而非裸 ImportError。
- **Docker 上线前**:先 `bash demo.sh` 冒烟后端,再 `docker compose up`。

详细分模式文档见 `deploy/LOCAL.md · HYBRID.md · PROD.md`。

## 自己构建安装包
```bash
bash packaging/build-installers.sh backend   # wheel + sdist(+单文件可执行,若装了 pyinstaller)
bash packaging/build-installers.sh desktop   # 桌面安装包(需 Rust)
# Windows: pwsh -File packaging\build-installers.ps1
```
支持的操作系统与产物形态见 `packaging/PLATFORMS.md`。
