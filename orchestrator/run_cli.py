"""CLI 驱动(代替桌面壳):跑 Orchestrator,验证真实多进程链路。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import Orchestrator

def make_shell(auto=True):
    def ask(gate_id):
        label = {"topic_confirm":"题目确认","experiment_design":"实验设计","pre_signoff":"署名前(hard)","share_consent":"是否贡献经验"}.get(gate_id, gate_id)
        print(f"    [壳] GATE:{label} -> {'确认' if auto else '?'}"); return "approve"
    def emit(stage, typ, data):
        print(f"    [event] {stage:9s} {typ:8s} {data}")
    return ask, emit

if __name__ == "__main__":
    db = "/tmp/orch_demo.db"
    if os.path.exists(db): os.remove(db)
    ask, emit = make_shell(auto=True)
    orch = Orchestrator(ask, emit, db=db)
    try:
        for i in (1, 2):
            print(f"\n################ 多进程 RUN {i}(orchestrator + 3 sidecars over stdio JSON-RPC)################")
            r = orch.run("efficient transformers for battery health", autonomy=1, contributor=f"user{i}")
            print(f"    => RESULT: {r['status']}")
    finally:
        orch.close()
    print("\n[所有 sidecar 子进程已关闭]")
