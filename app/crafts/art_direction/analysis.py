"""Treatment analysis: location, layout, prop-continuity, style, variation and asset checks, plus comparable measures.

Everything here is advice. A finding is either ``attention`` (a likely mistake worth fixing before approval) or ``note``
(something to know). Nothing blocks saving, comparing, approving or exporting; exports ask for an explicit override instead.
"""
import math
import re
from collections import Counter

from app.crafts.art_direction import layout as lay
from app.crafts.art_direction import props as propmod

DEPARTURE = 0.35   # mean palette distance (0..1) above which a shot variation is said to leave the treatment's look; a guess


def _issue(issues, rule, severity, message, fix, items=()):
    issues.append({"id": f"{rule}-{len(issues) + 1}", "rule": rule, "severity": severity, "message": message, "fix": fix, "items": list(items)})


def _pos_order(scene, plan):
    beat_idx = {b["id"]: i for i, b in enumerate(scene.get("beats", []))}
    shot_idx = {s["shot_id"]: (beat_idx.get(s["beat_id"], 0), n) for n, s in enumerate((plan or {}).get("shots", []))}
    return beat_idx, shot_idx


def _state_key(st, beat_idx, shot_idx):
    if st["at_kind"] == "beat":
        return (beat_idx.get(st["at_id"], 10 ** 6), -1)
    return shot_idx.get(st["at_id"], (10 ** 6, 10 ** 6))


