"""Experiment lifecycle: create -> run (immutable run records) -> review -> approve/reject -> export.

Experiments hold an immutable input. Each execution is a new immutable run; only the approval fields of
a run change, and every change is appended to an append-only event log. Nothing is ever deleted.
"""
import json
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from app import config
from app.core import ENGINE_VERSION, execute, get_craft, get_fixture
from app.db import Database
from app.hashing import canonical, sha256  # noqa: F401  (re-exported for callers)
from app.logging_setup import log
from app.validation import validate

EXPORT_SCHEMA = "filmcraft.export_manifest.v1"
ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_DIFF = 500


def resolve_schemas(manifest, payload):
    """(input_schema, output_schema) for this payload: a matching manifest mode, else the craft defaults."""
    if isinstance(payload, dict):
        for mode in manifest.get("modes", []):
            if payload.get("schema") == mode["match_schema"]:
                return mode["input_schema"], mode["output_schema"]
    return manifest.get("input_schema"), manifest.get("output_schema")


class NotFound(LookupError):
    pass


class Conflict(Exception):
    pass


class InvalidInput(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _loads(text):
    return json.loads(text) if text is not None else None


class ExperimentService:
    def __init__(self, db_path):
        self.db = Database(db_path)

    # ---- helpers -------------------------------------------------------------------------
    @staticmethod
    def _check_id(value, kind):
        if not isinstance(value, str) or not ID_RE.match(value):
            raise NotFound(f"{kind} not found")

    def _event(self, conn, experiment_id, run_id, event_type, actor="local-user", **detail):
        conn.execute(
            "INSERT INTO run_events (experiment_id, run_id, event_type, actor, detail_json, created_at) VALUES (?,?,?,?,?,?)",
            (experiment_id, run_id, event_type, actor, canonical(detail), now()))

    @staticmethod
    def _experiment_dict(row, include_input=True):
        out = {k: row[k] for k in ("id", "craft_id", "name", "notes", "input_hash", "input_schema",
                                   "parent_experiment_id", "created_at", "updated_at")}
        if include_input:
            out["input"] = _loads(row["input_json"])
        return out

    @staticmethod
    def _run_dict(row, full=False):
        out = {k: row[k] for k in (
            "id", "experiment_id", "seq", "craft_id", "run_status", "engine_version", "input_schema",
            "output_schema", "input_hash", "output_sha256", "artifact_type", "duration_ms", "created_at",
            "approval_status", "reviewer", "review_note", "approval_timestamp", "updated_at")}
        out["warnings"] = _loads(row["warnings_json"])
        out["error"] = _loads(row["error_json"])
        if full:
            out["envelope"] = _loads(row["output_json"])
        return out

    def _get_experiment_row(self, conn, experiment_id):
        self._check_id(experiment_id, "experiment")
        row = conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if row is None:
            raise NotFound("experiment not found")
        return row

    def _get_run_row(self, conn, run_id):
        self._check_id(run_id, "run")
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFound("run not found")
        return row

    # ---- experiments ---------------------------------------------------------------------
    def create_experiment(self, craft_id, name, input_payload=None, notes="", parent=None):
        try:
            manifest = get_craft(craft_id)
        except KeyError as exc:
            raise NotFound(str(exc)) from exc
        if manifest["status"] != "pilot":
            raise Conflict(f"{craft_id}: pilot engine not yet implemented; experiments cannot be created")
        name = (name or "").strip()
        if not 1 <= len(name) <= 120:
            raise InvalidInput("name must be 1-120 characters")
        if not isinstance(notes, str) or len(notes) > 5000:
            raise InvalidInput("notes must be text of at most 5000 characters")
        if input_payload is None:
            input_payload = get_fixture(craft_id)
        if not isinstance(input_payload, dict):
            raise InvalidInput("input must be a JSON object")
        schema_id, _ = resolve_schemas(manifest, input_payload)
        if schema_id:
            errors = validate(input_payload, schema_id)
            if errors:
                raise InvalidInput(f"input does not match {schema_id}", errors)
        eid, ts = str(uuid4()), now()
        with self.db.write() as conn:
            if parent is not None:
                self._get_experiment_row(conn, parent)
            conn.execute(
                "INSERT INTO experiments (id, craft_id, name, notes, input_json, input_hash, input_schema, parent_experiment_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (eid, craft_id, name, notes, canonical(input_payload), sha256(input_payload), schema_id, parent, ts, ts))
            self._event(conn, eid, None, "experiment.created", craft_id=craft_id, name=name, parent=parent)
        log("experiment.created", experiment_id=eid, craft_id=craft_id)
        return self.get_experiment(eid)

    def update_experiment(self, experiment_id, name=None, notes=None):
        with self.db.write() as conn:
            row = self._get_experiment_row(conn, experiment_id)
            new_name = row["name"] if name is None else str(name).strip()
            new_notes = row["notes"] if notes is None else notes
            if not 1 <= len(new_name) <= 120:
                raise InvalidInput("name must be 1-120 characters")
            if not isinstance(new_notes, str) or len(new_notes) > 5000:
                raise InvalidInput("notes must be text of at most 5000 characters")
            conn.execute("UPDATE experiments SET name=?, notes=?, updated_at=? WHERE id=?",
                         (new_name, new_notes, now(), experiment_id))
            self._event(conn, experiment_id, None, "experiment.updated", name=new_name)
        return self.get_experiment(experiment_id)

    def duplicate_experiment(self, experiment_id, name=None, input_payload=None):
        source = self.get_experiment(experiment_id)
        return self.create_experiment(
            source["craft_id"], name or f"{source['name']} (copy)",
            source["input"] if input_payload is None else input_payload,
            source["notes"], parent=experiment_id)

    def get_experiment(self, experiment_id):
        with self.db.read() as conn:
            row = self._get_experiment_row(conn, experiment_id)
            runs = conn.execute("SELECT * FROM runs WHERE experiment_id=? ORDER BY seq", (experiment_id,)).fetchall()
        out = self._experiment_dict(row)
        out["runs"] = [self._run_dict(r) for r in runs]
        out["reproducibility"] = self._reproducibility(out["runs"])
        return out

    @staticmethod
    def _reproducibility(runs):
        hashes = {r["output_sha256"] for r in runs if r["run_status"] == "completed"}
        completed = sum(1 for r in runs if r["run_status"] == "completed")
        return {"completed_runs": completed, "distinct_outputs": len(hashes),
                "reproducible": completed >= 2 and len(hashes) == 1}

    def list_experiments(self, craft_id=None, approval_status=None, limit=50, offset=0):
        limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
        where, args = [], []
        if craft_id:
            where.append("e.craft_id=?"); args.append(craft_id)
        if approval_status:
            where.append("EXISTS (SELECT 1 FROM runs r WHERE r.experiment_id=e.id AND r.approval_status=?)")
            args.append(approval_status)
        clause = "WHERE " + " AND ".join(where) if where else ""
        with self.db.read() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM experiments e {clause}", args).fetchone()[0]
            rows = conn.execute(
                f"""SELECT e.*, (SELECT COUNT(*) FROM runs r WHERE r.experiment_id=e.id) AS run_count,
                    (SELECT r.run_status FROM runs r WHERE r.experiment_id=e.id ORDER BY seq DESC LIMIT 1) AS latest_run_status,
                    (SELECT r.approval_status FROM runs r WHERE r.experiment_id=e.id ORDER BY seq DESC LIMIT 1) AS latest_approval
                    FROM experiments e {clause} ORDER BY e.created_at DESC, e.rowid DESC LIMIT ? OFFSET ?""",
                [*args, limit, offset]).fetchall()
        items = []
        for r in rows:
            d = self._experiment_dict(r, include_input=False)
            d.update(run_count=r["run_count"], latest_run_status=r["latest_run_status"],
                     latest_approval=r["latest_approval"])
            items.append(d)
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    # ---- runs ----------------------------------------------------------------------------
    def run_experiment(self, experiment_id):
        with self.db.read() as conn:
            exp = self._get_experiment_row(conn, experiment_id)
        payload = _loads(exp["input_json"])
        craft_id = exp["craft_id"]
        manifest = get_craft(craft_id)
        _, output_schema = resolve_schemas(manifest, payload)
        envelope = error = None
        started = time.perf_counter()
        try:
            envelope = execute(craft_id, payload)
            if output_schema:
                problems = validate(envelope["artifact"], output_schema)
                if problems:
                    error = {"type": "output_schema", "message": f"artifact does not match {output_schema}", "details": problems}
        except (ValueError, TypeError, NotImplementedError) as exc:
            error = {"type": "input_rejected", "message": str(exc)}
        except Exception as exc:  # engine bug: record it as a failed run, never crash the server
            log("run.engine_error", level="exception", experiment_id=experiment_id, craft_id=craft_id)
            error = {"type": "engine_error", "message": f"{type(exc).__name__}: {exc}"}
        duration_ms = round((time.perf_counter() - started) * 1000)
        ok = error is None
        run_id = envelope["run_id"] if envelope else str(uuid4())
        ts = now()
        output_hash = sha256({"artifact_type": envelope["artifact_type"], "artifact": envelope["artifact"],
                              "warnings": envelope["warnings"]}) if ok else None
        with self.db.write() as conn:
            seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM runs WHERE experiment_id=?", (experiment_id,)).fetchone()[0]
            conn.execute(
                """INSERT INTO runs (id, experiment_id, seq, craft_id, run_status, engine_version, contract_version,
                   input_schema, output_schema, input_hash, output_sha256, artifact_type, output_json, warnings_json,
                   error_json, duration_ms, created_at, approval_status, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, experiment_id, seq, craft_id, "completed" if ok else "failed", ENGINE_VERSION,
                 manifest["contract_version"], exp["input_schema"], output_schema, exp["input_hash"], output_hash,
                 envelope["artifact_type"] if ok else None, canonical(envelope) if ok else None,
                 canonical(envelope["warnings"] if ok else []), canonical(error) if error else None,
                 duration_ms, ts, "draft" if ok else "none", ts))
            self._event(conn, experiment_id, run_id, "run.completed" if ok else "run.failed",
                        seq=seq, duration_ms=duration_ms, output_sha256=output_hash,
                        error=error["message"] if error else None)
        log("run.completed" if ok else "run.failed", experiment_id=experiment_id, run_id=run_id,
            craft_id=craft_id, duration_ms=duration_ms, error=error["message"] if error else None)
        return self.get_run(run_id)

    def get_run(self, run_id):
        with self.db.read() as conn:
            row = self._get_run_row(conn, run_id)
        return self._run_dict(row, full=True)

    def run_events(self, run_id):
        with self.db.read() as conn:
            row = self._get_run_row(conn, run_id)
            events = conn.execute(
                "SELECT * FROM run_events WHERE run_id=? OR (run_id IS NULL AND experiment_id=?) ORDER BY id",
                (run_id, row["experiment_id"])).fetchall()
        return [{"id": e["id"], "event_type": e["event_type"], "actor": e["actor"],
                 "detail": _loads(e["detail_json"]), "created_at": e["created_at"]} for e in events]

    def verify_run(self, run_id):
        """Re-execute the stored input and compare against the stored output hash. Stores nothing but an event."""
        run = self.get_run(run_id)
        if run["run_status"] != "completed":
            raise Conflict("only completed runs can be verified")
        with self.db.read() as conn:
            payload = _loads(self._get_experiment_row(conn, run["experiment_id"])["input_json"])
        env = execute(run["craft_id"], payload)
        replay = sha256({"artifact_type": env["artifact_type"], "artifact": env["artifact"], "warnings": env["warnings"]})
        result = {"run_id": run_id, "matches": replay == run["output_sha256"],
                  "stored_sha256": run["output_sha256"], "replay_sha256": replay,
                  "stored_engine_version": run["engine_version"], "current_engine_version": ENGINE_VERSION}
        with self.db.write() as conn:
            self._event(conn, run["experiment_id"], run_id, "run.verified", matches=result["matches"])
        log("run.verified", run_id=run_id, matches=result["matches"])
        return result

    # ---- review / approval ---------------------------------------------------------------
    def _transition(self, run_id, allowed_from, to, reviewer, note, event, require_note=False, stamp=False):
        reviewer = (reviewer or "").strip()
        note = (note or "").strip() or None
        if to in ("approved", "rejected") and not reviewer:
            raise InvalidInput("reviewer is required")
        if require_note and not note:
            raise InvalidInput("a note explaining the decision is required")
        if note and len(note) > 2000:
            raise InvalidInput("note must be at most 2000 characters")
        with self.db.write() as conn:
            row = self._get_run_row(conn, run_id)
            if row["approval_status"] not in allowed_from:
                raise Conflict(f"cannot {event.split('.')[1]} a run whose approval status is '{row['approval_status']}'")
            ts = now()
            conn.execute(
                "UPDATE runs SET approval_status=?, reviewer=COALESCE(?, reviewer), review_note=?, approval_timestamp=?, updated_at=? WHERE id=?",
                (to, reviewer or None, note, ts if stamp else None, ts, run_id))
            self._event(conn, row["experiment_id"], run_id, event, actor=reviewer or "local-user",
                        from_status=row["approval_status"], to_status=to, note=note)
        log(event, run_id=run_id, to_status=to, reviewer=reviewer or None)
        return self.get_run(run_id)

    def submit_for_review(self, run_id, reviewer=None, note=None):
        return self._transition(run_id, ("draft", "rejected"), "review", reviewer, note, "approval.submit")

    def approve(self, run_id, reviewer, note=None):
        return self._transition(run_id, ("review",), "approved", reviewer, note, "approval.approve", stamp=True)

    def reject(self, run_id, reviewer, note):
        return self._transition(run_id, ("review",), "rejected", reviewer, note, "approval.reject", require_note=True)

    # ---- export --------------------------------------------------------------------------
    def export_run(self, run_id):
        """Idempotent: the first export stores the manifest; later calls return the stored bytes."""
        with self.db.write() as conn:
            row = self._get_run_row(conn, run_id)
            if row["approval_status"] not in ("approved", "exported"):
                raise Conflict("only approved runs can be exported; approval is a manual step")
            existing = conn.execute("SELECT manifest_json FROM exports WHERE run_id=?", (run_id,)).fetchone()
            if existing:
                return _loads(existing["manifest_json"])
            envelope = _loads(row["output_json"])
            artifact = envelope["artifact"]
            media = _collect_media(artifact)
            ts = now()
            manifest = {
                "schema": EXPORT_SCHEMA,
                "manifest_id": f"mf-{row['id']}",
                "exported_at": ts,
                "source": {"application": "craftbox", "version": config.VERSION, "contract_version": row["contract_version"]},
                "craft_id": row["craft_id"], "experiment_id": row["experiment_id"], "run_id": row["id"],
                "engine_version": row["engine_version"], "input_schema": row["input_schema"],
                "input_hash": row["input_hash"], "output_sha256": row["output_sha256"],
                "artifact_type": row["artifact_type"], "artifact_schema": row["output_schema"] or artifact.get("schema"),
                "artifact": artifact,
                "approval": {"status": "approved", "reviewer": row["reviewer"],
                             "approved_at": row["approval_timestamp"], "note": row["review_note"]},
                "media_references": media,
                "provenance": envelope["provenance"],
                "warnings": envelope["warnings"],
                "import_policy": {"auto_import": False, "requires_user_confirmation": True,
                                  "note": "Dreambox-owned adapter must validate schema, IDs and media before staging."},
                "signature": None,
            }
            manifest["manifest_sha256"] = sha256(manifest)
            problems = validate(manifest, EXPORT_SCHEMA)
            if problems:
                raise RuntimeError(f"generated manifest invalid: {problems}")
            conn.execute("INSERT INTO exports (run_id, manifest_id, manifest_json, manifest_sha256, exported_at) VALUES (?,?,?,?,?)",
                         (run_id, manifest["manifest_id"], canonical(manifest), manifest["manifest_sha256"], ts))
            conn.execute("UPDATE runs SET approval_status='exported', updated_at=? WHERE id=?", (ts, run_id))
            self._event(conn, row["experiment_id"], run_id, "export.created", actor=row["reviewer"] or "local-user",
                        manifest_sha256=manifest["manifest_sha256"])
        log("export.created", run_id=run_id, manifest_sha256=manifest["manifest_sha256"])
        return manifest

    def get_manifest(self, run_id):
        with self.db.read() as conn:
            self._get_run_row(conn, run_id)
            row = conn.execute("SELECT manifest_json FROM exports WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFound("run has not been exported")
        return _loads(row["manifest_json"])

    # ---- comparison ----------------------------------------------------------------------
    def compare_runs(self, run_a, run_b):
        a, b = self.get_run(run_a), self.get_run(run_b)
        if a["craft_id"] != b["craft_id"]:
            raise Conflict("runs belong to different crafts and cannot be compared")
        if a["run_status"] != "completed" or b["run_status"] != "completed":
            raise Conflict("both runs must be completed")
        with self.db.read() as conn:
            in_a = _loads(self._get_experiment_row(conn, a["experiment_id"])["input_json"])
            in_b = _loads(self._get_experiment_row(conn, b["experiment_id"])["input_json"])
        summary = lambda r: {k: r[k] for k in ("id", "experiment_id", "seq", "engine_version", "input_hash", "output_sha256", "created_at", "approval_status")}
        input_changes, artifact_changes = [], []
        _diff(in_a, in_b, "input", input_changes)
        _diff(a["envelope"]["artifact"], b["envelope"]["artifact"], "artifact", artifact_changes)
        warning_changes = {"only_in_a": [w for w in a["warnings"] if w not in b["warnings"]],
                           "only_in_b": [w for w in b["warnings"] if w not in a["warnings"]]}
        return {"a": summary(a), "b": summary(b),
                "identical_input": a["input_hash"] == b["input_hash"],
                "identical_output": a["output_sha256"] == b["output_sha256"],
                "input_changes": input_changes[:MAX_DIFF], "artifact_changes": artifact_changes[:MAX_DIFF],
                "truncated": len(input_changes) > MAX_DIFF or len(artifact_changes) > MAX_DIFF,
                "warning_changes": warning_changes}

    # ---- system --------------------------------------------------------------------------
    def stats(self):
        with self.db.read() as conn:
            return {"experiments": conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0],
                    "runs": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
                    "exports": conn.execute("SELECT COUNT(*) FROM exports").fetchone()[0]}


def _collect_media(node):
    ids, unresolved = set(), 0

    def walk(n):
        nonlocal unresolved
        if isinstance(n, dict):
            if "media_asset_id" in n:
                if n["media_asset_id"] is None:
                    unresolved += 1
                else:
                    ids.add(str(n["media_asset_id"]))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    return {"referenced": sorted(ids), "unresolved_count": unresolved}


_KEYS = ("shot_id", "id", "scene_id", "speaker_id")


def _list_key(a, b):
    for key in _KEYS:
        items = a + b
        if items and all(isinstance(i, dict) and isinstance(i.get(key), str) for i in items):
            if len({i[key] for i in a}) == len(a) and len({i[key] for i in b}) == len(b):
                return key
    return None


def _diff(a, b, path, out):
    if len(out) > MAX_DIFF:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append({"path": f"{path}.{k}", "change": "added", "b": b[k]})
            elif k not in b:
                out.append({"path": f"{path}.{k}", "change": "removed", "a": a[k]})
            else:
                _diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        key = _list_key(a, b)
        if key:
            ma, mb = {i[key]: i for i in a}, {i[key]: i for i in b}
            for k in [*ma, *[k for k in mb if k not in ma]]:
                label = f"{path}[{k}]"
                if k not in mb:
                    out.append({"path": label, "change": "removed", "a": ma[k]})
                elif k not in ma:
                    out.append({"path": label, "change": "added", "b": mb[k]})
                else:
                    _diff(ma[k], mb[k], label, out)
        else:
            for i in range(max(len(a), len(b))):
                label = f"{path}[{i}]"
                if i >= len(a):
                    out.append({"path": label, "change": "added", "b": b[i]})
                elif i >= len(b):
                    out.append({"path": label, "change": "removed", "a": a[i]})
                else:
                    _diff(a[i], b[i], label, out)
    elif a != b or type(a) is not type(b):
        out.append({"path": path, "change": "changed", "a": a, "b": b})
