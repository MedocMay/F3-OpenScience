# 部署快速指南

> 第一次部署请先看 [INSTALL.md](INSTALL.md)(一页上手:装什么、配模型、选模式)。

三种模式全部实测跑通。选一种:

| 模式 | 一条命令 | 数据 | 跨用户飞轮 |
|---|---|---|---|
| **本地** | `pip install jsonschema && bash deploy/run-local.sh` | 全本地 | 单用户 |
| **混合** ⭐ | 中心 `python3 deploy/global_service.py` + 各端 run-local 指向它 | 本地 | 共享脱敏 |
| **云端** | `docker compose --env-file deploy/.env.prod -f deploy/docker/compose.prod.yml up -d` | 托管 | 全局 |

- 详细步骤:`deploy/LOCAL.md` / `deploy/HYBRID.md` / `deploy/PROD.md`
- API:见 `deploy/README.md`
- 先冒烟后端(无需 Docker):`bash demo.sh`

## 网络 API(三模式统一)
```
POST /v1/runs                 开始研究 -> {run_id}
GET  /v1/runs/{id}/events     SSE 事件流
POST /v1/gates                确认 gate
云端另有: POST /admin/tenants(发 token) · POST/GET /v1/keys(BYOK)
```