def analyze(doc, scene, san, plan, names, profile=None, register=None):
    issues = []
    objs, props, style = doc["layout"]["objects"], doc["props"], doc["style"]
    obj_ids = {o["id"] for o in objs}
    solids = [o for o in objs if o.get("solid")]
    beats = {b["id"]: b for b in scene.get("beats", [])}
    beat_title = lambda bid: (beats.get(bid) or {}).get("title", bid)
    who = lambda cid: names.get(cid, cid)
    blocking = (plan or {}).get("blocking", [])
    shots = (plan or {}).get("shots", [])
    shot_ids = {s["shot_id"] for s in shots}

    # ---- location -----------------------------------------------------------------------------------------------------------
    loc = doc["location"]
    heading_kind = "interior" if "INT" in scene["heading"]["int_ext"] else "exterior"
    if loc["kind"] != heading_kind:
        _issue(issues, "location", "attention", f"The script heading says {scene['heading']['int_ext']} ({heading_kind}), but this design is {loc['kind']}.",
               "Change the location type here, or correct the scene heading in the Scene Lab.")
    h_name, l_name = scene["heading"]["location"].strip().lower(), loc["name"].strip().lower()
    if h_name and l_name and h_name not in l_name and l_name not in h_name:
        _issue(issues, "location", "note", f"The design calls the place “{loc['name']}”, the script calls it “{scene['heading']['location']}”.",
               "Rename one so everyone means the same place, or keep both if it is deliberate.")
    for e in loc.get("entrances", []) + loc.get("exits", []):
        if e["object_id"] not in obj_ids:
            _issue(issues, "entrance", "attention", f"The entrance or exit “{e.get('name') or e['object_id']}” is not in the set layout.", "Add the door to the layout, or remove it from the location.", [e["object_id"]])
    wanted = set()
    for b in blocking:
        for c in b["characters"]:
            for key in ("entrance", "exit"):
                tgt = (c.get(key) or {}).get("from") or (c.get(key) or {}).get("to")
                if tgt:
                    wanted.add((tgt, who(c["character_id"]), beat_title(b["beat_id"])))
    for tgt, person, beat in sorted(wanted):
        if tgt not in obj_ids:
            _issue(issues, "entrance", "attention", f"The director's blocking has {person} using “{tgt}” in “{beat}”, but the layout has no such object.",
                   "Add that door to the layout with the same ID, or change the entrance in the Direction Lab.", [tgt])

    # ---- layout against the blocking ----------------------------------------------------------------------------------------
    for b in blocking:
        for c in b["characters"]:
            for o in solids:
                if lay.inside(o, c["end"]["x"], c["end"]["y"]):
                    _issue(issues, "layout", "attention", f"{who(c['character_id'])} ends “{beat_title(b['beat_id'])}” inside “{o['name']}”.",
                           f"Move or resize “{o['name']}”, or change where {who(c['character_id'])} stands in the Direction Lab.", [o["id"], b["beat_id"]])
                path = c.get("path") or [c["start"], c["end"]]
                if any(lay.segment_hits(o, (p["x"], p["y"]), (q["x"], q["y"])) for p, q in zip(path, path[1:])) and not lay.inside(o, c["end"]["x"], c["end"]["y"]):
                    _issue(issues, "layout", "note", f"{who(c['character_id'])}'s path in “{beat_title(b['beat_id'])}” passes through “{o['name']}”.",
                           "Leave a gap in the furniture or reroute the path.", [o["id"], b["beat_id"]])
    for i, a in enumerate(solids):
        for o in solids[i + 1:]:
            ov = lay.overlap_area(a, o)
            if ov > 0.15 * min(a["w"] * a["h"], o["w"] * o["h"]):
                _issue(issues, "layout", "note", f"“{a['name']}” and “{o['name']}” overlap.", "Drag one of them apart.", [a["id"], o["id"]])
    for o in objs:
        if o["x"] - o["w"] / 2 < -0.001 or o["x"] + o["w"] / 2 > 1.001 or o["y"] - o["h"] / 2 < -0.001 or o["y"] + o["h"] / 2 > 1.001:
            _issue(issues, "layout", "note", f"“{o['name']}” reaches outside the stage.", "Move it inward.", [o["id"]])
    for w in propmod.architecture_mentions(scene, objs):
        _issue(issues, "layout", "note", f"The script mentions a {w}, which the layout does not have.", f"Add a {w} if the audience will see it, or ignore this note.")

    # ---- props ---------------------------------------------------------------------------------------------------------------
    beat_idx, shot_idx = _pos_order(scene, plan)
    have = {p["id"] for p in props} | {p["name"].lower() for p in props}
    for sp in propmod.extract(scene, plan):
        if sp["id"] not in have and sp["name"].lower() not in have:
            _issue(issues, "props", "note", f"The script mentions “{sp['name']}” (line {sp['mentions'][0].split('-')[-1]}), which is not in the inventory.",
                   "Add it to the prop inventory, or ignore this note if it is not seen.", [sp["id"]])
    elem_ids = {e["id"] for e in scene["elements"]}
    for p in props:
        gone_from = None
        ordered = sorted(p["states"], key=lambda s: _state_key(s, beat_idx, shot_idx))
        if [s for s in p["states"]] != ordered:
            _issue(issues, "props", "note", f"The states of “{p['name']}” are not in script order.", "Reorder them so the earliest comes first.", [p["id"]])
        prev = None
        for st in ordered:
            where = st["where"].strip().lower()
            if prev is not None:
                if prev.startswith(("gone", "removed", "used")) and not where.startswith(("gone", "removed", "used")):
                    _issue(issues, "props", "attention", f"“{p['name']}” is marked “{prev}” and then appears again as “{st['where']}”.",
                           "Say how it came back, or correct the earlier state.", [p["id"]])
                elif where != prev and not (st.get("note") or "").strip():
                    _issue(issues, "props", "note", f"“{p['name']}” moves from “{prev}” to “{st['where']}” with no explanation.", "Add a note saying how it moved (who carried it, and when).", [p["id"]])
            if where.startswith(("gone", "removed", "used")) and gone_from is None:
                gone_from = st
            prev = where
        for sid in p.get("shot_ids", []):
            if shot_idx and sid in shot_idx and gone_from is not None and shot_idx[sid] > _state_key(gone_from, beat_idx, shot_idx):
                _issue(issues, "props", "attention", f"Shot {sid} shows “{p['name']}”, but it was marked “{gone_from['where']}” earlier.",
                       "Hide it in that shot with a shot variation, or change its state.", [p["id"], sid])
        if p["position"] is None and not p["states"] and (p["mentions"] or p["shot_ids"]):
            _issue(issues, "props", "note", f"“{p['name']}” has no position and no states.", "Give it a position on the layout, or add a state saying who holds it.", [p["id"]])
        for m in p["mentions"]:
            if m not in elem_ids:
                _issue(issues, "props", "attention", f"“{p['name']}” points at script line {m}, which no longer exists.", "Remove that reference or re-link the prop.", [p["id"]])
        for st in p["states"]:
            if st["at_kind"] == "shot" and shots and st["at_id"] not in shot_ids:
                _issue(issues, "props", "attention", f"A state of “{p['name']}” refers to shot {st['at_id']}, which is not in the direction plan.", "Re-link it to a shot that exists, or remove the state.", [p["id"]])
            if st["at_kind"] == "beat" and st["at_id"] not in beats:
                _issue(issues, "props", "attention", f"A state of “{p['name']}” refers to a beat that no longer exists ({st['at_id']}).", "Re-link or remove the state.", [p["id"]])

    # ---- style ---------------------------------------------------------------------------------------------------------------
    pal = style.get("palette", [])
    if len(pal) < 3:
        _issue(issues, "style", "note", f"The palette has {len(pal)} colour(s).", "Add at least three colours (a main colour, an accent and a light) so the look can be judged.")
    hexes = [c["hex"].lower() for c in pal]
    if len(set(hexes)) < len(hexes):
        _issue(issues, "style", "note", "Two palette colours are the same.", "Change or remove the duplicate.")
    if len(pal) >= 2 and max(lay.luminance(c["hex"]) for c in pal) - min(lay.luminance(c["hex"]) for c in pal) < 0.25:
        _issue(issues, "style", "note", "The palette has very little light-to-dark range.", "Add a clearly lighter or darker colour so shapes stay readable.")
    corpus = " ".join(str(x).lower() for x in [loc.get("name"), loc.get("description"), doc["treatment"].get("summary"), doc["treatment"].get("intent"), *[o["name"] for o in objs], *[p["name"] for p in props],
                                              *[m["name"] for m in style.get("materials", [])], *[t["name"] for t in style.get("textures", [])], *style.get("themes", []), (style.get("period") or {}).get("era", "")])
    for c in (profile or {}).get("profile", {}).get("constraints", []):
        hit = c["term"].lower() in corpus
        if c["kind"] == "avoid" and hit:
            _issue(issues, "style", "attention", f"The project style says to avoid “{c['term']}”, and this treatment mentions it.{(' ' + c['note']) if c.get('note') else ''}",
                   "Remove it, or edit the project style profile if the rule has changed.", [c["id"]])
        if c["kind"] == "require" and not hit:
            _issue(issues, "style", "note", f"The project style asks for “{c['term']}”, which this treatment does not mention.", "Add it, or edit the project style profile.", [c["id"]])

    # ---- shot variations -----------------------------------------------------------------------------------------------------
    pid = {p["id"] for p in props}
    for v in doc.get("variations", []):
        if plan and v["shot_id"] not in shot_ids:
            _issue(issues, "variation", "attention", f"The variation for shot {v['shot_id']} points at a shot that is not in the direction plan.", "Re-link it to an existing shot or delete it.", [v["id"]])
        for key in ("hide_prop_ids", "show_prop_ids"):
            for x in v.get(key, []):
                if x not in pid:
                    _issue(issues, "variation", "attention", f"The variation for shot {v['shot_id']} uses a prop that is not in the inventory ({x}).", "Choose a prop from the inventory.", [v["id"]])
        if v.get("palette") and pal:
            d = sum(min(lay.distance(c["hex"], b["hex"]) for b in pal) for c in v["palette"]) / len(v["palette"])
            if d > DEPARTURE:
                _issue(issues, "variation", "note", f"The palette for shot {v['shot_id']} is far from the treatment's palette (distance {d:.2f}).", "Keep the treatment's colours and shift only one accent, or accept the break on purpose.", [v["id"]])

    # ---- assets ---------------------------------------------------------------------------------------------------------------
    used = {}
    for t in style.get("textures", []):
        if t.get("asset_id"):
            used.setdefault(t["asset_id"], []).append(f"texture {t['name']}")
    for p in props:
        for a in p.get("asset_ids", []):
            used.setdefault(a, []).append(f"prop {p['name']}")
    for a in doc.get("asset_ids", []):
        used.setdefault(a, []).append("treatment")
    reg = {a["id"]: a for a in (register or {}).get("assets", [])}
    for aid, by in sorted(used.items()):
        a = reg.get(aid)
        if a is None:
            _issue(issues, "assets", "attention", f"Asset {aid} (used by {', '.join(by)}) is not in the asset register.", "Register the file in the Art Library, or remove the reference.", [aid])
        elif a["rights"]["status"] != "cleared":
            _issue(issues, "assets", "attention", f"“{a['name']}” has rights status “{a['rights']['status']}”.", "Clear the licence in the Art Library, or replace the asset before this is used.", [aid])
        elif a["source"]["type"] == "unknown":
            _issue(issues, "assets", "note", f"The source of “{a['name']}” is unknown.", "Record where it came from in the Art Library.", [aid])

    return {"issues": issues, "metrics": metrics(doc, scene, plan), "reading": reading(doc, scene, plan),
            "readiness": {"attention": sum(1 for i in issues if i["severity"] == "attention"), "notes": sum(1 for i in issues if i["severity"] == "note"),
                          "advice": "Advice only: you can save, compare, approve and export with open findings; an export that depends on one asks for an explicit, recorded override."}}


