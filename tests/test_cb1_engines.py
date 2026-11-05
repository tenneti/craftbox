"""CB1 engine tests: Screenwriting Lab (screenplay.v1) and Direction Lab (direction_plan.v1), no server needed."""
import copy
import unittest

from app.core import execute, get_fixture
from app.crafts.direction import exports as dexp
from app.crafts.direction import impact
from app.crafts.screenwriting import fountain, screenplay
from app.hashing import sha256
from app.validation import validate

PRESETS = ("intimate", "observational")


def authored():
    return copy.deepcopy(get_fixture("screenwriting", "screenplay"))


def processed(doc=None):
    return execute("screenwriting", doc or authored())["artifact"]


def direct(sp, approach="intimate", plan=None, scene_id="SC-001"):
    payload = {"screenplay": sp, "scene_id": scene_id}
    payload["plan" if plan else "approach"] = plan or {"preset": approach}
    return execute("direction", payload)["artifact"]


def issues(plan, rule=None, severity=None):
    return [i for i in plan["analysis"]["issues"] if (rule is None or i["rule"] == rule) and (severity is None or i["severity"] == severity)]


class ScreenwritingLabTests(unittest.TestCase):
    def test_sample_scene_is_valid_and_within_60_to_90_seconds(self):
        self.assertEqual(validate(authored(), "filmcraft.screenplay.v1"), [])
        sp = processed()
        self.assertEqual(validate(sp, "filmcraft.screenplay.v1"), [])
        san = sp["analysis"]["scenes"][0]
        self.assertTrue(60 <= san["estimated_seconds"] <= 90, san["estimated_seconds"])
        self.assertEqual(san["duration_frames"], round(san["estimated_seconds"] * 24))
        self.assertEqual(len(sp["scenes"][0]["elements"]), 24)
        self.assertEqual(len(san["beats"]), 7)
        self.assertEqual(sp["scenes"][0]["slugline"], "INT. PAGE & CANDLE BOOKSHOP - NIGHT")
        self.assertEqual({c["id"] for c in sp["characters"]}, {"C-001", "C-002"})

    def test_beats_tile_the_scene_and_follow_three_act_balance(self):
        san = processed()["analysis"]["scenes"][0]
        self.assertAlmostEqual(sum(b["duration_seconds"] for b in san["beats"]), san["estimated_seconds"], places=1)
        shares = {m["act"]: m["share"] for m in san["micro_structure"]}
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=2)
        self.assertTrue(abs(shares[2] - 0.5) < 0.1)
        self.assertEqual(san["pacing"]["label"], "slow")
        curve = [p["intensity"] for p in san["intensity_curve"]]
        self.assertEqual(curve, [2, 3, 5, 7, 8, 10, 6])

    def test_deterministic_and_does_not_mutate_input(self):
        doc = authored()
        before = copy.deepcopy(doc)
        a, b = processed(doc), processed(doc)
        self.assertEqual(doc, before)
        self.assertEqual(sha256(a), sha256(b))

    def test_scene_card_mode_still_works(self):
        r = execute("screenwriting", get_fixture("screenwriting"))
        self.assertEqual(r["artifact"]["schema"], "filmcraft.scene.v1")

    def test_integrity_errors_fail_clearly(self):
        def broken(mutate):
            doc = authored(); mutate(doc)
            with self.assertRaises(ValueError) as ctx:
                execute("screenwriting", doc)
            return str(ctx.exception)
        self.assertIn("duplicate element id", broken(lambda d: d["scenes"][0]["elements"][1].update(id="SC-001-E01")))
        self.assertIn("known character", broken(lambda d: d["scenes"][0]["elements"][2].update(character_id="C-999")))
        self.assertIn("unknown element", broken(lambda d: d["scenes"][0]["beats"][0]["element_ids"].append("NOPE")))
        self.assertIn("two beats", broken(lambda d: d["scenes"][0]["beats"][1]["element_ids"].append("SC-001-E01")))
        self.assertIn("unknown sequence", broken(lambda d: d["scenes"][0].update(sequence_id="SEQ-9")))
        self.assertIn("unknown scene", broken(lambda d: d["sequences"][0]["scene_ids"].append("SC-404")))
        self.assertIn("duplicate character id", broken(lambda d: d["characters"].append(copy.deepcopy(d["characters"][0]))))
        self.assertIn("unknown character", broken(lambda d: d["characters"][0]["relationships"].append({"character_id": "C-404"})))

    def test_schema_rejects_malformed_documents(self):
        doc = authored(); doc["scenes"][0]["heading"]["int_ext"] = "INSIDE"
        self.assertTrue(validate(doc, "filmcraft.screenplay.v1"))
        doc = authored(); doc["scenes"][0]["beats"][0]["intensity"] = 11
        self.assertTrue(validate(doc, "filmcraft.screenplay.v1"))

    def test_speaker_missing_from_scene_characters_is_added_with_a_warning(self):
        doc = authored(); doc["scenes"][0]["characters"] = ["C-001"]
        r = execute("screenwriting", doc)
        self.assertIn("C-002", r["artifact"]["scenes"][0]["characters"])
        self.assertTrue(any("not listed" in w for w in r["warnings"]))

    def test_override_rescales_timings(self):
        doc = authored(); doc["scenes"][0]["estimated_seconds_override"] = 60
        san = processed(doc)["analysis"]["scenes"][0]
        self.assertEqual(san["estimated_seconds"], 60)
        self.assertAlmostEqual(sum(e["duration_seconds"] for e in san["elements"]), 60, delta=0.5)

    def test_hashes_localise_a_script_change_to_the_beat_it_touches(self):
        base = processed()["analysis"]["scenes"][0]
        doc = authored()
        doc["scenes"][0]["elements"][11]["text"] = "It leans toward the door. It has always leaned that way."   # E12, in beat B3
        new = processed(doc)["analysis"]["scenes"][0]
        self.assertNotEqual(base["scene_hash"], new["scene_hash"])
        b0, b1 = {b["id"]: b["hash"] for b in base["beats"]}, {b["id"]: b["hash"] for b in new["beats"]}
        self.assertEqual([k for k in b0 if b0[k] != b1[k]], ["SC-001-B3"])
        e0, e1 = {e["id"]: e["hash"] for e in base["elements"]}, {e["id"]: e["hash"] for e in new["elements"]}
        self.assertEqual([k for k in e0 if e0[k] != e1[k]], ["SC-001-E12"])

    def test_revision_note_does_not_change_scene_hashes(self):
        doc = authored(); doc["revision"] = {"number": 7, "note": "just a note"}
        self.assertEqual(processed()["analysis"]["scenes"][0]["scene_hash"], processed(doc)["analysis"]["scenes"][0]["scene_hash"])

    def test_work_in_progress_skeleton_is_valid_and_warns_not_fails(self):
        sk = screenplay.skeleton({"title": "Night Train", "logline": "Two strangers share a cabin.", "location": "Train cabin", "time": "Night",
                                  "characters": [{"name": "Isha", "want": "silence"}, {"name": "Kabir", "want": "company"}],
                                  "emotional_arc": {"start": "wary", "end": "warm"}})
        self.assertEqual(validate(sk, "filmcraft.screenplay.v1"), [])
        r = execute("screenwriting", sk)
        self.assertEqual(r["artifact"]["project"]["id"], "night-train")
        self.assertEqual(len(sk["scenes"][0]["beats"]), 6)
        self.assertTrue(any("no script elements" in w for w in r["warnings"]))
        with self.assertRaises(ValueError):
            screenplay.skeleton({"title": "", "characters": [{"name": "A"}]})
        with self.assertRaises(ValueError):
            screenplay.skeleton({"title": "X", "characters": []})


