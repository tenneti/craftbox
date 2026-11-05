"""CB2A engine tests: the Art Direction craft (treatments, style profiles, asset registers) without a server."""
import copy
import unittest

from app.core import execute, get_fixture
from app.crafts.art_direction import exports as aexp
from app.crafts.art_direction import impact
from app.hashing import sha256
from app.validation import validate

TREATMENT = "filmcraft.art_direction.v1"


def sp_artifact(doc=None):
    return execute("screenwriting", doc or copy.deepcopy(get_fixture("screenwriting", "screenplay")))["artifact"]


def plan_for(sp, approach="intimate"):
    return execute("direction", {"screenplay": sp, "scene_id": "SC-001", "approach": {"preset": approach}})["artifact"]


def art(sp, plan=None, preset="warm_nostalgia", **extra):
    payload = {"screenplay": sp, "scene_id": "SC-001", "preset": preset, **extra}
    if plan is not None:
        payload["direction_plan"] = plan
    return execute("art_direction", payload)["artifact"]


def edited(sp, plan, doc, **extra):
    d = copy.deepcopy(doc)
    d.pop("analysis", None)
    payload = {"screenplay": sp, "scene_id": "SC-001", "art": d, "direction_plan": plan, **extra}
    return execute("art_direction", payload)["artifact"]


def issues(a, rule=None, severity=None):
    return [i for i in a["analysis"]["issues"] if (rule is None or i["rule"] == rule) and (severity is None or i["severity"] == severity)]


class ArtDirectionEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp = sp_artifact()
        cls.plan = plan_for(cls.sp)
        cls.a = art(cls.sp, cls.plan, "warm_nostalgia")
        cls.b = art(cls.sp, cls.plan, "emotional_distance")

    # ---- 1. scene and blocking imports ------------------------------------------------------------------------------------------
    def test_drafts_are_valid_and_reuse_the_stage_coordinates_and_ids_of_the_direction_plan(self):
        stage = {o["id"]: o for o in self.plan["stage"]["objects"]}
        for doc in (self.a, self.b):
            self.assertEqual(validate(doc, TREATMENT), [])
            objs = {o["id"]: o for o in doc["layout"]["objects"]}
            self.assertIn("P-DOOR", objs)                                           # the id the blocking enters through
            for oid in ("P-DOOR", "P-SHELF"):
                self.assertEqual((objs[oid]["y"],), (stage[oid]["y"],))
            self.assertEqual(doc["project_id"], "closing-hour"); self.assertEqual(doc["scene_id"], "SC-001")
        self.assertEqual({o["id"]: o for o in self.a["layout"]["objects"]}["P-COUNTER"]["x"], stage["P-COUNTER"]["x"])   # A keeps the counter where the director put it
        self.assertEqual([i for i in issues(self.a, "entrance")], [])

    def test_source_block_records_what_the_design_was_built_from(self):
        src = self.a["source"]
        self.assertEqual(src["scene_hash"], self.sp["analysis"]["scenes"][0]["scene_hash"])
        self.assertEqual(set(src["plan"]["shot_ids"]), {s["shot_id"] for s in self.plan["shots"]})
        self.assertEqual(set(src["plan"]["blocking_hashes"]), {b["beat_id"] for b in self.plan["blocking"]})
        self.assertIn("P-DOOR", src["plan"]["stage_object_ids"])

    def test_works_without_a_direction_plan(self):
        d = art(self.sp, None)
        self.assertEqual(validate(d, TREATMENT), [])
        self.assertIn("P-DOOR", {o["id"] for o in d["layout"]["objects"]})
        self.assertIsNone(d["source"]["plan"])

    def test_wrong_scene_or_unprocessed_screenplay_fail_clearly(self):
        with self.assertRaises(ValueError):
            execute("art_direction", {"screenplay": self.sp, "scene_id": "SC-404", "preset": "blank"})
        with self.assertRaises(ValueError):
            execute("art_direction", {"screenplay": copy.deepcopy(get_fixture("screenwriting", "screenplay")), "scene_id": "SC-001", "preset": "blank"})
        with self.assertRaises(ValueError):
            execute("art_direction", {"screenplay": self.sp, "scene_id": "SC-001", "preset": "nonsense"})

    # ---- props -----------------------------------------------------------------------------------------------------------------------
    def test_props_are_extracted_from_the_script_and_linked_to_lines_and_shots(self):
        props = {p["id"]: p for p in self.a["props"]}
        self.assertTrue({"P-BOOK", "P-SIGN", "PR-TICKET", "PR-COAT", "PR-LAMP"} <= set(props))
        ticket = props["PR-TICKET"]
        self.assertIn("SC-001-E15", ticket["mentions"])
        self.assertTrue(set(ticket["shot_ids"]) <= {s["shot_id"] for s in self.plan["shots"]} and ticket["shot_ids"])
        self.assertEqual(props["P-BOOK"]["position"], {"x": 0.5, "y": 0.12})        # taken from the plan's stage
        self.assertEqual(props["PR-LAMP"]["kind"], "practical")
        self.assertTrue(all(p["scene_ids"] == ["SC-001"] and p["source"] == "script" for p in props.values() if p["id"] in ("P-BOOK", "PR-TICKET")))
        self.assertEqual(sum(1 for p in self.b["props"] if p["kind"] == "personal"), 0)
        self.assertEqual(sum(1 for p in self.a["props"] if p["kind"] == "personal"), 3)

    def test_prop_continuity_rules(self):
        def with_states(states):
            d = copy.deepcopy(self.a)
            next(p for p in d["props"] if p["id"] == "PR-TICKET")["states"] = states
            return edited(self.sp, self.plan, d)
        good = with_states([{"at_kind": "beat", "at_id": "SC-001-B4", "where": "inside the book"}, {"at_kind": "beat", "at_id": "SC-001-B5", "where": "in Nila's hand", "note": "she lifts it out"}])
        self.assertEqual(issues(good, "props", "attention"), [])
        back = with_states([{"at_kind": "beat", "at_id": "SC-001-B5", "where": "gone: in her pocket"}, {"at_kind": "beat", "at_id": "SC-001-B6", "where": "on the counter"}])
        self.assertTrue(any("appears again" in i["message"] for i in issues(back, "props", "attention")))
        unexplained = with_states([{"at_kind": "beat", "at_id": "SC-001-B4", "where": "inside the book"}, {"at_kind": "beat", "at_id": "SC-001-B5", "where": "on the counter"}])
        self.assertTrue(any("no explanation" in i["message"] for i in issues(unexplained, "props", "note")))
        shown_after_gone = with_states([{"at_kind": "beat", "at_id": "SC-001-B1", "where": "gone"}])
        self.assertTrue(any("shows" in i["message"] and "marked" in i["message"] for i in issues(shown_after_gone, "props", "attention")))
        dangling = with_states([{"at_kind": "shot", "at_id": "SC-001-S99", "where": "on the counter"}])
        self.assertTrue(any("not in the direction plan" in i["message"] for i in issues(dangling, "props", "attention")))
        unordered = with_states([{"at_kind": "beat", "at_id": "SC-001-B5", "where": "a", "note": "x"}, {"at_kind": "beat", "at_id": "SC-001-B2", "where": "a"}])
        self.assertTrue(any("script order" in i["message"] for i in issues(unordered, "props", "note")))

    def test_a_prop_the_script_names_but_the_inventory_lacks_is_flagged(self):
        d = copy.deepcopy(self.a)
        d["props"] = [p for p in d["props"] if p["id"] != "PR-TICKET"]
        out = edited(self.sp, self.plan, d)
        self.assertTrue(any("Ticket" in i["message"] and "not in the inventory" in i["message"] for i in issues(out, "props", "note")))

    # ---- 2. layout editing and persistence ---------------------------------------------------------------------------------------------
    def test_layout_edits_are_kept_and_checked_against_the_blocking(self):
        d = copy.deepcopy(self.a)
        counter = next(o for o in d["layout"]["objects"] if o["id"] == "P-COUNTER")
        stand = self.plan["blocking"][2]["characters"][0]["end"]           # where someone actually stands in the director's blocking
        counter.update(x=stand["x"], y=stand["y"])
        d["layout"]["objects"].append({"id": "D-NEW", "name": "Coat stand", "kind": "decor", "x": 0.12, "y": 0.7, "w": 0.04, "h": 0.04, "solid": False, "notes": ""})
        out = edited(self.sp, self.plan, d)
        kept = {o["id"]: o for o in out["layout"]["objects"]}
        self.assertEqual((kept["P-COUNTER"]["x"], kept["P-COUNTER"]["y"]), (stand["x"], stand["y"])); self.assertIn("D-NEW", kept)
        self.assertEqual(out["analysis"]["art_hash"] != self.a["analysis"]["art_hash"], True)
        # the counter now sits where the people stand: attention, with a way to recover
        crash = issues(out, "layout", "attention")
        self.assertTrue(crash and "inside" in crash[0]["message"] and crash[0]["fix"])
        self.assertEqual(issues(self.a, "layout", "attention"), [])

    def test_missing_entrance_object_heading_mismatch_and_overlap(self):
        d = copy.deepcopy(self.a)
        d["layout"]["objects"] = [o for o in d["layout"]["objects"] if o["id"] != "P-DOOR"]
        self.assertTrue(any("P-DOOR" in i["message"] for i in issues(edited(self.sp, self.plan, d), "entrance", "attention")))
        d = copy.deepcopy(self.a); d["location"]["kind"] = "exterior"
        self.assertTrue(issues(edited(self.sp, self.plan, d), "location", "attention"))
        d = copy.deepcopy(self.a)
        next(o for o in d["layout"]["objects"] if o["id"] == "D-ARMCHAIR").update(x=0.74, y=0.42)
        self.assertTrue(any("overlap" in i["message"] for i in issues(edited(self.sp, self.plan, d), "layout", "note")))

    def test_hard_errors_raise(self):
        d = copy.deepcopy(self.a); d["layout"]["objects"].append(copy.deepcopy(d["layout"]["objects"][0]))
        with self.assertRaises(ValueError):
            edited(self.sp, self.plan, d)
        d = copy.deepcopy(self.a); d["scene_id"] = "SC-002"
        with self.assertRaises(ValueError):
            edited(self.sp, self.plan, d)
        d = copy.deepcopy(self.a); d["style"]["palette"][0]["hex"] = "red"
        self.assertTrue(validate(d, TREATMENT))
        d = copy.deepcopy(self.a); d["layout"]["objects"][0]["x"] = 1.4
        self.assertTrue(validate(d, TREATMENT))

    # ---- 4. independent treatments ----------------------------------------------------------------------------------------------------
    def test_the_two_treatments_differ_and_are_independent_of_each_other(self):
        ma, mb = self.a["analysis"]["metrics"], self.b["analysis"]["metrics"]
        self.assertGreater(ma["warmth"], 0.15); self.assertLess(mb["warmth"], 0.0)
        self.assertGreater(ma["central_objects"], mb["central_objects"]); self.assertGreater(ma["personal_props"], mb["personal_props"])
        self.assertEqual(self.a["source"]["scene_hash"], self.b["source"]["scene_hash"])               # the screenplay is unchanged
        ta, tb = " ".join(x["text"] for x in self.a["analysis"]["reading"]), " ".join(x["text"] for x in self.b["analysis"]["reading"])
        self.assertIn("intimate", ta); self.assertIn("detached", tb)
        self.assertTrue(all("because" in x and x["because"] for x in self.a["analysis"]["reading"]))     # every reading shows its basis
        d = copy.deepcopy(self.a); d["style"]["palette"][0]["hex"] = "#112233"
        out = edited(self.sp, self.plan, d)
        self.assertNotEqual(out["analysis"]["art_hash"], self.a["analysis"]["art_hash"])
        self.assertEqual(art(self.sp, self.plan, "emotional_distance")["analysis"]["art_hash"], self.b["analysis"]["art_hash"])   # editing A never changes B

    def test_deterministic(self):
        self.assertEqual(sha256(art(self.sp, self.plan, "warm_nostalgia")), sha256(self.a))

    # ---- style, variations, constraints ----------------------------------------------------------------------------------------------------
    def profile(self, **kw):
        base = {"schema": "filmcraft.style_profile.v1", "project_id": "closing-hour", "profile": {"id": "STYLE-HOUSE", "name": "House style", "summary": "",
                "palette": [{"id": "C1", "name": "Oak", "hex": "#8B5E3C", "role": "dominant"}, {"id": "C2", "name": "Amber", "hex": "#E0A85A", "role": "accent"}, {"id": "C3", "name": "Cream", "hex": "#F1E3C8", "role": "light"}],
                "textures": [{"id": "T1", "name": "Wood grain", "description": ""}], "materials": [{"id": "M1", "name": "Oak", "finish": "matte"}], "period": {"era": "1980s", "notes": ""},
                "themes": ["memory"], "mood_words": ["warm"], "constraints": [{"id": "K1", "kind": "avoid", "term": "neon", "note": "never in this film"}, {"id": "K2", "kind": "require", "term": "lamp", "note": ""}]}}
        base["profile"].update(kw)
        return base

    def test_style_profile_mode_and_project_constraints(self):
        r = execute("art_direction", self.profile())
        self.assertEqual(validate(r["artifact"], "filmcraft.style_profile.v1"), []); self.assertEqual(r["artifact"]["analysis"]["constraints"], {"avoid": 1, "require": 1})
        prof = r["artifact"]
        d = art(self.sp, self.plan, "warm_nostalgia", style_profile=prof)
        self.assertEqual(d["style"]["profile_ref"]["profile_id"], "STYLE-HOUSE"); self.assertEqual(d["style"]["palette"][0]["hex"], "#8B5E3C")
        bad = copy.deepcopy(d); bad["layout"]["objects"].append({"id": "D-NEON", "name": "Neon sign", "kind": "decor", "x": 0.3, "y": 0.2, "w": 0.1, "h": 0.03, "solid": False, "notes": ""})
        out = edited(self.sp, self.plan, bad, style_profile=prof)
        hit = issues(out, "style", "attention")
        self.assertTrue(hit and "neon" in hit[0]["message"].lower())
        self.assertEqual(issues(d, "style", "attention"), [])                       # constraints belong to the project, not to every project
        self.assertEqual(issues(art(self.sp, self.plan, "warm_nostalgia"), "style", "attention"), [])
        with self.assertRaises(ValueError):
            execute("art_direction", self.profile(palette=[{"id": "C1", "name": "a", "hex": "#000000"}, {"id": "C1", "name": "b", "hex": "#111111"}]))

    def test_shot_variations_keep_overall_consistency(self):
        shot = self.plan["shots"][11]["shot_id"]
        d = copy.deepcopy(self.a)
        d["variations"] = [{"id": "V1", "shot_id": shot, "summary": "Cooler for the reveal", "palette": [{"id": "V1C1", "name": "Amber shift", "hex": "#D9A24F"}], "hide_prop_ids": ["P-SIGN"], "show_prop_ids": [], "status": "proposed"}]
        ok = edited(self.sp, self.plan, d)
        self.assertEqual(issues(ok, "variation"), [])
        d["variations"][0]["palette"] = [{"id": "V1C1", "name": "Teal", "hex": "#00B7C7"}]
        self.assertTrue(any("far from the treatment" in i["message"] for i in issues(edited(self.sp, self.plan, d), "variation", "note")))
        d["variations"][0].update(shot_id="SC-001-S99", hide_prop_ids=["PR-NOPE"])
        self.assertGreaterEqual(len(issues(edited(self.sp, self.plan, d), "variation", "attention")), 2)
        meta = aexp.storyboard_metadata(ok, self.plan)
        row = next(s for s in meta["shots"] if s["shot_id"] == shot)
        self.assertEqual(row["variation"]["id"], "V1"); self.assertNotIn("P-SIGN", [p["id"] for p in row["props_visible"]])
        self.assertEqual(row["palette"], ok["variations"][0]["palette"])

    def test_asset_register_mode_and_rights_advice(self):
        asset = lambda **kw: {"id": "A-001", "name": "Oak grain", "kind": "texture", "sha256": "a" * 64, "source": {"type": "own"}, "rights": {"status": "cleared", "owner": "Me"}, **kw}
        reg = execute("art_direction", {"schema": "filmcraft.asset_register.v1", "project_id": "closing-hour", "assets": [asset(), asset(id="A-002", name="Brick", sha256="b" * 64, rights={"status": "pending"}, source={"type": "unknown"})]})
        self.assertEqual(validate(reg["artifact"], "filmcraft.asset_register.v1"), [])
        self.assertEqual(reg["artifact"]["analysis"]["by_rights"], {"cleared": 1, "pending": 1}); self.assertEqual(len(reg["artifact"]["analysis"]["issues"]), 2)
        with self.assertRaises(ValueError):
            execute("art_direction", {"schema": "filmcraft.asset_register.v1", "project_id": "p", "assets": [asset(), asset()]})
        d = copy.deepcopy(self.a); d["style"]["textures"][0]["asset_id"] = "A-002"; d["props"][0]["asset_ids"] = ["A-404"]
        out = edited(self.sp, self.plan, d, asset_register=reg["artifact"])
        msgs = " ".join(i["message"] for i in issues(out, "assets", "attention"))
        self.assertIn("pending", msgs); self.assertIn("A-404", msgs)
        d["style"]["textures"][0]["asset_id"] = "A-001"; d["props"][0]["asset_ids"] = []
        self.assertEqual(issues(edited(self.sp, self.plan, d, asset_register=reg["artifact"]), "assets"), [])

    # ---- 5. change impact and version preservation ----------------------------------------------------------------------------------------
    def test_script_change_flags_only_the_props_that_depend_on_it(self):
        doc = copy.deepcopy(get_fixture("screenwriting", "screenplay"))
        doc["scenes"][0]["elements"][14]["text"] = "She stops. He nods at the book. She opens it. Inside: a ticket to her city, two years old, unused."   # E15
        new_sp = sp_artifact(doc)
        imp = impact.compute(self.a, new_sp, plan_for(new_sp))
        self.assertTrue(imp["stale"]); self.assertIn("SC-001-E15", imp["changed_elements"])
        self.assertIn("PR-TICKET", imp["affected_props"]); self.assertNotIn("PR-COAT", imp["affected_props"])
        self.assertFalse(impact.compute(self.a, self.sp, self.plan)["stale"])

    def test_direction_plan_changes_are_detected(self):
        p2 = copy.deepcopy(self.plan)
        removed = p2["shots"].pop(2)["shot_id"]
        p2["blocking"][1]["characters"][0]["end"]["x"] = 0.2
        p2["stage"]["objects"] = [o for o in p2["stage"]["objects"] if o["id"] != "P-SIGN"]
        p2["analysis"] = {**p2["analysis"], "plan_hash": "changed"}
        imp = impact.compute(self.a, self.sp, p2)
        self.assertTrue(imp["stale"]); self.assertIn(removed, imp["removed_shots"])
        self.assertIn(p2["blocking"][1]["beat_id"], imp["blocking_changed_beats"]); self.assertEqual(imp["removed_stage_objects"], ["P-SIGN"])

    def test_rebase_flags_affected_items_keeps_approved_ones_and_leaves_the_original(self):
        d = copy.deepcopy(self.a)
        for p in d["props"]:
            p["status"] = "approved"
        d["variations"] = [{"id": "V1", "shot_id": self.plan["shots"][2]["shot_id"], "summary": "", "status": "approved"}]
        base = edited(self.sp, self.plan, d)
        original = copy.deepcopy(base)
        p2 = copy.deepcopy(self.plan)
        p2["shots"].pop(2)
        p2["analysis"] = {**p2["analysis"], "plan_hash": "x"}
        rebased, imp = impact.rebase(base, self.sp, p2)
        self.assertEqual(base, original)
        status = {p["id"]: p["status"] for p in rebased["props"]}
        for pid in imp["affected_props"]:
            self.assertEqual(status[pid], "needs_review")
        self.assertTrue(all(s == "approved" for pid, s in status.items() if pid not in imp["affected_props"]))
        self.assertEqual(rebased["variations"][0]["status"], "needs_review"); self.assertEqual(rebased["variations"][0]["previous_status"], "approved")

    # ---- 6. exports ---------------------------------------------------------------------------------------------------------------------------
    ctx = {"run_id": "r-1", "experiment_id": "e-1", "exported_at": "2026-01-01T00:00:00.000Z", "app_version": "test",
           "approval": {"status": "approved", "reviewer": "T", "approved_at": "2026-01-01T00:00:00.000Z", "note": None}}

    def test_exports_validate_and_prepare_the_future_integrations(self):
        m = aexp.art_manifest(self.ctx, self.a, self.sp)
        self.assertEqual(validate(m, "filmcraft.art_direction_manifest.v1"), [])
        self.assertFalse(m["import_policy"]["auto_import"]); self.assertFalse(m["provenance"]["ai_used"])
        for k in ("lighting", "costume", "cinematography", "scene_maker"):
            self.assertIn(k, m["integration"])
        self.assertTrue(m["integration"]["lighting"]["practical_lights"]); self.assertEqual(m["integration"]["costume"]["palette"], self.a["style"]["palette"])
        self.assertEqual(m["integration"]["scene_maker"]["location"]["name"], "Page & Candle Bookshop")
        sb = aexp.storyboard_metadata(self.a, self.plan)
        self.assertEqual(validate(sb, "filmcraft.storyboard_metadata.v1"), []); self.assertEqual(len(sb["shots"]), len(self.plan["shots"]))
        self.assertEqual(sb["previz_hint"]["environment_preset"], "CAFE")
        reg = {"schema": "filmcraft.asset_register.v1", "project_id": "closing-hour", "assets": [{"id": "A-001", "name": "Oak", "kind": "texture", "sha256": "a" * 64, "source": {"type": "own"}, "rights": {"status": "cleared"}}]}
        d = copy.deepcopy(self.a); d["style"]["textures"][0]["asset_id"] = "A-001"
        am = aexp.asset_manifest(self.ctx, d, reg, {"a" * 64: True})
        self.assertEqual(validate(am, "filmcraft.asset_reference_manifest.v1"), []); self.assertEqual(am["summary"]["assets"], 1)
        self.assertEqual(am["assets"][0]["dreambox_hint"]["library_kind"], "texture"); self.assertIn("Reference only", am["assets"][0]["dreambox_hint"]["copy_policy"])
        self.assertEqual(len(aexp.prop_csv(self.a).strip().split("\n")), len(self.a["props"]) + 1)


if __name__ == "__main__":
    unittest.main()
