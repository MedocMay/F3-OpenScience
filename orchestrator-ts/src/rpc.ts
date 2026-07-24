// JSON-RPC 2.0 over stdio 客户端。拉起一个 sidecar 子进程,按 contracts 调方法。
// 与 Python 版 rpc.py 同协议:sidecar 读 stdin 一行 JSON、写 stdout 一行 JSON。
import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";

export class RpcClient {
  private proc: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: any) => void }>();
  private buf = "";

  constructor(public name: string, argv: string[], cwd?: string) {
    this.proc = spawn(argv[0], argv.slice(1), { cwd, stdio: ["pipe", "pipe", "pipe"] });
    this.proc.stdout.setEncoding("utf8");
    this.proc.stdout.on("data", (chunk: string) => this.onData(chunk));
    this.proc.stderr.on("data", () => {}); // 静默;调试时可打印
  }

  private onData(chunk: string) {
    this.buf += chunk;
    let idx: number;
    while ((idx = this.buf.indexOf("\n")) >= 0) {
      const line = this.buf.slice(0, idx).trim();
      this.buf = this.buf.slice(idx + 1);
      if (!line) continue;
      let resp: any;
      try { resp = JSON.parse(line); } catch { continue; }
      const waiter = this.pending.get(resp.id);
      if (!waiter) continue;
      this.pending.delete(resp.id);
      if (resp.error) waiter.reject(new Error(`[${this.name}] ${JSON.stringify(resp.error)}`));
      else waiter.resolve(resp.result);
    }
  }

  call<T = any>(method: string, params: unknown, timeoutMs = 60000): Promise<T> {
    const id = this.nextId++;
    const payload = JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n";
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`[${this.name}] timeout on ${method}`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });
      this.proc.stdin.write(payload);
    });
  }

  close() { try { this.proc.stdin.end(); this.proc.kill(); } catch {} }
}
