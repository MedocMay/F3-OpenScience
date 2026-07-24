# 本地化部署

**适合:** 个人 / 实验室 / 内网。数据与推理全留本地,合规友好。

## 方式 A:一键脚本(无需 Docker)
```bash
cp deploy/.env.example deploy/.env      # 按需改模型;OPENSCI_MODEL=ollama:qwen2.5 即全本地
pip install jsonschema                   # 核心零依赖,仅此一个(测试用)
bash deploy/run-local.sh                 # 起网关:8080 + global:8090,数据落 ./data/
```
验证:`curl localhost:8080/healthz`。开始一次研究:
```bash
curl -sN -X POST localhost:8080/v1/runs -d '{"direction":"few-shot RL for battery health","autonomy":1}'
# 用返回的 run_id 开 SSE 事件流:
curl -N localhost:8080/v1/runs/<run_id>/events
```

## 方式 B:Docker 一体化
```bash
cd deploy/docker && docker compose -f compose.local.yml up
```

## 方式 C:桌面 App(给非技术用户)
Tauri 壳(`apps/shell`),需在各平台构建安装包:
```bash
cd apps/shell && npm i && npm run tauri build   # 产出 .dmg/.msi/.AppImage
```
> 首次需 Rust 工具链。CI 三平台构建见 `apps/shell/README.md`。

## 数据主权
- 存储:`./data/` 下 SQLite,不外发。
- 模型:`OPENSCI_MODEL=ollama:...` 或 `local:...` → 推理不出域。
- 飞轮:纯本地时在**单用户内**累积;要跨用户复利,见 HYBRID.md。