class FountainTests(unittest.TestCase):
    def test_json_to_script_to_json_preserves_ids_and_text(self):
        doc = authored()
        text = fountain.export(doc)
        self.assertIn("INT. PAGE & CANDLE BOOKSHOP - NIGHT #SC-001#", text)
        self.assertIn("\nNILA\n", text)
        self.assertIn("(too lightly)", text)
        back = fountain.parse(text)
        self.assertEqual(validate(back, "filmcraft.screenplay.v1"), [])
        self.assertEqual(back["project"]["id"], doc["project"]["id"])
        self.assertEqual([(c["id"], c["name"]) for c in back["characters"]], [(c["id"], c["name"]) for c in doc["characters"]])
        a, b = doc["scenes"][0], back["scenes"][0]
        self.assertEqual(b["id"], a["id"])
        self.assertEqual(b["heading"]["location"], a["heading"]["location"].upper())
        for k in ("synopsis", "objective", "conflict", "turning_point", "outcome"):
            self.assertEqual(b[k], a[k], k)
        self.assertEqual([(e["type"], e["character_id"], e["text"]) for e in b["elements"]],
                         [(e["type"], e.get("character_id"), e["text"]) for e in a["elements"]])
        self.assertEqual(set(b["characters"]), {"C-001", "C-002"})
        execute("screenwriting", back)   # the imported script is a runnable screenplay

    def test_plain_script_without_metadata_imports(self):
        text = "INT. KITCHEN - DAY\n\nSteam rises from a kettle. MAYA waits.\n\nMAYA\n(quietly)\nHe is late again.\n\nDEV\nTraffic.\n\nCUT TO:\n\nEXT. STREET - NIGHT\n\nRain.\n"
        doc = fountain.parse(text, project_id="kitchen-test", title="Kitchen")
        self.assertEqual([s["id"] for s in doc["scenes"]], ["SC-001", "SC-002"])
        self.assertEqual([c["id"] for c in doc["characters"]], ["C-001", "C-002"])
        kinds = [e["type"] for e in doc["scenes"][0]["elements"]]
        self.assertEqual(kinds, ["action", "parenthetical", "dialogue", "dialogue", "transition"])
        self.assertEqual(validate(doc, "filmcraft.screenplay.v1"), [])
        execute("screenwriting", doc)

    def test_bad_scripts_fail_clearly(self):
        with self.assertRaises(ValueError):
            fountain.parse("   ")
        with self.assertRaises(ValueError):
            fountain.parse("Just some words with no scene heading.")


class DirectionLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp = processed()
        cls.plans = {p: direct(cls.sp, p) for p in PRESETS}

    def test_requires_a_processed_screenplay(self):
        with self.assertRaises(ValueError):
            execute("direction", {"screenplay": authored(), "scene_id": "SC-001", "approach": {"preset": "intimate"}})
        with self.assertRaises(ValueError):
            execute("direction", {"screenplay": self.sp, "scene_id": "SC-404", "approach": {"preset": "intimate"}})
        with self.assertRaises(ValueError):
            execute("direction", {"screenplay": self.sp, "scene_id": "SC-001", "approach": {"preset": "nonsense"}})

    def test_both_presets_produce_valid_clean_plans(self):
        for name, plan in self.plans.items():
            self.assertEqual(validate(plan, "filmcraft.direction_plan.v1"), [], name)
            self.assertEqual(issues(plan, severity="error"), [], name)
            self.assertEqual(plan["analysis"]["readiness"]["errors"], 0)
            self.assertAlmostEqual(plan["analysis"]["total_seconds"], plan["analysis"]["script_seconds"], delta=plan["analysis"]["script_seconds"] * 0.1)

    def test_deterministic(self):
        again = direct(self.sp, "intimate")
        self.assertEqual(sha256(again), sha256(self.plans["intimate"]))

    def test_every_shot_has_a_purpose_and_every_beat_and_line_is_covered(self):
        for name, plan in self.plans.items():
            for s in plan["shots"]:
                self.assertTrue(s["purpose"] and len(s["purpose_note"]) >= 8, (name, s["shot_id"]))
                self.assertEqual(s["status"], "proposed")
            cov = plan["analysis"]["coverage"]
            self.assertEqual(cov["uncovered_beats"], [], name)
            self.assertEqual(cov["uncovered_dialogue"], [], name)

    def test_shots_have_variety_not_one_framing(self):
        for name, plan in self.plans.items():
            v = plan["analysis"]["variety"]
            self.assertGreaterEqual(len(v["sizes"]), 4, name)
            self.assertLessEqual(v["longest_same_size_run"], 2, name)
            self.assertGreaterEqual(v["variety_score"], 0.6, name)
            self.assertGreaterEqual(len(plan["analysis"]["purposes"]), 5, name)
            self.assertEqual(issues(plan, "variety"), [], name)

    def test_the_two_approaches_are_genuinely_different(self):
        a, b = self.plans["intimate"], self.plans["observational"]
        self.assertGreater(len(a["shots"]), len(b["shots"]) * 1.4)
        self.assertLess(a["analysis"]["avg_shot_seconds"], b["analysis"]["avg_shot_seconds"] * 0.7)
        self.assertGreater(a["analysis"]["variety"]["close_ups"], b["analysis"]["variety"]["close_ups"])
        self.assertIn("handheld", a["analysis"]["variety"]["movements"])
        self.assertNotIn("handheld", b["analysis"]["variety"]["movements"])
        self.assertIn("B", {s["camera_side"] for s in a["shots"]})            # A crosses the line once, with a neutral shot
        self.assertEqual({s["camera_side"] for s in b["shots"]}, {"A"})
        self.assertNotEqual(a["interpretation"]["directorial_intent"], b["interpretation"]["directorial_intent"])

    def test_axis_is_crossed_only_through_neutral_shots(self):
        shots = self.plans["intimate"]["shots"]
        sides = [s["camera_side"] for s in shots]
        for i in range(1, len(sides)):
            if {sides[i - 1], sides[i]} == {"A", "B"}:
                self.fail("direct A<->B cut without a neutral shot")
        self.assertIn("axis", sides)

    def test_blocking_has_entrance_exit_paths_and_eyelines(self):
        plan = self.plans["intimate"]
        first = {c["character_id"]: c for c in plan["blocking"][0]["characters"]}
        self.assertIsNotNone(first["C-001"]["entrance"])        # Nila enters in beat 1
        self.assertIsNone(first["C-002"]["entrance"])
        last = {c["character_id"]: c for c in plan["blocking"][-1]["characters"]}
        self.assertIsNotNone(last["C-001"]["exit"])
        climax = {c["character_id"]: c for c in plan["blocking"][5]["characters"]}
        self.assertTrue(climax["C-001"]["eyeline"]["target"] == "C-002" and climax["C-002"]["eyeline"]["target"] == "C-001")
        gap = lambda b: abs(b["characters"][0]["end"]["x"] - b["characters"][1]["end"]["x"])
        self.assertLess(gap(plan["blocking"][5]), gap(plan["blocking"][1]))   # they close the distance as intensity rises
        self.assertTrue(all(len(c["path"]) >= 2 for b in plan["blocking"] for c in b["characters"]))

    def test_previz_and_storyboard_metadata_present(self):
        s = self.plans["intimate"]["shots"][0]
        self.assertIn("camera_position", s["previz"]); self.assertGreater(s["previz"]["fov_deg"], 10)
        self.assertTrue(s["storyboard"]["description"])

    # ---- editing a plan: validation of manual changes ----------------------------------------------------------
    def edit(self, mutate, approach="intimate"):
        plan = copy.deepcopy(self.plans[approach]); mutate(plan)
        return direct(self.sp, plan=plan)

    def test_crossing_the_line_without_a_neutral_shot_is_an_error(self):
        out = self.edit(lambda p: p["shots"][4].update(camera_side="B"))
        errs = issues(out, "axis", "error")
        self.assertTrue(errs and "SC-001-S05" in errs[0]["shot_ids"])
        self.assertIn("180", errs[0]["message"])
        self.assertFalse(out["analysis"]["readiness"]["ready_for_approval"])

    def test_motivated_axis_cross_is_not_flagged(self):
        def fix(p):
            p["shots"][4].update(camera_side="B", axis_cross={"motivated": True, "reason": "Nila walks across the line"})
            p["shots"][5].update(camera_side="B"); p["shots"][6].update(camera_side="B"); p["shots"][7].update(camera_side="B")
            p["shots"][8].update(camera_side="B"); p["shots"][9].update(camera_side="B"); p["shots"][10].update(camera_side="B")
            p["shots"][11].update(camera_side="B"); p["shots"][12].update(camera_side="B")
            for s in p["shots"][13:17]:
                s["camera_side"] = "B"
            p["shots"][17].update(camera_side="axis")
            for s in p["shots"][18:20]:
                s["camera_side"] = "B"
        out = self.edit(fix)
        self.assertEqual([i for i in issues(out, "axis", "error") if i["shot_ids"][0] == "SC-001-S05"], [])

    def test_eyelines_that_do_not_meet_are_flagged(self):
        def face_same_way(p):
            for c in p["blocking"][2]["characters"]:
                c["facing"] = "screen_right"
        out = self.edit(face_same_way)
        self.assertTrue(issues(out, "eyeline"))

    def test_position_jump_without_movement_is_an_error(self):
        def jump(p):
            c = p["blocking"][3]["characters"][0]
            c["start"] = {"x": min(1, c["start"]["x"] + 0.3), "y": c["start"]["y"]}
        out = self.edit(jump)
        self.assertTrue(any("jumps position" in i["message"] for i in issues(out, "blocking", "error")))

    def test_reappearing_after_exit_and_double_entrance_are_errors(self):
        def mutate(p):
            p["blocking"][1]["characters"][0]["entrance"] = {"from": "P-DOOR"}   # enters twice
        out = self.edit(mutate)
        self.assertTrue(any("already on stage" in i["message"] for i in issues(out, "blocking", "error")))

    def test_dropping_shots_creates_coverage_gaps(self):
        def drop(p):
            p["shots"] = [s for s in p["shots"] if s["beat_id"] != "SC-001-B4"]
        out = self.edit(drop)
        self.assertEqual(out["analysis"]["coverage"]["uncovered_beats"], ["SC-001-B4"])
        self.assertTrue(issues(out, "coverage", "error"))
        self.assertIn("SC-001-E14", out["analysis"]["coverage"]["uncovered_dialogue"])

    def test_repetitive_framing_is_flagged(self):
        def repeat(p):
            for s in p["shots"]:
                s.update(size="MS", angle="eye", movement="static", framing="single", subject=["C-001"], camera_side="A")
        out = self.edit(repeat)
        self.assertTrue(issues(out, "variety"))

    def test_rejected_shots_leave_the_timeline_and_manual_reorder_keeps_ids(self):
        def mutate(p):
            p["shots"][1]["status"] = "rejected"
            p["shots"][2], p["shots"][3] = p["shots"][3], p["shots"][2]
        out = self.edit(mutate)
        ids = [t["shot_id"] for t in out["analysis"]["timeline"]]
        self.assertNotIn("SC-001-S02", ids)
        self.assertEqual(ids.index("SC-001-S04"), ids.index("SC-001-S03") - 1)
        self.assertEqual(out["analysis"]["status_summary"]["rejected"], 1)

    def test_hard_rules_raise(self):
        def bad(mutate):
            plan = copy.deepcopy(self.plans["intimate"]); mutate(plan)
            with self.assertRaises(ValueError):
                direct(self.sp, plan=plan)
        bad(lambda p: p["shots"].append(copy.deepcopy(p["shots"][0])))                       # duplicate shot id
        bad(lambda p: p["shots"][0].update(subject=["C-404"]))                                # unknown character
        bad(lambda p: p.update(scene_id="SC-002"))                                            # wrong scene
        plan = copy.deepcopy(self.plans["intimate"]); plan["shots"][0]["purpose_note"] = ""
        self.assertTrue(validate(plan, "filmcraft.direction_plan.v1"))                        # purpose is required by the schema
        plan = copy.deepcopy(self.plans["intimate"]); del plan["shots"][0]["purpose"]
        self.assertTrue(validate(plan, "filmcraft.direction_plan.v1"))

    # ---- script changes propagate without overwriting approved work ------------------------------------------
    def approved_plan(self):
        plan = copy.deepcopy(self.plans["intimate"])
        for s in plan["shots"]:
            s["status"] = "approved"
        return direct(self.sp, plan=plan)

    def test_unchanged_script_is_not_stale(self):
        imp = impact.compute(self.approved_plan(), self.sp)
        self.assertFalse(imp["stale"]); self.assertEqual(imp["affected_shots"], [])

    def test_script_edit_flags_exactly_the_dependent_shots(self):
        doc = authored(); doc["scenes"][0]["elements"][16]["text"] = "The day after you left. I stood on that platform until the lights went out."   # E17
        new_sp = processed(doc)
        plan = self.approved_plan()
        imp = impact.compute(plan, new_sp)
        self.assertTrue(imp["stale"])
        self.assertEqual(imp["changed_elements"], ["SC-001-E17"])
        self.assertEqual(imp["changed_beats"], ["SC-001-B5"])
        hit = {s["shot_id"] for s in plan["shots"] if s["beat_id"] == "SC-001-B5"}
        self.assertEqual(set(imp["affected_shots"]), hit)
        self.assertEqual(set(imp["approved_affected"]), hit)

    def test_rebase_returns_only_affected_shots_to_review_and_leaves_the_original(self):
        doc = authored(); doc["scenes"][0]["elements"][16]["text"] = "I waited on the platform until the train was gone."
        new_sp = processed(doc)
        plan = self.approved_plan()
        original = copy.deepcopy(plan)
        rebased, imp = impact.rebase(plan, new_sp)
        self.assertEqual(plan, original)                                    # nothing overwritten
        out = direct(new_sp, plan=rebased)
        by = {s["shot_id"]: s for s in out["shots"]}
        for s in plan["shots"]:
            if s["beat_id"] == "SC-001-B5":
                self.assertEqual(by[s["shot_id"]]["status"], "needs_review")
                self.assertEqual(by[s["shot_id"]]["previous_status"], "approved")
                self.assertIn("Script changed", by[s["shot_id"]]["review_note"])
            else:
                self.assertEqual(by[s["shot_id"]]["status"], "approved")
        self.assertEqual(out["analysis"]["status_summary"]["needs_review"], len([s for s in plan["shots"] if s["beat_id"] == "SC-001-B5"]))
        self.assertFalse(impact.compute(out, new_sp)["stale"])                # the rebased plan is current again

    def test_removed_beat_orphans_shots_without_deleting_them(self):
        doc = authored()
        sc = doc["scenes"][0]
        sc["beats"] = [b for b in sc["beats"] if b["id"] != "SC-001-B4"]
        new_sp = processed(doc)
        rebased, imp = impact.rebase(self.approved_plan(), new_sp)
        self.assertEqual(imp["removed_beats"], ["SC-001-B4"])
        out = direct(new_sp, plan=rebased)
        orphans = [s for s in out["shots"] if s["beat_id"] == "SC-001-B4"]
        self.assertTrue(orphans and all(s["status"] == "needs_review" for s in orphans))
        self.assertTrue(any("no longer exists" in i["message"] for i in issues(out, "reference", "error")))

    def test_new_dialogue_is_reported_as_unplanned(self):
        doc = authored()
        sc = doc["scenes"][0]
        sc["elements"].insert(21, {"id": "SC-001-E99", "type": "dialogue", "character_id": "C-001", "text": "I know."})
        sc["beats"][5]["element_ids"].insert(2, "SC-001-E99")
        imp = impact.compute(self.approved_plan(), processed(doc))
        self.assertEqual(imp["unplanned_elements"], ["SC-001-E99"])

    # ---- exports ------------------------------------------------------------------------------------------------
    ctx = {"run_id": "r-1", "experiment_id": "e-1", "exported_at": "2026-01-01T00:00:00.000Z", "app_version": "test",
           "approval": {"status": "approved", "reviewer": "T", "approved_at": "2026-01-01T00:00:00.000Z", "note": None}}

    def test_exports_are_valid_and_consistent(self):
        plan = self.approved_plan()
        names = {c["id"]: c["name"] for c in self.sp["characters"]}
        self.assertEqual(validate(dexp.blocking_export(plan, self.sp["scenes"][0]), "filmcraft.blocking.v1"), [])
        listing = dexp.shot_list_export(plan, names)
        self.assertEqual(validate(listing, "filmcraft.shot_list.v1"), [])
        self.assertEqual(len(dexp.shot_list_csv(listing).strip().split("\n")), len(plan["shots"]) + 1)
        sm = dexp.scene_manifest(self.ctx, plan, self.sp)
        self.assertEqual(validate(sm, "filmcraft.scene_manifest.v1"), [])
        self.assertEqual(sm["scene"]["duration_frames"], 2016); self.assertFalse(sm["import_policy"]["auto_import"])
        shm = dexp.shot_manifest(self.ctx, plan, self.sp)
        self.assertEqual(validate(shm, "filmcraft.shot_manifest.v1"), [])
        self.assertEqual(shm["totals"]["shots"], len(plan["shots"]))
        starts = [s["start_frame"] for s in shm["shots"]]
        self.assertEqual(starts, sorted(starts)); self.assertEqual(starts[0], 0)
        self.assertEqual(shm["hashes"]["scene_hash"], sm["hashes"]["scene_hash"])

    def test_shot_manifest_excludes_rejected_and_pending(self):
        plan = copy.deepcopy(self.plans["intimate"])
        for i, s in enumerate(plan["shots"]):
            s["status"] = "approved" if i % 3 else ("rejected" if i % 2 else "proposed")
        plan = direct(self.sp, plan=plan)
        shm = dexp.shot_manifest(self.ctx, plan, self.sp)
        self.assertTrue(all(s["status"] == "approved" for s in shm["shots"]))
        self.assertEqual(set(shm["excluded"]["rejected"]), {s["shot_id"] for s in plan["shots"] if s["status"] == "rejected"})
        self.assertEqual(set(shm["excluded"]["pending"]), {s["shot_id"] for s in plan["shots"] if s["status"] == "proposed"})

    def test_plan_feeds_the_existing_editing_pilot(self):
        names = {c["id"]: c["name"] for c in self.sp["characters"]}
        sp_plan = dexp.shot_plan_export(self.plans["intimate"], names)
        self.assertEqual(validate(sp_plan, "filmcraft.shot_plan.v1"), [])
        edit = execute("editing", {"shot_plan": sp_plan})
        self.assertEqual(edit["artifact"]["total_frames"], sp_plan["total_frames"])
        self.assertEqual(len(edit["artifact"]["clips"]), len(self.plans["intimate"]["shots"]))




