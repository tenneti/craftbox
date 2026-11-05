"""Run an end-to-end, non-AI scene -> camera -> edit metadata demonstration."""
import json
from pathlib import Path
from app.core import execute, get_fixture

scene = execute('screenwriting', get_fixture('screenwriting'))['artifact']
shot_input = get_fixture('cinematography')
shot_input['scene'] = scene
shots = execute('cinematography', shot_input)['artifact']
edit = execute('editing', {'shot_plan': shots})
output = Path(__file__).resolve().parents[1] / 'pilot-edit-plan.json'
output.write_text(json.dumps(edit, indent=2), encoding='utf-8')
print(f'Wrote {output.name}: {edit["artifact"]["total_seconds"]} seconds; {len(edit["artifact"]["clips"])} offline clips')
