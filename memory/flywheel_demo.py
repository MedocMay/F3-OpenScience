"""飞轮闭环 demo — 真实 CoE + 真实经验库。
证明:被拒模式回写 → 前置注入触发"生成前预核验引用"→ 下一 run 规避假引用 → 拦截率下降。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel import run_verify
from coe_kernel import apis
from memory import ExperienceStore

# 候选引用池:2 真 + 1 假。真实系统里来自 LLM 生成;这里固定以便可复现。
CANDIDATES = [
    {"id": "c-attn", "type": "citation", "arxiv_id": "1706.03762", "title": "Attention Is All You Need", "text": "transformer backbone"},
    {"id": "c-af",   "type": "citation", "doi": "10.1038/s41586-021-03819-2", "text": "structure prediction"},
    {"id": "c-fake", "type": "citation", "arxiv_id": "2099.99999", "text": "fabricated prior work"},
]

def generate(direction: str, injected: list) -> dict:
    """mock 生成器。若注入了 fake_cite 教训 → 启用'生成前预核验'策略,丢弃核验不过的引用。"""
    guard_on = any(l["kind"] == "fake_cite" for l in injected)
    claims = []
    for c in CANDIDATES:
        if guard_on and c.get("arxiv_id"):
            exists, _ = apis.check_arxiv(c["arxiv_id"])      # 前置注入触发的预核验
            if exists is False:
                continue                                     # 规避:不把不存在的引用写进 draft
        claims.append(c)
    draft = f"# {direction}\n" + " ".join(f"[{c['id']}]" for c in claims)
    return {"draft": draft, "claims": claims, "run_log": "improvement 12.4%", "guard_on": guard_on}

def run_once(store, direction, n):
    injected = store.inject(kinds=["fake_cite", "unsourced_num"], scope_max="global")
    gen = generate(direction, injected)
    report = run_verify(f"run{n}", gen["draft"], gen["claims"], gen["run_log"])
    written = store.write_from_report(report, contributor=f"user{n}")
    rej = report["stats"]["hallucinated_citations"]
    print(f"  RUN {n}: injected={len(injected)} guard={'ON ' if gen['guard_on'] else 'off'} "
          f"claims={len(gen['claims'])} rejected={rej} all_green={report['all_green']} "
          f"-> {'✅ signed' if report['all_green'] else '❌ blocked'}")
    return rej

if __name__ == "__main__":
    import os
    db = "/tmp/flywheel_demo.db"
    if os.path.exists(db): os.remove(db)
    store = ExperienceStore(db)
    print("=== 飞轮闭环:同题连跑 3 次 ===")
    rejs = [run_once(store, "efficient transformers for battery health", i) for i in (1, 2, 3)]
    print(f"\n  拦截曲线(每 run 被拦假引用数): {rejs}")
    print(f"  经验库: {store.stats()}")
    assert rejs[0] == 1, "首次应犯错并被拦"
    assert rejs[1] == 0 and rejs[2] == 0, "飞轮生效后应规避"
    print("  🎯 飞轮闭环成立:拦截率 1 → 0,后续 run 一次过署名")
