# apps/shell/ — F3-OpenScience 桌面壳(fork ai4s / Tauri 2 脚手架)

架构 ① 交付层。壳不碰业务,通过 Rust bridge 调 orchestrator server(`../../orchestrator-ts/src/server.ts`,实现 `contracts/ipc.schema.json`)。

```
src/                 React UI:运行工作区 + gate 确认弹窗 + 用户主权面板 + 模型选择器
src-tauri/src/lib.rs Rust IPC bridge:spawn orchestrator server;命令<->JSON-RPC;notification->Tauri event
src-tauri/tauri.conf.json / Cargo.toml / build.rs  Tauri 2 配置
```

## 数据流
```
React UI ──invoke(run_start/gate_resolve/sovereignty_*)──▶ Rust bridge
   ▲                                                          │ JSON-RPC / stdio
   └──Tauri event(run.event / gate.request)◀── Rust bridge ──▶ orchestrator server(TS)
                                                                 └─▶ Python sidecars(CoE / Pipeline / 经验库)
```

## 构建运行(需桌面 Rust 工具链)
```bash
npm i
npm run tauri dev        # 或 cargo tauri dev
```
> 本仓库环境无 cargo,Tauri 未在此构建。但**壳↔orchestrator 的 IPC 边界(ipc.schema)已用 Node 模拟壳实测通过**:
> `run.start` 流式 `run.event` + `gate.request/gate.resolve` 全链路通(见 orchestrator-ts/src/server.ts)。

## UI 三块
- **运行工作区**:研究方向 + 模型选择(Claude/GPT/Gemini/Kimi/DeepSeek/Qwen/本地)+ 自主度 L0–L6 + 事件流。
- **gate 确认**:题目 / 实验设计 / 署名前(hard)/ 是否贡献经验(consent)。
- **用户主权面板**:查看自己贡献了哪些、scope、被复用多少,一键撤回(private-by-default)。

## 生产化 TODO
- orchestrator server 打包为 node 单文件 / Bun 二进制,免运行时依赖 tsx。
- fork ai4s 的工作区/artifact 浏览/notebook 组件复用进来。