def metrics(doc, scene, plan):
    objs, props, pal = doc["layout"]["objects"], doc["props"], doc["style"].get("palette", [])
    solid_area = sum(o["w"] * o["h"] for o in objs if o.get("solid"))
    kinds = Counter(o["kind"] for o in objs)
    peak = max(scene.get("beats", []), key=lambda b: b.get("intensity", 0), default=None)
    gap = obstructions = mean_dist = None
    if plan and plan.get("blocking"):
        dists = []
        for b in plan["blocking"]:
            cs = b["characters"]
            if len(cs) >= 2:
                dists.append(math.dist((cs[0]["end"]["x"], cs[0]["end"]["y"]), (cs[1]["end"]["x"], cs[1]["end"]["y"])))
        mean_dist = round(sum(dists) / len(dists), 3) if dists else None
        pb = next((b for b in plan["blocking"] if peak and b["beat_id"] == peak["id"]), None)
        if pb and len(pb["characters"]) >= 2:
            a, c = pb["characters"][0]["end"], pb["characters"][1]["end"]
            gap = round(math.dist((a["x"], a["y"]), (c["x"], c["y"])), 3)
            obstructions = sum(1 for o in objs if o.get("solid") and lay.segment_hits(o, (a["x"], a["y"]), (c["x"], c["y"])))
    lums = [lay.luminance(c["hex"]) for c in pal]
    in_zone = lambda x, y: 0.2 <= x <= 0.8 and 0.25 <= y <= 0.85          # the middle of the stage, where the actors play
    central = sum(1 for o in objs if o["kind"] != "architecture" and in_zone(o["x"], o["y"])) + sum(1 for p in props if p.get("position") and in_zone(p["position"]["x"], p["position"]["y"]))
    return {"central_objects": central, "objects": len(objs), "furniture": kinds.get("furniture", 0), "decor": kinds.get("decor", 0), "architecture": kinds.get("architecture", 0),
            "solid_area": round(solid_area, 3), "open_floor": round(max(0.0, 1 - solid_area), 3), "props": len(props), "personal_props": sum(1 for p in props if p.get("kind") == "personal"),
            "script_props": sum(1 for p in props if p["source"] == "script"), "colours": len(pal),
            "warmth": round(sum(lay.warmth(c["hex"]) for c in pal) / len(pal), 3) if pal else None,
            "brightness": round(sum(lums) / len(lums), 3) if lums else None, "saturation": round(sum(lay.saturation(c["hex"]) for c in pal) / len(pal), 3) if pal else None,
            "contrast": round(max(lums) - min(lums), 3) if lums else None, "textures": len(doc["style"].get("textures", [])), "materials": len(doc["style"].get("materials", [])),
            "variations": len(doc.get("variations", [])), "peak_beat": peak["id"] if peak else None, "peak_gap": gap, "peak_obstructions": obstructions, "mean_character_distance": mean_dist}


