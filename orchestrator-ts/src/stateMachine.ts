// 阶段 + AutonomyLevel + gate 引擎(与 Python state_machine.py 同语义)。
export const GATES = new Set(["topic_confirm", "experiment_design", "pre_signoff"]);
export const HARD_GATES = new Set(["pre_signoff"]); // 不可被 L6 自动跳过

export function gateShouldPause(gateId: string, autonomy: number): boolean {
  if (HARD_GATES.has(gateId)) return true;
  return autonomy < 6;
}
