"""M6 回归:可复现包(T7)+ 用户主权面板(T8)。"""
import sys, os, json, hashlib, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline
from memory import ExperienceStore
from memory.global_store import GlobalMemory
from orchestrator.packager import build_package

FAKE = {"claims":[{"id":"x","type":"citation","status":"reject","text":"arxiv:2099.99999","evidence_chain":{"ref":"arxiv:2099.99999"}}]}

def test_reproducible_package():
    gen = {"draft":"# t\n[c] 5.0%","code":"print('improvement 5.0%')","run_log":"improvement 5.0%",
           "data_sources":["arXiv"],"papers":[{"arxiv_id":"1706.03762","title":"Attention Is All You Need"}]}
    report = {"run_id":"pkg1","all_green":True,"claims":[],"stats":{"hallucinated_citations":0,"numbers_sourced":"1/1","citations_checked":1,"citations_rejected":0}}
    p = build_package("pkg1","test dir",gen,report,"/tmp/pkgtest")
    for f in ["draft.md","experiment.py","run.log","verification_report.json","manifest.json","repro.sh"]:
        assert os.path.exists(os.path.join(p,f)), f
    man = json.load(open(os.path.join(p,"manifest.json")))
    assert man["verification"]["hallucinated_citations"] == 0
    assert man["environment"]["seed"] == 42
    print("  可复现包含 6 件套 + manifest(env/数据源/校验/指纹) ✅")

def test_sovereignty_list_and_revoke():
    db = "/tmp/sov.db"
    if os.path.exists(db): os.remove(db)
    g = GlobalMemory("/tmp/sov_g.db")
    if os.path.exists("/tmp/sov_g.db"): os.remove("/tmp/sov_g.db"); g = GlobalMemory("/tmp/sov_g.db")
    A = ExperienceStore(db); B = ExperienceStore("/tmp/sov_b.db")
    if os.path.exists("/tmp/sov_b.db"): os.remove("/tmp/sov_b.db"); B = ExperienceStore("/tmp/sov_b.db")
    la = A.write_from_report(FAKE,"userA")[0]; lb = B.write_from_report(FAKE,"userB")[0]
    A.promote_to_global(la, g, consent=True); B.promote_to_global(lb, g, consent=True)
    # A 查看自己的贡献
    fpA = hashlib.sha256("userA".encode()).hexdigest()[:12]
    contribs = A.list_contributions(fpA, global_mem=g)
    assert len(contribs) == 1 and contribs[0]["scope"] == "global", contribs
    assert g.query(["fake_cite"]), "global 有该经验"
    # A 撤回 -> 掉出 global(2->1 贡献者)
    sig = A._lesson_dict(la)["signature"]
    g.revoke(sig, fpA)
    assert g.query(["fake_cite"]) == [], "撤回后 global 查不到"
    print("  主权面板:查看贡献(scope=global,可见 reuse)+ 撤回掉出 global ✅")

if __name__ == "__main__":
    test_reproducible_package()
    test_sovereignty_list_and_revoke()
    print("\nM6 (T7 可复现包 + T8 主权面板) PASSED")
