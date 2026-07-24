"""存储抽象 — global 记忆同码跑 SQLite(默认)或 Postgres(云端多实例)。
SQL 用 ? 占位;PG 后端自动转 %s、REAL→DOUBLE PRECISION。row 以 key 访问(两端一致)。"""
from __future__ import annotations

def open_db(dsn: str):
    if dsn.startswith("postgres"):
        return _PG(dsn)
    path = dsn[len("sqlite:///"):] if dsn.startswith("sqlite:///") else dsn
    return _SQLite(path)

class _SQLite:
    dialect = "sqlite"
    def __init__(self, path):
        import sqlite3
        self.c = sqlite3.connect(path, check_same_thread=False); self.c.row_factory = sqlite3.Row
    def execute(self, sql, params=()):
        return self.c.execute(sql, params)
    def executescript(self, s):
        self.c.executescript(s); self.c.commit()
    def commit(self): self.c.commit()

class _PG:
    dialect = "postgres"
    def __init__(self, dsn):
        import psycopg
        from psycopg.rows import dict_row
        self.conn = psycopg.connect(dsn, row_factory=dict_row)
    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)   # 占位符方言
        return cur
    def executescript(self, s):
        s = s.replace(" REAL", " DOUBLE PRECISION")    # 类型方言
        cur = self.conn.cursor()
        for stmt in filter(str.strip, s.split(";")):
            cur.execute(stmt)
        self.conn.commit()
    def commit(self): self.conn.commit()
