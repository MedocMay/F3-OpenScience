// Orchestrator(TS)— 唯一大脑。拉起 CoE / 经验库 / Pipeline 三个 Python sidecar,
// 用 JSON-RPC over stdio 协调,跑 state-machine + gate + 飞轮。证明跨语言架构。
import { RpcClient } from "./rpc.js";
import { gateShouldPause } from "./stateMachine.js";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");           // opensci/
const PY = process.env.PYTHON || "python3";

type Ask = (gateId: string) => Promise<string> | string;
type Emit = (stage: string, type: string, data: unknown) => void;

export class Orchestrator {
  private coe: RpcClient; private pipe: RpcClient; private mem: RpcClient;
  constructor(private ask: Ask, private emit: Emit, db = "/tmp/orch_ts.db") {
    this.coe  = new RpcClient("coe",  [PY, "-m", "coe_kernel.server"], ROOT);
    this.pipe = new RpcClient("pipe", [PY, "-m", "pipeline.server"], ROOT);
    this.mem  = new RpcClient("mem",  [PY, "-c", `import sys;from memory.server import main;main('${db}')`], ROOT);
  }
  close() { this.coe.close(); this.pipe.close(); this.mem.close(); }

  private async gate(gateId: string, autonomy: number): Promise<string> {
    if (gateShouldPause(gateId, autonomy)) return await this.ask(gateId);
    this.emit(gateId, "gate", { auto_approved: true }); return "approve";
  }

  async run(direction: string, autonomy = 1, contributor = "anon") {
    const rid = "run-" + Math.random().toString(16).slice(2, 10);
    this.emit("start", "log", { run_id: rid, autonomy });

    if (await this.gate("topic_confirm", autonomy) !== "approve") return { run_id: rid, status: "aborted_at_topic" };

    const injected = await this.mem.call("mem.query", { kinds: ["fake_cite", "unsourced_num"], scope_max: "global" });
    this.emit("inject", "log", { n_lessons: (injected as any[]).length });
    const gen: any = await this.pipe.call("pipeline.generate", { direction, injected });
    this.emit("generate", "log", { guard_on: gen.guard_on, n_claims: gen.claims.length });

    if (await this.gate("experiment_design", autonomy) !== "approve") return { run_id: rid, status: "aborted_at_design" };

    const report: any = await this.coe.call("coe.verify", {
      run_id: rid, draft: gen.draft, claims: gen.claims, run_logs_ref: gen.run_log });
    this.emit("verify", "log", { all_green: report.all_green, stats: report.stats });

    const written: any = await this.mem.call("mem.write_from_report", { report, contributor });
    this.emit("flywheel", "log", { written });

    if (!report.all_green) {
      this.emit("signoff", "gate", { blocked: true, reason: "校验未全绿" });
      return { run_id: rid, status: "blocked_pre_signoff", report };
    }
    if ((written as any[]).length && await this.ask("share_consent") === "approve") {
      for (const lid of written) await this.mem.call("mem.promote", { lesson_id: lid, target_scope: "global", consent: true });
    }
    if (await this.gate("pre_signoff", autonomy) !== "approve") return { run_id: rid, status: "aborted_at_signoff" };

    this.emit("package", "artifact", { signed: true });
    return { run_id: rid, status: "signed", report };
  }
}
