# cloud/ — 云端多租户能力

| 模块 | 作用 | 实测 |
|---|---|---|
| `tenancy.py` | token → 租户/用户;每租户独立经验库(隔离核心) | ✅ |
| `vault.py` | 每用户 BYOK 密钥,Fernet 加密落盘,按需解密注入 | ✅ |
| `db.py` | 存储抽象:global 记忆同码跑 SQLite / Postgres | ✅ sqlite |
| `sandbox.py` | 沙箱强隔离:执行 agent 生成代码(环境擦除 + 资源限制 + jail) | ✅ |

配套网关:`../deploy/gateway_cloud.py`(多租户 + BYOK 版)。

## 关键设计
- **隔离**:每租户一个 `experience.db` + `vault.db`(`data/tenants/<tenant>/`);global 跨租户共享,只存脱敏模式。
- **BYOK 安全**:主密钥 `OPENSCI_MASTER_KEY` 从 KMS/环境注入;用户 key 密文落盘,明文仅在注入模型调用的瞬间解密,不进日志、不驻留。
- **Postgres**:设 `OPENSCI_GLOBAL_DSN=postgresql://...` 即把 global 切到 Postgres(多实例并发)。DDL 见 `../deploy/STORAGE.md`。

## 云网关额外端点
```
POST /admin/tenants   {tenant_id,user_id}     -> {token}   (需 admin token)
POST /v1/keys         {provider,api_key}       存 BYOK(密文)
GET  /v1/keys                                  列出本用户已配 provider
```
