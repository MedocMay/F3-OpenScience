# 云端部署(多租户 SaaS)

**适合:** 团队 / 对外服务。网关无状态可横向扩展,global 记忆集中共享。

## 起步
```bash
export OPENSCI_TOKEN=$(openssl rand -hex 24)         # 网关 Bearer 认证(必开)
export OPENSCI_GLOBAL_TOKEN=$(openssl rand -hex 24)  # global 服务认证
export ANTHROPIC_API_KEY=...                         # 或其他 provider
cd deploy/docker && docker compose -f compose.cloud.yml up -d
```
所有 API 需带 `Authorization: Bearer $OPENSCI_TOKEN`。

## 已实现(可运行,见 cloud/ + gateway_cloud.py)
- **多租户隔离** ✅:`deploy/gateway_cloud.py` + `cloud/tenancy.py`。token→租户,每租户独立经验库。用 `POST /admin/tenants` 发 token。
- **每用户 BYOK 密管** ✅:`cloud/vault.py`。key Fernet 加密落盘,run 时按用户解密注入。`POST /v1/keys` 存,主密钥走 `OPENSCI_MASTER_KEY`(KMS)。
- **Postgres 适配** ✅(同接口):`cloud/db.py`。`OPENSCI_GLOBAL_DSN=postgresql://...` 切换;DDL 见 STORAGE.md。

启动云网关:
```bash
export OPENSCI_MASTER_KEY=<from-kms>  OPENSCI_ADMIN_TOKEN=<admin>
PORT=8080 python3 deploy/gateway_cloud.py
```

## 仍需补(生产强化)
1. **多租户 global 上 Postgres**:设 OPENSCI_GLOBAL_DSN(psycopg)。
2. **沙箱强隔离**:pipeline 跑真实代码,云上用容器/gVisor/Firecracker,而非裸 subprocess。
3. **TLS + 反代**(Nginx/Caddy)+ 速率限制;网关本身只监听内网。
4. **可观测**:健康检查已内置 `/healthz`;接 Prometheus/日志聚合。
5. **会话外置**:长任务会话现于内存,多实例网关建议用 Redis 存会话跨实例。

## 横向扩展
网关无状态(会话在内存,长任务建议加 Redis 存会话即可跨实例);`compose.cloud.yml` 已 `replicas: 2`。global 服务是共享单点,换 Postgres 后可主从。

## Web 前端
`apps/shell` 的 React UI 可复用:把 Tauri `invoke` 换成对网关的 `fetch`/SSE(端点同名)。作为纯 Web 部署即可,无需 Tauri。
