"""CB2B API tests: the Lighting Lab on top of CB0's lifecycle, CB1's plans and CB2A's treatments."""
import copy
import os
import tempfile
import unittest

os.environ.setdefault("CRAFTBOX_LOG_LEVEL", "ERROR")

from fastapi.testclient import TestClient  # noqa: E402

from app.core import get_fixture  # noqa: E402
from app.server import create_app  # noqa: E402
from app.validation import validate  # noqa: E402


def authored():
    return copy.deepcopy(get_fixture("screenwriting", "screenplay"))


def revised():
    doc = authored()
    doc["revision"] = {"number": 2, "note": "ticket line"}
    doc["scenes"][0]["elements"][14]["text"] = "She stops. He nods at the book. She opens it. Inside: a ticket to her city, two years old, never used."
    return doc


class LightCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(self.tmp.name, log_to_file=False))
        self.addCleanup(self.client.close)
        r = self.client.post("/api/experiments", json={"craft_id": "screenwriting", "name": "rev 1", "input": authored(), "run_now": True}).json()
        self.sp_exp = r["id"]
        p = self.client.post("/api/lab/direction/draft", json={"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-001", "name": "plan", "approach": {"preset": "intimate"}}).json()
        self.plan_exp = p["experiment"]["id"]
        self.art_a = self.art("warm_nostalgia", "Warm nostalgia")
        self.art_b = self.art("emotional_distance", "Emotional distance")

    def post(self, path, body=None, status=None):
        r = self.client.post(path, json=body)
        if status:
            self.assertEqual(r.status_code, status, r.text)
        return r

    def art(self, preset, name):
        r = self.post("/api/art/draft", {"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-001", "name": name, "preset": preset, "plan_experiment_id": self.plan_exp}, 201).json()
        return {"exp": r["experiment"]["id"], "run": r["run"]["id"]}

    def draft(self, art, preset, name=None, **kw):
        r = self.post("/api/light/draft", {"screenplay_experiment_id": self.sp_exp, "art_experiment_id": art["exp"], "name": name or preset, "preset": preset, "plan_experiment_id": self.plan_exp, **kw}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]

    def save(self, base, doc, name="edit", note=""):
        d = copy.deepcopy(doc); d.pop("analysis", None)
        r = self.post("/api/light/save", {"base_experiment_id": base, "light": d, "name": name, "note": note}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]

    def approve(self, run, who="Gaffer"):
        self.post(f"/api/runs/{run}/submit-review", {}, 200)
        self.post(f"/api/runs/{run}/approve", {"reviewer": who, "note": "good"}, 200)

    def status(self, run):
        return self.client.get(f"/api/runs/{run}").json()["approval_status"]


