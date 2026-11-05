"""CB1 API tests: the Scene Lab workflow on top of CB0's experiment lifecycle."""
import copy
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("CRAFTBOX_LOG_LEVEL", "ERROR")

from fastapi.testclient import TestClient  # noqa: E402

from app import ai_adapters  # noqa: E402
from app.core import get_fixture  # noqa: E402
from app.server import create_app  # noqa: E402
from app.validation import validate  # noqa: E402


def authored():
    return copy.deepcopy(get_fixture("screenwriting", "screenplay"))


class LabCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(self.tmp.name, log_to_file=False))
        self.addCleanup(self.client.close)
        self.db = os.path.join(self.tmp.name, "craftbox.db")

    def post(self, path, body=None, status=None, **kw):
        r = self.client.post(path, json=body, **kw)
        if status:
            self.assertEqual(r.status_code, status, r.text)
        return r

    def save_screenplay(self, doc=None, name="Screenplay", parent=None):
        r = self.post("/api/experiments", {"craft_id": "screenwriting", "name": name, "input": doc or authored(), "run_now": True,
                                           "parent_experiment_id": parent}, 201)
        body = r.json()
        self.assertEqual(body["latest_run"]["run_status"], "completed", body["latest_run"].get("error"))
        return body["id"], body["latest_run"]["id"]

    def draft(self, sp_exp, approach="intimate", name=None, scene_id="SC-001"):
        r = self.post("/api/lab/direction/draft", {"screenplay_experiment_id": sp_exp, "scene_id": scene_id, "name": name or f"Plan {approach}",
                                                   "approach": {"preset": approach}}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]

    def approve(self, run_id, reviewer="Tester"):
        self.post(f"/api/runs/{run_id}/submit-review", {}, 200)
        self.post(f"/api/runs/{run_id}/approve", {"reviewer": reviewer, "note": "ok"}, 200)

    def save_plan(self, base_exp, plan, name="Edited plan"):
        r = self.post("/api/lab/direction/save", {"base_experiment_id": base_exp, "plan": plan, "name": name}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]


