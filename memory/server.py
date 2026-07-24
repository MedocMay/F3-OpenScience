"""经验库 sidecar — JSON-RPC over stdio。mem.query / mem.write_from_report / mem.promote / mem.revoke。"""
import sys, json
from .store import ExperienceStore

def main(db="opensci_mem.db"):
    store = ExperienceStore(db)
    disp = {
        "mem.query": lambda p: store.inject(p.get("kinds", []), p.get("scope_max", "global")),
        "mem.write_from_report": lambda p: store.write_from_report(p.get("report", {}), p.get("contributor", "anon")),
        "mem.promote": lambda p: store.promote(p["lesson_id"], p["target_scope"], p["consent"]),
        "mem.revoke": lambda p: store.revoke(p["lesson_id"]),
        "mem.stats": lambda p: store.stats(),
        "mem.list_contributions": lambda p: store.list_contributions(p.get("contributor_fp")),
    }
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            req = json.loads(line); m = req.get("method")
            resp = {"jsonrpc":"2.0","id":req.get("id"),"result": disp[m](req.get("params", {}))} if m in disp \
                   else {"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"method not found"}}
        except Exception as e:
            resp = {"jsonrpc":"2.0","id":None,"error":{"code":-32603,"message":str(e)}}
        sys.stdout.write(json.dumps(resp)+"\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
