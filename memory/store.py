"""经验库 · 真实实现(T5)。SQLite 三级(local/team/global)+ 时间衰减 + 校验记忆。
飞轮:CoE 报告的 reject → 提炼成可泛化 pattern → 写入 → 生成前置注入。"""
from __future__ import annotations
import sqlite3, hashlib, time, json, re

_SCHEMA = """
CREATE TABLE IF NOT EXISTS verify_lesson(
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,                    -- fake_cite | unsourced_num | fig_code_mismatch
  lesson_class TEXT DEFAULT 'fabrication', -- fabrication=可约束生成 | verification_gap=仅记待办
  pattern TEXT NOT NULL,                 -- 抽象模式(非原始内容)
  signature TEXT UNIQUE,                 -- 去重指纹
  hit_count INTEGER DEFAULT 1,
  repro_count INTEGER DEFAULT 1,         -- 独立复现次数(跨 run/用户)
  scope TEXT DEFAULT 'local',            -- local | team | global
  share_consent TEXT DEFAULT 'none',
  contributor_fingerprint TEXT,
  reuse_count INTEGER DEFAULT 0,
  weight REAL DEFAULT 1.0,
  created_at REAL, last_seen_at REAL,
  status TEXT DEFAULT 'active'           -- active | retracted
);
CREATE TABLE IF NOT EXISTS research_memory(
  id TEXT PRIMARY KEY, kind TEXT, direction TEXT, outcome TEXT, artifact_ref TEXT, scope TEXT DEFAULT 'local', created_at REAL
);
CREATE TABLE IF NOT EXISTS global_promotion_log(
  lesson_id TEXT, from_scope TEXT, to_scope TEXT, repro_count INTEGER, desensitized INTEGER, user_consent INTEGER, ts REAL
);
"""

DECAY_TAU = 60 * 60 * 24 * 30           # 30 天半衰(秒)