class ScreenplayWorkflowTests(LabCase):
    def test_screenplay_save_runs_through_the_cb0_lifecycle(self):
        exp, run = self.save_screenplay()
        r = self.client.get(f"/api/runs/{run}").json()
        self.assertEqual((r["artifact_type"], r["output_schema"], r["input_schema"]), ("screenplay", "filmcraft.screenplay.v1", "filmcraft.screenplay.v1"))
        self.assertEqual(r["approval_status"], "draft")
        self.approve(run)
        self.assertEqual(self.client.get(f"/api/runs/{run}").json()["approval_status"], "approved")
        m = self.post(f"/api/runs/{run}/export", None, 200).json()           # the CB0 manifest still works for the new artifact type
        self.assertEqual(m["artifact_schema"], "filmcraft.screenplay.v1")
        self.assertEqual(validate(m, "filmcraft.export_manifest.v1"), [])

    def test_invalid_screenplays_are_rejected_before_saving(self):
        bad = authored(); bad["scenes"][0]["heading"]["int_ext"] = "INSIDE"
        r = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "bad", "input": bad})
        self.assertEqual(r.status_code, 422); self.assertTrue(r.json()["detail"]["errors"])
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 0)
        broken = authored(); broken["scenes"][0]["elements"][2]["character_id"] = "C-404"     # passes the schema, fails integrity
        exp = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "integrity", "input": broken, "run_now": True}, 201).json()
        self.assertEqual(exp["latest_run"]["run_status"], "failed")
        self.assertIn("known character", exp["latest_run"]["error"]["message"])

    def test_version_history_and_comparison_use_experiment_infrastructure(self):
        e1, r1 = self.save_screenplay(name="Rev 1")
        doc = authored(); doc["revision"] = {"number": 2, "note": "sharper line"}
        doc["scenes"][0]["elements"][11]["text"] = "It leans toward the door. It always has."
        e2, r2 = self.save_screenplay(doc, "Rev 2", parent=e1)
        self.assertEqual(self.client.get(f"/api/experiments/{e2}").json()["parent_experiment_id"], e1)
        d = self.client.get(f"/api/compare?run_a={r1}&run_b={r2}").json()
        paths = {c["path"] for c in d["artifact_changes"]}
        self.assertIn("artifact.scenes[SC-001].elements[SC-001-E12].text", paths)
        self.assertIn("artifact.revision.number", paths)
        ov = self.client.get("/api/lab/projects/closing-hour").json()
        self.assertEqual([v["revision"] for v in ov["screenplay_versions"]], [1, 2])
        self.assertEqual(ov["latest_screenplay"]["experiment_id"], e2)
        self.assertNotEqual(ov["screenplay_versions"][0]["scene_hashes"]["SC-001"], ov["screenplay_versions"][1]["scene_hashes"]["SC-001"])
        self.assertEqual(self.client.get("/api/lab/projects").json()[0]["versions"], 2)
        self.assertEqual(self.client.get("/api/lab/projects/nope").status_code, 404)

    def test_idea_import_export_and_analyze_endpoints(self):
        sk = self.post("/api/lab/idea", {"title": "Night Train", "characters": [{"name": "Isha"}, {"name": "Kabir"}]}, 200).json()
        self.assertEqual(sk["project"]["id"], "night-train")
        self.assertEqual(self.post("/api/lab/idea", {"title": ""}).status_code, 422)
        a = self.post("/api/lab/analyze/screenplay", {"screenplay": authored()}, 200).json()
        self.assertEqual(a["artifact"]["analysis"]["totals"]["estimated_seconds"], 84.0)
        bad = authored(); bad["scenes"][0]["beats"][0]["element_ids"] = ["NOPE"]
        self.assertEqual(self.post("/api/lab/analyze/screenplay", {"screenplay": bad}).status_code, 422)
        text = self.post("/api/lab/export/fountain", {"screenplay": authored()}, 200).text
        self.assertIn("#SC-001#", text)
        imp = self.post("/api/lab/import/fountain", {"text": text}, 200).json()
        self.assertTrue(imp["check"]["ok"]); self.assertEqual(imp["screenplay"]["scenes"][0]["id"], "SC-001")
        self.assertEqual(self.post("/api/lab/import/fountain", {"text": "no headings here"}).status_code, 422)

    def test_reordering_scenes_keeps_ids_and_does_not_disturb_other_scenes(self):
        doc = authored()
        two = json.loads(json.dumps(doc["scenes"][0]).replace("SC-001", "SC-002"))
        two["heading"]["location"] = "Railway platform"
        doc["scenes"].append(two)
        doc["sequences"][0]["scene_ids"] = ["SC-001", "SC-002"]
        e1, r1 = self.save_screenplay(doc, "two scenes")
        _, _, plan1 = self.draft(e1)
        swapped = copy.deepcopy(doc); swapped["revision"] = {"number": 2, "note": "reordered"}
        swapped["scenes"].reverse(); swapped["sequences"][0]["scene_ids"].reverse()
        e2, r2 = self.save_screenplay(swapped, "reordered", parent=e1)
        a1, a2 = (self.client.get(f"/api/runs/{r}").json()["envelope"]["artifact"]["analysis"]["scenes"] for r in (r1, r2))
        self.assertEqual({s["scene_id"]: s["scene_hash"] for s in a1}, {s["scene_id"]: s["scene_hash"] for s in a2})   # order is not content
        self.assertEqual([s["scene_id"] for s in a2], ["SC-002", "SC-001"])
        plan_exp = self.client.get("/api/lab/projects/closing-hour").json()["plans"][0]
        self.assertFalse(plan_exp["stale"])