class StoryProcessTests(unittest.TestCase):
    """The six-phase story process (guidelines/story-process.md) as rule-based, advice-only checks."""

    def audit(self, mutate=None, drop_story=False):
        doc = authored()
        if drop_story:
            doc.pop("story", None)
        if mutate:
            mutate(doc)
        return execute("screenwriting", doc)["artifact"]["analysis"]["story"]

    def item(self, audit, phase, item_id):
        return next(i for i in audit["phases"][phase - 1]["items"] if i["id"] == item_id)

    def test_every_phase_and_required_input_of_the_process_is_audited(self):
        a = self.audit()
        self.assertEqual([p["phase"] for p in a["phases"]], [1, 2, 3, 4, 5, 6])
        ids = {i["id"] for p in a["phases"] for i in p["items"]}
        for required in ("setting", "protagonist", "antagonist", "core_conflict", "plot", "theme", "minimal", "master_plot",       # phase 1
                         "breach", "hook", "defamiliarization", "vulnerability", "consciousness", "target", "agency",              # phases 2-3
                         "unity", "expectation", "information", "subtext", "circle", "draft", "feedback", "polish", "simulator"):  # phases 4-6
            self.assertIn(required, ids)
        self.assertEqual({i["id"] for i in a["phases"][4]["items"] if i["id"].startswith("labov_")},
                         {f"labov_{k}" for k in ("abstract", "orientation", "complicating_action", "evaluation", "resolution", "coda")})
        self.assertTrue(all(p["helps"] for p in a["phases"]))

    def test_sample_story_passes_phases_1_to_5_and_leaves_revision_honestly_open(self):
        a = self.audit()
        for p in a["phases"][1:5]:
            self.assertEqual(p["ok"], p["total"], p["title"])
        self.assertEqual([i["id"] for i in a["phases"][5]["items"] if i["status"] == "advice"], ["feedback", "polish", "simulator"])
        self.assertEqual(a["overall"]["missing"], 0)
        self.assertEqual(self.item(a, 1, "supporting")["status"], "advice")                       # a two-hander has no supporting cast
        self.assertIn("nothing here blocks", a["overall"]["note"])

    def test_empty_story_is_all_missing_and_never_blocks_the_screenplay(self):
        a = self.audit(drop_story=True)
        self.assertEqual(a["overall"]["total"], 31)
        self.assertGreaterEqual(a["overall"]["missing"], 26)
        self.assertEqual(self.item(a, 6, "draft")["status"], "ok")                                  # the script itself still counts

    def test_hook_timing_is_checked_against_the_script(self):
        self.assertEqual(self.item(self.audit(), 2, "hook")["status"], "ok")
        late = self.audit(lambda d: d["story"]["hook"].update(element_id="SC-001-E24"))
        i = self.item(late, 2, "hook")
        self.assertEqual(i["status"], "advice"); self.assertIn("15", i["message"])
        self.assertEqual(self.item(self.audit(lambda d: d["story"]["hook"].update(element_id="")), 2, "hook")["status"], "advice")

    def test_story_circle_order_is_checked_against_the_beats(self):
        def backwards(d):
            d["story"]["circle"]["you"]["beat_id"] = "SC-001-B7"
        self.assertEqual(self.item(self.audit(backwards), 5, "circle")["status"], "advice")
        def partial(d):
            del d["story"]["circle"]["change"]
        i = self.item(self.audit(partial), 5, "circle")
        self.assertEqual(i["status"], "advice"); self.assertIn("7 of 8", i["message"])

    def test_advice_rules(self):
        cases = {
            ("pillars", "antagonist"): lambda d: d["story"]["pillars"].update(antagonist_id="C-001"),
            ("pillars", "minimal"): lambda d: d["story"]["minimal_narrative"].update(event_2=d["story"]["minimal_narrative"]["event_1"]),
            ("empathy", "vulnerability"): lambda d: d["story"]["empathy"].update(distress_risk="high"),
            ("agency", "agency"): lambda d: d["story"]["agency"]["choices"][0].update(cost=""),
            ("conflict", "information"): lambda d: d["story"]["conflict"]["information_gaps"][0].update(reveal_beat_id="SC-001-B1"),
            ("conflict", "expectation"): lambda d: d["story"]["conflict"]["expectation_gaps"].pop(),
            ("conflict", "subtext"): lambda d: d["scenes"][0].update(estimated_seconds_override=20),   # dialogue far too dense for 20 s
        }
        phase_of = {"pillars": 1, "empathy": 3, "agency": 3, "conflict": 4}
        for (group, item_id), mutate in cases.items():
            self.assertEqual(self.item(self.audit(mutate), phase_of[group], item_id)["status"], "advice", item_id)

    def test_story_answers_do_not_make_plans_stale_but_scene_edits_do(self):
        base = processed()
        plan = direct(base)
        doc = authored(); doc["story"]["pillars"]["theme"] = "A completely different theme, written afterwards."
        edited = processed(doc)
        self.assertNotEqual(base["analysis"]["screenplay_hash"], edited["analysis"]["screenplay_hash"])
        self.assertEqual(base["analysis"]["scenes"][0]["scene_hash"], edited["analysis"]["scenes"][0]["scene_hash"])
        self.assertFalse(impact.compute(plan, edited)["stale"])

    def test_idea_skeleton_prefills_the_pillars(self):
        sk = screenplay.skeleton({"title": "Night Train", "location": "Train cabin", "theme": "Trust", "characters": [{"name": "Isha"}, {"name": "Kabir"}, {"name": "Guard"}]})
        p = sk["story"]["pillars"]
        self.assertEqual((p["setting"], p["protagonist_id"], p["antagonist_id"], p["supporting_ids"], p["theme"]), ("Train cabin", "C-001", "C-002", ["C-003"], "Trust"))
        self.assertEqual(validate(sk, "filmcraft.screenplay.v1"), [])
        a = execute("screenwriting", sk)["artifact"]["analysis"]["story"]
        self.assertEqual(self.item(a, 1, "protagonist")["status"], "ok")

    def test_schema_rejects_unknown_choices(self):
        doc = authored(); doc["story"]["master_plot"] = "nonsense"
        self.assertTrue(validate(doc, "filmcraft.screenplay.v1"))
        doc = authored(); doc["story"]["empathy"]["target"] = "everyone"
        self.assertTrue(validate(doc, "filmcraft.screenplay.v1"))


if __name__ == "__main__":
    unittest.main()
