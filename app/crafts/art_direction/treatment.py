"""Drafting, normalising and fingerprinting an art direction treatment."""
import json

from app.crafts.art_direction import layout as lay
from app.crafts.art_direction import props as propmod
from app.hashing import sha256


def _blocking_positions(plan):
    out = []
    for b in (plan or {}).get("blocking", []):
        for c in b["characters"]:
            out.append((c["end"]["x"], c["end"]["y"]))
    return out


def _free(obj, placed, avoid):
    for p in placed:
        if p.get("solid") and obj.get("solid") and lay.overlap_area(obj, p) > 0:
            return False
    return not any(lay.inside(obj, x, y, 0.05) for x, y in avoid if obj.get("solid"))


def base_objects(scene, plan, preset):
    """Layout objects for the scene: the direction plan's stage objects when there is one, else the scene's own props."""
    mod = preset.get("modify", {})
    src = [(o["id"], o["name"], o["x"], o["y"]) for o in ((plan or {}).get("stage") or {}).get("objects", [])]
    if not src:
        free = 0
        for p in scene.get("props", []):
            s = lay.slot(p["name"])
            if s is None and lay.classify(p["name"]) != "prop":
                free += 1
                s = (round(free / 6, 2), 0.12)
            if s is not None:
                src.append((p["id"], p["name"], s[0], s[1]))
        if not any("door" in lay.words(n) for _, n, _, _ in src):
            src.append(("P-DOOR", "Door", 0.08, 0.88))
    objs = []
    for oid, name, x, y in src:
        kind = lay.classify(name)
        if kind == "prop":
            continue
        w, h = lay.footprint(name)
        words = lay.words(name)
        if mod.get("shelf_scale") and ({"shelf", "shelves", "bookcase", "bookshelf"} & set(words)):
            w = round(w * mod["shelf_scale"], 3)
        if mod.get("counter_shift_x") and ({"counter", "desk", "bar"} & set(words)):
            x = lay.clamp(x + mod["counter_shift_x"], w / 2, 1 - w / 2)
        solid = kind == "furniture" or "wall" in words
        objs.append({"id": oid, "name": name, "kind": kind, "x": round(x, 3), "y": round(y, 3), "w": w, "h": h, "solid": solid, "material_id": None, "texture_id": None, "notes": ""})
    return objs


def draft(scene, san, plan, preset_key, name, profile=None):
    if preset_key not in lay.PRESETS:
        raise ValueError(f"unknown preset '{preset_key}' (choose {', '.join(lay.PRESETS)})")
    pr = lay.PRESETS[preset_key]
    h = scene["heading"]
    objs = base_objects(scene, plan, pr)
    avoid = _blocking_positions(plan)
    notes = []
    for key, label, kind, w, hh, solid, cands in pr["kit"]:
        placed = None
        grid = [(round(0.1 * i, 2), round(0.1 * j, 2)) for j in range(1, 10) for i in range(1, 10)]
        for x, y in list(cands) + grid:
            cand = {"id": f"D-{key.upper()}", "name": label, "kind": kind, "x": x, "y": y, "w": w, "h": hh, "solid": solid, "material_id": None, "texture_id": None, "notes": ""}
            if _free(cand, objs, avoid):
                placed = cand
                break
        if placed:
            objs.append(placed)
        else:
            notes.append(f"No free place was found for “{label}”; add it by hand.")
    props = propmod.extract(scene, plan)
    taken = {p["id"] for p in props}
    for label, kind, (x, y) in pr["personal"]:
        pid = f"PR-{lay.slug(label).upper()}"
        if pid not in taken:
            props.append({"id": pid, "name": label, "source": "manual", "kind": kind, "description": "", "position": {"x": x, "y": y}, "mentions": [], "scene_ids": [scene["id"]],
                          "shot_ids": [], "states": [], "asset_ids": [], "status": "proposed", "notes": ""})
    entrance = next((o for o in objs if "door" in lay.words(o["name"])), None)
    style = {"profile_ref": None, "palette": [{"id": f"C{i}", "name": n, "hex": hx, "role": role} for i, (n, hx, role) in enumerate(pr["palette"], 1)],
             "textures": [{"id": f"T{i}", "name": n, "description": d, "asset_id": None} for i, (n, d) in enumerate(pr["textures"], 1)],
             "materials": [{"id": f"M{i}", "name": n, "finish": f, "notes": ""} for i, (n, f) in enumerate(pr["materials"], 1)],
             "period": {"era": pr["period"][0], "notes": pr["period"][1]}, "themes": list(pr["themes"]), "mood_words": list(pr["mood_words"])}
    if profile:
        p = profile["profile"]
        style = {"profile_ref": {"profile_id": p["id"], "name": p["name"], "hash": sha256(p)[:16]}, "palette": json.loads(json.dumps(p.get("palette", []))),
                 "textures": [dict(t, asset_id=None) for t in p.get("textures", [])], "materials": json.loads(json.dumps(p.get("materials", []))),
                 "period": dict(p.get("period") or {"era": "", "notes": ""}), "themes": list(p.get("themes", [])), "mood_words": list(p.get("mood_words", []))}
    tid = "TR-" + (lay.slug(name or pr["name"]).upper()[:20] or "X")
    doc = {"schema": "filmcraft.art_direction.v1", "project_id": None, "scene_id": scene["id"],
           "treatment": {"id": tid, "name": name or pr["name"], "summary": pr["summary"], "intent": pr["intent"], "preset": preset_key},
           "location": {"name": h["location"].strip().title(), "kind": "interior" if "INT" in h["int_ext"] else "exterior", "setting": "fictional", "description": scene.get("synopsis", ""),
                        "architecture": [{"id": o["id"], "name": o["name"], "description": ""} for o in objs if o["kind"] == "architecture"],
                        "entrances": [{"object_id": entrance["id"], "name": entrance["name"], "note": ""}] if entrance else [],
                        "exits": [{"object_id": entrance["id"], "name": entrance["name"], "note": ""}] if entrance else [],
                        "environment": {"time_of_day": h.get("time", ""), "weather": "", "atmosphere": pr["atmosphere"], "sounds": ""}, "details": []},
           "layout": {"width_m": 6.0, "depth_m": 5.0, "note": "Coordinates match the direction plan's stage: x left to right, y back wall to audience.", "objects": objs},
           "props": props, "style": style, "variations": [], "asset_ids": []}
    return doc, notes


