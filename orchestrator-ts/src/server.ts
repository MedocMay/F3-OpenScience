// Orchestrator stdio server — 实现 contracts/ipc.schema.json,供壳(Tauri)调用。
// run.start(长任务,流式发 run.event / gate.request)· gate.resolve · sovereignty.list/revoke。
// 壳↔orchestrator 的真实边界:壳发 JSON-RPC 行,server 回 result / 发 notification。
import { Orchestrator } from "./orchestrator.js";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const PY = process.env.PYTHON || "python3";

function send(obj: unknown) { process.stdout.write(JSON.stringify(obj) + "\n"); }
function notify(method: string, params: unknown) { send({ jsonrpc: "2.0", method, params }); }

// 待决 gate:ask 返回 promise,gate.resolve 到达时兑现
const pendingGates = new Map<string, (decision: string) => void>();

const emit = (stage: string, type: string, data: unknown) => notify("run.event", { stage, type, data });
const ask = (gateId: string): Promise<string> =>
  new Promise((resolve) => { pendingGates.set(gateId, resolve); notify("gate.request", { gate_id: gateId }); });

let orch: Orchestrator | null = null;
function getOrch(db = "/tmp/orch_shell.db") {
  if (!orch) orch = new Orchestrator(ask, emit, db);
  return orch;
}

// sovereignty:直接起一个 memory sidecar 查询(壳的主权面板用)
function memCall(method: string, params: unknown, db = "/tmp/orch_shell.db"): Promise<any> {
  return new Promise((resolve, reject) => {
    const p = spawn(PY, ["-c", `import sys;from memory.server import main;main('${db}')`], { cwd: ROOT });
    let out = "";
    p.stdout.on("data", (d) => { out += d; });
    p.on("close", () => { try { resolve(JSON.parse(out.trim().split("\n")[0]).result); } catch (e) { reject(e); } });
    p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) + "\n"); p.stdin.end();
  });
}

async function handle(req: any) {
  const { id, method, params } = req;
  try {
    switch (method) {
      case "run.start": {
        const r = await getOrch().run(params.direction, params.autonomy ?? 1, params.contributor ?? "user");
        send({ jsonrpc: "2.0", id, result: r }); break;
      }
      case "gate.resolve": {
        const g = pendingGates.get(params.gate_id);
        if (g) { pendingGates.delete(params.gate_id); g(params.decision); }
        send({ jsonrpc: "2.0", id, result: { ok: true } }); break;
      }
      case "sovereignty.list": {
        const rows = await memCall("mem.list_contributions", { contributor_fp: params.contributor_fp ?? null });
        send({ jsonrpc: "2.0", id, result: { contributions: rows } }); break;
      }
      case "sovereignty.revoke": {
        const r = await memCall("mem.revoke", { lesson_id: params.lesson_id });
        send({ jsonrpc: "2.0", id, result: r }); break;
      }
      case "model.available": {
        const r = await memCall("mem.stats", {}); // placeholder;真实由 model router 提供
        send({ jsonrpc: "2.0", id, result: r }); break;
      }
      default: send({ jsonrpc: "2.0", id, error: { code: -32601, message: "method not found" } });
    }
  } catch (e: any) {
    send({ jsonrpc: "2.0", id, error: { code: -32603, message: String(e?.message ?? e) } });
  }
}

let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk: string) => {
  buf += chunk; let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (line) { try { handle(JSON.parse(line)); } catch {} }
  }
});
notify("ready", { server: "orchestrator", ipc: "contracts/ipc.schema.json" });
