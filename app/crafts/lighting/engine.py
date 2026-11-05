"""Lighting craft: a deterministic, editable lighting plan for one scene, built on an art treatment and the director's plan. No AI, no rendering.

Two modes, chosen by the payload:
- a plan input (a processed screenplay, the scene, the art treatment, optionally the director's plan) with either a ``preset``
  (or a saved ``setup``) to draft from, or an edited ``light`` plan to validate and re-analyse -> ``filmcraft.lighting_plan.v1``;
- a reusable lighting setup (``filmcraft.lighting_setup.v1``) that can start a plan in another scene.
This craft imports nothing from other crafts.
"""
import json

from app.crafts.lighting import analysis, plan as pl
from app.hashing import sha256

SETUP = "filmcraft.lighting_setup.v1"


def _scene(screenplay, scene_id):
    scene = next((s for s in screenplay["scenes"] if s["id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"scene {scene_id} is not in the screenplay")
    san = next((s for s in (screenplay.get("analysis") or {}).get("scenes", []) if s["scene_id"] == scene_id), None)
    if san is None:
        raise ValueError("the screenplay has no analysis; run it through Screenwriting first so timings and hashes exist")
    return scene, san


def run_plan(payload):
    sp, scene_id, art, dplan = payload["screenplay"], payload["scene_id"], payload["art_direction"], payload.get("direction_plan")
    scene, san = _scene(sp, scene_id)
    if art.get("scene_id") != scene_id:
        raise ValueError("the art treatment is for a different scene than the one given")
    if dplan and dplan.get("scene_id") != scene_id:
        raise ValueError("the direction plan is for a different scene than the one given")
    names = {c["id"]: c["name"] for c in sp["characters"]}
    notes = []
    if payload.get("light"):
        doc = pl.normalize(payload["light"], scene, dplan)
    else:
        doc, notes = pl.draft(scene, san, art, dplan, payload.get("preset") or "blank", payload.get("plan_name"), payload.get("setup"))
        doc = pl.normalize(doc, scene, dplan)
    doc["project_id"] = sp["project"]["id"]
    if payload.get("note") is not None:
        doc["note"] = payload["note"]
    doc["source"] = pl.source_block(sp, scene, san, art, dplan, payload.get("source_ref"))
    doc["analysis"] = analysis.analyze(doc, scene, san, art, dplan, names)
    doc["analysis"]["draft_notes"] = notes
    doc["analysis"]["plan_hash"] = pl.plan_hash(doc)
    warnings = [i["message"] for i in doc["analysis"]["issues"] if i["severity"] == "attention"]
    return {"artifact_type": "lighting_plan", "data": doc, "warnings": warnings}


def run_setup(payload):
    doc = json.loads(json.dumps(payload))
    doc.pop("analysis", None)
    s = doc["setup"]
    s["lights"] = [pl._light_in(l, i) for i, l in enumerate(s["lights"])]
    ids = [l["id"] for l in s["lights"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"light ids must be unique; repeated: {', '.join(dup)}")
    doc["analysis"] = {"lights": len(s["lights"]), "by_role": {r: sum(1 for l in s["lights"] if l["role"] == r) for r in pl.ROLES if any(l["role"] == r for l in s["lights"])}, "setup_hash": sha256(s["lights"])[:16]}
    return {"artifact_type": "lighting_setup", "data": doc, "warnings": []}


def run(payload):
    if payload.get("schema") == SETUP:
        return run_setup(payload)
    return run_plan(payload)
