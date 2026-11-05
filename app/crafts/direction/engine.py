"""Direction craft: an editable director's plan for one scene. Rule-based, no AI, no rendering.

Input: a processed ``filmcraft.screenplay.v1`` (it carries the timings and hashes this craft reads),
the ``scene_id`` to direct and EITHER an approach (draft a plan) OR an edited ``plan`` (validate and
re-analyse it). Output: ``filmcraft.direction_plan.v1``. This craft imports nothing from other crafts.
"""
import copy
import json

from app.crafts.direction import approaches as ap
from app.crafts.direction import analysis, generator
from app.hashing import sha256

SCHEMA = "filmcraft.direction_plan.v1"
SOURCE_KEYS = ("project_id", "scene_id", "scene_hash", "screenplay_hash", "screenplay_revision", "beat_hashes", "element_hashes")


def infer_roles(beats):
    roles = {}
    if not beats:
        return roles
    peak = max(range(len(beats)), key=lambda i: beats[i].get("intensity", 0))
    for i, b in enumerate(beats):
        roles[b["id"]] = b.get("role") or ("setup" if i == 0 else "resolution" if i == len(beats) - 1 else "climax" if i == peak else "rising")
    return roles


def find_scene(screenplay, scene_id):
    scene = next((s for s in screenplay["scenes"] if s["id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"scene {scene_id} is not in the screenplay")
    an = screenplay.get("analysis") or {}
    san = next((s for s in an.get("scenes", []) if s["scene_id"] == scene_id), None)
    if san is None:
        raise ValueError("the screenplay has no analysis; run it through Screenwriting first so timings and hashes exist")
    return scene, san


def source_block(screenplay, scene, san, ref=None):
    return {"project_id": screenplay["project"]["id"], "scene_id": scene["id"], "scene_hash": san["scene_hash"],
            "screenplay_hash": screenplay["analysis"]["screenplay_hash"], "screenplay_revision": (screenplay.get("revision") or {}).get("number", 1),
            "beat_hashes": {b["id"]: b["hash"] for b in san["beats"]}, "element_hashes": {e["id"]: e["hash"] for e in san["elements"]},
            "ref": ref or {}}


def normalize(plan, scene, san, names):
    """Fill derived defaults on an edited plan and check hard integrity rules (raises ValueError)."""
    plan = json.loads(json.dumps(plan))
    plan.pop("analysis", None)
    errors = []
    ids = [s["shot_id"] for s in plan["shots"]]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate shot id {d}")
    for b in plan["blocking"]:
        for c in b["characters"]:
            if c["character_id"] not in names:
                errors.append(f"blocking names unknown character {c['character_id']}")
    for s in plan["shots"]:
        for sub in s["subject"]:
            if sub not in names:
                errors.append(f"{s['shot_id']} frames unknown character {sub}")
    objs = {o["id"] for o in plan["stage"]["objects"]}
    if len(objs) != len(plan["stage"]["objects"]):
        errors.append("duplicate stage object id")
    if errors:
        raise ValueError("plan problems: " + "; ".join(errors[:8]))
    pos_by_beat = {b["beat_id"]: {c["character_id"]: c["end"] for c in b["characters"]} for b in plan["blocking"]}
    beats = {b["id"]: b for b in scene.get("beats", [])}
    fps = plan.get("fps") or san.get("fps") or 24
    plan["fps"] = fps
    for s in plan["shots"]:
        s.setdefault("covers", [])
        s.setdefault("transition_in", "cut")
        s.setdefault("review_note", "")
        s.setdefault("lens_mm", ap.LENS_BY_SIZE[s["size"]])
        s.setdefault("intensity", beats.get(s["beat_id"], {}).get("intensity", 5))
        s["previz"] = {**generator.previz(s, pos_by_beat.get(s["beat_id"], {}), s["camera_side"], plan["stage"]["objects"]),
                       "notes": (s.get("previz") or {}).get("notes", "")}
        if not (s.get("storyboard") or {}).get("description"):
            s["storyboard"] = generator._board(s, names)
    return plan


def run(payload):
    screenplay, scene_id = payload["screenplay"], payload["scene_id"]
    scene, san = find_scene(screenplay, scene_id)
    names = {c["id"]: c["name"] for c in screenplay["characters"]}
    if payload.get("plan"):
        plan = payload["plan"]
        if plan["scene_id"] != scene_id or plan["project_id"] != screenplay["project"]["id"]:
            raise ValueError("the plan belongs to a different project or scene than the screenplay given")
        plan = normalize(plan, scene, san, names)
    else:
        approach = ap.resolve(payload.get("approach"))
        stage = generator.stage_for(scene, names)
        blocking, who = generator.make_blocking(scene, san, names, stage)
        roles = infer_roles(scene.get("beats", []))
        shots = generator.draft_shots(scene, san, names, approach, blocking, stage, roles)
        plan = {"schema": SCHEMA, "project_id": screenplay["project"]["id"], "scene_id": scene_id, "fps": san["fps"],
                "approach": ap.public(approach), "interpretation": generator.interpretation(scene, approach, names, who, scene.get("beats", [])),
                "stage": stage, "blocking": blocking, "shots": shots}
        plan = normalize(plan, scene, san, names)
    if payload.get("note") is not None:
        plan["note"] = payload["note"]
    plan["source"] = source_block(screenplay, scene, san, payload.get("source_ref"))
    plan["analysis"] = analysis.analyze(plan, scene, san, names)
    plan["analysis"]["plan_hash"] = sha256({k: v for k, v in plan.items() if k not in ("analysis", "source", "note")})[:16]
    warnings = [f"{i['severity'].upper()}: {i['message']}" for i in plan["analysis"]["issues"] if i["severity"] == "error"]
    warnings += [i["message"] for i in plan["analysis"]["issues"] if i["severity"] == "warning"]
    return {"artifact_type": "direction_plan", "data": plan, "warnings": warnings}
