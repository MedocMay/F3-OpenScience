# generated/ — 自动生成,请勿手改

这些类型从 `../contracts/` 生成,是跨进程契约的**语言绑定**:
- `python/` — pydantic v2 模型(给 CoE / Pipeline / 经验库 sidecar)
- `ts/` — TypeScript 类型(给 Orchestrator 和桌面壳)

改契约的正确姿势:改 `contracts/*.json|proto` → 跑 `scripts/gen-types.sh` → 提交。
CI 应校验 `generated/` 与 `contracts/` 一致(生成后 `git diff --exit-code`)。