def reading(doc, scene, plan):
    """How the design is likely to read emotionally, by explicit rules. Each statement shows the measure it rests on."""
    m = metrics(doc, scene, plan)
    out = []
    if m["warmth"] is not None:
        if m["warmth"] > 0.15:
            out.append({"text": "Warm colours: the room reads as intimate and remembered.", "because": f"palette warmth {m['warmth']:+.2f}"})
        elif m["warmth"] < -0.05:
            out.append({"text": "Cool colours: the room reads as detached and quiet.", "because": f"palette warmth {m['warmth']:+.2f}"})
        else:
            out.append({"text": "Neutral colour temperature: the colours do not push the mood either way.", "because": f"palette warmth {m['warmth']:+.2f}"})
        if m["brightness"] is not None and m["brightness"] < 0.55:
            out.append({"text": "A darker palette gives low-key, enclosed light.", "because": f"average brightness {m['brightness']:.2f}"})
        elif m["brightness"] is not None and m["brightness"] >= 0.7:
            out.append({"text": "A pale palette gives an airy, exposed look.", "because": f"average brightness {m['brightness']:.2f}"})
        if m["saturation"] is not None and m["saturation"] >= 0.4:
            out.append({"text": "Rich colour makes the setting feel full and lived in.", "because": f"average saturation {m['saturation']:.2f}"})
        elif m["saturation"] is not None and m["saturation"] < 0.2:
            out.append({"text": "Muted colour makes the setting feel restrained.", "because": f"average saturation {m['saturation']:.2f}"})
    if m["central_objects"] <= 1:
        out.append({"text": "An almost empty playing area: space between people reads as distance or restraint.", "because": f"{m['central_objects']} object(s) in the middle of the stage"})
    elif m["central_objects"] >= 3:
        out.append({"text": "A furnished playing area keeps people close to objects and to each other.", "because": f"{m['central_objects']} objects in the middle of the stage"})
    if m["personal_props"] >= 2:
        out.append({"text": "Personal objects suggest a shared history.", "because": f"{m['personal_props']} personal prop(s)"})
    elif m["personal_props"] == 0:
        out.append({"text": "No personal objects: nothing shows that anyone has a past here.", "because": "0 personal props"})
    if m["peak_obstructions"] is not None:
        if m["peak_obstructions"] >= 1:
            out.append({"text": "Furniture stands between the two people at the peak of the scene.", "because": f"{m['peak_obstructions']} solid object(s) on the line between them"})
        else:
            out.append({"text": "Nothing stands between the two people at the peak of the scene.", "because": f"gap {m['peak_gap']:.2f}, clear line"})
    return out
