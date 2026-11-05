"""CB2A API tests: the Art Direction Lab on top of CB0's lifecycle and CB1's artifacts."""
import copy
import os
import tempfile
import unittest

os.environ.setdefault("CRAFTBOX_LOG_LEVEL", "ERROR")

from fastapi.testclient import TestClient  # noqa: E402

from app.core import get_fixture  # noqa: E402
from app.server import create_app  # noqa: E402
from app.validation import validate  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(64))


def authored():
    return copy.deepcopy(get_fixture("screenwriting", "screenplay"))


class ArtCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(self.tmp.name, log_to_file=False))
        self.addCleanup(self.client.close)
        r = self.client.post("/api/experiments", json={"craft_id": "screenwriting", "name": "rev 1", "input": authored(), "run_now": True}).json()
        self.sp_exp, self.sp_run = r["id"], r["latest_run"]["id"]
        p = self.client.post("/api/lab/direction/draft", json={"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-001", "name": "plan", "approach": {"preset": "intimate"}}).json()
        self.plan_exp, self.plan_run, self.plan = p["experiment"]["id"], p["run"]["id"], p["run"]["envelope"]["artifact"]

    def post(self, path, body=None, status=None):
        r = self.client.post(path, json=body)
        if status:
            self.assertEqual(r.status_code, status, r.text)
        return r

    def draft(self, preset="warm_nostalgia", name=None, **kw):
        r = self.post("/api/art/draft", {"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-001", "name": name or preset, "preset": preset, "plan_experiment_id": self.plan_exp, **kw}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]

    def save(self, base, art, name="edit", note=""):
        r = self.post("/api/art/save", {"base_experiment_id": base, "art": art, "name": name, "note": note}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed", r["run"].get("error"))
        return r["experiment"]["id"], r["run"]["id"], r["run"]["envelope"]["artifact"]

    def approve(self, run, who="Art director"):
        self.post(f"/api/runs/{run}/submit-review", {}, 200)
        self.post(f"/api/runs/{run}/approve", {"reviewer": who, "note": "good"}, 200)

    def status(self, run):
        return self.client.get(f"/api/runs/{run}").json()["approval_status"]


class TreatmentLifecycleTests(ArtCase):
    def test_two_treatments_are_independent_through_every_stage(self):
        ea, ra, a = self.draft("warm_nostalgia", "Warm nostalgia")
        eb, rb, b = self.draft("emotional_distance", "Emotional distance")
        self.assertEqual(validate(a, "filmcraft.art_direction.v1"), []); self.assertNotEqual(ea, eb)
        self.assertEqual(a["source"]["ref"]["plan_experiment_id"], self.plan_exp)
        self.approve(ra)
        self.assertEqual((self.status(ra), self.status(rb)), ("approved", "draft"))                       # approving one never touches the other
        edited = copy.deepcopy(b); edited.pop("analysis")
        edited["style"]["palette"][0]["hex"] = "#445566"
        eb2, rb2, b2 = self.save(eb, edited, "Emotional distance v2", "darker")
        self.assertEqual(self.client.get(f"/api/experiments/{eb2}").json()["parent_experiment_id"], eb)
        self.assertEqual(self.status(ra), "approved")
        before = self.client.get(f"/api/runs/{rb}").json()["envelope"]
        self.assertEqual(before["artifact"]["style"]["palette"][0]["hex"], b["style"]["palette"][0]["hex"])   # the earlier version is unchanged
        self.assertEqual(b2["style"]["palette"][0]["hex"], "#445566")
        ov = self.client.get("/api/art/projects/closing-hour").json()
        self.assertEqual({t["treatment_name"] for t in ov["treatments"]}, {"Warm nostalgia", "Emotional distance"})
        self.assertEqual(len(ov["treatments"]), 3)

    def test_comparison_shows_what_differs_and_how_each_reads(self):
        _, ra, _ = self.draft("warm_nostalgia"); _, rb, _ = self.draft("emotional_distance")
        c = self.client.get(f"/api/art/compare?run_a={ra}&run_b={rb}").json()
        rows = {m["key"]: m for m in c["metrics"]}
        self.assertTrue(rows["warmth"]["differs"] and rows["warmth"]["a"] > rows["warmth"]["b"])
        self.assertTrue(rows["personal_props"]["differs"] and rows["central_objects"]["a"] > rows["central_objects"]["b"])
        self.assertIn("Reading armchair", c["differences"]["objects_only_a"]); self.assertIn("Single bench", c["differences"]["objects_only_b"])
        self.assertTrue(c["readings"]["a"] and c["readings"]["b"] and c["palettes"]["a"] != c["palettes"]["b"])
        generic = self.client.get(f"/api/compare?run_a={ra}&run_b={rb}").json()                         # the CB0 diff also works
        self.assertFalse(generic["identical_output"])
        _, rs, _ = self.draft("warm_nostalgia", "Warm again")
        self.assertEqual(self.client.get(f"/api/art/compare?run_a={ra}&run_b={self.plan_run}").status_code, 409)
        same = self.client.get(f"/api/art/compare?run_a={ra}&run_b={rs}").json()
        self.assertFalse(any(m["differs"] for m in same["metrics"]))

    def test_analyze_is_stateless_and_validation_errors_are_clear(self):
        ea, _, a = self.draft()
        broken = copy.deepcopy(a); broken["layout"]["objects"][0]["x"] = 1.5
        r = self.post("/api/art/analyze", {"base_experiment_id": ea, "art": broken})
        self.assertEqual(r.status_code, 422); self.assertTrue(any("x" in e["path"] for e in r.json()["detail"]["errors"]))
        ok = copy.deepcopy(a); ok["layout"]["objects"][1]["x"] = 0.6
        out = self.post("/api/art/analyze", {"base_experiment_id": ea, "art": ok}, 200).json()
        self.assertIn("issues", out["analysis"]); self.assertEqual(self.client.get("/api/experiments").json()["total"], 3)   # screenplay, plan, treatment: nothing new was saved
        dup = copy.deepcopy(a); dup["props"].append(copy.deepcopy(dup["props"][0]))
        self.assertEqual(self.post("/api/art/analyze", {"base_experiment_id": ea, "art": dup}).status_code, 422)
        self.assertEqual(self.post("/api/art/save", {"base_experiment_id": self.sp_exp, "art": a, "name": "x"}).status_code, 409)

    def test_cb0_single_craft_run_of_art_direction_still_works(self):
        r = self.post("/api/experiments", {"craft_id": "art_direction", "name": "single craft", "input": self.client.get("/api/crafts/art_direction/fixture").json(), "run_now": True}, 201).json()
        self.assertEqual((r["latest_run"]["run_status"], r["latest_run"]["output_schema"]), ("completed", "filmcraft.art_direction.v1"))


class ChangeImpactTests(ArtCase):
    def revise_script(self):
        doc = authored(); doc["revision"] = {"number": 2, "note": "ticket line"}
        doc["scenes"][0]["elements"][14]["text"] = "She stops. He nods at the book. She opens it. Inside: a ticket to her city, two years old, never used."
        r = self.post("/api/experiments", {"craft_id": "screenwriting", "name": "rev 2", "input": doc, "run_now": True, "parent_experiment_id": self.sp_exp}, 201).json()
        self.assertEqual(r["latest_run"]["run_status"], "completed")
        return r["id"]

    def test_script_revision_flags_outdated_design_without_touching_approved_work(self):
        ea, ra, a = self.draft()
        approved = copy.deepcopy(a); approved.pop("analysis")
        for p in approved["props"]:
            p["status"] = "approved"
        eb, rb, b = self.save(ea, approved, "approved props")
        self.approve(rb)
        self.assertFalse(self.client.get(f"/api/art/treatments/{eb}/impact").json()["stale"])
        self.revise_script()
        imp = self.client.get(f"/api/art/treatments/{eb}/impact").json()
        self.assertTrue(imp["stale"]); self.assertIn("PR-TICKET", imp["affected_props"]); self.assertNotIn("PR-COAT", imp["affected_props"])
        entry = next(t for t in self.client.get("/api/art/projects/closing-hour").json()["treatments"] if t["experiment_id"] == eb)
        self.assertTrue(entry["stale"] and entry["affected"] >= 1)
        self.assertEqual(self.status(rb), "approved")                                                    # approved version preserved
        out = self.post(f"/api/art/treatments/{eb}/rebase", {}, 201).json()
        new = out["run"]["envelope"]["artifact"]
        st = {p["id"]: p["status"] for p in new["props"]}
        self.assertEqual(st["PR-TICKET"], "needs_review"); self.assertEqual(st["PR-COAT"], "approved")
        self.assertEqual(next(p for p in new["props"] if p["id"] == "PR-TICKET")["previous_status"], "approved")
        self.assertEqual(out["experiment"]["parent_experiment_id"], eb); self.assertEqual(new["source"]["screenplay_revision"], 2)
        self.assertEqual(self.status(rb), "approved")
        self.assertFalse(self.client.get(f"/api/art/treatments/{out['experiment']['id']}/impact").json()["stale"])
        self.assertEqual(self.post(f"/api/art/treatments/{out['experiment']['id']}/rebase", {}).status_code, 409)

    def test_a_blocking_change_in_the_direction_plan_outdates_the_layout(self):
        ea, ra, a = self.draft()
        plan = copy.deepcopy(self.plan); plan.pop("analysis")
        plan["blocking"][2]["characters"][0]["end"]["x"] = 0.31
        r = self.post("/api/lab/direction/save", {"base_experiment_id": self.plan_exp, "plan": plan, "name": "plan v2"}, 201).json()
        self.assertEqual(r["run"]["run_status"], "completed")
        imp = self.client.get(f"/api/art/treatments/{ea}/impact").json()
        self.assertTrue(imp["stale"]); self.assertEqual(imp["blocking_changed_beats"], [plan["blocking"][2]["beat_id"]])
        self.assertEqual(imp["against"]["plan_experiment_id"], r["experiment"]["id"])
        out = self.post(f"/api/art/treatments/{ea}/rebase", {}, 201).json()
        self.assertIn("blocking changed", out["run"]["envelope"]["artifact"]["layout"]["note"])
        self.assertEqual(out["run"]["envelope"]["artifact"]["source"]["ref"]["plan_experiment_id"], r["experiment"]["id"])


class ExportTests(ArtCase):
    def approved_clean(self):
        ea, ra, a = self.draft()
        clean = copy.deepcopy(a); clean.pop("analysis")
        clean["props"] = [p for p in clean["props"] if p["id"] not in ("PR-TICKET", "PR-COAT", "PR-LAMP")] + []
        clean["location"]["details"] = []
        e, r, art = self.save(ea, clean, "clean")
        return e, r, art

    def test_working_exports_are_always_available_and_manifests_need_approval(self):
        ea, ra, a = self.draft()
        for kind in ("art-direction-json", "prop-list-csv", "storyboard-metadata"):
            self.assertEqual(self.post(f"/api/runs/{ra}/exports/{kind}", None, 200).status_code, 200, kind)
        sb = self.post(f"/api/runs/{ra}/exports/storyboard-metadata", None, 200).json()
        self.assertEqual(validate(sb, "filmcraft.storyboard_metadata.v1"), [])
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/art-direction-manifest").status_code, 409)
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/nonsense").status_code, 422)
        self.assertEqual(self.post(f"/api/runs/{ra}/exports/art-direction-manifest?override=bogus").status_code, 422)

    def test_open_findings_need_an_explicit_recorded_override(self):
        ea, ra, a = self.draft()
        self.assertGreaterEqual(a["analysis"]["readiness"]["attention"], 0)
        broken = copy.deepcopy(a); broken.pop("analysis")
        stand = self.plan["blocking"][2]["characters"][0]["end"]
        next(o for o in broken["layout"]["objects"] if o["id"] == "P-COUNTER").update(x=stand["x"], y=stand["y"])
        eb, rb, b = self.save(ea, broken, "counter on an actor")
        self.assertGreaterEqual(b["analysis"]["readiness"]["attention"], 1)
        self.approve(rb)
        r = self.post(f"/api/runs/{rb}/exports/art-direction-manifest")
        self.assertEqual(r.status_code, 409); self.assertIn("allow_open_findings", r.json()["detail"])
        m = self.post(f"/api/runs/{rb}/exports/art-direction-manifest?override=allow_open_findings", None, 200).json()
        self.assertEqual(validate(m, "filmcraft.art_direction_manifest.v1"), []); self.assertEqual(m["overrides"], ["allow_open_findings"])
        again = self.post(f"/api/runs/{rb}/exports/art-direction-manifest", None, 200)
        self.assertEqual(again.json(), m); self.assertEqual(again.headers["X-Craftbox-Existing"], "true")
        events = [e["event_type"] for e in self.client.get(f"/api/runs/{rb}/events").json()]
        self.assertIn("export.art-direction-manifest", events)

    def test_a_clean_approved_treatment_exports_without_overrides(self):
        e, r, art = self.approved_clean()
        self.assertEqual(art["analysis"]["readiness"]["attention"], 0)
        self.approve(r)
        m = self.post(f"/api/runs/{r}/exports/art-direction-manifest", None, 200).json()
        self.assertEqual((m["overrides"], m["approval"]["reviewer"], m["source"]["source_status"]), ([], "Art director", "current"))
        self.assertEqual(m["hashes"]["scene_hash"], self.plan["source"]["scene_hash"]); self.assertFalse(m["import_policy"]["auto_import"])
        am = self.post(f"/api/runs/{r}/exports/asset-reference-manifest", None, 200).json()
        self.assertEqual(validate(am, "filmcraft.asset_reference_manifest.v1"), []); self.assertEqual(am["summary"]["assets"], 0)

    def test_stale_and_pending_items_block_a_manifest_until_acknowledged(self):
        e, r, art = self.approved_clean()
        self.approve(r)
        doc = authored(); doc["revision"] = {"number": 2, "note": "x"}
        doc["scenes"][0]["elements"][0]["text"] = "Rain ticks on the window. ARJUN counts the till, alone, under one lamp."
        self.post("/api/experiments", {"craft_id": "screenwriting", "name": "rev 2", "input": doc, "run_now": True, "parent_experiment_id": self.sp_exp}, 201)
        refused = self.post(f"/api/runs/{r}/exports/art-direction-manifest")
        self.assertEqual(refused.status_code, 409); self.assertIn("acknowledge_stale", refused.json()["detail"])
        ok = self.post(f"/api/runs/{r}/exports/art-direction-manifest?override=acknowledge_stale", None, 200).json()
        self.assertEqual((ok["overrides"], ok["source"]["source_status"]), (["acknowledge_stale"], "stale_acknowledged"))


class AssetAndStyleTests(ArtCase):
    def test_uploads_are_checked_deduplicated_and_served_safely(self):
        u = self.client.post("/api/assets/upload?filename=oak.png", content=PNG)
        self.assertEqual(u.status_code, 201); sha = u.json()["sha256"]
        self.assertEqual((u.json()["mime"], u.json()["already_stored"]), ("image/png", False))
        again = self.client.post("/api/assets/upload?filename=copy.png", content=PNG).json()
        self.assertEqual((again["sha256"], again["already_stored"]), (sha, True))                       # one stored copy
        f = self.client.get(f"/api/assets/{sha}/file")
        self.assertEqual((f.status_code, f.headers["content-type"], f.headers["x-content-type-options"]), (200, "image/png", "nosniff"))
        bad = self.client.post("/api/assets/upload?filename=run.exe", content=b"MZ" + b"0" * 50)
        self.assertEqual(bad.status_code, 422); self.assertIn("PNG, JPEG, GIF and WebP", bad.json()["detail"])
        self.assertEqual(self.client.post("/api/assets/upload?filename=x.png", content=b"").status_code, 422)
        self.assertEqual(self.client.post("/api/assets/upload?filename=big.png", content=PNG + b"0" * 8_100_000).status_code, 413)
        self.assertEqual(self.client.get("/api/assets/not-a-hash/file").status_code, 404)
        svg = self.client.post("/api/assets/upload?filename=a.svg", content=b"<svg onload='x'/>")
        self.assertEqual(svg.status_code, 422)

    def test_a_local_file_can_be_registered_by_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "wall.png")
            with open(path, "wb") as fh:
                fh.write(PNG + b"1")
            ok = self.post("/api/assets/from-path", {"path": path}, 201).json()
            self.assertEqual(ok["origin_path"], path); self.assertEqual(self.client.get(f"/api/assets/{ok['sha256']}/file").status_code, 200)
            self.assertEqual(self.post("/api/assets/from-path", {"path": os.path.join(d, "missing.png")}).status_code, 422)
            self.assertEqual(self.post("/api/assets/from-path", {"path": "relative.png"}).status_code, 422)

    def register(self, sha, rights="cleared", source="own", parent=None):
        reg = {"schema": "filmcraft.asset_register.v1", "project_id": "closing-hour", "assets": [
            {"id": "A-001", "name": "Oak grain", "kind": "texture", "sha256": sha, "filename": "oak.png", "size_bytes": len(PNG), "mime": "image/png", "source": {"type": source, "creator": "Me"},
             "rights": {"status": rights, "owner": "Me", "licence": "own work"}, "usage": {"allowed": ["film"]}, "tags": ["wood"]}]}
        r = self.post("/api/experiments", {"craft_id": "art_direction", "name": "register", "input": reg, "run_now": True, "parent_experiment_id": parent}, 201).json()
        self.assertEqual(r["latest_run"]["run_status"], "completed", r["latest_run"].get("error"))
        return r["id"]

    def test_register_rights_flow_into_the_treatment_analysis_and_the_asset_manifest(self):
        sha = self.client.post("/api/assets/upload?filename=oak.png", content=PNG).json()["sha256"]
        reg1 = self.register(sha, rights="pending")
        view = self.client.get("/api/art/assets?project_id=closing-hour").json()
        self.assertEqual((len(view["assets"]), view["assets"][0]["file_present"]), (1, True))
        ea, ra, a = self.draft()
        doc = copy.deepcopy(a); doc.pop("analysis"); doc["style"]["textures"][0]["asset_id"] = "A-001"
        eb, rb, b = self.save(ea, doc, "uses the oak texture")
        self.assertTrue(any("pending" in i["message"] for i in b["analysis"]["issues"] if i["rule"] == "assets"))     # rights advice
        self.register(sha, rights="cleared", parent=reg1)
        ec, rc, c = self.save(eb, {k: v for k, v in b.items() if k != "analysis"}, "rights cleared")
        self.assertEqual([i for i in c["analysis"]["issues"] if i["rule"] == "assets"], [])
        self.approve(rc)
        am = self.post(f"/api/runs/{rc}/exports/asset-reference-manifest?override=allow_open_findings", None, 200).json()
        self.assertEqual(am["assets"][0]["sha256"], sha); self.assertTrue(am["assets"][0]["file_present"]); self.assertEqual(am["summary"]["rights_cleared"], 1)
        self.assertEqual(am["assets"][0]["used_by"], ["texture:T1"])

    def test_style_profiles_are_project_level_versioned_and_reusable(self):
        prof = lambda note: {"schema": "filmcraft.style_profile.v1", "project_id": "closing-hour", "note": note, "profile": {"id": "STYLE-HOUSE", "name": "House style",
              "palette": [{"id": "C1", "name": "Oak", "hex": "#8B5E3C"}, {"id": "C2", "name": "Amber", "hex": "#E0A85A"}, {"id": "C3", "name": "Cream", "hex": "#F1E3C8"}],
              "constraints": [{"id": "K1", "kind": "avoid", "term": "neon"}]}}
        v1 = self.post("/api/experiments", {"craft_id": "art_direction", "name": "House style v1", "input": prof("v1"), "run_now": True}, 201).json()
        v2 = self.post("/api/experiments", {"craft_id": "art_direction", "name": "House style v2", "input": prof("v2"), "run_now": True, "parent_experiment_id": v1["id"]}, 201).json()
        styles = self.client.get("/api/art/styles?project_id=closing-hour").json()
        self.assertEqual([s["experiment_id"] for s in styles], [v2["id"]])                              # latest version per profile
        ea, ra, a = self.draft("warm_nostalgia", "From the house style", style_experiment_id=v2["id"])
        self.assertEqual((a["style"]["profile_ref"]["profile_id"], a["style"]["palette"][0]["hex"]), ("STYLE-HOUSE", "#8B5E3C"))
        self.assertEqual(self.post("/api/art/draft", {"screenplay_experiment_id": self.sp_exp, "scene_id": "SC-001", "name": "x", "preset": "blank", "style_experiment_id": self.sp_exp}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
