"""CB2B engine tests: the Lighting craft (plans, shot adjustments, continuity checks, impact, exports) without a server."""
import copy
import csv
import io
import unittest

from app.core import execute, get_fixture
from app.crafts.lighting import exports as lexp
from app.crafts.lighting import geo, impact, plan as lpl
from app.hashing import sha256
from app.validation import validate

PLAN_SCHEMA = "filmcraft.lighting_plan.v1"


def sp_artifact(doc=None):
    return execute("screenwriting", doc or copy.deepcopy(get_fixture("screenwriting", "screenplay")))["artifact"]


def plan_for(sp, approach="intimate"):
    return execute("direction", {"screenplay": sp, "scene_id": "SC-001", "approach": {"preset": approach}})["artifact"]


def art_for(sp, plan, preset):
    return execute("art_direction", {"screenplay": sp, "scene_id": "SC-001", "preset": preset, "direction_plan": plan})["artifact"]


def light(sp, art, plan, preset="warm_naturalistic", **extra):
    payload = {"screenplay": sp, "scene_id": "SC-001", "art_direction": art, "preset": preset, **extra}
    if plan is not None:
        payload["direction_plan"] = plan
    return execute("lighting", payload)["artifact"]


def edited(sp, art, plan, doc, **extra):
    d = copy.deepcopy(doc)
    d.pop("analysis", None)
    payload = {"screenplay": sp, "scene_id": "SC-001", "art_direction": art, "light": d, **extra}
    if plan is not None:
        payload["direction_plan"] = plan
    return execute("lighting", payload)["artifact"]


def issues(doc, rule=None, severity=None):
    return [i for i in doc["analysis"]["issues"] if (rule is None or i["rule"] == rule) and (severity is None or i["severity"] == severity)]


def lamp(doc, lid):
    return next(l for l in doc["lights"] if l["id"] == lid)


class LightingEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp = sp_artifact()
        cls.plan = plan_for(cls.sp)
        cls.art_a = art_for(cls.sp, cls.plan, "warm_nostalgia")
        cls.art_b = art_for(cls.sp, cls.plan, "emotional_distance")
        cls.a = light(cls.sp, cls.art_a, cls.plan, "warm_naturalistic")
        cls.b = light(cls.sp, cls.art_b, cls.plan, "cool_dramatic")

    # ---- 1. drafting and the shape of a plan ------------------------------------------------------------------------------
    def test_drafts_are_valid_and_tied_to_stable_ids(self):
        for d in (self.a, self.b):
            self.assertEqual(validate(d, PLAN_SCHEMA), [])
            self.assertEqual(d["scene_id"], "SC-001")
            shots = {s["shot_id"] for s in self.plan["shots"]}
            self.assertTrue({a["shot_id"] for a in d["adjustments"]} <= shots)
            self.assertEqual(set(d["source"]["plan"]["camera_hashes"]), shots)                    # every shot's camera is recorded
        objs = {o["id"] for o in self.art_a["layout"]["objects"]}
        for l in self.a["lights"]:
            self.assertTrue(l["motivated_by"] in objs or l["motivated_by"] == "")
        self.assertEqual(lamp(self.a, "L-LAMP")["practical_object_id"], "D-LAMP")                  # the practical is attached to the art treatment's own lamp
        self.assertEqual(lamp(self.b, "L-LAMP")["practical_object_id"], "D-FLOORLAMP")

    def test_all_roles_sources_and_parameters_are_supported(self):
        roles = {l["role"] for l in self.a["lights"]} | {l["role"] for l in self.b["lights"]}
        self.assertTrue({"key", "fill", "backlight", "practical", "ambient", "motivated"} <= roles)
        self.assertEqual({l["source"] for l in self.a["lights"]}, {"natural", "artificial"})
        for k in ("x", "y", "height_m", "rotation_deg", "tilt_deg", "intensity", "color_temp_k", "beam_angle_deg", "softness", "falloff", "enabled"):
            self.assertIn(k, self.a["lights"][0])
        self.assertEqual(self.a["conditions"]["time_of_day"], "night")                              # from the slugline and the art design
        self.assertTrue(self.a["conditions"]["mood_words"])

    def test_works_without_a_direction_plan(self):
        d = light(self.sp, self.art_a, None, "warm_naturalistic")
        self.assertEqual(validate(d, PLAN_SCHEMA), [])
        self.assertEqual(d["adjustments"], []); self.assertEqual(d["analysis"]["shots"], [])

    def test_wrong_scene_and_bad_values_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "different scene"):
            execute("lighting", {"screenplay": self.sp, "scene_id": "SC-001", "art_direction": {**self.art_a, "scene_id": "SC-009"}, "preset": "blank"})
        for field, value, msg in (("intensity", 1.5, "intensity"), ("color_temp_k", 500, "colour temperature"), ("beam_angle_deg", 2, "beam angle"), ("softness", -1, "softness")):
            d = copy.deepcopy(self.a); d["lights"][0][field] = value
            with self.assertRaisesRegex(ValueError, msg):
                edited(self.sp, self.art_a, self.plan, d)
        d = copy.deepcopy(self.a); d["lights"][1]["id"] = d["lights"][0]["id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            edited(self.sp, self.art_a, self.plan, d)
        d = copy.deepcopy(self.a); d["adjustments"][0]["shot_id"] = "SC-001-S99"
        with self.assertRaisesRegex(ValueError, "not a shot"):
            edited(self.sp, self.art_a, self.plan, d)

    # ---- 2. editing: positions and saved parameters persist --------------------------------------------------------------------
    def test_manual_positioning_rotation_and_parameters_are_kept_and_reanalysed(self):
        d = copy.deepcopy(self.a)
        k = lamp(d, "L-KEY")
        k.update(x=0.31, y=0.77, rotation_deg=95.5, intensity=0.6, color_temp_k=3300, beam_angle_deg=55, softness=0.4, height_m=2.4, falloff={"mode": "linear", "range_m": 6.0})
        out = edited(self.sp, self.art_a, self.plan, d)
        kk = lamp(out, "L-KEY")
        self.assertEqual((kk["x"], kk["y"], kk["rotation_deg"], kk["intensity"], kk["color_temp_k"], kk["beam_angle_deg"], kk["softness"], kk["height_m"]), (0.31, 0.77, 95.5, 0.6, 3300, 55, 0.4, 2.4))
        self.assertEqual(kk["falloff"], {"mode": "linear", "range_m": 6.0})
        self.assertEqual(out["analysis"]["metrics"]["key_kelvin"], round((3300 + lamp(self.a, "L-DOOR")["color_temp_k"]) / 2))                              # the analysis follows the edit
        self.assertNotEqual(out["analysis"]["plan_hash"], self.a["analysis"]["plan_hash"])

    def test_rotation_wraps_and_deterministic(self):
        d = copy.deepcopy(self.a); lamp(d, "L-KEY")["rotation_deg"] = 360
        self.assertEqual(lamp(edited(self.sp, self.art_a, self.plan, d), "L-KEY")["rotation_deg"], 0)
        again = light(self.sp, self.art_a, self.plan, "warm_naturalistic")
        self.assertEqual(sha256(again), sha256(self.a))

    # ---- 3. the two treatments ------------------------------------------------------------------------------------------------
    def test_treatments_differ_in_measured_settings_and_in_stated_effect(self):
        ma, mb = self.a["analysis"]["metrics"], self.b["analysis"]["metrics"]
        self.assertLess(ma["mean_kelvin"], 3500); self.assertGreater(mb["mean_kelvin"], 5000)
        self.assertGreater(ma["key_softness"], 0.6); self.assertLess(mb["key_softness"], 0.35)
        self.assertGreater(mb["key_fill_ratio"], ma["key_fill_ratio"] * 1.5)
        self.assertGreater(mb["shadow_fraction"], ma["shadow_fraction"] + 0.2)
        ta, tb = " ".join(r["text"] for r in self.a["analysis"]["reading"]), " ".join(r["text"] for r in self.b["analysis"]["reading"])
        self.assertIn("intimate", ta); self.assertIn("detached", tb)
        for r in self.a["analysis"]["reading"] + self.b["analysis"]["reading"]:
            self.assertTrue(r["because"])                                                          # every reading says what it rests on
        self.assertIn("not measured light", self.a["analysis"]["model_note"])                      # approximations are labelled

    # ---- 4. illumination model ------------------------------------------------------------------------------------------------------
    def test_illumination_falls_with_distance_angle_and_solid_pieces(self):
        stage = {"width_m": 6.0, "depth_m": 5.0}
        base = lpl._light_in({"id": "T", "name": "t", "role": "key", "source": "artificial", "x": 0.5, "y": 0.9, "rotation_deg": 180, "intensity": 1.0, "color_temp_k": 3200, "beam_angle_deg": 40, "softness": 0.2,
                              "falloff": {"mode": "inverse_square", "range_m": 12}}, 0)
        near, _ = geo.light_at(base, stage, (0.5, 0.7), ())
        far, _ = geo.light_at(base, stage, (0.5, 0.2), ())
        off, _ = geo.light_at(base, stage, (0.95, 0.7), ())
        self.assertGreater(near, far); self.assertGreater(far, 0); self.assertEqual(off, 0.0)
        blocked, was = geo.light_at(base, stage, (0.5, 0.5), [(0.4, 0.6, 0.6, 0.7)])
        clear, _ = geo.light_at(base, stage, (0.5, 0.5), ())
        self.assertTrue(was); self.assertLess(blocked, clear)
        self.assertEqual(geo.light_at({**base, "enabled": False}, stage, (0.5, 0.7), ())[0], 0.0)

    # ---- 5. shot adjustments keep the shared setup ----------------------------------------------------------------------------
    def test_shot_adjustments_apply_to_one_shot_and_leave_the_scene_setup_alone(self):
        d = copy.deepcopy(self.a)
        adj = next(a for a in d["adjustments"] if any(c["light_id"] == "L-KEY" and "softness" in c for c in a["changes"]))
        lights, got = lpl.resolve_shot(d, adj["shot_id"])
        self.assertEqual(lamp({"lights": lights}, "L-KEY")["softness"], 1.0)
        self.assertTrue(lamp({"lights": lights}, "L-KEY")["adjusted"])
        other = next(s["shot_id"] for s in self.plan["shots"] if s["shot_id"] not in {a["shot_id"] for a in d["adjustments"]})
        self.assertEqual(lamp({"lights": lpl.resolve_shot(d, other)[0]}, "L-KEY")["softness"], lamp(d, "L-KEY")["softness"])
        self.assertEqual(lamp(d, "L-KEY")["softness"], 0.8)                                       # the scene setup itself was not modified
        added = {"id": "L-EXTRA", **{k: v for k, v in lamp(d, "L-FILL").items() if k != "id"}}
        d["adjustments"].append({"id": "ADJ-X", "shot_id": other, "reason": "extra bounce", "changes": [], "added_lights": [added], "status": "proposed"})
        out = edited(self.sp, self.art_a, self.plan, d)
        self.assertIn("L-EXTRA", next(r for r in out["analysis"]["shots"] if r["shot_id"] == other)["lights_on"])
        self.assertNotIn("L-EXTRA", [l["id"] for l in out["lights"]])

    # ---- 6. continuity ---------------------------------------------------------------------------------------------------------------
    def test_a_clean_draft_has_nothing_that_needs_attention(self):
        self.assertEqual(self.a["analysis"]["readiness"]["attention"], 0, [i["message"] for i in issues(self.a, severity="attention")])

    def test_colour_and_direction_jumps_between_related_shots_are_caught(self):
        d = copy.deepcopy(self.a)
        s1, s2 = self.plan["shots"][4]["shot_id"], self.plan["shots"][5]["shot_id"]
        d["adjustments"] = [a for a in d["adjustments"] if a["shot_id"] not in (s1, s2)]
        d["adjustments"].append({"id": "ADJ-JUMP", "shot_id": s2, "reason": "", "changes": [{"light_id": "L-KEY", "color_temp_k": 5600, "x": 0.1, "y": 0.2, "rotation_deg": 90}], "added_lights": [], "status": "proposed"})
        out = edited(self.sp, self.art_a, self.plan, d)
        self.assertTrue(issues(out, "colour_jump", "attention"))
        self.assertTrue(issues(out, "key_direction_jump"))
        d["adjustments"][-1]["reason"] = "The lamp is switched for a street light"                    # a stated reason is advice, not an alarm
        out2 = edited(self.sp, self.art_a, self.plan, d)
        self.assertFalse(issues(out2, "colour_jump", "attention")); self.assertTrue(issues(out2, "colour_jump", "note"))

    def test_time_of_day_conflicts(self):
        d = copy.deepcopy(self.a); d["conditions"]["time_of_day"] = "day"
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "time_of_day_mismatch", "attention"))      # the art design says night
        d = copy.deepcopy(self.a); sun = lamp(d, "L-DOOR"); sun["kind"] = "sun"
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "sun_at_night", "attention"))
        d = copy.deepcopy(self.a); lamp(d, "L-DOOR")["color_temp_k"] = 12000
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "natural_colour"))

    def test_source_placement_and_set_geometry_conflicts(self):
        d = copy.deepcopy(self.a)
        lamp(d, "L-LAMP")["x"], lamp(d, "L-LAMP")["y"] = 0.2, 0.7
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "practical_moved", "attention"))              # the practical left its lamp
        d = copy.deepcopy(self.a); lamp(d, "L-KEY")["motivated_by"] = "P-WINDOW"
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "unknown_object", "attention"))
        d = copy.deepcopy(self.a); counter = next(o for o in self.art_a["layout"]["objects"] if o["id"] == "P-COUNTER")
        lamp(d, "L-FILL")["x"], lamp(d, "L-FILL")["y"] = counter["x"], counter["y"]
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "light_inside_set", "attention"))
        d = copy.deepcopy(self.a); lamp(d, "L-RIM")["intensity"] = 0.0; lamp(d, "L-FILL")["rotation_deg"] = 0; lamp(d, "L-FILL")["beam_angle_deg"] = 5; lamp(d, "L-FILL")["x"] = 0.05; lamp(d, "L-FILL")["y"] = 0.05
        self.assertTrue(issues(edited(self.sp, self.art_a, self.plan, d), "light_lights_nothing"))

    def test_a_fixture_in_a_wide_shot_is_found_and_the_draft_already_raises_it(self):
        d = copy.deepcopy(self.a); d["adjustments"] = []
        out = edited(self.sp, self.art_a, self.plan, d)
        wide = issues(out, "fixture_in_frame", "attention")
        self.assertTrue(wide, "without shot adjustments some wide shot should see a fixture")
        self.assertEqual(issues(self.a, "fixture_in_frame"), [])                                  # the drafted adjustments keep fixtures out of frame
        raised = [c for a in self.a["adjustments"] for c in a["changes"] if "height_m" in c]
        self.assertTrue(raised and all(c["height_m"] <= 4.5 for c in raised))

    def test_movement_that_leaves_the_light_is_reported_and_can_be_accepted_explicitly(self):
        plan2 = copy.deepcopy(self.plan)
        b = next(b for b in plan2["blocking"] if b["beat_id"] == "SC-001-B3")
        ch = next(c for c in b["characters"] if c["character_id"] == "C-001")
        ch["end"] = {"x": 0.96, "y": 0.95}; ch["path"] = [ch["start"], ch["end"]]
        d = copy.deepcopy(self.b)                                                                   # the hard, narrow cool plan
        out = edited(self.sp, self.art_b, plan2, d)
        gone = issues(out, "moves_out_of_light") + issues(out, "moves_into_shadow")
        self.assertTrue(gone, "Nila walking into a dark corner should be reported")
        self.assertTrue(all(i["fix"] for i in gone))                                              # every warning says how to recover
        att = issues(out, "moves_out_of_light", "attention")
        if att:
            shot = att[0]["shot_id"]
            d2 = copy.deepcopy(d)
            adj = next((a for a in d2["adjustments"] if a["shot_id"] == shot), None)
            if adj is None:
                adj = {"id": "ADJ-ACC", "shot_id": shot, "reason": "She leaves the light on purpose", "changes": [], "added_lights": [], "status": "proposed"}
                d2["adjustments"].append(adj)
            adj["accepted_findings"] = ["moves_out_of_light"]
            out2 = edited(self.sp, self.art_b, plan2, d2)
            self.assertFalse([i for i in issues(out2, "moves_out_of_light", "attention") if i["shot_id"] == shot])
            self.assertTrue([i for i in issues(out2, "moves_out_of_light", "note") if i.get("accepted")])

    # ---- 7. upstream changes and approval preservation ----------------------------------------------------------------------------
    def test_up_to_date_plan_reports_no_change(self):
        out = impact.compute(self.a, self.sp, self.art_a, self.plan)
        self.assertFalse(out["stale"]); self.assertEqual(out["affected_lights"], [])

    def test_blocking_and_camera_changes_flag_only_the_shots_they_touch(self):
        plan2 = copy.deepcopy(self.plan)
        b = next(b for b in plan2["blocking"] if b["beat_id"] == "SC-001-B4")
        b["characters"][0]["end"] = {"x": 0.2, "y": 0.8}
        out = impact.compute(self.a, self.sp, self.art_a, plan2)
        self.assertEqual(out["blocking_beats"], ["SC-001-B4"])
        beat_shots = {s["shot_id"] for s in self.plan["shots"] if s["beat_id"] == "SC-001-B4"}
        flagged = {a["shot_id"] for a in self.a["adjustments"] if a["id"] in out["affected_adjustments"]}
        self.assertTrue(flagged <= beat_shots)
        plan3 = copy.deepcopy(self.plan)
        sh = plan3["shots"][3]; sh["previz"]["camera_position"]["x"] += 0.2
        self.assertEqual(impact.compute(self.a, self.sp, self.art_a, plan3)["changed_shots"], [sh["shot_id"]])

    def test_an_art_change_flags_the_lights_tied_to_that_set_piece(self):
        art2 = copy.deepcopy(self.art_a)
        o = next(o for o in art2["layout"]["objects"] if o["id"] == "D-LAMP"); o["x"] = 0.5
        out = impact.compute(self.a, self.sp, art2, self.plan)
        self.assertEqual(out["changed_objects"], ["D-LAMP"])
        self.assertIn("L-LAMP", out["affected_lights"]); self.assertIn("L-KEY", out["affected_lights"])              # the key is motivated by that lamp
        self.assertNotIn("L-FILL", out["affected_lights"])

    def test_rebase_returns_affected_items_to_review_and_leaves_the_rest_and_the_original(self):
        d = copy.deepcopy(self.a)
        for l in d["lights"]:
            l["status"] = "approved"
        for a in d["adjustments"]:
            a["status"] = "approved"
        approved = edited(self.sp, self.art_a, self.plan, d)
        art2 = copy.deepcopy(self.art_a); next(o for o in art2["layout"]["objects"] if o["id"] == "D-LAMP")["x"] = 0.5
        rebased, imp = impact.rebase(approved, self.sp, art2, self.plan)
        self.assertEqual(lamp(rebased, "L-LAMP")["status"], "needs_review"); self.assertEqual(lamp(rebased, "L-LAMP")["previous_status"], "approved")
        self.assertEqual(lamp(rebased, "L-FILL")["status"], "approved")
        self.assertEqual(lamp(approved, "L-LAMP")["status"], "approved")                              # the approved original is untouched
        out = edited(self.sp, art2, self.plan, rebased)
        self.assertGreaterEqual(out["analysis"]["readiness"]["pending_review"], 2)
        self.assertFalse(impact.compute(out, self.sp, art2, self.plan)["stale"])                       # after the rebase the plan is current

    def test_a_script_change_flags_the_adjustments_of_the_changed_beat(self):
        doc = copy.deepcopy(get_fixture("screenwriting", "screenplay"))
        doc["revision"] = {"number": 2, "note": "ticket line"}
        doc["scenes"][0]["elements"][14]["text"] = "She stops. He nods at the book. She opens it. Inside: a ticket to her city, two years old, never used."
        sp2 = sp_artifact(doc)
        out = impact.compute(self.a, sp2, self.art_a, self.plan)
        self.assertTrue(out["stale"]); self.assertTrue(out["changed_beats"])
        beats = {s["shot_id"]: s["beat_id"] for s in self.plan["shots"]}
        for a in self.a["adjustments"]:
            if a["id"] in out["affected_adjustments"]:
                self.assertIn(beats[a["shot_id"]], out["changed_beats"])

    # ---- 8. reusable setups ----------------------------------------------------------------------------------------------------------
    def test_a_setup_can_start_another_plan_and_links_are_cleared_when_the_piece_is_missing(self):
        setup = execute("lighting", {"schema": "filmcraft.lighting_setup.v1", "project_id": "closing-hour",
                                     "setup": {"id": "WARM-ROOM", "name": "Warm room", "lights": copy.deepcopy(self.a["lights"])}})["artifact"]
        self.assertEqual(validate(setup, "filmcraft.lighting_setup.v1"), []); self.assertEqual(setup["analysis"]["lights"], len(self.a["lights"]))
        d = light(self.sp, self.art_b, self.plan, "setup", setup=setup)
        self.assertEqual(d["from_setup"]["setup_id"], "WARM-ROOM")
        self.assertEqual(len(d["lights"]), len(self.a["lights"])); self.assertEqual(d["adjustments"], [])
        self.assertEqual(lamp(d, "L-LAMP")["practical_object_id"], "")                                # the table lamp does not exist in treatment B
        self.assertTrue(any("D-LAMP" in n for n in d["analysis"]["draft_notes"]))
        with self.assertRaisesRegex(ValueError, "unique"):
            dup = copy.deepcopy(setup); dup["setup"]["lights"][1]["id"] = dup["setup"]["lights"][0]["id"]
            execute("lighting", dup)

    # ---- 9. exports -------------------------------------------------------------------------------------------------------------------
    def test_exports_validate_separate_art_from_lighting_and_prepare_later_crafts(self):
        ctx = {"run_id": "r1", "experiment_id": "e1", "exported_at": "2026-11-01T00:00:00.000Z", "app_version": "t", "overrides": [], "approval": {"status": "approved", "reviewer": "DP", "approved_at": "x", "note": ""}}
        ins = lexp.instructions(self.a, self.art_a, self.plan, ctx)
        self.assertEqual(validate(ins, "filmcraft.lighting_instructions.v1"), [])
        self.assertEqual(len(ins["shots"]), len([s for s in self.plan["shots"] if s["status"] != "rejected"]))
        s0 = ins["shots"][0]
        self.assertTrue(s0["camera"]["position"] and s0["lights"] and "metres" in s0["lights"][0])
        m = lexp.lighting_manifest(ctx, self.a, self.art_a, self.plan, self.sp)
        self.assertEqual(validate(m, "filmcraft.lighting_manifest.v1"), [])
        self.assertFalse(m["import_policy"]["auto_import"])
        for section in ("cinematography", "previz", "scene_maker"):
            self.assertIn(section, m["integration"])
        self.assertNotIn("layout", m); self.assertNotIn("props", m); self.assertNotIn("style", m)        # art-direction data is referenced, not copied
        self.assertEqual(m["art_reference"]["treatment_id"], self.art_a["treatment"]["id"])
        rows = list(csv.reader(io.StringIO(lexp.schedule_csv(self.a, self.art_a, self.plan))))
        self.assertEqual(rows[0][:3], ["shot_id", "beat_id", "light_id"]); self.assertGreater(len(rows), len(self.a["lights"]))


if __name__ == "__main__":
    unittest.main()
