"""The shipped CB2B sample exports (./samples/light) must stay valid and in step with the engines."""
import csv
import io
import json
import unittest
from pathlib import Path

from app.validation import validate

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "light"
TAGS = ("treatment-A-warm-naturalistic", "treatment-B-cool-dramatic")
ART_ONLY_KEYS = {"layout", "props", "palette", "materials", "textures"}   # art-direction data that must not be copied into lighting files


def load(name):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def keys_anywhere(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from keys_anywhere(v)
    elif isinstance(node, list):
        for v in node:
            yield from keys_anywhere(v)


@unittest.skipUnless(SAMPLES.is_dir(), "samples not generated (python scripts/make_light_samples.py)")
class LightSampleTests(unittest.TestCase):
    def test_every_sample_validates_against_its_schema(self):
        for tag in TAGS:
            for suffix, schema in (("lighting-plan.json", "filmcraft.lighting_plan.v1"), ("lighting-instructions.json", "filmcraft.lighting_instructions.v1"),
                                   ("lighting-manifest.json", "filmcraft.lighting_manifest.v1")):
                self.assertEqual(validate(load(f"{tag}.{suffix}"), schema), [], f"{tag}.{suffix}")
        self.assertEqual(validate(load("setup-WARM-ROOM.lighting-setup.json"), "filmcraft.lighting_setup.v1"), [])

    def test_manifests_are_inert_approved_and_need_no_override(self):
        for tag in TAGS:
            m = load(f"{tag}.lighting-manifest.json")
            self.assertFalse(m["import_policy"]["auto_import"])
            self.assertEqual((m["approval"]["status"], m["overrides"], m["source"]["source_status"]), ("approved", [], "current"))
            self.assertEqual(m["art_reference"]["art_approval_status"], "approved")
            for section in ("cinematography", "previz", "scene_maker"):
                self.assertIn(section, m["integration"])
            self.assertEqual(m["continuity"]["readiness"]["attention"], 0)

    def test_lighting_files_point_at_the_art_design_and_do_not_copy_it(self):
        for tag in TAGS:
            for suffix in ("lighting-instructions.json", "lighting-manifest.json"):
                doc = load(f"{tag}.{suffix}")
                self.assertLessEqual(set(doc["art_reference"]), {"treatment_id", "treatment_name", "art_hash", "art_approval_status"}, f"{tag}.{suffix}")
                self.assertFalse(ART_ONLY_KEYS & set(keys_anywhere(doc)), f"{tag}.{suffix} carries art-direction data")

    def test_the_two_treatments_share_one_scene_and_differ_in_measured_light(self):
        a, b = (load(f"{t}.lighting-plan.json") for t in TAGS)
        self.assertEqual(a["source"]["scene_hash"], b["source"]["scene_hash"])
        self.assertEqual((a["scene_id"], b["scene_id"]), ("SC-001", "SC-001"))
        ma, mb = a["analysis"]["metrics"], b["analysis"]["metrics"]
        self.assertLess(ma["key_kelvin"], 3500)                       # treatment A: warm
        self.assertGreater(mb["key_kelvin"], 4500)                    # treatment B: cool
        self.assertLess(ma["key_fill_ratio"], mb["key_fill_ratio"])   # A is gentler, B more contrasty
        self.assertGreater(ma["key_softness"], mb["key_softness"])
        self.assertGreater(a["analysis"]["metrics"]["mean_level"], mb["mean_level"])

    def test_comparison_gives_a_reason_for_every_stated_effect(self):
        c = load("treatments-A-vs-B.comparison.json")
        self.assertTrue(c["metrics"] and any(m["differs"] for m in c["metrics"]))
        for side in ("a", "b"):
            self.assertTrue(c["readings"][side])
            self.assertTrue(all(r["because"] and r["text"] for r in c["readings"][side]))
        self.assertTrue(c["model_note"])

    def test_every_shot_has_lights_tied_to_stable_ids(self):
        for tag in TAGS:
            ins = load(f"{tag}.lighting-instructions.json")
            plan = load(f"{tag}.lighting-plan.json")
            ids = {l["id"] for l in plan["lights"]}
            self.assertGreaterEqual(len(ins["shots"]), 10)
            for shot in ins["shots"]:
                self.assertTrue(shot["shot_id"] and shot["beat_id"], shot)
                self.assertTrue(shot["lights"])
                self.assertTrue(all(l["id"] in ids or l["id"].startswith("L-S") for l in shot["lights"]))

    def test_light_schedule_is_a_readable_spreadsheet(self):
        rows = list(csv.reader(io.StringIO((SAMPLES / f"{TAGS[0]}.light-schedule.csv").read_text(encoding="utf-8"))))
        self.assertEqual(rows[0][:3], ["shot_id", "beat_id", "light_id"])
        self.assertGreater(len(rows), 10)

    def test_setup_can_be_reused(self):
        s = load("setup-WARM-ROOM.lighting-setup.json")
        self.assertEqual((s["setup"]["id"], s["setup"]["from_scene_id"]), ("WARM-ROOM", "SC-001"))
        self.assertGreaterEqual(len(s["setup"]["lights"]), 5)


if __name__ == "__main__":
    unittest.main()
