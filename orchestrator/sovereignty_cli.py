"""用户主权面板(T8)— CLI 代表桌面面板。查看/撤回自己的贡献。"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from memory import ExperienceStore

def panel(db, user):
    fp = hashlib.sha256(user.encode()).hexdigest()[:12]
    s = ExperienceStore(db)
    rows = s.list_contributions(fp)
    print(f"\n=== 用户主权面板 · {user} ===  (private-by-default)")
    if not rows:
        print("  (无贡献记录 — 你的经验默认仅本地,未共享)"); return
    for r in rows:
        print(f"  {r['id']}  [{r['kind']}]  scope={r['scope']:6s} consent={r['share_consent']:6s} "
              f"reuse={r['reuse_count']} status={r['status']}")
    return s, rows

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "/tmp/orch_demo.db"
    user = sys.argv[2] if len(sys.argv) > 2 else "user1"
    panel(db, user)
