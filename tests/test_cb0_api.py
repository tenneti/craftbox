"""CB0 backend tests: schemas, experiment lifecycle, persistence, export, comparison, config."""
import copy
import os
import socket
import sqlite3
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("CRAFTBOX_LOG_LEVEL", "ERROR")  # keep test output readable

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.core import all_crafts, execute, get_fixture
from app.experiments import sha256
from app.run import port_in_use
from app.server import create_app
from app.validation import get_schema, list_schemas, validate

PILOTS = ("screenwriting", "cinematography", "editing")


def pilot_input(craft):
    """Chain the three pilots exactly as examples/pipeline.py does."""
    scene = execute("screenwriting", get_fixture("screenwriting"))["artifact"]
    if craft == "screenwriting":
        return get_fixture("screenwriting")
    if craft in ("direction", "art_direction", "lighting"):
        return get_fixture(craft)
    cam = get_fixture("cinematography")
    cam["scene"] = scene
    if craft == "cinematography":
        return cam
    return {"shot_plan": execute("cinematography", cam)["artifact"]}


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(self.tmp.name, log_to_file=False)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.db_path = os.path.join(self.tmp.name, "craftbox.db")

    def make(self, craft="screenwriting", name="exp", payload=None, run=False):
        body = {"craft_id": craft, "name": name, "input": payload if payload is not None else pilot_input(craft), "run_now": run}
        r = self.client.post("/api/experiments", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def run_of(self, exp_id):
        r = self.client.post(f"/api/experiments/{exp_id}/run")
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class SchemaTests(unittest.TestCase):
    def test_registry_contains_artifact_input_and_export_schemas(self):
        ids = set(list_schemas())
        for sid in ("filmcraft.scene.v1", "filmcraft.shot_plan.v1", "filmcraft.edit_plan.v1",
                    "filmcraft.export_manifest.v1", *(f"filmcraft.input.{c}.v1" for c in PILOTS)):
            self.assertIn(sid, ids)

    def test_every_pilot_manifest_references_existing_schemas_and_fixture_validates(self):
        for craft in (c for c in all_crafts() if c["status"] == "pilot"):
            self.assertEqual(validate(pilot_input(craft["id"]), craft["input_schema"]), [], craft["id"])
            artifact = execute(craft["id"], pilot_input(craft["id"]))["artifact"]
            self.assertEqual(validate(artifact, craft["output_schema"]), [], craft["id"])
            self.assertEqual(artifact["schema"], craft["output_schema"])

    def test_negative_cases_report_paths(self):
        bad = pilot_input("cinematography")
        bad["shots"][0]["lens_mm"] = "wide"
        bad["scene"]["schema"] = "filmcraft.scene.v2"
        errors = validate(bad, "filmcraft.input.cinematography.v1")
        paths = {e["path"] for e in errors}
        self.assertIn("$.shots[0].lens_mm", paths)
        self.assertIn("$.scene.schema", paths)
        self.assertTrue(validate({}, "filmcraft.input.editing.v1"))

    def test_unsupported_keyword_is_never_ignored(self):
        with self.assertRaises(RuntimeError):
            validate({}, {"type": "object", "dependencies": {}})

    def test_non_pilot_has_no_schema_claims(self):
        for c in all_crafts():
            if c["status"] != "pilot":
                self.assertNotIn("input_schema", c)


class LifecycleTests(ApiCase):
    def test_full_lifecycle_for_each_pilot(self):
        for craft in PILOTS:
            exp = self.make(craft, f"{craft} lifecycle")
            self.assertEqual(exp["runs"], [])
            run = self.run_of(exp["id"])
            self.assertEqual(run["run_status"], "completed")
            self.assertEqual(run["approval_status"], "draft")
            self.assertEqual(validate(run["envelope"]["artifact"], run["output_schema"]), [])
            rid = run["id"]
            # approval requires review first
            self.assertEqual(self.client.post(f"/api/runs/{rid}/approve", json={"reviewer": "kc"}).status_code, 409)
            self.assertEqual(self.client.post(f"/api/runs/{rid}/export").status_code, 409)
            r = self.client.post(f"/api/runs/{rid}/submit-review", json={})
            self.assertEqual(r.json()["approval_status"], "review")
            r = self.client.post(f"/api/runs/{rid}/approve", json={"reviewer": "kc", "note": "looks right"})
            self.assertEqual(r.json()["approval_status"], "approved")
            self.assertTrue(r.json()["approval_timestamp"])
            manifest = self.client.post(f"/api/runs/{rid}/export").json()
            self.assertEqual(validate(manifest, "filmcraft.export_manifest.v1"), [])
            self.assertEqual(manifest["run_id"], rid)
            self.assertEqual(manifest["artifact"], run["envelope"]["artifact"])
            self.assertEqual(self.client.get(f"/api/runs/{rid}").json()["approval_status"], "exported")
            events = [e["event_type"] for e in self.client.get(f"/api/runs/{rid}/events").json()]
            self.assertEqual(events, ["experiment.created", "run.completed", "approval.submit", "approval.approve", "export.created"])

    def test_reject_requires_reviewer_and_note_and_blocks_export(self):
        run = self.run_of(self.make()["id"])
        rid = run["id"]
        self.assertEqual(self.client.post(f"/api/runs/{rid}/reject", json={"reviewer": "kc", "note": "x"}).status_code, 409)
        self.client.post(f"/api/runs/{rid}/submit-review", json={})
        self.assertEqual(self.client.post(f"/api/runs/{rid}/reject", json={"reviewer": "kc"}).status_code, 422)
        self.assertEqual(self.client.post(f"/api/runs/{rid}/reject", json={"note": "bad"}).status_code, 422)
        r = self.client.post(f"/api/runs/{rid}/reject", json={"reviewer": "kc", "note": "framing wrong"})
        self.assertEqual(r.json()["approval_status"], "rejected")
        self.assertEqual(r.json()["review_note"], "framing wrong")
        self.assertEqual(self.client.post(f"/api/runs/{rid}/export").status_code, 409)
        self.assertEqual(self.client.get(f"/api/runs/{rid}/manifest").status_code, 404)
        # a rejected run may be resubmitted, and is recorded
        self.assertEqual(self.client.post(f"/api/runs/{rid}/submit-review", json={}).json()["approval_status"], "review")

    def test_export_is_idempotent_and_hash_verifiable(self):
        rid = self.run_of(self.make()["id"])["id"]
        self.client.post(f"/api/runs/{rid}/submit-review", json={})
        self.client.post(f"/api/runs/{rid}/approve", json={"reviewer": "kc"})
        first = self.client.post(f"/api/runs/{rid}/export").json()
        second = self.client.post(f"/api/runs/{rid}/export").json()
        self.assertEqual(first, second)
        body = {k: v for k, v in first.items() if k != "manifest_sha256"}
        self.assertEqual(sha256(body), first["manifest_sha256"])
        self.assertEqual(self.client.get(f"/api/runs/{rid}/manifest").json(), first)
        self.assertFalse(first["import_policy"]["auto_import"])
        self.assertEqual(first["media_references"]["unresolved_count"], 0 if first["craft_id"] == "screenwriting" else first["media_references"]["unresolved_count"])

    def test_manifest_flags_unresolved_media(self):
        rid = self.run_of(self.make("editing")["id"])["id"]
        self.client.post(f"/api/runs/{rid}/submit-review", json={})
        self.client.post(f"/api/runs/{rid}/approve", json={"reviewer": "kc"})
        m = self.client.post(f"/api/runs/{rid}/export").json()
        self.assertEqual(m["media_references"]["unresolved_count"], 2)
        self.assertTrue(m["warnings"])

    def test_run_now_and_failed_runs_are_recorded(self):
        ok = self.make(run=True)
        self.assertEqual(ok["latest_run"]["run_status"], "completed")
        bad = pilot_input("screenwriting")
        bad["slugline"] = "UNKNOWN"  # passes the schema, rejected by the engine
        exp = self.make(payload=bad)
        run = self.run_of(exp["id"])
        self.assertEqual(run["run_status"], "failed")
        self.assertEqual(run["approval_status"], "none")
        self.assertIn("slugline", run["error"]["message"])
        self.assertEqual(self.client.post(f"/api/runs/{run['id']}/submit-review", json={}).status_code, 409)

    def test_invalid_inputs_fail_clearly_and_are_not_stored(self):
        r = self.client.post("/api/experiments", json={"craft_id": "editing", "name": "x", "input": {"shot_plan": {}}})
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.json()["detail"]["errors"])
        self.assertEqual(self.client.post("/api/experiments", json={"craft_id": "editing", "name": "  ", "input": pilot_input("editing")}).status_code, 422)
        self.assertEqual(self.client.post("/api/experiments", json={"craft_id": "costume", "name": "x"}).status_code, 409)
        self.assertEqual(self.client.post("/api/experiments", json={"craft_id": "nope", "name": "x"}).status_code, 404)
        self.assertEqual(self.client.post("/api/experiments", json={"craft_id": "editing", "name": "x", "input": [1]}).status_code, 422)
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 0)

    def test_unknown_and_malformed_ids_are_404(self):
        for path in ("/api/experiments/nope", "/api/runs/../../etc", "/api/runs/00000000-0000-4000-8000-000000000000",
                     "/api/experiments/00000000-0000-4000-8000-000000000000"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_list_filters_and_pagination(self):
        for i in range(3):
            self.make("screenwriting", f"s{i}")
        e = self.make("editing", "e")
        rid = self.run_of(e["id"])["id"]
        self.client.post(f"/api/runs/{rid}/submit-review", json={})
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 4)
        self.assertEqual(self.client.get("/api/experiments?craft_id=screenwriting").json()["total"], 3)
        self.assertEqual(self.client.get("/api/experiments?approval_status=review").json()["items"][0]["id"], e["id"])
        page = self.client.get("/api/experiments?limit=2&offset=3").json()
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(self.client.get("/api/experiments").json()["items"][0]["name"], "e")

    def test_metadata_update_does_not_touch_input(self):
        e = self.make()
        r = self.client.patch(f"/api/experiments/{e['id']}", json={"name": "renamed", "notes": "n"}).json()
        self.assertEqual((r["name"], r["notes"], r["input_hash"]), ("renamed", "n", e["input_hash"]))
        self.assertEqual(self.client.patch(f"/api/experiments/{e['id']}", json={"name": ""}).status_code, 422)