class ExperienceStore:
    def __init__(self, path: str = "opensci_mem.db"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA); self.db.commit()

    # ---------- 飞轮:从 CoE 报告提炼校验记忆 ----------
    @staticmethod
    def distill(claim: dict) -> tuple[str, str, str] | None:
        """把一条未通过的 claim 抽象成 (kind, pattern, lesson_class)。
        只保留可泛化模式,不含原始内容(隐私)。

        可达性关键(R2):
          reject     -> fabrication      :世界确证不允许,可回写为生成约束
          unresolved -> verification_gap :只是我们看不到,**不得**回写为生成约束,
                                          否则 verifier 的盲区会变成 generator 的世界边界
        """
        status = claim.get("status")
        if status not in ("reject", "unresolved"):
            return None
        lesson_class = claim.get("failure_kind") or ("fabrication" if status == "reject" else "verification_gap")
        if claim["type"] == "citation":
            # 泛化:不存的引用 id 前缀模式(如 arxiv:2099.* / doi:10.9999.*)
            ref = (claim.get("evidence_chain") or {}).get("ref", "")
            m = re.search(r"(arxiv:\d{4}|doi:10\.\d{4})", claim.get("text","") + " " + ref)
            pat = "NONEXISTENT_CITATION" if lesson_class == "fabrication" else "UNINDEXED_CITATION"
            return ("fake_cite", pat, lesson_class)
        if claim["type"] == "number":
            pat = "UNSOURCED_RESULT_NUMBER" if lesson_class == "fabrication" else "UNVERIFIABLE_DERIVED_NUMBER"
            return ("unsourced_num", pat, lesson_class)
        if claim["type"] == "figure":
            return ("fig_code_mismatch", "FIG_CODE_MISMATCH", lesson_class)
        return None

    def write_from_report(self, report: dict, contributor: str = "anon") -> list[str]:
        """飞轮回写:遍历报告里的 reject,提炼并 upsert(复现则 repro_count+1)。返回 lesson id 列表。"""
        ids = []
        for c in report.get("claims", []):
            d = self.distill(c)
            if not d:
                continue
            kind, pattern, lesson_class = d
            ids.append(self._upsert(kind, pattern, contributor, lesson_class))
        return ids

    def _upsert(self, kind: str, pattern: str, contributor: str, lesson_class: str = "fabrication") -> str:
        sig = hashlib.sha256(f"{kind}|{pattern}".encode()).hexdigest()[:16]
        now = time.time()
        row = self.db.execute("SELECT id, repro_count FROM verify_lesson WHERE signature=?", (sig,)).fetchone()
        if row:
            self.db.execute("UPDATE verify_lesson SET hit_count=hit_count+1, repro_count=repro_count+1, last_seen_at=?, weight=1.0 WHERE id=?",
                            (now, row["id"]))
            self.db.commit(); return row["id"]
        lid = "L" + sig
        self.db.execute(
            "INSERT INTO verify_lesson(id,kind,pattern,signature,lesson_class,contributor_fingerprint,created_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?)",
            (lid, kind, pattern, sig, lesson_class, hashlib.sha256(contributor.encode()).hexdigest()[:12], now, now))
        self.db.commit(); return lid

    # ---------- 生成前置注入 ----------
    def inject(self, kinds: list[str], scope_max: str = "global") -> list[dict]:
        """给生成阶段的黑名单/规则。按 scope + 时间衰减权重排序。

        ★ 可达性护栏(R2):只注入 lesson_class='fabrication'。
        校验缺口(verification_gap)绝不进入生成约束 —— 那只会让系统学会
        「绕开难以校验的区域」,把护城河变成牢笼。它们改由 capability_backlog() 消费。
        """
        order = {"local": ["local"], "team": ["local","team"], "global": ["local","team","global"]}[scope_max]
        q = (f"SELECT id,kind,pattern,scope,repro_count,last_seen_at FROM verify_lesson "
             f"WHERE status='active' AND lesson_class='fabrication' "
             f"AND kind IN ({','.join('?'*len(kinds))}) AND scope IN ({','.join('?'*len(order))})")
        rows = self.db.execute(q, (*kinds, *order)).fetchall()
        now = time.time()
        out = []
        for r in rows:
            decay = 0.5 ** ((now - r["last_seen_at"]) / DECAY_TAU)
            out.append({"id": r["id"], "kind": r["kind"], "pattern": r["pattern"],
                        "scope": r["scope"], "weight": round(r["repro_count"] * decay, 3)})
            self.db.execute("UPDATE verify_lesson SET reuse_count=reuse_count+1 WHERE id=?", (r["id"],))
        self.db.commit()
        return sorted(out, key=lambda x: -x["weight"])

    # ---------- 治理(D3/D6,M4 展开) ----------
    def promote(self, lesson_id: str, target_scope: str, consent: bool, min_repro: int = 2) -> dict:
        if not consent:
            return {"ok": False, "rejected_reason": "no_consent"}
        r = self.db.execute("SELECT repro_count FROM verify_lesson WHERE id=?", (lesson_id,)).fetchone()
        if not r or r["repro_count"] < min_repro:
            return {"ok": False, "rejected_reason": "below_quality_gate"}
        self.db.execute("UPDATE verify_lesson SET scope=?, share_consent=? WHERE id=?", (target_scope, target_scope, lesson_id))
        self.db.execute("INSERT INTO global_promotion_log VALUES(?,?,?,?,?,?,?)",
                        (lesson_id, "local", target_scope, r["repro_count"], 1, 1, time.time()))
        self.db.commit(); return {"ok": True}

    def revoke(self, lesson_id: str) -> dict:
        self.db.execute("UPDATE verify_lesson SET status='retracted', scope='local' WHERE id=?", (lesson_id,))
        self.db.commit(); return {"ok": True}

    def stats(self) -> dict:
        c = self.db.execute("SELECT COUNT(*) n, SUM(scope='global') g, SUM(reuse_count) reuse FROM verify_lesson WHERE status='active'").fetchone()
        return {"lessons": c["n"] or 0, "global": c["g"] or 0, "total_reuse": c["reuse"] or 0}

    def _lesson_dict(self, lesson_id: str) -> dict | None:
        r = self.db.execute("SELECT id,kind,pattern,signature,repro_count,contributor_fingerprint FROM verify_lesson WHERE id=?", (lesson_id,)).fetchone()
        if not r: return None
        return {"id": r["id"], "kind": r["kind"], "pattern": r["pattern"], "signature": r["signature"],
                "repro_count": r["repro_count"], "contributor_fingerprint": r["contributor_fingerprint"]}

    def promote_to_global(self, lesson_id: str, global_mem, consent: bool) -> dict:
        """跨用户晋升:把本地 lesson 交给 GlobalMemory 按 signature 聚合(consent+脱敏在 global 侧再校验)。"""
        les = self._lesson_dict(lesson_id)
        if not les: return {"ok": False, "rejected_reason": "not_found"}
        res = global_mem.promote(les, les["contributor_fingerprint"], consent)
        if res.get("ok") and res.get("status") == "active":
            self.db.execute("UPDATE verify_lesson SET scope='global', share_consent='global' WHERE id=?", (lesson_id,))
            self.db.commit()
        return res

    def list_contributions(self, contributor_fp: str | None = None, global_mem=None) -> list[dict]:
        """T8:用户查看自己贡献了哪些经验、真实当前 scope、被复用多少次。
        给 global_mem 时,按 signature 回填 global 的真实状态(反映后续被他人复现晋升)。"""
        q = "SELECT id,kind,pattern,signature,scope,share_consent,reuse_count,status FROM verify_lesson"
        args = ()
        if contributor_fp:
            q += " WHERE contributor_fingerprint=?"; args = (contributor_fp,)
        out = []
        for r in self.db.execute(q, args).fetchall():
            d = dict(zip(["id","kind","pattern","signature","scope","share_consent","reuse_count","status"], r))
            if global_mem is not None and contributor_fp:
                gs = global_mem.status_for(d["signature"], contributor_fp)
                if gs and gs["is_contributor"] and gs["status"] == "active":
                    d["scope"] = "global"; d["reuse_count"] = gs["reuse_count"]
                d["global_status"] = gs["status"] if gs else "not_in_global"
            out.append(d)
        return out

    def capability_backlog(self, limit: int = 20) -> list[dict]:
        """校验能力待办 —— verification_gap 类经验的去处。
        它们不约束生成器,而是回答:「我们的校验器还看不见什么?该扩哪块证据基质?」
        这是把可达性缺口转化为**能力建设需求**,而非生成禁区。
        """
        rows = self.db.execute(
            "SELECT kind, pattern, SUM(hit_count) hits, COUNT(*) n FROM verify_lesson "
            "WHERE status='active' AND lesson_class='verification_gap' "
            "GROUP BY kind, pattern ORDER BY hits DESC LIMIT ?", (limit,)).fetchall()
        hint = {
            "UNINDEXED_CITATION": "扩展证据基质(Semantic Scholar / PubMed / 机构库),或要求作者补可校验标识",
            "UNVERIFIABLE_DERIVED_NUMBER": "R3 已上线:可在 claim 补 derivation 字段声明推导式;若仍失败,考虑让实验脚本打印该中间量",
            "FIG_CODE_MISMATCH": "接入图↔码一致性核验",
        }
        return [{"kind": r["kind"], "pattern": r["pattern"], "hits": r["hits"],
                 "occurrences": r["n"], "suggested_capability": hint.get(r["pattern"], "扩展校验能力")}
                for r in rows]
