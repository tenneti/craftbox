"""The shipped CB2A sample exports (./samples/art) must stay valid and in step with the engines."""
import csv
import io
import json
import unittest
from pathlib import Path

from app.validation import validate

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "art"


def load(name):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


@unittest.skipUnless(SAMPLES.is_dir(), "samples not generated (python scripts/make_art_samples.py)")
class ArtSampleTests(unittest.TestCase):
    TAGS = ("treatment-A-warm-nostalgia", "treatment-B-emotional-distance")

    def test_every_sample_validates_against_its_schema(self):
        for tag in self.TAGS:
            for suffix, schema in (("art-direction.json", "filmcraft.art_direction.v1"), ("storyboard-metadata.json", "filmcraft.storyboard_metadata.v1"),
                                   ("art-direction-manifest.json", "filmcraft.art_direction_manifest.v1"),
                                   ("asset-reference-manifest.json", "filmcraft.asset_reference_manifest.v1")):
                self.assertEqual(validate(load(f"{tag}.{suffix}"), schema), [], f"{tag}.{suffix}")

    def test_manifests_are_inert_and_prepared_for_later_crafts(self):
        for tag in self.TAGS:
            m = load(f"{tag}.art-direction-manifest.json")
            self.assertFalse(m["import_policy"]["auto_import"])
            self.assertEqual(m["approval"]["status"], "approved")
            for section in ("lighting", "costume", "cinematography"):
                self.assertIn(section, m["integration"])

    def test_the_two_treatments_share_one_screenplay_and_differ_in_design(self):
        a, b = (load(f"{t}.art-direction.json") for t in self.TAGS)
        self.assertEqual(a["source"]["scene_hash"], b["source"]["scene_hash"])
        self.assertNotEqual([c["hex"] for c in a["style"]["palette"]], [c["hex"] for c in b["style"]["palette"]])
        self.assertGreater(len(a["props"]), len(b["props"]))

    def test_asset_manifest_lists_the_registered_picture(self):
        m = load("treatment-A-warm-nostalgia.asset-reference-manifest.json")
        self.assertEqual([x["id"] for x in m["assets"]], ["A-001"])
        self.assertEqual(m["summary"]["missing_from_register"], [])

    def test_prop_list_is_a_readable_spreadsheet(self):
        rows = list(csv.reader(io.StringIO((SAMPLES / "treatment-A-warm-nostalgia.props.csv").read_text(encoding="utf-8"))))
        self.assertEqual(rows[0][:3], ["id", "name", "kind"])
        self.assertGreater(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
