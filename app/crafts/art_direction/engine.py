"""Art Direction craft: location, set layout, props, visual style and shot variations for one scene. Rule-based; no AI, no rendering.

Three modes, chosen by the payload:
- a treatment input (a processed screenplay, the scene, optionally the director's plan, a style profile and the asset register) with
  either a ``preset`` (draft a treatment) or an edited ``art`` (validate and re-analyse it) -> ``filmcraft.art_direction.v1``;
- a project style profile (``filmcraft.style_profile.v1``);
- an asset register (``filmcraft.asset_register.v1``).
This craft imports nothing from other crafts.
"""
import json

from app.crafts.art_direction import analysis, layout as lay, treatment
from app.hashing import sha256

SCHEMA = "filmcraft.art_direction.v1"
STYLE = "filmcraft.style_profile.v1"
REGISTER = "filmcraft.asset_register.v1"


def _scene(screenplay, scene_id):
    scene = next((s for s in screenplay["scenes"] if s["id"] == scene_id), None)
    if scene is None:
        raise ValueError(f"scene {scene_id} is not in the screenplay")
    san = next((s for s in (screenplay.get("analysis") or {}).get("scenes", []) if s["scene_id"] == scene_id), None)
    if san is None:
        raise ValueError("the screenplay has no analysis; run it through Screenwriting first so timings and hashes exist")
    return scene, san


def run_treatment(payload):
    sp, scene_id = payload["screenplay"], payload["scene_id"]
    plan, profile, register = payload.get("direction_plan"), payload.get("style_profile"), payload.get("asset_register")
    scene, san = _scene(sp, scene_id)
    if plan and plan.get("scene_id") != scene_id:
        raise ValueError("the direction plan is for a different scene than the one given")
    names = {c["id"]: c["name"] for c in sp["characters"]}
    notes = []
    if payload.get("art"):
        doc = treatment.normalize(payload["art"], scene)
    else:
        doc, notes = treatment.draft(scene, san, plan, payload.get("preset") or "blank", payload.get("treatment_name"), profile)
        doc = treatment.normalize(doc, scene)
    doc["project_id"] = sp["project"]["id"]
    if payload.get("note") is not None:
        doc["note"] = payload["note"]
    doc["source"] = treatment.source_block(sp, scene, san, plan, payload.get("source_ref"))
    doc["analysis"] = analysis.analyze(doc, scene, san, plan, names, profile, register)
    doc["analysis"]["draft_notes"] = notes
    doc["analysis"]["art_hash"] = sha256({k: v for k, v in doc.items() if k not in ("analysis", "source", "note")})[:16]
    warnings = [i["message"] for i in doc["analysis"]["issues"] if i["severity"] == "attention"]
    return {"artifact_type": "art_direction", "data": doc, "warnings": warnings}


def run_style(payload):
    doc = json.loads(json.dumps(payload))
    doc.pop("analysis", None)
    p = doc["profile"]
    errors = []
    for label, items in (("palette colour", p.get("palette", [])), ("texture", p.get("textures", [])), ("material", p.get("materials", [])), ("constraint", p.get("constraints", []))):
        ids = [i["id"] for i in items]
        errors += [f"duplicate {label} id {d}" for d in sorted({i for i in ids if ids.count(i) > 1})]
    if errors:
        raise ValueError("style profile problems: " + "; ".join(errors))
    pal = p.get("palette", [])
    lums = [lay.luminance(c["hex"]) for c in pal]
    advice = []
    if len(pal) < 3:
        advice.append("Add at least three colours so the profile can guide a treatment.")
    terms = [(c["kind"], c["term"].lower()) for c in p.get("constraints", [])]
    if any(t[1] == other[1] and t[0] != other[0] for i, t in enumerate(terms) for other in terms[i + 1:]):
        advice.append("One term is both required and avoided; remove one of the two constraints.")
    doc["analysis"] = {"palette": {"colours": len(pal), "warmth": round(sum(lay.warmth(c["hex"]) for c in pal) / len(pal), 3) if pal else None,
                                   "brightness": round(sum(lums) / len(lums), 3) if lums else None, "contrast": round(max(lums) - min(lums), 3) if lums else None},
                       "constraints": {"avoid": sum(1 for k, _ in terms if k == "avoid"), "require": sum(1 for k, _ in terms if k == "require")}, "advice": advice,
                       "profile_hash": sha256(p)[:16]}
    return {"artifact_type": "style_profile", "data": doc, "warnings": advice}


def run_register(payload):
    doc = json.loads(json.dumps(payload))
    doc.pop("analysis", None)
    ids = [a["id"] for a in doc["assets"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError("asset register problems: duplicate asset id " + ", ".join(dup))
    issues, by_rights = [], {}
    for a in doc["assets"]:
        by_rights[a["rights"]["status"]] = by_rights.get(a["rights"]["status"], 0) + 1
        if a["rights"]["status"] != "cleared":
            issues.append({"asset_id": a["id"], "message": f"“{a['name']}” has rights status “{a['rights']['status']}”.", "fix": "Record the licence and set the status to cleared, or do not use the asset."})
        if a["source"]["type"] == "unknown":
            issues.append({"asset_id": a["id"], "message": f"The source of “{a['name']}” is unknown.", "fix": "Record who made it or where it came from."})
        if a["source"]["type"] == "licensed" and not (a["rights"].get("licence") or "").strip():
            issues.append({"asset_id": a["id"], "message": f"“{a['name']}” is licensed but no licence is recorded.", "fix": "Write the licence name or reference."})
    seen = {}
    for a in doc["assets"]:
        seen.setdefault(a["sha256"], []).append(a["id"])
    for sha, group in seen.items():
        if len(group) > 1:
            issues.append({"asset_id": group[1], "message": f"Assets {', '.join(group)} are the same file.", "fix": "Keep one entry, or give each a reason to exist."})
    doc["analysis"] = {"assets": len(doc["assets"]), "by_rights": by_rights, "issues": issues, "register_hash": sha256(doc["assets"])[:16]}
    return {"artifact_type": "asset_register", "data": doc, "warnings": [i["message"] for i in issues]}


def run(payload):
    schema = payload.get("schema")
    if schema == STYLE:
        return run_style(payload)
    if schema == REGISTER:
        return run_register(payload)
    return run_treatment(payload)
