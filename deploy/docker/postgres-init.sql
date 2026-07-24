CREATE TABLE IF NOT EXISTS global_lesson (
  signature      TEXT PRIMARY KEY,
  kind           TEXT NOT NULL,
  pattern        TEXT NOT NULL,
  contributors   TEXT DEFAULT '',
  repro_count    INTEGER DEFAULT 0,
  reuse_count    INTEGER DEFAULT 0,
  votes_down     INTEGER DEFAULT 0,
  status         TEXT DEFAULT 'pending',
  created_at     DOUBLE PRECISION,
  updated_at     DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_lesson_kind_status ON global_lesson(kind, status);