class ReproducibilityTests(ApiCase):
    def test_rerun_is_deterministic_and_reported(self):
        e = self.make("cinematography")
        r1, r2 = self.run_of(e["id"]), self.run_of(e["id"])
        self.assertNotEqual(r1["id"], r2["id"])
        self.assertEqual((r1["seq"], r2["seq"]), (1, 2))
        self.assertEqual(r1["output_sha256"], r2["output_sha256"])
        self.assertTrue(self.client.get(f"/api/experiments/{e['id']}").json()["reproducibility"]["reproducible"])
        v = self.client.post(f"/api/runs/{r1['id']}/verify").json()
        self.assertTrue(v["matches"])
        self.assertEqual(self.client.get(f"/api/experiments/{e['id']}").json()["runs"][0]["id"], r1["id"])

    def test_verify_detects_changed_engine_output(self):
        run = self.run_of(self.make("editing")["id"])
        real = execute

        def altered(craft, payload):
            out = real(craft, payload)
            out["artifact"]["total_frames"] += 1
            return out

        with mock.patch("app.experiments.execute", altered):
            self.assertFalse(self.client.post(f"/api/runs/{run['id']}/verify").json()["matches"])

    def test_compare_runs_across_variants(self):
        base = pilot_input("cinematography")
        e1 = self.make("cinematography", "A", base)
        variant = copy.deepcopy(base)
        variant["shots"][0]["lens_mm"] = 35
        variant["shots"].append({"shot_id": "SC-001-C", "duration_frames": 48, "lens_mm": 85, "media_asset_id": "asset-1"})
        e2 = self.duplicate = self.client.post(f"/api/experiments/{e1['id']}/duplicate", json={"name": "B", "input": variant}).json()
        self.assertEqual(e2["parent_experiment_id"], e1["id"])
        a, b = self.run_of(e1["id"])["id"], self.run_of(e2["id"])["id"]
        diff = self.client.get(f"/api/compare?run_a={a}&run_b={b}").json()
        self.assertFalse(diff["identical_output"])
        changes = {(c["path"], c["change"]) for c in diff["artifact_changes"]}
        self.assertIn(("artifact.shots[SC-001-A].lens_mm", "changed"), changes)
        self.assertIn(("artifact.shots[SC-001-C]", "added"), changes)
        self.assertIn(("input.shots[SC-001-C]", "added"), {(c["path"], c["change"]) for c in diff["input_changes"]})
        same = self.client.get(f"/api/compare?run_a={a}&run_b={a}").json()
        self.assertTrue(same["identical_output"] and not same["artifact_changes"])

    def test_compare_rejects_cross_craft_and_failed_runs(self):
        a = self.run_of(self.make("screenwriting")["id"])["id"]
        b = self.run_of(self.make("editing")["id"])["id"]
        self.assertEqual(self.client.get(f"/api/compare?run_a={a}&run_b={b}").status_code, 409)
        bad = pilot_input("screenwriting"); bad["slugline"] = "UNKNOWN"
        f = self.run_of(self.make(payload=bad)["id"])["id"]
        self.assertEqual(self.client.get(f"/api/compare?run_a={a}&run_b={f}").status_code, 409)
        self.assertEqual(self.client.get("/api/compare?run_a=x&run_b=y").status_code, 404)


