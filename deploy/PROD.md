# 生产部署(一条命令)

面向对外多租户 SaaS。一条 `docker compose up` 起全栈:**Caddy 自动 TLS + 云网关(多租户/BYOK/沙箱)+ global + Postgres + Redis**。

## 步骤
```bash
# 1) 配置
cp deploy/.env.prod.example deploy/.env.prod
#   编辑 deploy/.env.prod:
#   DOMAIN=opensci.yourorg.com
#   OPENSCI_ADMIN_TOKEN=$(openssl rand -hex 24)
#   OPENSCI_MASTER_KEY=$(openssl rand -hex 24)      # 生产建议从 KMS 注入
#   OPENSCI_GLOBAL_TOKEN=$(openssl rand -hex 24)
#   POSTGRES_PASSWORD=$(openssl rand -hex 24)

# 2) 启动全栈
cd deploy/docker
docker compose --env-file ../.env.prod -f compose.prod.yml up -d

# 3) 域名 A 记录指向服务器 → Caddy 自动签发 Let's Encrypt 证书
```

## 起来之后
```bash
# 发一个租户 token(管理端)
curl -X POST https://$DOMAIN/admin/tenants \
  -H "Authorization: Bearer $OPENSCI_ADMIN_TOKEN" \
  -d '{"tenant_id":"acme","user_id":"alice"}'
# 用户存自己的模型 key(BYOK,密文落盘)
curl -X POST https://$DOMAIN/v1/keys -H "Authorization: Bearer <token>" \
  -d '{"provider":"anthropic","api_key":"sk-..."}'
# 开始一次研究 + 订阅事件
curl -X POST https://$DOMAIN/v1/runs -H "Authorization: Bearer <token>" \
  -d '{"direction":"...","autonomy":1}'
```

## 这套栈解决了哪些运维项(全部开箱)
| 项 | 组件 | 状态 |
|---|---|---|
| TLS / 反代 / SSE | Caddy(自动 Let's Encrypt) | ✅ |
| 多租户隔离 + BYOK | gateway_cloud | ✅ |
| global 记忆持久化 | Postgres(DSN 自动接线 + 初始化 DDL) | ✅ |
| 会话外置 | Redis | ✅ |
| 代码执行隔离 | 沙箱(local 强隔离,默认) | ✅ |
| 健康检查 | 各服务 healthcheck | ✅ |

## 加固建议(可选)
- **主密钥入 KMS**:`OPENSCI_MASTER_KEY` 改从 AWS KMS / Vault 注入,不落 .env。
- **沙箱升级**:高危场景把宿主运行时换 gVisor,或 `OPENSCI_SANDBOX=container`(需挂 docker.sock,注意权限)。
- **多副本网关**:`replicas: N` + Caddy 按 `X-Run-Id` 粘性路由(Caddyfile 已注释),会话已在 Redis。
- **备份**:定期备份 `pg-data`(global 记忆)与 `tenants-data`(各租户经验/密钥库)。
