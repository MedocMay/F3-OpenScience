"""M2 回归:飞轮闭环 + 经验库治理机制(质量门 / consent / 撤回)。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _netguard import skip_if_offline, run_suite
from memory import ExperienceStore

FAKE_REPORT = {"claims": [
    {"id":"x","type":"citation","status":"reject","text":"arxiv:2099.99999 fake","evidence_chain":{"ref":"arxiv:2099.99999"}},
    {"id":"n","type":"number","status":"reject","text":"energy 88.8%"},
]}

def _store(tmp): 
    p=f"/tmp/{tmp}.db"; 
    if os.path.exists(p): os.remove(p)
    return ExperienceStore(p)

def test_writeback_and_inject():
    if skip_if_offline("test_writeback_and_inject"): return
    s=_store("m2a")
    ids=s.write_from_report(FAKE_REPORT, "userA")
    assert len(ids)==2                              # fake_cite + unsourced_num 两条
    inj=s.inject(["fake_cite","unsourced_num"],"global")
    assert {i["kind"] for i in inj}=={"fake_cite","unsourced_num"}

def test_quality_gate_blocks_single():
    s=_store("m2b")
    lid=s.write_from_report(FAKE_REPORT,"userA")[0]
    r=s.promote(lid,"global",consent=True)          # repro=1 < 2
    assert r=={"ok":False,"rejected_reason":"below_quality_gate"}

def test_consent_required():
    s=_store("m2c")
    lid=s.write_from_report(FAKE_REPORT,"userA")[0]
    s.write_from_report(FAKE_REPORT,"userB")         # 复现 -> repro=2
    assert s.promote(lid,"global",consent=False)=={"ok":False,"rejected_reason":"no_consent"}  # D6
    assert s.promote(lid,"global",consent=True)=={"ok":True}                                    # 质量门+consent 齐 -> 晋升
    assert any(i["scope"]=="global" for i in s.inject(["fake_cite"],"global"))

def test_revoke():
    s=_store("m2d")
    lid=s.write_from_report(FAKE_REPORT,"userA")[0]
    s.write_from_report(FAKE_REPORT,"userB"); s.promote(lid,"global",consent=True)
    s.revoke(lid)
    assert not any(l["id"]==lid for l in s.inject(["fake_cite"],"global"))   # 撤回后 global 查不到

if __name__=="__main__":
    run_suite([test_writeback_and_inject, test_quality_gate_blocks_single,
               test_consent_required, test_revoke], "M2 governance tests")
