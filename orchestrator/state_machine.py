"""状态机 + AutonomyLevel + gate 引擎。阶段执行器由 orchestrator 注入。"""
STAGES = ["topic_confirm", "inject", "generate", "experiment_design", "verify", "flywheel", "pre_signoff", "package"]
GATES = {"topic_confirm", "experiment_design", "pre_signoff"}
HARD_GATES = {"pre_signoff"}   # 不可被 --auto 跳过

def gate_should_pause(gate_id: str, autonomy: int) -> bool:
    if gate_id in HARD_GATES:
        return True                      # 署名前永远暂停
    return autonomy < 6                  # L6 全自动才自动过普通 gate
