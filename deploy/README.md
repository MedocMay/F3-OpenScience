# deploy/ — 三种部署方式

F3-OpenScience 支持三种部署,按需求选:

| 方式 | 适合 | 数据主权 | 跨用户飞轮 | 文档 |
|---|---|---|---|---|
| **本地化** | 个人/实验室/内网 | ✅ 全本地 | 单用户内 | [LOCAL.md](LOCAL.md) |
| **云端** | 团队/SaaS | 集中托管 | ✅ 全局 | [CLOUD.md](CLOUD.md) |
| **混合** ⭐ | 要主权又要复利 | ✅ 本地 | ✅ 共享脱敏 | [HYBRID.md](HYBRID.md) |

## 组件
- `gateway.py` — HTTP+SSE 网络网关(把 orchestrator 暴露成 API)。零第三方依赖。
- `global_service.py` — global 记忆共享服务(混合/云端)。
- `../memory/remote_global.py` — 本地连远程 global 的客户端(混合)。
- `docker/` — Dockerfile + compose(local / cloud / **prod 全家桶**:Caddy+Postgres+Redis)。
- `run-local.sh` — 无 Docker 一键本地。
- `.env.example` — 配置模板。 · `STORAGE.md` — SQLite→Postgres。

## 网络 API(所有模式统一)
```
POST /v1/runs                    开始一次研究 -> {run_id}
GET  /v1/runs/{id}/events        SSE:run.event / gate.request / result
POST /v1/gates                   {run_id,gate_id,decision} 确认 gate
GET  /v1/sovereignty?contributor=..   查看贡献
POST /v1/sovereignty/revoke      撤回贡献
GET  /healthz
```
云端加 `Authorization: Bearer $OPENSCI_TOKEN`。

## 生产一键(对外 SaaS)
```bash
cp deploy/.env.prod.example deploy/.env.prod   # 填域名/密钥
cd deploy/docker && docker compose --env-file ../.env.prod -f compose.prod.yml up -d
```
详见 [PROD.md](PROD.md)。

## 最快上手
```bash
bash deploy/run-local.sh                             # 本地(核心零依赖,无需 pip install)
```