class DirectionWorkflowTests(LabCase):
    def setUp(self):
        super().setUp()
        self.sp_exp, self.sp_run = self.save_screenplay()

    def test_draft_two_approaches_and_compare_them(self):
        ea, ra, pa = self.draft(self.sp_exp, "intimate", "Plan A")
        eb, rb, pb = self.draft(self.sp_exp, "observational", "Plan B")
        self.assertEqual(pa["source"]["ref"]["experiment_id"], self.sp_exp)
        self.assertEqual(validate(pa, "filmcraft.direction_plan.v1"), [])
        cmp_ = self.client.get(f"/api/lab/compare-plans?run_a={ra}&run_b={rb}").json()
        rows = {r["metric"]: r for r in cmp_["metrics"]}
        self.assertGreater(rows["Shots"]["a"], rows["Shots"]["b"])
        self.assertTrue(rows["Average shot (s)"]["differs"]); self.assertEqual(len(cmp_["beats"]), 7)
        self.assertNotEqual(cmp_["interpretation"]["a"], cmp_["interpretation"]["b"])
        d = self.client.get(f"/api/compare?run_a={ra}&run_b={rb}").json()    # CB0 diff also works on plans
        self.assertFalse(d["identical_output"])
        ov = self.client.get("/api/lab/projects/closing-hour").json()
        self.assertEqual({p["approach_id"] for p in ov["plans"]}, {"intimate", "observational"})
        self.assertEqual(self.client.get(f"/api/lab/compare-plans?run_a={ra}&run_b={self.sp_run}").status_code, 409)

    def test_draft_needs_a_completed_screenplay_version(self):
        bad = authored(); bad["scenes"][0]["elements"][2]["character_id"] = "C-404"
        e, _ = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "failed", "input": bad, "run_now": True}, 201).json()["id"], None
        r = self.post("/api/lab/direction/draft", {"screenplay_experiment_id": e, "scene_id": "SC-001", "name": "x", "approach": {"preset": "intimate"}})
        self.assertEqual(r.status_code, 409)
        r = self.post("/api/lab/direction/draft", {"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-404", "name": "x", "approach": {"preset": "intimate"}})
        self.assertEqual(r.json().get("run", {}).get("run_status"), "failed")

    def test_editing_a_plan_creates_a_new_version_and_never_touches_the_old_one(self):
        ea, ra, pa = self.draft(self.sp_exp)
        before = self.client.get(f"/api/runs/{ra}").json()["envelope"]
        edited = copy.deepcopy(pa)
        edited["shots"][1]["status"] = "rejected"; edited["shots"][1]["review_note"] = "too busy"
        edited["shots"][3]["status"] = "approved"
        edited["shots"][2], edited["shots"][4] = edited["shots"][4], edited["shots"][2]       # reorder
        edited["note"] = "tried a different order"
        eb, rb, pb = self.save_plan(ea, edited, "Plan A v2")
        self.assertEqual(self.client.get(f"/api/experiments/{eb}").json()["parent_experiment_id"], ea)
        self.assertEqual(self.client.get(f"/api/runs/{ra}").json()["envelope"], before)        # original untouched
        self.assertEqual(pb["analysis"]["status_summary"]["rejected"], 1)
        self.assertEqual([s["shot_id"] for s in pb["shots"]][2], pa["shots"][4]["shot_id"])
        self.assertNotIn(pa["shots"][1]["shot_id"], [t["shot_id"] for t in pb["analysis"]["timeline"]])
        d = self.client.get(f"/api/compare?run_a={ra}&run_b={rb}").json()
        self.assertTrue(any(c["path"].endswith(".status") for c in d["artifact_changes"]))

    def test_analyze_endpoint_reports_planted_continuity_errors_without_saving(self):
        ea, ra, pa = self.draft(self.sp_exp)
        broken = copy.deepcopy(pa); broken["shots"][4]["camera_side"] = "B"
        out = self.post("/api/lab/direction/analyze", {"base_experiment_id": ea, "plan": broken}, 200).json()
        self.assertTrue([i for i in out["analysis"]["issues"] if i["rule"] == "axis" and i["severity"] == "error"])
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 2)             # nothing new was saved
        bad = copy.deepcopy(pa); bad["shots"][0]["purpose"] = "because"
        self.assertEqual(self.post("/api/lab/direction/analyze", {"base_experiment_id": ea, "plan": bad}).status_code, 422)
        dup = copy.deepcopy(pa); dup["shots"].append(copy.deepcopy(dup["shots"][0]))
        self.assertEqual(self.post("/api/lab/direction/analyze", {"base_experiment_id": ea, "plan": dup}).status_code, 422)

    def test_manifests_require_approval_and_reviewed_shots_and_are_idempotent(self):
        ea, ra, pa = self.draft(self.sp_exp)
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/scene-manifest").status_code, 409)           # not approved
        for kind in ("blocking", "shot-list", "shot-list-csv", "shot-plan"):                              # working exports are always available
            self.assertEqual(self.post(f"/api/runs/{ra}/exports/{kind}", None, 200).status_code, 200, kind)
        self.approve(ra)
        r = self.post(f"/api/runs/{ra}/exports/shot-manifest")
        self.assertEqual(r.status_code, 409); self.assertIn("allow_pending", r.json()["detail"])
        m = self.post(f"/api/runs/{ra}/exports/scene-manifest", None, 200).json()
        self.assertEqual(validate(m, "filmcraft.scene_manifest.v1"), [])
        self.assertEqual(m["approval"]["reviewer"], "Tester")
        again = self.post(f"/api/runs/{ra}/exports/scene-manifest", None, 200)
        self.assertEqual(again.json(), m); self.assertEqual(again.headers["X-Craftbox-Existing"], "true")
        r = self.post(f"/api/runs/{ra}/exports/shot-manifest?override=allow_pending", None, 200)
        sm = r.json()
        self.assertEqual(validate(sm, "filmcraft.shot_manifest.v1"), [])
        self.assertEqual(sm["overrides"], ["allow_pending"]); self.assertEqual(sm["totals"]["shots"], len(pa["shots"]))
        events = [e["event_type"] for e in self.client.get(f"/api/runs/{ra}/events").json()]
        self.assertIn("export.scene-manifest", events); self.assertIn("export.shot-manifest", events)
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/shot-manifest?override=bogus").status_code, 422)
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/nonsense").status_code, 422)

    def test_fully_approved_plan_exports_without_overrides(self):
        ea, ra, pa = self.draft(self.sp_exp)
        done = copy.deepcopy(pa)
        for s in done["shots"]:
            s["status"] = "approved"
        done["shots"][5]["status"] = "rejected"
        eb, rb, pb = self.save_plan(ea, done)
        self.approve(rb)
        sm = self.post(f"/api/runs/{rb}/exports/shot-manifest", None, 200).json()
        self.assertEqual(sm["overrides"], []); self.assertEqual(sm["excluded"]["rejected"], [done["shots"][5]["shot_id"]])
        self.assertEqual(sm["totals"]["shots"], len(done["shots"]) - 1)
        self.assertEqual(sm["source"]["source_status"], "current")

    def test_screenplay_run_exports_json_and_script(self):
        j = self.post(f"/api/runs/{self.sp_run}/exports/screenplay-json", None, 200).json()
        self.assertEqual(j["schema"], "filmcraft.screenplay.v1")
        t = self.post(f"/api/runs/{self.sp_run}/exports/script", None, 200)
        self.assertIn("The Closing Hour", t.text); self.assertIn("attachment", t.headers["content-disposition"])
        self.assertEqual(self.post(f"/api/runs/{self.sp_run}/exports/blocking").status_code, 422)

    # ---- the key integrity scenario -------------------------------------------------------------------
    def test_script_revision_marks_dependent_plans_stale_without_overwriting_approved_work(self):
        ea, ra, pa = self.draft(self.sp_exp)
        done = copy.deepcopy(pa)
        for s in done["shots"]:
            s["status"] = "approved"
        eb, rb, pb = self.save_plan(ea, done, "Approved plan")
        self.approve(rb)
        self.assertFalse(self.client.get(f"/api/lab/plans/{eb}/impact").json()["stale"])
        # the writer revises one line of dialogue (beat B5)
        doc = authored(); doc["revision"] = {"number": 2, "note": "softer line"}
        doc["scenes"][0]["elements"][16]["text"] = "The day after you left. I waited on the platform until the lights went out."
        e2, r2 = self.save_screenplay(doc, "Rev 2", parent=self.sp_exp)
        imp = self.client.get(f"/api/lab/plans/{eb}/impact").json()
        self.assertTrue(imp["stale"]); self.assertEqual(imp["changed_elements"], ["SC-001-E17"])
        self.assertEqual(imp["against"]["experiment_id"], e2)
        b5 = {s["shot_id"] for s in pb["shots"] if s["beat_id"] == "SC-001-B5"}
        self.assertEqual(set(imp["affected_shots"]), b5)
        ov = self.client.get("/api/lab/projects/closing-hour").json()
        entry = next(p for p in ov["plans"] if p["experiment_id"] == eb)
        self.assertTrue(entry["stale"]); self.assertEqual(entry["affected_shots"], len(b5))
        # approved work is intact: same run, still approved, identical artifact
        run = self.client.get(f"/api/runs/{rb}").json()
        self.assertEqual(run["approval_status"], "approved"); self.assertEqual(run["envelope"]["artifact"]["analysis"]["status_summary"]["approved"], len(pb["shots"]))
        # exporting a stale approved plan is advice, with an explicit recorded override
        r = self.post(f"/api/runs/{rb}/exports/scene-manifest")
        self.assertEqual(r.status_code, 409); self.assertIn("acknowledge_stale", r.json()["detail"])
        ok = self.post(f"/api/runs/{rb}/exports/scene-manifest?override=acknowledge_stale", None, 200).json()
        self.assertEqual(ok["overrides"], ["acknowledge_stale"]); self.assertEqual(ok["source"]["source_status"], "stale_acknowledged")
        # rebase: a NEW plan version; only dependent shots return to review
        rb_out = self.post(f"/api/lab/plans/{eb}/rebase", {}, 201).json()
        new_plan = rb_out["run"]["envelope"]["artifact"]
        self.assertNotEqual(rb_out["experiment"]["id"], eb)
        self.assertEqual(rb_out["experiment"]["parent_experiment_id"], eb)
        status = {s["shot_id"]: s["status"] for s in new_plan["shots"]}
        for sid, st in status.items():
            self.assertEqual(st, "needs_review" if sid in b5 else "approved", sid)
        self.assertEqual(new_plan["source"]["screenplay_revision"], 2)
        self.assertEqual(new_plan["source"]["ref"]["experiment_id"], e2)
        self.assertEqual(self.client.get(f"/api/runs/{rb}").json()["approval_status"], "approved")     # original still approved
        self.assertEqual(self.post(f"/api/lab/plans/{rb_out['experiment']['id']}/rebase", {}).status_code, 409)   # already current
        self.assertFalse(self.client.get(f"/api/lab/plans/{rb_out['experiment']['id']}/impact").json()["stale"])
        # the new plan cannot be exported until its shots are decided again
        self.approve(rb_out["run"]["id"])
        r = self.post(f"/api/runs/{rb_out['run']['id']}/exports/shot-manifest")
        self.assertEqual(r.status_code, 409)

    def test_drafts_and_plans_survive_restart(self):
        ea, ra, pa = self.draft(self.sp_exp)
        reopened = TestClient(create_app(self.tmp.name, log_to_file=False))
        self.assertEqual(reopened.get(f"/api/lab/projects/closing-hour").json()["plans"][0]["experiment_id"], ea)


