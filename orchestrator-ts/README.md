# orchestrator-ts/ — Orchestrator(TypeScript 实现)

架构里"大脑=TS、sidecar=Python、只依赖 contracts"的生产实现。用 Node/tsx 运行,**驱动同一批 Python sidecar**(`coe_kernel.server` / `pipeline.server` / `memory.server`),JSON-RPC over stdio 协议不变。

```
src/rpc.ts           JSON-RPC stdio 客户端(与 Python rpc.py 同协议)
src/stateMachine.ts  阶段 + AutonomyLevel + gate(pre_signoff = hard)
src/orchestrator.ts  唯一大脑:spawn 3 Python sidecar -> inject/generate/verify/flywheel/gate
src/runCli.ts        CLI 驱动
```

## 跑
```bash
npm i                   # 装 tsx + @types/node(联网)
npm run start           # = tsx src/runCli.ts(TS 大脑驱动 Python sidecar)
npm run typecheck       # tsc --noEmit(需 @types/node)
```
## 实测(live)
```
RUN 1: inject=0 → verify all_green=false(1 假引用)→ blocked_pre_signoff → 飞轮回写
RUN 2: inject=1 → guard 规避 → all_green=true → signed
```
→ **TS 大脑驱动 Python sidecar,飞轮跨语言边界生效**。证明 contracts 驱动的跨语言架构成立。
生产可进一步:Bun 运行、把类型从 `../generated/ts` 引入、壳(Tauri)通过 IPC 调本 orchestrator。
