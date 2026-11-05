"""Directorial approaches: named, numeric style knobs the deterministic planner follows.

An approach is data, not code, so a user can start from a preset and override any knob. Two presets
give genuinely different treatments of the same script.
"""

SIZES = ["ECU", "CU", "MCU", "MS", "MWS", "WS", "EWS"]  # tightest to widest
LENS_BY_SIZE = {"ECU": 100, "CU": 85, "MCU": 65, "MS": 50, "MWS": 40, "WS": 28, "EWS": 24}
CAMERA_DISTANCE = {"ECU": 0.15, "CU": 0.25, "MCU": 0.35, "MS": 0.45, "MWS": 0.55, "WS": 0.8, "EWS": 1.1}  # in stage depths
HEIGHT_M = {"eye": 1.6, "low": 0.8, "high": 2.4, "dutch": 1.6, "overhead": 4.0}

PRESETS = {
    "intimate": {
        "id": "intimate",
        "name": "A — Intimate: close, handheld, reactive",
        "summary": "Stay close to faces and hands. Cut on emotional shifts, push in as pressure rises, and cross the axis once, at the climax, to mark the reversal.",
        "avg_shot_seconds": 4.5, "intensity_sensitivity": 0.7, "lens_scale": 1.0,
        "establish": {"size": "WS", "movement": "static"},
        "size_by_band": {"low": ["MWS", "MS", "WS"], "mid": ["MS", "MCU", "CU"], "high": ["CU", "ECU", "MCU"]},
        "movement_by_band": {"low": ["handheld", "static"], "mid": ["handheld", "push_in"], "high": ["push_in", "handheld"]},
        "angle_by_band": {"low": ["eye"], "mid": ["eye", "low"], "high": ["eye", "high"]},
        "exchange_framing": {"low": "over_shoulder", "mid": "over_shoulder", "high": "single"},
        "axis_cross_at_climax": True, "reaction_on_peak": True, "closing_transition": "cut",
        "tone": "Charged, close, a little unsteady",
        "motifs": ["Hands and objects as emotional proxies", "Faces held longer than is comfortable", "The door always at the edge of frame"],
        "intent": "{visitor} and {host} are circling something neither will say. The camera stays close and slightly unsteady so the audience feels the pressure under the small talk, tightening as it rises and finally crossing the line between them when the truth is spoken.",
    },
    "observational": {
        "id": "observational",
        "name": "B — Observational: wide, still, restrained",
        "summary": "Hold back. Wide two-shots and long takes in the room, framed through the shelves. Move in only for the turning point and the final ask.",
        "avg_shot_seconds": 9.0, "intensity_sensitivity": 0.35, "lens_scale": 1.15,
        "establish": {"size": "EWS", "movement": "static"},
        "size_by_band": {"low": ["WS", "MWS", "EWS"], "mid": ["MWS", "MS", "WS"], "high": ["MS", "MCU", "CU"]},
        "movement_by_band": {"low": ["static"], "mid": ["static", "track"], "high": ["static", "push_in"]},
        "angle_by_band": {"low": ["eye"], "mid": ["eye", "high"], "high": ["eye", "low"]},
        "exchange_framing": {"low": "two_shot", "mid": "two_shot", "high": "single"},
        "axis_cross_at_climax": False, "reaction_on_peak": True, "closing_transition": "dissolve",
        "tone": "Restrained, patient, observant",
        "motifs": ["Shelves and counter as barriers between them", "Distance that closes only when they speak", "A still room while the rain moves"],
        "intent": "{visitor} and {host} are two people in a room that remembers them. The camera keeps its distance and lets the space and the silences do the work, closing in only when something finally changes hands.",
    },
}
DEFAULT_PRESET = "intimate"
KNOBS = ("avg_shot_seconds", "intensity_sensitivity", "lens_scale")


def resolve(spec):
    """Build a full approach from {} / {"preset": id, <overrides>} / a previously stored approach."""
    spec = dict(spec or {})
    preset_id = spec.get("preset") or (spec.get("id") if spec.get("id") in PRESETS else DEFAULT_PRESET)
    if preset_id not in PRESETS:
        raise ValueError(f"unknown approach preset '{preset_id}' (choose {', '.join(PRESETS)})")
    base = dict(PRESETS[preset_id])
    for key in KNOBS + ("name", "summary", "tone", "intent"):
        if key in spec and spec[key] not in (None, ""):
            base[key] = spec[key]
    if spec.get("id") and spec["id"] not in PRESETS:
        base["id"] = spec["id"]
    if not 0.5 <= float(base["avg_shot_seconds"]) <= 60:
        raise ValueError("approach avg_shot_seconds must be between 0.5 and 60")
    if not 0 <= float(base["intensity_sensitivity"]) <= 1:
        raise ValueError("approach intensity_sensitivity must be between 0 and 1")
    base["preset"] = preset_id
    return base


def public(approach):
    """The small, stored description of an approach (plan.approach)."""
    keys = ("id", "name", "summary", "avg_shot_seconds", "intensity_sensitivity", "lens_scale", "preset")
    return {k: approach[k] for k in keys if k in approach}
