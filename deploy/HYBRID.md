# 混合部署(推荐)

**适合:** 既要数据主权、又要跨用户飞轮复利。**这是架构为之设计的最佳形态。**

## 形态
```
每个用户/机构:  本地 agent(网关 + sidecar)         ← 研究数据、原始记忆、推理都在本地
                      │  只上「脱敏后的校验模式」(非原始内容)
                      ▼
中心:            远程 global 记忆服务(一处)         ← 跨用户共享,越多人用越准
```
数据主权(本地)+ 护城河复利(共享)兼得;D6 用户主权(默认本地、opt-in、可撤回)让它合规站得住。

## 部署
**中心侧(部署一次):**
```bash
export OPENSCI_GLOBAL_TOKEN=$(openssl rand -hex 24)
cd deploy/docker && docker compose -f compose.cloud.yml up -d global   # 只起 global
# 或裸跑:OPENSCI_GLOBAL_TOKEN=... PORT=8090 python3 deploy/global_service.py
```
**每个用户/机构侧:**
```bash
cp deploy/.env.example deploy/.env
# .env 里指向远程 global:
#   OPENSCI_GLOBAL_URL=https://global.yourorg.com
#   OPENSCI_GLOBAL_TOKEN=<中心发的 token>
#   OPENSCI_MODEL=ollama:qwen2.5     # 本地模型 -> 数据/推理不出域
bash deploy/run-local.sh
```

## 数据流保证(实测)
- 本地拦下的假引用/无源数字 → 脱敏成抽象模式(去 PII/DOI/原文,见 `memory/desensitize.py`)→ 才上行。
- 需 **≥2 个不同用户**独立复现才在 global 生效(防噪声/中毒)。
- 用户可查看/撤回自己的贡献。
- 已实测:本地 agent 经 HTTP 连远程 global,userA+userB→active,userC 受益。

## 只共享、不泄露
上行的只有 `NONEXISTENT_CITATION` 这类**抽象模式**,绝不含研究内容、想法、原始引用。脱敏门在 global 服务端二次校验,双保险。
