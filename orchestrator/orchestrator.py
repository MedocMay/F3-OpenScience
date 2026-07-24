"""Orchestrator — 唯一大脑(M3)。拉起 CoE / 经验库 / Pipeline 三个真实 sidecar 进程,
用 JSON-RPC over stdio 协调,跑 state-machine + gate + 飞轮。
(参考实现为 Python;生产按 ENGINEERING.md 换 TS/Bun,IPC 协议不变。)"""
from __future__ import annotations
import os, sys, uuid
sys.path.insert(0, os.path.dirname(__file__))
from rpc import RpcClient
from state_machine import gate_should_pause
from packager import build_package

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.environ.get("OPENSCI_OUT", "/tmp/opensci_packages")

class Orchestrator:
    def __init__(self, ask_human, emit, db="/tmp/orch_mem.db"):
        self.ask, self.emit = ask_human, emit
        py = sys.executable
        # 三个真实 sidecar 子进程(独立进程,stdio JSON-RPC)
        self.coe  = RpcClient("coe",  [py, "-m", "coe_kernel.server"], cwd=ROOT)
        self.pipe = RpcClient("pipe", [py, "-m", "pipeline.server"], cwd=ROOT)
        self.mem  = RpcClient("mem",  [py, "-c", f"import sys;from memory.server import main;main('{db}')"], cwd=ROOT)

    def close(self):
        for c in (self.coe, self.pipe, self.mem): c.close()

    def _gate(self, gate_id, autonomy):
        if gate_should_pause(gate_id, autonomy):
            return self.ask(gate_id)
        self.emit(gate_id, "gate", {"auto_approved": True}); return "approve"

    def run(self, direction, autonomy=1, contributor="anon"):
        rid = "run-" + uuid.uuid4().hex[:8]
        self.emit("start", "log", {"run_id": rid, "autonomy": autonomy})

        if self._gate("topic_confirm", autonomy) != "approve":
            return {"run_id": rid, "status": "aborted_at_topic"}

        # inject (mem sidecar) -> generate (pipeline sidecar)
        injected = self.mem.call("mem.query", {"kinds": ["fake_cite", "unsourced_num"], "scope_max": "global"})
        self.emit("inject", "log", {"n_lessons": len(injected)})
        gen = self.pipe.call("pipeline.generate", {"direction": direction, "injected": injected})
        self.emit("generate", "log", {"guard_on": gen["guard_on"], "n_claims": len(gen["claims"])})

        if self._gate("experiment_design", autonomy) != "approve":
            return {"run_id": rid, "status": "aborted_at_design"}

        # verify (coe sidecar)
        report = self.coe.call("coe.verify", {"run_id": rid, "draft": gen["draft"],
                                              "claims": gen["claims"], "run_logs_ref": gen["run_log"]})
        self.emit("verify", "log", {"all_green": report["all_green"], "stats": report["stats"]})

        # flywheel writeback (mem sidecar)
        written = self.mem.call("mem.write_from_report", {"report": report, "contributor": contributor})
        self.emit("flywheel", "log", {"written": written})

        # pre-signoff GATE (hard)
        if not report["all_green"]:
            self.emit("signoff", "gate", {"blocked": True, "reason": "校验未全绿"})
            return {"run_id": rid, "status": "blocked_pre_signoff", "report": report}
        # consent 提示(D6)
        if written and self.ask("share_consent") == "approve":
            for lid in written:
                self.mem.call("mem.promote", {"lesson_id": lid, "target_scope": "global", "consent": True})
        if self._gate("pre_signoff", autonomy) != "approve":
            return {"run_id": rid, "status": "aborted_at_signoff"}

        pkg = build_package(rid, direction, gen, report, OUT)
        self.emit("package", "artifact", {"reproducible_package": pkg})
        return {"run_id": rid, "status": "signed", "report": report, "package": pkg}
