"""M4 回归:跨用户 global 聚合 + 脱敏 + 质量门 + 撤回/投票(D3+D6)。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline
from memory import ExperienceStore
from memory.global_store import GlobalMemory

FAKE = {"claims":[{"id":"x","type":"citation","status":"reject","text":"arxiv:2099.99999","evidence_chain":{"ref":"arxiv:2099.99999"}}]}

def _fresh(p):
    p=f"/tmp/{p}.db"
    if os.path.exists(p): os.remove(p)
    return p

def test_cross_user_aggregation():
    g = GlobalMemory(_fresh("g_agg"))
    A = ExperienceStore(_fresh("uA")); B = ExperienceStore(_fresh("uB")); C = ExperienceStore(_fresh("uC"))
    la = A.write_from_report(FAKE, "userA")[0]
    lb = B.write_from_report(FAKE, "userB")[0]
    # A 先晋升 -> 只有 1 个贡献者 -> pending(未过质量门)
    ra = A.promote_to_global(la, g, consent=True)
    assert ra["status"] == "pending" and ra["distinct_contributors"] == 1, ra
    assert g.query(["fake_cite"]) == []                       # C 此时查不到(还没 active)
    # B 独立晋升同一模式 -> 2 个不同贡献者 -> active
    rb = B.promote_to_global(lb, g, consent=True)
    assert rb["status"] == "active" and rb["distinct_contributors"] == 2, rb
    # 用户 C 现在能从 global 拿到这条经验(跨用户受益)
    got = g.query(["fake_cite"])
    assert len(got) == 1 and got[0]["scope"] == "global", got
    print("  cross-user: A(pending)+B -> active -> C 受益 ✅")

def test_desensitize_blocks_poison():
    g = GlobalMemory(_fresh("g_pois"))
    A = ExperienceStore(_fresh("uP"))
    lid = A.write_from_report(FAKE, "userA")[0]
    # 人为污染 pattern 为原始内容
    A.db.execute("UPDATE verify_lesson SET pattern='private idea 10.1038/xyz john@lab.edu' WHERE id=?", (lid,)); A.db.commit()
    r = A.promote_to_global(lid, g, consent=True)
    assert r["ok"] is False and r["rejected_reason"].startswith("desensitize_failed"), r
    print("  desensitize 拦污染:", r["rejected_reason"], "✅")

def test_consent_required():
    g = GlobalMemory(_fresh("g_con")); A = ExperienceStore(_fresh("uC2"))
    lid = A.write_from_report(FAKE, "userA")[0]
    assert A.promote_to_global(lid, g, consent=False)["rejected_reason"] == "no_consent"   # D6
    print("  consent 门 ✅")

def test_revoke_drops_below_gate():
    g = GlobalMemory(_fresh("g_rev"))
    A=ExperienceStore(_fresh("uR1")); B=ExperienceStore(_fresh("uR2"))
    la=A.write_from_report(FAKE,"userA")[0]; lb=B.write_from_report(FAKE,"userB")[0]
    A.promote_to_global(la,g,True); B.promote_to_global(lb,g,True)
    assert len(g.query(["fake_cite"]))==1
    fpA=A._lesson_dict(la)["contributor_fingerprint"]; sig=A._lesson_dict(la)["signature"]
    g.revoke(sig, fpA)                                        # A 撤回 -> 掉回 1 贡献者 -> retracted
    assert g.query(["fake_cite"])==[]
    print("  撤回后掉出 global ✅")

if __name__=="__main__":
    for t in [test_cross_user_aggregation,test_desensitize_blocks_poison,test_consent_required,test_revoke_drops_below_gate]:
        t()
    print("\nM4 global 治理测试 PASSED")
