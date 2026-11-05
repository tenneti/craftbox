import json
import unittest
from collections import Counter
from pathlib import Path
from app.core import all_crafts, execute, get_fixture, get_craft


class RegistryTests(unittest.TestCase):
    def test_exactly_23_unique_crafts_and_groups(self):
        crafts = all_crafts()
        self.assertEqual(len(crafts), 23)
        self.assertEqual(len(set(c['id'] for c in crafts)), 23)
        self.assertEqual(Counter(c['group'] for c in crafts), Counter({
            'Story & Direction': 5, 'Visual Production': 7,
            'Post-production': 4, 'Production Operations': 7,
        }))
        for c in crafts:
            self.assertTrue((Path(__file__).parent.parent/'app'/'crafts'/c['id']/'engine.py').exists())
            self.assertEqual(c['contract_version'], '1.0')

    def test_planned_craft_does_not_fake_completion(self):
        with self.assertRaises(NotImplementedError):
            execute('costume', {})

    def test_path_traversal_denied(self):
        with self.assertRaises(KeyError):
            get_craft('../../app')


class PipelineTests(unittest.TestCase):
    def test_screenwriting_scene_validates(self):
        scene = execute('screenwriting', get_fixture('screenwriting'))
        self.assertEqual(scene['artifact']['schema'], 'filmcraft.scene.v1')
        self.assertEqual(scene['approval_status'], 'draft')
        self.assertFalse(scene['provenance']['ai_used'])

    def test_invalid_screenwriting_input(self):
        bad = get_fixture('screenwriting')
        bad['slugline'] = 'UNKNOWN'
        with self.assertRaises(ValueError):
            execute('screenwriting', bad)

    def test_cinematography_to_editing_handoff(self):
        scene = execute('screenwriting', get_fixture('screenwriting'))['artifact']
        cam_fixture = get_fixture('cinematography')
        cam_fixture['scene'] = scene
        shot_plan = execute('cinematography', cam_fixture)['artifact']
        edit = execute('editing', {'shot_plan': shot_plan})
        self.assertEqual(edit['artifact']['schema'], 'filmcraft.edit_plan.v1')
        self.assertEqual(edit['artifact']['total_frames'], sum(x['duration_frames'] for x in cam_fixture['shots']))
        self.assertEqual(len(edit['artifact']['clips']), len(cam_fixture['shots']))
        self.assertGreater(len(edit['warnings']), 0)

    def test_duplicate_shot_is_rejected(self):
        payload = get_fixture('cinematography')
        payload['shots'].append(payload['shots'][0].copy())
        with self.assertRaises(ValueError):
            execute('cinematography', payload)


if __name__ == '__main__':
    unittest.main()
