"""CoE Audit Kernel — 编排:抽取 -> 证据链门控 -> 4 层/数字核验 -> verification_report。
产出符合 contracts/verification_report.schema.json。

可达性原则(R0/R2):
  署名门槛不放松 —— reject / unresolved / manual 任一存在,all_green 均为 False。
  但两类失败的**语义**必须分开:
    reject      = 权威登记处确证矛盾(捏造)      -> 可作为生成约束
    unresolved  = 索引/校验能力未覆盖(我看不到) -> 不得作为生成约束,记入校验能力待办
  否则 verifier 的能力边界会悄悄变成 generator 的世界边界。
"""
from . import extract, verify
from . import novelty as nov
from . import domains as dom

# 当前使用的证据基质与已知盲区(诚实声明覆盖率,而非假装全知)
SUBSTRATES = ["arxiv", "crossref", "datacite", "openalex", "run_log"]
KNOWN_BLIND_SPOTS = [
    "未被 OpenAlex 收录的新预印本 / 非英语文献 / 小众会议",
    "无 DOI 的数据集与代码仓库",
    "需推导才能溯源的数字(推导式校验见 R3)",
    "机制性命题的因果强度(仅校验证据基质,不判断因果是否成立)",
]

def run_verify(run_id: str, draft: str, claims: list | None = None, run_log: str = "",
               artifacts: dict | None = None, domain: str | None = None) -> dict:
    all_claims = extract.extract_claims(draft, claims)
    # R5:补上机制性命题 —— 此前它们完全不进校验(反向可达性缺口)
    all_claims += nov.extract_mechanism_claims(draft, all_claims)
    # R6:领域物理判据(按需启用)。质量守恒、价键上限等由领域规律裁决,与索引无关。
    if domain:
        for d in dom.check(domain, draft):
            all_claims.append({"id": f"dom-{len(all_claims)}", "type": "domain", "domain": domain,
                               "text": f"{d['kind']}: {d['expr']}", **d})
    out = []
    for c in all_claims:
        if c.get("type") == "number":
            r = verify.verify_number(c, run_log)
        elif c.get("type") == "domain":
            r = verify.verify_domain(c)
        elif c.get("type") == "mechanism":
            r = verify.verify_mechanism(c, artifacts)
        elif c.get("type") == "figure":
            r = {"id": c["id"], "text": c.get("text", ""), "type": "figure",
                 "status": "manual", "reason": "图↔码一致性核验待接(T4.2)"}
        else:
            r = verify.verify_citation(c)
        out.append(r)

    n = lambda **kw: sum(1 for r in out if all(r.get(k) == v for k, v in kw.items()))
    rejected   = n(status="reject")
    unresolved = n(status="unresolved")
    manual     = n(status="manual")
    cite_total = sum(1 for c in all_claims if c.get("type") == "citation")
    num_total  = n(type="number")
    resolved   = n(status="pass")

    return {
        "run_id": run_id,
        # 署名保证不变:三类未决状态任一存在都不放行
        "all_green": rejected == 0 and unresolved == 0 and manual == 0,
        "claims": out,
        "stats": {
            "citations_checked": cite_total,
            "citations_rejected": n(type="citation", status="reject"),
            "citations_unresolved": n(type="citation", status="unresolved"),
            "numbers_sourced": f"{n(type='number', status='pass')}/{num_total}",
            # 只统计"确证捏造",不再把"查不到"计入幻觉
            "hallucinated_citations": n(type="citation", status="reject"),
        },
        "coverage": {
            "substrates_queried": SUBSTRATES,
            "resolved": resolved,
            "unresolved": unresolved,
            "coverage_ratio": round(resolved / len(out), 3) if out else 1.0,
            "known_blind_spots": KNOWN_BLIND_SPOTS,
            "domain_checks": ([domain] if domain else []),
        },
        "novelty": {
            "mechanism_claims": n(type="mechanism"),
            "unestablished_in_index": sum(1 for r in out
                                          if r.get("literature_support") == "unestablished_in_index"),
            # 由计算型证据(而非引用)背书而通过的论断 —— 系统"敢主张新东西"的能力
            "signed_on_computational_evidence": sum(
                1 for r in out if r.get("status") == "pass"
                and (r.get("evidence_chain") or {}).get("kind") in ("code+data", "derivation", "log")),
        },
    }
