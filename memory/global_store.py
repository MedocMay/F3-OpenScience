"""GlobalMemory — 跨用户 global 汇聚服务(独立 DB)。按 signature 聚合;
质量门 = 达到 >=N 个"不同贡献者"才 active;consent+脱敏 为上行前提;可撤回/投票下架。
生产传输为 gRPC(contracts/memory.proto);此处同一 JSON-RPC 语义,便于本地跑通。"""
from __future__ import annotations
import time, os
from .desensitize import desensitize
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cloud.db import open_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS global_lesson(
  signature TEXT PRIMARY KEY, kind TEXT, pattern TEXT,
  contributors TEXT DEFAULT '',        -- 去重指纹集合(逗号分隔),不含身份
  repro_count INTEGER DEFAULT 0,       -- = 不同贡献者数
  reuse_count INTEGER DEFAULT 0,
  votes_down INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',       -- pending(未达门) | active | retracted
  created_at REAL, updated_at REAL
);
"""
MIN_CONTRIBUTORS = 2   # 质量门:>=2 个不同用户独立复现才 active

class GlobalMemory:
    def __init__(self, path="/tmp/global_mem.db"):
        # path 可为 SQLite 路径或 postgres:// DSN(云端多实例共享)
        dsn = os.environ.get("OPENSCI_GLOBAL_DSN") or path
        self.db = open_db(dsn)
        self.db.executescript(_SCHEMA); self.db.commit()

    def promote(self, lesson: dict, contributor_fp: str, consent: bool) -> dict:
        if not consent:
            return {"ok": False, "rejected_reason": "no_consent"}          # D6
        ok, reason = desensitize(lesson)
        if not ok:
            return {"ok": False, "rejected_reason": f"desensitize_failed:{reason}"}
        sig = lesson["signature"]; now = time.time()
        row = self.db.execute("SELECT contributors, repro_count FROM global_lesson WHERE signature=?", (sig,)).fetchone()
        if row:
            contribs = set(filter(None, row["contributors"].split(",")))
            contribs.add(contributor_fp)
            status = "active" if len(contribs) >= MIN_CONTRIBUTORS else "pending"
            self.db.execute("UPDATE global_lesson SET contributors=?, repro_count=?, status=CASE WHEN status='retracted' THEN 'retracted' ELSE ? END, updated_at=? WHERE signature=?",
                            (",".join(sorted(contribs)), len(contribs), status, now, sig))
        else:
            self.db.execute("INSERT INTO global_lesson(signature,kind,pattern,contributors,repro_count,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                            (sig, lesson["kind"], lesson["pattern"], contributor_fp, 1, "pending", now, now))
        self.db.commit()
        r = self.db.execute("SELECT repro_count,status FROM global_lesson WHERE signature=?", (sig,)).fetchone()
        return {"ok": True, "status": r["status"], "distinct_contributors": r["repro_count"]}

    def query(self, kinds: list[str]) -> list[dict]:
        q = f"SELECT signature,kind,pattern,repro_count FROM global_lesson WHERE status='active' AND kind IN ({','.join('?'*len(kinds))})"
        rows = self.db.execute(q, tuple(kinds)).fetchall()
        for r in rows:
            self.db.execute("UPDATE global_lesson SET reuse_count=reuse_count+1 WHERE signature=?", (r["signature"],))
        self.db.commit()
        return [{"id": r["signature"], "kind": r["kind"], "pattern": r["pattern"],
                 "scope": "global", "repro_count": r["repro_count"]} for r in rows]

    def revoke(self, signature: str, contributor_fp: str) -> dict:
        row = self.db.execute("SELECT contributors FROM global_lesson WHERE signature=?", (signature,)).fetchone()
        if not row: return {"ok": False}
        contribs = set(filter(None, row["contributors"].split(","))) - {contributor_fp}
        status = "retracted" if len(contribs) < MIN_CONTRIBUTORS else "active"
        self.db.execute("UPDATE global_lesson SET contributors=?, repro_count=?, status=? WHERE signature=?",
                        (",".join(sorted(contribs)), len(contribs), status, signature))
        self.db.commit()
        return {"ok": True, "status": status}

    def vote_down(self, signature: str) -> dict:
        self.db.execute("UPDATE global_lesson SET votes_down=votes_down+1 WHERE signature=?", (signature,))
        r = self.db.execute("SELECT votes_down FROM global_lesson WHERE signature=?", (signature,)).fetchone()
        if r and r["votes_down"] >= 3:
            self.db.execute("UPDATE global_lesson SET status='retracted' WHERE signature=?", (signature,))
        self.db.commit()
        return {"ok": True, "votes_down": r["votes_down"] if r else 0}

    def status_for(self, signature: str, contributor_fp: str) -> dict | None:
        """给主权面板:某贡献者在某 signature 上的真实当前状态。"""
        r = self.db.execute("SELECT contributors,status,reuse_count,repro_count FROM global_lesson WHERE signature=?", (signature,)).fetchone()
        if not r:
            return None
        is_contrib = contributor_fp in set(filter(None, r["contributors"].split(",")))
        return {"in_global": True, "status": r["status"], "reuse_count": r["reuse_count"],
                "distinct_contributors": r["repro_count"], "is_contributor": is_contrib}