class PlanLifecycleTests(LightCase):
    def test_two_plans_for_the_two_treatments_are_independent_through_every_stage(self):
        ea, ra, a = self.draft(self.art_a, "warm_naturalistic", "Warm, naturalistic")
        eb, rb, b = self.draft(self.art_b, "cool_dramatic", "Cool, dramatic")
        self.assertEqual(validate(a, "filmcraft.lighting_plan.v1"), [])
        self.assertEqual((a["source"]["art"]["treatment_name"], b["source"]["art"]["treatment_name"]), ("Warm nostalgia", "Emotional distance"))
        self.approve(ra)
        self.assertEqual((self.status(ra), self.status(rb)), ("approved", "draft"))
        edited = copy.deepcopy(b)
        next(l for l in edited["lights"] if l["id"] == "L-KEY")["color_temp_k"] = 4800
        eb2, rb2, b2 = self.save(eb, edited, "Cool, dramatic v2", "a little less blue")
        self.assertEqual(self.client.get(f"/api/experiments/{eb2}").json()["parent_experiment_id"], eb)
        before = self.client.get(f"/api/runs/{rb}").json()["envelope"]["artifact"]
        self.assertEqual(next(l for l in before["lights"] if l["id"] == "L-KEY")["color_temp_k"], 5200)      # the earlier version is unchanged
        self.assertEqual(next(l for l in b2["lights"] if l["id"] == "L-KEY")["color_temp_k"], 4800)
        self.assertEqual(self.status(ra), "approved")
        ov = self.client.get("/api/light/projects/closing-hour").json()
        self.assertEqual({p["plan_name"] for p in ov["plans"]}, {"Warm, naturalistic", "Cool, dramatic"})
        self.assertEqual(len(ov["plans"]), 3)
        self.assertTrue(all(p["stale"] is False for p in ov["plans"]))

    def test_comparison_shows_technical_settings_and_the_stated_effect_of_each_plan(self):
        _, ra, _ = self.draft(self.art_a, "warm_naturalistic"); _, rb, _ = self.draft(self.art_b, "cool_dramatic")
        c = self.client.get(f"/api/light/compare?run_a={ra}&run_b={rb}").json()
        by = {m["key"]: m for m in c["metrics"]}
        self.assertLess(by["mean_kelvin"]["a"], by["mean_kelvin"]["b"]); self.assertGreater(by["key_softness"]["a"], by["key_softness"]["b"])
        self.assertTrue(by["key_fill_ratio"]["differs"])
        self.assertTrue(c["readings"]["a"] and c["readings"]["b"] and all(r["because"] for r in c["readings"]["a"]))
        self.assertTrue(c["docs"]["a"]["lights"] and c["docs"]["a"]["art"]["layout"]["objects"])
        self.assertNotEqual(c["a"]["art_treatment"], c["b"]["art_treatment"])
        self.assertIn("not measured light", c["model_note"])
        self.assertEqual(self.client.get(f"/api/light/compare?run_a={ra}&run_b={ra}").status_code, 200)
        self.assertEqual(self.client.get("/api/light/compare?run_a=x&run_b=y").status_code, 404)

    def test_analyze_is_stateless_and_validation_errors_are_clear(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        d = copy.deepcopy(a); d["conditions"]["time_of_day"] = "day"
        out = self.post("/api/light/analyze", {"base_experiment_id": e, "light": d}, 200).json()
        self.assertTrue([i for i in out["analysis"]["issues"] if i["rule"] == "time_of_day_mismatch"])
        self.assertEqual(len(self.client.get("/api/light/projects/closing-hour").json()["plans"]), 1)               # nothing was saved
        d["lights"][0]["intensity"] = 5
        bad = self.post("/api/light/analyze", {"base_experiment_id": e, "light": d})
        self.assertEqual(bad.status_code, 422); self.assertTrue(bad.json()["detail"]["errors"] if isinstance(bad.json()["detail"], dict) else bad.json()["detail"])
        d["lights"][0]["intensity"] = 0.5; d["adjustments"][0]["shot_id"] = "SC-001-S99"
        self.assertEqual(self.post("/api/light/analyze", {"base_experiment_id": e, "light": d}).status_code, 422)

    def test_single_craft_run_of_lighting_works_through_cb0(self):
        r = self.post("/api/crafts/lighting/run", get_fixture("lighting"), 200).json()
        self.assertEqual(r["artifact_type"], "lighting_plan"); self.assertEqual(r["provenance"]["ai_used"], False)
        self.assertEqual(validate(r["artifact"], "filmcraft.lighting_plan.v1"), [])


class UpstreamChangeTests(LightCase):
    def revise_script(self):
        r = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "rev 2", "input": revised(), "run_now": True, "parent_experiment_id": self.sp_exp}, 201).json()
        self.assertEqual(r["latest_run"]["run_status"], "completed")
        return r["id"]

    def test_script_revision_flags_the_plan_without_touching_approved_work_and_rebase_preserves_approvals(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        d = copy.deepcopy(a)
        for l in d["lights"]:
            l["status"] = "approved"
        for adj in d["adjustments"]:
            adj["status"] = "approved"
        e2, r2, a2 = self.save(e, d, "all approved")
        self.approve(r2)
        self.assertFalse(self.client.get(f"/api/light/plans/{e2}/impact").json()["stale"])
        self.revise_script()
        imp = self.client.get(f"/api/light/plans/{e2}/impact").json()
        self.assertTrue(imp["stale"]); self.assertTrue(imp["changed_beats"])
        self.assertEqual(self.status(r2), "approved")                                                                 # the approved version is not touched
        self.assertTrue(self.client.get("/api/light/projects/closing-hour").json()["plans"][-1]["stale"])
        rb = self.post(f"/api/light/plans/{e2}/rebase", {}, 201).json()
        new = rb["run"]["envelope"]["artifact"]
        flagged = [x["id"] for x in new["adjustments"] if x["status"] == "needs_review"]
        self.assertEqual(sorted(flagged), sorted(imp["affected_adjustments"]))
        self.assertTrue(all(x["previous_status"] == "approved" for x in new["adjustments"] if x["status"] == "needs_review"))
        self.assertTrue([l for l in new["lights"] if l["status"] == "approved"])                                      # unaffected items keep their approval
        self.assertEqual(self.status(r2), "approved"); self.assertEqual(self.client.get(f"/api/experiments/{rb['experiment']['id']}").json()["parent_experiment_id"], e2)
        self.assertEqual(self.post(f"/api/light/plans/{rb['experiment']['id']}/rebase", {}).status_code, 409)         # already current

    def test_a_blocking_change_in_the_direction_plan_is_noticed_through_the_lineage(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        plan = self.client.get(f"/api/experiments/{self.plan_exp}").json()
        run = plan["runs"][-1]["id"]
        doc = copy.deepcopy(self.client.get(f"/api/runs/{run}").json()["envelope"]["artifact"]); doc.pop("analysis", None)
        beat = next(b for b in doc["blocking"] if b["beat_id"] == "SC-001-B4")
        beat["characters"][0]["end"] = {"x": 0.2, "y": 0.8}; beat["characters"][0]["path"] = [beat["characters"][0]["start"], beat["characters"][0]["end"]]
        self.post("/api/lab/direction/save", {"base_experiment_id": self.plan_exp, "plan": doc, "name": "plan v2", "note": "Nila stays by the door"}, 201)
        imp = self.client.get(f"/api/light/plans/{e}/impact").json()
        self.assertTrue(imp["stale"]); self.assertEqual(imp["blocking_beats"], ["SC-001-B4"])
        self.assertIn("blocking changed", imp["summary"])

    def test_an_art_treatment_change_is_noticed_and_the_plan_is_rebased_onto_it(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        art_run = self.client.get(f"/api/runs/{self.art_a['run']}").json()["envelope"]["artifact"]
        d = copy.deepcopy(art_run); d.pop("analysis", None)
        next(o for o in d["layout"]["objects"] if o["id"] == "D-LAMP")["x"] = 0.5
        self.post("/api/art/save", {"base_experiment_id": self.art_a["exp"], "art": d, "name": "lamp moved", "note": ""}, 201)
        imp = self.client.get(f"/api/light/plans/{e}/impact").json()
        self.assertEqual(imp["changed_objects"], ["D-LAMP"]); self.assertIn("L-LAMP", imp["affected_lights"])
        rb = self.post(f"/api/light/plans/{e}/rebase", {}, 201).json()["run"]["envelope"]["artifact"]
        self.assertEqual(next(l for l in rb["lights"] if l["id"] == "L-LAMP")["status"], "needs_review")
        self.assertEqual(rb["source"]["art"]["object_hashes"]["D-LAMP"], self.client.get(f"/api/light/plans/{e}/impact").json() and rb["source"]["art"]["object_hashes"]["D-LAMP"])


class ExportTests(LightCase):
    def test_working_exports_are_always_available_and_the_manifest_needs_approval(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        for kind, ctype in (("lighting-plan-json", "json"), ("lighting-instructions", "json"), ("light-schedule-csv", "csv")):
            res = self.post(f"/api/runs/{r}/exports/{kind}", None, 200)
            self.assertIn(ctype, res.headers["content-type"])
        ins = self.post(f"/api/runs/{r}/exports/lighting-instructions").json()
        self.assertEqual(validate(ins, "filmcraft.lighting_instructions.v1"), [])
        self.assertEqual(self.post(f"/api/runs/{r}/exports/lighting-manifest").status_code, 409)
        self.assertEqual(self.post(f"/api/runs/{r}/exports/nonsense").status_code, 422)
        self.assertEqual(self.post(f"/api/runs/{r}/exports/lighting-plan-json?override=bogus").status_code, 422)

    def test_a_manifest_needs_the_art_treatment_to_be_approved_or_an_explicit_recorded_choice(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        self.approve(r)
        res = self.post(f"/api/runs/{r}/exports/lighting-manifest")
        self.assertEqual(res.status_code, 409); self.assertIn("allow_unapproved_art", res.text)
        ok = self.post(f"/api/runs/{r}/exports/lighting-manifest?override=allow_unapproved_art", None, 200)
        m = ok.json()
        self.assertEqual(validate(m, "filmcraft.lighting_manifest.v1"), []); self.assertEqual(m["overrides"], ["allow_unapproved_art"])
        self.assertFalse(m["import_policy"]["auto_import"]); self.assertEqual(m["approval"]["reviewer"], "Gaffer")
        self.assertEqual(m["art_reference"]["art_approval_status"], "draft")
        self.assertEqual(ok.headers["x-craftbox-existing"], "false")
        again = self.post(f"/api/runs/{r}/exports/lighting-manifest", None, 200)                                      # exports are made once
        self.assertEqual(again.headers["x-craftbox-existing"], "true"); self.assertEqual(again.json()["manifest_sha256"], m["manifest_sha256"])

    def test_with_the_art_approved_a_clean_plan_exports_without_any_override_and_without_art_data(self):
        self.approve(self.art_a["run"])
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        self.approve(r)
        m = self.post(f"/api/runs/{r}/exports/lighting-manifest", None, 200).json()
        self.assertEqual(m["overrides"], []); self.assertEqual(m["art_reference"]["art_approval_status"], "approved")
        for key in ("layout", "props", "style", "location"):
            self.assertNotIn(key, m)

    def test_open_findings_and_pending_items_and_stale_inputs_each_need_their_own_recorded_choice(self):
        self.approve(self.art_a["run"])
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        d = copy.deepcopy(a); d["conditions"]["time_of_day"] = "day"
        next(x for x in d["lights"] if x["id"] == "L-FILL")["status"] = "needs_review"
        e2, r2, a2 = self.save(e, d, "has problems")
        self.approve(r2)
        res = self.post(f"/api/runs/{r2}/exports/lighting-manifest")
        self.assertEqual(res.status_code, 409)
        for token in ("allow_open_findings", "allow_pending"):
            self.assertIn(token, res.text)
        m = self.post(f"/api/runs/{r2}/exports/lighting-manifest?override=allow_open_findings&override=allow_pending", None, 200).json()
        self.assertEqual(sorted(m["overrides"]), ["allow_open_findings", "allow_pending"]); self.assertTrue(m["continuity"]["open_findings"])
        e3, r3, _ = self.draft(self.art_a, "warm_naturalistic", "second")
        self.approve(r3)
        r_ = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "rev 2", "input": revised(), "run_now": True, "parent_experiment_id": self.sp_exp}, 201)
        res = self.post(f"/api/runs/{r3}/exports/lighting-manifest")
        self.assertEqual(res.status_code, 409); self.assertIn("acknowledge_stale", res.text)
        m3 = self.post(f"/api/runs/{r3}/exports/lighting-manifest?override=acknowledge_stale", None, 200).json()
        self.assertEqual(m3["source"]["source_status"], "stale_acknowledged")


class SetupReuseTests(LightCase):
    def test_a_setup_is_saved_listed_versioned_and_starts_a_plan_for_another_treatment(self):
        e, r, a = self.draft(self.art_a, "warm_naturalistic")
        s1 = self.post("/api/light/setups", {"plan_experiment_id": e, "setup_id": "WARM-ROOM", "name": "Warm room", "summary": "lamp-led"}, 201).json()
        self.assertEqual(s1["run"]["run_status"], "completed")
        s2 = self.post("/api/light/setups", {"plan_experiment_id": e, "setup_id": "WARM-ROOM", "name": "Warm room v2", "summary": "lamp-led", "parent_experiment_id": s1["experiment"]["id"]}, 201).json()
        listed = self.client.get("/api/light/setups?project_id=closing-hour").json()
        self.assertEqual([x["name"] for x in listed], ["Warm room v2"]); self.assertEqual(listed[0]["lights"], len(a["lights"]))             # latest version of each setup
        e2, r2, b = self.draft(self.art_b, "setup", "Reused in treatment B", setup_experiment_id=s2["experiment"]["id"])
        self.assertEqual(b["from_setup"]["setup_id"], "WARM-ROOM"); self.assertEqual(len(b["lights"]), len(a["lights"]))
        self.assertEqual(self.post(f"/api/runs/{s2['run']['id']}/exports/lighting-setup-json", None, 200).json()["setup"]["id"], "WARM-ROOM")
        self.assertEqual(self.post("/api/light/setups", {"plan_experiment_id": e, "setup_id": "bad id!", "name": "x"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
