# 存储:SQLite(默认)→ Postgres(云端规模)

## 现状
所有状态存 **SQLite 本地文件**(`./data/*.db`):
- 网关经验库:`OPENSCI_DB`
- global 记忆:`OPENSCI_GLOBAL_DB`

单机 / 内网 / 单租户,SQLite 足够,零运维。

## 何时换 Postgres
云端**多实例网关**或**多租户 global** 时:SQLite 单文件不支持多进程并发写、无法跨实例共享。换 Postgres。

## 切换点(代码)
存储集中在两处 `sqlite3.connect(...)`:`memory/store.py`(ExperienceStore)与 `memory/global_store.py`(GlobalMemory)。生产化建议抽一层 `Storage` 接口,SQLite / Postgres 两实现;SQL 方言差异很小(下方 DDL 即 Postgres 版)。

## Postgres DDL(global 服务)
```sql
CREATE TABLE global_lesson (
  signature      TEXT PRIMARY KEY,
  kind           TEXT NOT NULL,
  pattern        TEXT NOT NULL,
  contributors   TEXT DEFAULT '',      -- 贡献者指纹集合(不含身份)
  repro_count    INT  DEFAULT 0,       -- = 不同贡献者数
  reuse_count    INT  DEFAULT 0,
  votes_down     INT  DEFAULT 0,
  status         TEXT DEFAULT 'pending',
  created_at     DOUBLE PRECISION,
  updated_at     DOUBLE PRECISION
);
CREATE INDEX idx_lesson_kind_status ON global_lesson(kind, status);
```
并发:`promote` 用 `INSERT ... ON CONFLICT (signature) DO UPDATE` 替代读-改-写,天然并发安全。

## 迁移
SQLite → Postgres 一次性:`pgloader sqlite://./data/global.db postgresql://.../opensci` 或按表导出 CSV 再 `COPY`。