def normalize(doc, scene):
    doc = json.loads(json.dumps(doc))
    doc.pop("analysis", None)
    if doc["scene_id"] != scene["id"]:
        raise ValueError("the treatment belongs to a different scene than the screenplay given")
    errors = []
    for label, items in (("layout object", doc["layout"]["objects"]), ("prop", doc["props"]), ("variation", doc.get("variations", [])),
                         ("palette colour", doc["style"].get("palette", [])), ("texture", doc["style"].get("textures", [])), ("material", doc["style"].get("materials", []))):
        ids = [i["id"] for i in items]
        for d in sorted({i for i in ids if ids.count(i) > 1}):
            errors.append(f"duplicate {label} id {d}")
    if errors:
        raise ValueError("treatment problems: " + "; ".join(errors[:8]))
    doc.setdefault("variations", [])
    doc.setdefault("asset_ids", [])
    for p in doc["props"]:
        p.setdefault("kind", "prop"); p.setdefault("mentions", []); p.setdefault("scene_ids", [scene["id"]]); p.setdefault("shot_ids", [])
        p.setdefault("states", []); p.setdefault("asset_ids", []); p.setdefault("position", None)
    for o in doc["layout"]["objects"]:
        o.setdefault("solid", o["kind"] == "furniture")
    return doc


def blocking_hashes(plan):
    out = {}
    for b in (plan or {}).get("blocking", []):
        key = [(c["character_id"], round(c["end"]["x"], 2), round(c["end"]["y"], 2), (c.get("entrance") or {}).get("from"), (c.get("exit") or {}).get("to")) for c in b["characters"]]
        out[b["beat_id"]] = sha256(key)[:16]
    return out


def source_block(screenplay, scene, san, plan, ref=None):
    return {"project_id": screenplay["project"]["id"], "scene_id": scene["id"], "scene_hash": san["scene_hash"], "screenplay_revision": (screenplay.get("revision") or {}).get("number", 1),
            "beat_hashes": {b["id"]: b["hash"] for b in san["beats"]}, "element_hashes": {e["id"]: e["hash"] for e in san["elements"]},
            "plan": {"plan_hash": (plan or {}).get("analysis", {}).get("plan_hash"), "shot_ids": [s["shot_id"] for s in (plan or {}).get("shots", [])],
                     "blocking_hashes": blocking_hashes(plan), "stage_object_ids": [o["id"] for o in ((plan or {}).get("stage") or {}).get("objects", [])]} if plan else None,
            "ref": ref or {}}
