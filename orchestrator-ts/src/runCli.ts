// CLI 驱动(代替桌面壳):跑 TS Orchestrator,验证 TS 大脑驱动 Python sidecar。
import { Orchestrator } from "./orchestrator.js";
import fs from "node:fs";

const db = "/tmp/orch_ts_demo.db";
if (fs.existsSync(db)) fs.rmSync(db);

const ask = (gateId: string) => {
  const label: Record<string,string> = { topic_confirm:"题目确认", experiment_design:"实验设计", pre_signoff:"署名前(hard)", share_consent:"是否贡献经验" };
  console.log(`    [壳] GATE:${label[gateId] ?? gateId} -> 确认`); return "approve";
};
const emit = (stage: string, type: string, data: unknown) =>
  console.log(`    [event] ${stage.padEnd(9)} ${type.padEnd(8)} ${JSON.stringify(data)}`);

const orch = new Orchestrator(ask, emit, db);
try {
  for (const i of [1, 2]) {
    console.log(`\n################ TS-Orchestrator RUN ${i}(TS 大脑 + Python sidecars over stdio）################`);
    const r = await orch.run("efficient transformers for battery health", 1, `user${i}`);
    console.log(`    => RESULT: ${r.status}`);
  }
} finally {
  orch.close();
}
console.log("\n[Python sidecar 子进程已由 TS 关闭]");
