"""GlobalMemory sidecar — JSON-RPC over stdio(生产传输为 gRPC,见 contracts/memory.proto)。
方法:global.promote / global.query / global.revoke / global.vote_down。"""
import sys, json
from .global_store import GlobalMemory

def main(db="/tmp/global_mem.db"):
    g = GlobalMemory(db)
    disp = {
        "global.promote":   lambda p: g.promote(p["lesson"], p["contributor_fp"], p["consent"]),
        "global.query":     lambda p: g.query(p.get("kinds", [])),
        "global.revoke":    lambda p: g.revoke(p["signature"], p["contributor_fp"]),
        "global.vote_down": lambda p: g.vote_down(p["signature"]),
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
