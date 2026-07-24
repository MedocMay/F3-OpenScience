"""CoE Kernel sidecar — JSON-RPC 2.0 over stdio。Orchestrator 起它为独立进程。
方法:coe.verify(run_id, draft, claims[], run_logs_ref) -> verification_report。"""
import sys, json
from .kernel import run_verify

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get("method") == "coe.verify":
                p = req.get("params", {})
                result = run_verify(p.get("run_id",""), p.get("draft",""), p.get("claims"), p.get("run_logs_ref",""))
                resp = {"jsonrpc":"2.0","id":req.get("id"),"result":result}
            else:
                resp = {"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"method not found"}}
        except Exception as e:
            resp = {"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":str(e)}}
        sys.stdout.write(json.dumps(resp)+"\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
