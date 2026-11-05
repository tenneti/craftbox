"""SQLite persistence: connection helper and ordered, versioned migrations (PRAGMA user_version).

Run and event records are append-only: triggers reject deletes and edits of immutable columns, so
experiment history cannot be silently rewritten. API keys are never stored here.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_RUN_IMMUTABLE = (
    "id, experiment_id, seq, craft_id, run_status, engine_version, contract_version, input_schema, "
    "output_schema, input_hash, output_sha256, artifact_type, output_json, warnings_json, error_json, "
    "duration_ms, created_at"
)

MIGRATIONS = [
    # 1: CB0 foundation
    f"""
    CREATE TABLE experiments (
        id TEXT PRIMARY KEY,
        craft_id TEXT NOT NULL,
        name TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        input_json TEXT NOT NULL,
        input_hash TEXT NOT NULL,
        input_schema TEXT,
        parent_experiment_id TEXT REFERENCES experiments(id),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_experiments_craft ON experiments(craft_id, created_at);
    CREATE TABLE runs (
        id TEXT PRIMARY KEY,
        experiment_id TEXT NOT NULL REFERENCES experiments(id),
        seq INTEGER NOT NULL,
        craft_id TEXT NOT NULL,
        run_status TEXT NOT NULL CHECK (run_status IN ('completed', 'failed')),
        engine_version TEXT NOT NULL,
        contract_version TEXT NOT NULL,
        input_schema TEXT,
        output_schema TEXT,
        input_hash TEXT NOT NULL,
        output_sha256 TEXT,
        artifact_type TEXT,
        output_json TEXT,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        error_json TEXT,
        duration_ms INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        approval_status TEXT NOT NULL CHECK (approval_status IN ('none', 'draft', 'review', 'approved', 'rejected', 'exported')),
        reviewer TEXT,
        review_note TEXT,
        approval_timestamp TEXT,
        updated_at TEXT NOT NULL,
        UNIQUE (experiment_id, seq)
    );
    CREATE TABLE run_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id TEXT NOT NULL,
        run_id TEXT,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL,
        detail_json TEXT NOT NULL DEFAULT '{{}}',
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_events_run ON run_events(run_id);
    CREATE INDEX idx_events_experiment ON run_events(experiment_id);
    CREATE TABLE exports (
        run_id TEXT PRIMARY KEY REFERENCES runs(id),
        manifest_id TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        manifest_sha256 TEXT NOT NULL,
        exported_at TEXT NOT NULL
    );
    CREATE TRIGGER runs_immutable BEFORE UPDATE OF {_RUN_IMMUTABLE} ON runs
        BEGIN SELECT RAISE(ABORT, 'run record is immutable'); END;
    CREATE TRIGGER experiments_immutable BEFORE UPDATE OF id, craft_id, input_json, input_hash, input_schema, parent_experiment_id, created_at ON experiments
        BEGIN SELECT RAISE(ABORT, 'experiment input is immutable'); END;
    CREATE TRIGGER events_no_update BEFORE UPDATE ON run_events
        BEGIN SELECT RAISE(ABORT, 'run log is append-only'); END;
    CREATE TRIGGER exports_no_update BEFORE UPDATE ON exports
        BEGIN SELECT RAISE(ABORT, 'exports are immutable'); END;
    CREATE TRIGGER experiments_no_delete BEFORE DELETE ON experiments BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END;
    CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END;
    CREATE TRIGGER events_no_delete BEFORE DELETE ON run_events BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END;
    CREATE TRIGGER exports_no_delete BEFORE DELETE ON exports BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END;
    """,
    # 2: CB1 derived exports (scene/shot manifests prepared for Dreambox); immutable and never deleted
    """
    CREATE TABLE derived_exports (
        run_id TEXT NOT NULL REFERENCES runs(id),
        kind TEXT NOT NULL,
        manifest_id TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        manifest_sha256 TEXT NOT NULL,
        overrides_json TEXT NOT NULL DEFAULT '[]',
        exported_at TEXT NOT NULL,
        PRIMARY KEY (run_id, kind)
    );
    CREATE TRIGGER derived_exports_no_update BEFORE UPDATE ON derived_exports BEGIN SELECT RAISE(ABORT, 'exports are immutable'); END;
    CREATE TRIGGER derived_exports_no_delete BEFORE DELETE ON derived_exports BEGIN SELECT RAISE(ABORT, 'history is never deleted'); END;
    """,
]


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def _open(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def read(self):
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self):
        """One immediate transaction: commits on success, rolls back on any exception."""
        conn = self._open()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def version(self):
        with self.read() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self):
        conn = self._open()
        try:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current > len(MIGRATIONS):
                raise RuntimeError(f"database schema v{current} is newer than this Craftbox ({len(MIGRATIONS)})")
            for number in range(current + 1, len(MIGRATIONS) + 1):
                conn.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _split(MIGRATIONS[number - 1]):
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version = {number}")
                    conn.execute("COMMIT")
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
        finally:
            conn.close()

    def integrity(self):
        with self.read() as conn:
            return conn.execute("PRAGMA integrity_check").fetchone()[0]


def _split(script):
    """Split a script into statements; triggers contain ';' inside BEGIN..END."""
    statements, buf, in_trigger = [], [], False
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        buf.append(line)
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger:
            if stripped.endswith("END;"):
                statements.append("\n".join(buf)); buf, in_trigger = [], False
        elif stripped.endswith(";"):
            statements.append("\n".join(buf)); buf = []
    return statements
