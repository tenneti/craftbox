"""Which design decisions went out of date after the screenplay or the director's plan changed. Never edits the original."""
import json


def _diff(old, new):
    return (sorted(k for k in old if k in new and old[k] != new[k]), sorted(k for k in old if k not in new), sorted(k for k in new if k not in old))


def _san(screenplay, scene_id):
    return next((s for s in (screenplay.get("analysis") or {}).get("scenes", []) if s["scene_id"] == scene_id), None)


def compute(art, screenplay, plan=None):
    src = art.get("source") or {}
    san = _san(screenplay, art["scene_id"])
    if san is None:
        return {"stale": True, "scene_removed": True, "changed_elements": [], "removed_elements": [], "changed_beats": [], "removed_beats": [], "removed_shots": [], "blocking_changed_beats": [],
                "removed_stage_objects": [], "affected_props": [p["id"] for p in art["props"]], "affected_variations": [v["id"] for v in art.get("variations", [])], "reasons": {},
                "summary": f"Scene {art['scene_id']} is no longer in the screenplay."}
    cb, rb, _ = _diff(src.get("beat_hashes", {}), {b["id"]: b["hash"] for b in san["beats"]})
    ce, re_, _ = _diff(src.get("element_hashes", {}), {e["id"]: e["hash"] for e in san["elements"]})
    old_plan = src.get("plan") or {}
    removed_shots, blocking_changed, removed_objs, plan_changed = [], [], [], False
    if old_plan and plan is not None:
        new_ids = {s["shot_id"] for s in plan.get("shots", [])}
        removed_shots = sorted(set(old_plan.get("shot_ids", [])) - new_ids)
        from app.crafts.art_direction.treatment import blocking_hashes
        nb = blocking_hashes(plan)
        blocking_changed = sorted(b for b, h in old_plan.get("blocking_hashes", {}).items() if nb.get(b) not in (None, h) or b not in nb)
        removed_objs = sorted(set(old_plan.get("stage_object_ids", [])) - {o["id"] for o in (plan.get("stage") or {}).get("objects", [])})
        plan_changed = (plan.get("analysis") or {}).get("plan_hash") != old_plan.get("plan_hash")
    changed = set(ce) | set(re_)
    reasons, affected_props, affected_vars = {}, [], []
    for p in art["props"]:
        r = []
        if set(p.get("mentions", [])) & changed:
            r.append("a script line that mentions it changed or was removed")
        if any(s["at_kind"] == "beat" and s["at_id"] in set(cb) | set(rb) for s in p.get("states", [])):
            r.append("a beat that holds one of its states changed or was removed")
        if any(s["at_kind"] == "shot" and s["at_id"] in removed_shots for s in p.get("states", [])):
            r.append("a shot that holds one of its states was removed")
        if set(p.get("shot_ids", [])) & set(removed_shots):
            r.append("a shot that shows it was removed")
        if r:
            reasons[p["id"]] = r
            affected_props.append(p["id"])
    for v in art.get("variations", []):
        if v["shot_id"] in removed_shots:
            reasons[v["id"]] = ["its shot was removed from the direction plan"]
            affected_vars.append(v["id"])
    stale = san["scene_hash"] != src.get("scene_hash") or plan_changed
    bits = []
    if san["scene_hash"] != src.get("scene_hash"):
        bits.append(f"{len(ce)} script line(s) changed, {len(re_)} removed, {len(cb)} beat(s) changed, {len(rb)} removed")
    if plan_changed:
        bits.append(f"the direction plan changed ({len(removed_shots)} shot(s) removed, blocking changed in {len(blocking_changed)} beat(s), {len(removed_objs)} stage object(s) removed)")
    if bits:
        bits.append(f"{len(affected_props)} prop(s) and {len(affected_vars)} variation(s) are affected")
    return {"stale": stale, "scene_removed": False, "changed_elements": ce, "removed_elements": re_, "changed_beats": cb, "removed_beats": rb, "removed_shots": removed_shots,
            "blocking_changed_beats": blocking_changed, "removed_stage_objects": removed_objs, "affected_props": affected_props, "affected_variations": affected_vars, "reasons": reasons,
            "summary": "; ".join(bits) if bits else "The script and the direction plan have not changed since this design was made."}


def rebase(art, screenplay, plan=None):
    imp = compute(art, screenplay, plan)
    new = json.loads(json.dumps(art))
    new.pop("analysis", None); new.pop("source", None)
    for coll, ids in (("props", imp["affected_props"]), ("variations", imp["affected_variations"])):
        for x in new.get(coll, []):
            if x["id"] in ids:
                if x["status"] != "needs_review":
                    x["previous_status"] = x["status"]
                x["status"] = "needs_review"
                note = "Design may be out of date: " + "; ".join(imp["reasons"].get(x["id"], []))
                x["notes" if coll == "props" else "note"] = (x.get("notes" if coll == "props" else "note", "") + " " + note).strip()
    if imp["blocking_changed_beats"] or imp["removed_stage_objects"]:
        new["layout"]["note"] = (new["layout"].get("note", "") + " [The director's blocking changed; check the layout against it.]").strip()
    return new, imp