class SafetyAndCompatibilityTests(LabCase):
    def test_derived_exports_are_immutable(self):
        sp_exp, _ = self.save_screenplay()
        ea, ra, _ = self.draft(sp_exp)
        self.approve(ra)
        self.post(f"/api/runs/{ra}/exports/scene-manifest", None, 200)
        conn = sqlite3.connect(self.db)
        for sql in ("DELETE FROM derived_exports", "UPDATE derived_exports SET manifest_json='{}'"):
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(sql)
        conn.close()

    def test_a_cb0_database_upgrades_in_place_and_keeps_its_history(self):
        from app import db as dbmod
        path = os.path.join(self.tmp.name, "old.db")
        conn = sqlite3.connect(path, isolation_level=None)
        for stmt in dbmod._split(dbmod.MIGRATIONS[0]):        # exactly what a CB0 (schema v1) install contains
            conn.execute(stmt)
        conn.execute("PRAGMA user_version = 1")
        conn.execute("INSERT INTO experiments (id, craft_id, name, notes, input_json, input_hash, input_schema, created_at, updated_at) VALUES ('11111111-1111-4111-8111-111111111111','screenwriting','old','','{}','h',NULL,'t','t')")
        conn.close()
        upgraded = dbmod.Database(path)
        self.assertEqual(upgraded.version(), len(dbmod.MIGRATIONS))
        with upgraded.read() as c:
            self.assertEqual(c.execute("SELECT name FROM experiments").fetchone()[0], "old")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM derived_exports").fetchone()[0], 0)

    def test_ai_adapters_are_disabled_and_make_no_network_calls(self):
        st = self.client.get("/api/ai/adapters").json()
        self.assertFalse(st["network_calls"])
        remote = {a["name"]: a for a in st["adapters"] if a["network_calls"]}
        self.assertEqual(set(remote), {"chatgpt", "gemini", "venice"})
        self.assertTrue(all(not a["enabled"] for a in remote.values()))
        for name in remote:
            r = self.post(f"/api/ai/adapters/{name}/suggest", {"task": "direction.suggest_shots", "payload": {}})
            self.assertEqual(r.status_code, 409)
            self.assertIn("no network call was made", r.json()["detail"])
        with mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network call attempted")),                 mock.patch.object(socket, "create_connection", side_effect=AssertionError("network call attempted")):
            for name in remote:   # the adapters themselves must not even try to open a socket
                with self.assertRaises(ai_adapters.AdapterDisabled):
                    ai_adapters.get(name).suggest("direction.suggest_shots", {})
        self.assertEqual(self.post("/api/ai/adapters/unknown/suggest", {}).status_code, 404)
        with self.assertRaises(ai_adapters.AdapterDisabled):
            ai_adapters.get("chatgpt").suggest("x", {})

    def test_local_rules_adapter_returns_an_unapplied_proposal(self):
        sp = self.client.get("/api/crafts/direction/fixture").json()["screenplay"]
        out = self.post("/api/ai/adapters/local-rules/suggest", {"task": "direction.draft_plan", "payload": {"screenplay": sp, "scene_id": "SC-001", "approach": {"preset": "observational"}}}, 200).json()
        self.assertFalse(out["applied"]); self.assertEqual(out["proposal"]["schema"], "filmcraft.direction_plan.v1")
        self.assertEqual(self.client.get("/api/experiments").json()["total"], 0)

    def test_cb0_behaviour_is_preserved(self):
        self.assertEqual(len(self.client.get("/api/crafts").json()), 23)
        self.assertEqual(self.client.get("/health").json()["module_count"], 23)
        self.assertEqual(self.post("/api/crafts/costume/run", {}).status_code, 409)
        r = self.post("/api/crafts/screenwriting/run", get_fixture("screenwriting"), 200).json()
        self.assertEqual(r["artifact"]["schema"], "filmcraft.scene.v1")          # the original scene-card mode
        sc = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "card", "input": get_fixture("screenwriting"), "run_now": True}, 201).json()
        self.assertEqual(sc["latest_run"]["output_schema"], "filmcraft.scene.v1")
        self.assertEqual(self.client.get("/api/crafts/screenwriting/fixture").json()["slugline"], "EXT. RAILWAY PLATFORM - DAWN")
        self.assertEqual(self.client.get("/api/crafts/screenwriting/fixture?name=screenplay").json()["schema"], "filmcraft.screenplay.v1")
        self.assertEqual(self.client.get("/api/crafts/direction/fixture?name=../x").status_code, 404)
        self.assertEqual(self.client.get("/api/crafts/direction").json()["status"], "pilot")
        self.assertEqual(sum(1 for c in self.client.get("/api/crafts").json() if c["status"] == "pilot"), 6)   # screenwriting, direction, art_direction, cinematography, editing


if __name__ == "__main__":
    unittest.main()
