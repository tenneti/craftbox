"""Script-change tracking for direction plans.

A plan remembers the hashes of the beats and script lines it was built from (``plan.source``). Given a
newer screenplay, ``compute`` says what changed and which shots depend on it; ``rebase`` produces a new
plan in which only affected shots are sent back to review. Neither ever edits the original plan.
"""
import json


def _scene_an(screenplay, scene_id):
    return next((s for s in (screenplay.get("analysis") or {}).get("scenes", []) if s["scene_id"] == scene_id), None)


def _diff(old, new):
    return (sorted(k for k in old if k in new and old[k] != new[k]),
            sorted(k for k in old if k not in new),
            sorted(k for k in new if k not in old))


def compute(plan, screenplay):
    src = plan.get("source") or {}
    scene_id = plan["scene_id"]
    san = _scene_an(screenplay, scene_id)
    if san is None:
        affected = [s["shot_id"] for s in plan["shots"]]
        return {"stale": True, "scene_removed": True, "changed_beats": [], "removed_beats": [], "added_beats": [], "changed_elements": [],
                "removed_elements": [], "added_elements": [], "affected_shots": affected,
                "approved_affected": [s["shot_id"] for s in plan["shots"] if s["status"] == "approved"], "reasons": {sid: ["scene removed"] for sid in affected},
                "unplanned_beats": [], "unplanned_elements": [], "summary": f"Scene {scene_id} no longer exists in the screenplay."}
    new_beats = {b["id"]: b["hash"] for b in san["beats"]}
    new_els = {e["id"]: e["hash"] for e in san["elements"]}
    cb, rb, ab = _diff(src.get("beat_hashes", {}), new_beats)
    ce, re_, ae = _diff(src.get("element_hashes", {}), new_els)
    changed_el, removed_el = set(ce), set(re_)
    reasons = {}
    for s in plan["shots"]:
        r = []
        if s["beat_id"] in cb:
            r.append("its beat changed")
        if s["beat_id"] in rb:
            r.append("its beat was removed")
        hit = sorted(set(s.get("covers", [])) & changed_el)
        gone = sorted(set(s.get("covers", [])) & removed_el)
        if hit:
            r.append("script line(s) changed: " + ", ".join(hit))
        if gone:
            r.append("script line(s) removed: " + ", ".join(gone))
        if r:
            reasons[s["shot_id"]] = r
    covered = {c for s in plan["shots"] if s["status"] != "rejected" for c in s.get("covers", [])}
    new_el_types = {e["id"]: e["type"] for e in san["elements"]}
    unplanned_el = [e for e in ae if new_el_types.get(e) == "dialogue" and e not in covered]
    affected = list(reasons)
    stale = san["scene_hash"] != src.get("scene_hash")
    bits = []
    if stale:
        bits.append(f"{len(cb)} beat(s) changed, {len(rb)} removed, {len(ab)} added; {len(ce)} script line(s) changed, {len(re_)} removed, {len(ae)} added")
        bits.append(f"{len(affected)} shot(s) depend on changed material")
    return {"stale": stale, "scene_removed": False, "changed_beats": cb, "removed_beats": rb, "added_beats": ab,
            "changed_elements": ce, "removed_elements": re_, "added_elements": ae, "affected_shots": affected,
            "approved_affected": [s["shot_id"] for s in plan["shots"] if s["shot_id"] in reasons and s["status"] == "approved"],
            "reasons": reasons, "unplanned_beats": ab, "unplanned_elements": unplanned_el,
            "summary": "; ".join(bits) if bits else "The scene has not changed since this plan was made."}


def rebase(plan, screenplay):
    """New plan data (a copy) re-pointed at ``screenplay``: affected shots return to review, the rest keep their status."""
    imp = compute(plan, screenplay)
    new = json.loads(json.dumps(plan))
    new.pop("analysis", None); new.pop("source", None)
    for s in new["shots"]:
        if s["shot_id"] in imp["reasons"]:
            if s["status"] != "needs_review":
                s["previous_status"] = s["status"]
            s["status"] = "needs_review"
            note = "Script changed: " + "; ".join(imp["reasons"][s["shot_id"]])
            s["review_note"] = (s.get("review_note", "") + " " + note).strip() if note not in s.get("review_note", "") else s.get("review_note", "")
    for b in new["blocking"]:
        if b["beat_id"] in imp["changed_beats"] or b["beat_id"] in imp["removed_beats"]:
            b["notes"] = ("[Script changed: check this blocking] " + b.get("notes", "")).strip()
    return new, imp
