"""Pipeline sidecar — JSON-RPC over stdio。pipeline.generate -> 真实主线(M5)。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline.pipeline import run_pipeline

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            req = json.loads(line)
            if req.get("method") == "pipeline.generate":
                p = req.get("params", {})
                resp = {"jsonrpc":"2.0","id":req.get("id"),"result": run_pipeline(p.get("direction",""), p.get("injected", []))}
            else:
                resp = {"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"method not found"}}
        except Exception as e:
            resp = {"jsonrpc":"2.0","id":None,"error":{"code":-32603,"message":str(e)}}
        sys.stdout.write(json.dumps(resp)+"\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
