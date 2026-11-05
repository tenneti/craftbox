"""What changed upstream since a lighting plan was made (script, art treatment, director's blocking and cameras), and rebasing onto it.

Nothing is changed silently: ``compute`` only reports; ``rebase`` returns a new document in which the affected items are sent back
to review (their earlier status is kept in ``previous_status``). The approved original is never touched.
"""
import copy

from app.crafts.lighting import plan as pl


def _diff(old, new):
    changed = sorted(k for k in old if k in new and old[k] != new[k])
    removed = sorted(k for k in old if k not in new)
    added = sorted(k for k in new if k not in old)
    return changed, removed, added


def compute(doc, screenplay, art, plan=None):
    src = doc.get("source") or {}
    san = next((s for s in (screenplay.get("analysis") or {}).get("scenes", []) if s["scene_id"] == doc["scene_id"]), None)
    if san is None:
        return {"stale": True, "reasons": {}, "affected_lights": [l["id"] for l in doc["lights"]], "affected_adjustments": [a["id"] for a in doc.get("adjustments", [])], "changed_beats": [], "changed_objects": [],
                "changed_shots": [], "time_changed": False, "summary": f"Scene {doc['scene_id']} is no longer in the screenplay."}
    cb, rb, _ = _diff(src.get("beat_hashes", {}), {b["id"]: b["hash"] for b in san["beats"]})
    script_beats = sorted(set(cb) | set(rb))
    old_art = src.get("art") or {}
    co, ro, ao = _diff(old_art.get("object_hashes", {}), pl.object_hashes(art)) if art else ([], [], [])
    changed_objs = sorted(set(co) | set(ro))
    time_changed = bool(art) and old_art.get("time_of_day", "") != (art["location"].get("environment") or {}).get("time_of_day", "")
    old_plan = src.get("plan") or {}
    blocking_beats, changed_shots = [], []
    if old_plan and plan is not None:
        nb = pl.blocking_hashes(plan)
        blocking_beats = sorted(b for b, h in old_plan.get("blocking_hashes", {}).items() if nb.get(b) != h)
        nc = {k: pl.camera_hash(s) for k, s in pl.shot_index(plan).items()}
        changed_shots = sorted(k for k, h in old_plan.get("camera_hashes", {}).items() if nc.get(k) != h)
    beat_of = {s["shot_id"]: s["beat_id"] for s in (plan or {}).get("shots", [])}
    touched_beats = set(script_beats) | set(blocking_beats)
    reasons, aff_l, aff_a = {}, [], []
    for l in doc["lights"]:
        r = []
        for f in ("motivated_by", "practical_object_id"):
            if l.get(f) and l[f] in changed_objs:
                r.append(f"the set piece {l[f]} changed in the art treatment")
        if r:
            aff_l.append(l["id"]); reasons[l["id"]] = r
    for a in doc.get("adjustments", []):
        r = []
        if beat_of.get(a["shot_id"]) in touched_beats:
            r.append("the script or the blocking changed in this shot's beat")
        if a["shot_id"] in changed_shots:
            r.append("the camera for this shot moved")
        if old_plan and plan is not None and a["shot_id"] not in beat_of:
            r.append("the shot is no longer in the direction plan")
        if r:
            aff_a.append(a["id"]); reasons[a["id"]] = r
    stale = bool(script_beats or changed_objs or time_changed or blocking_beats or changed_shots or aff_a)
    bits = []
    if script_beats:
        bits.append(f"the script changed in beat(s) {', '.join(b.split('-')[-1] for b in script_beats)}")
    if changed_objs:
        bits.append(f"the art design changed these set pieces: {', '.join(changed_objs)}")
    if time_changed:
        bits.append("the art design's time of day changed")
    if blocking_beats:
        bits.append(f"the blocking changed in beat(s) {', '.join(b.split('-')[-1] for b in blocking_beats)}")
    if changed_shots:
        bits.append(f"cameras moved for {', '.join(s.split('-')[-1] for s in changed_shots)}")
    summary = ("Upstream changed: " + "; ".join(bits) + f". {len(aff_l)} light(s) and {len(aff_a)} shot adjustment(s) need another look.") if stale else "Up to date with the script, the art design and the director's plan."
    return {"stale": stale, "reasons": reasons, "affected_lights": aff_l, "affected_adjustments": aff_a, "changed_beats": script_beats, "blocking_beats": blocking_beats, "changed_objects": changed_objs,
            "changed_shots": changed_shots, "time_changed": time_changed, "summary": summary}


def rebase(doc, screenplay, art, plan=None):
    imp = compute(doc, screenplay, art, plan)
    out = copy.deepcopy(doc)
    for l in out["lights"]:
        if l["id"] in imp["affected_lights"]:
            l["previous_status"] = l["status"]
            l["status"] = "needs_review"
    for a in out.get("adjustments", []):
        if a["id"] in imp["affected_adjustments"]:
            a["previous_status"] = a["status"]
            a["status"] = "needs_review"
    return out, imp