class PersistenceTests(ApiCase):
    def test_history_survives_restart_and_is_append_only(self):
        e = self.make()
        rid = self.run_of(e["id"])["id"]
        reopened = TestClient(create_app(self.tmp.name, log_to_file=False))
        self.assertEqual(reopened.get(f"/api/experiments/{e['id']}").json()["runs"][0]["id"], rid)
        conn = sqlite3.connect(self.db_path)
        for sql in ("DELETE FROM runs", "DELETE FROM experiments", "DELETE FROM run_events",
                    "UPDATE run_events SET event_type='x'", "UPDATE runs SET output_json='{}'",
                    "UPDATE runs SET input_hash='x'", "UPDATE experiments SET input_json='{}'"):
            with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                conn.execute(sql)
        conn.close()

    def test_system_and_health(self):
        self.make()
        s = self.client.get("/api/system").json()
        self.assertEqual((s["db_integrity"], s["counts"]["experiments"], s["ai_calls"]), ("ok", 1, False))
        h = self.client.get("/health").json()
        self.assertEqual((h["status"], h["standalone"], h["module_count"], h["database"]), ("ok", True, 23, "ok"))

    def test_oversized_body_rejected(self):
        r = self.client.post("/api/experiments", content=b"{" + b" " * (config.MAX_BODY_BYTES + 10) + b"}",
                             headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 413)

    def test_newer_database_is_refused(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA user_version = 99")
        conn.close()
        with self.assertRaises(RuntimeError):
            create_app(self.tmp.name, log_to_file=False)


class LegacyApiTests(ApiCase):
    def test_original_endpoints_unchanged(self):
        self.assertEqual(len(self.client.get("/api/crafts").json()), 23)
        for craft in PILOTS:
            r = self.client.post(f"/api/crafts/{craft}/run", json=pilot_input(craft))
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json()["approval_status"], r.json()["provenance"]["ai_used"]), ("draft", False))
        self.assertEqual(self.client.post("/api/crafts/costume/run", json={}).status_code, 409)
        self.assertEqual(self.client.get("/api/crafts/nope").status_code, 404)
        self.assertEqual(self.client.get("/api/crafts/screenwriting/fixture").status_code, 200)

    def test_malformed_payload_is_422_not_404_or_500(self):
        self.assertEqual(self.client.post("/api/crafts/editing/run", json={"shot_plan": {"schema": "filmcraft.shot_plan.v1"}}).status_code, 422)
        self.assertEqual(self.client.post("/api/crafts/screenwriting/run", json={**get_fixture("screenwriting"), "characters": ["x"], "dialogue": [{"speaker_id": "a"}]}).status_code, 422)

    def test_stateless_run_saves_nothing(self):
        self.client.post("/api/crafts/screenwriting/run", json=get_fixture("screenwriting"))
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 0)


