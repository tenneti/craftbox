"""The shipped sample exports (./samples) must stay valid and in step with the engines."""
import json
import unittest
from pathlib import Path

from app.core import execute, get_fixture
from app.validation import validate

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


@unittest.skipUnless(SAMPLES.is_dir(), "samples not generated (python scripts/make_samples.py)")
class SampleTests(unittest.TestCase):
    def test_every_sample_validates_against_its_schema(self):
        pairs = {"the-closing-hour.screenplay.json": "filmcraft.screenplay.v1", "plan-A-intimate.direction-plan.json": "filmcraft.direction_plan.v1",
                 "plan-B-observational.direction-plan.json": "filmcraft.direction_plan.v1", "plan-A-intimate.blocking.json": "filmcraft.blocking.v1",
                 "plan-B-observational.blocking.json": "filmcraft.blocking.v1", "plan-A-intimate.shot-list.json": "filmcraft.shot_list.v1",
                 "plan-B-observational.shot-list.json": "filmcraft.shot_list.v1", "plan-A-intimate.shot-plan.json": "filmcraft.shot_plan.v1",
                 "plan-B-observational.shot-plan.json": "filmcraft.shot_plan.v1", "plan-A-intimate.scene-manifest.json": "filmcraft.scene_manifest.v1",
                 "plan-A-intimate.shot-manifest.json": "filmcraft.shot_manifest.v1", "plan-B-observational.shot-manifest.json": "filmcraft.shot_manifest.v1",
                 "change-tracking/plan-A.rebased.direction-plan.json": "filmcraft.direction_plan.v1"}
        for name, schema in pairs.items():
            self.assertEqual(validate(load(name), schema), [], name)

    def test_sample_screenplay_matches_the_current_engine(self):
        fresh = execute("screenwriting", get_fixture("screenwriting", "screenplay"))["artifact"]
        shipped = load("the-closing-hour.screenplay.json")
        self.assertEqual(shipped["analysis"]["scenes"][0]["scene_hash"], fresh["analysis"]["scenes"][0]["scene_hash"])
        self.assertEqual(shipped["analysis"]["totals"], fresh["analysis"]["totals"])
        self.assertEqual(get_fixture("direction")["screenplay"]["analysis"]["screenplay_hash"], fresh["analysis"]["screenplay_hash"])

    def test_two_approaches_are_present_and_different(self):
        a, b = load("plan-A-intimate.direction-plan.json"), load("plan-B-observational.direction-plan.json")
        self.assertNotEqual(a["approach"]["id"], b["approach"]["id"])
        self.assertGreater(len(a["shots"]), len(b["shots"]))
        self.assertEqual(a["source"]["scene_hash"], b["source"]["scene_hash"])        # same screenplay, two readings
        cmp_ = load("approaches-A-vs-B.comparison.json")
        self.assertTrue(any(m["differs"] for m in cmp_["metrics"]))

    def test_manifests_are_approved_inert_and_traceable(self):
        for name in ("plan-A-intimate.scene-manifest.json", "plan-A-intimate.shot-manifest.json", "plan-B-observational.shot-manifest.json"):
            m = load(name)
            self.assertFalse(m["import_policy"]["auto_import"], name)
            self.assertEqual(m["approval"]["status"], "approved", name)
            self.assertEqual(m["overrides"], [], name)
            self.assertFalse(m["provenance"]["ai_used"], name)
        shot = load("plan-A-intimate.shot-manifest.json")
        self.assertEqual(shot["excluded"]["rejected"], ["SC-001-S04"])
        self.assertNotIn("SC-001-S04", [s["shot_id"] for s in shot["shots"]])

    def test_change_tracking_sample_shows_dependency_not_overwrite(self):
        imp = load("change-tracking/plan-A.impact.json")
        self.assertTrue(imp["stale"]); self.assertEqual(imp["changed_elements"], ["SC-001-E17"])
        rebased = load("change-tracking/plan-A.rebased.direction-plan.json")
        statuses = {s["shot_id"]: s["status"] for s in rebased["shots"]}
        self.assertEqual({sid for sid, st in statuses.items() if st == "needs_review"}, set(imp["affected_shots"]))
        original = load("plan-A-intimate.direction-plan.json")
        self.assertEqual(sum(1 for s in original["shots"] if s["status"] == "approved"), len(original["shots"]) - 1)   # untouched: all but the one rejected shot

    def test_readable_script_has_ids(self):
        text = (SAMPLES / "the-closing-hour.fountain").read_text(encoding="utf-8")
        self.assertIn("#SC-001#", text); self.assertIn("Characters: C-001=Nila; C-002=Arjun", text)


if __name__ == "__main__":
    unittest.main()