class ConfigTests(unittest.TestCase):
    def env(self, **kw):
        return mock.patch.dict(os.environ, kw, clear=False)

    def test_defaults_are_8099_on_loopback(self):
        with mock.patch.dict(os.environ):
            for k in ("CRAFTBOX_PORT", "CRAFTBOX_HOST", "CRAFTBOX_ALLOW_REMOTE"):
                os.environ.pop(k, None)
            self.assertEqual((config.host(), config.port()), ("127.0.0.1", 8099))

    def test_port_override_and_validation(self):
        with self.env(CRAFTBOX_PORT="8123"):
            self.assertEqual(config.port(), 8123)
        for bad in ("abc", "80", "70000", "8000"):
            with self.env(CRAFTBOX_PORT=bad), self.assertRaises(config.ConfigError, msg=bad):
                config.port()

    def test_network_exposure_refused(self):
        with self.env(CRAFTBOX_HOST="0.0.0.0"):
            os.environ.pop("CRAFTBOX_ALLOW_REMOTE", None)
            with self.assertRaises(config.ConfigError):
                config.host()

    def test_port_in_use_detected_without_touching_owner(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            busy = server.getsockname()[1]
            self.assertTrue(port_in_use("127.0.0.1", busy))
        self.assertFalse(port_in_use("127.0.0.1", busy))

    def test_launcher_reports_clear_error_when_port_busy(self):
        from app import run as launcher
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with self.env(CRAFTBOX_PORT=str(server.getsockname()[1])), mock.patch("sys.stderr") as err:
                self.assertEqual(launcher.main([]), 3)
            self.assertIn("already in use", "".join(c.args[0] for c in err.write.call_args_list))


if __name__ == "__main__":
    unittest.main()
