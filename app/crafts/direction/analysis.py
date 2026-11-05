"""Direction plan analysis: timeline, coverage gaps, variety, pacing, blocking and continuity checks.

Geometry convention. Stage coordinates run 0..1: x from master-left to master-right, y from the back
wall (0) to the audience side (1). Camera side "A" is the master side (audience side of the line between
the two main characters), "B" the opposite side, "axis" a neutral camera on the line. Seen from side B
screen left/right are mirrored, which is what the 180-degree rule protects.
"""
from collections import Counter

from app.crafts.direction.approaches import SIZES

SIZE_RANK = {s: i for i, s in enumerate(SIZES)}
JUMP_TOLERANCE = 0.06      # beat-to-beat position drift allowed without an entrance (stage units)
OVER_PCT, UNDER_PCT = 0.15, -0.20   # total shot time vs script estimate (guess; advice only)
FACE_EPS = 0.02


def _issue(issues, rule, severity, message, shots=(), beats=()):
    issues.append({"id": f"{rule}-{len(issues) + 1}", "rule": rule, "severity": severity, "message": message,
                   "shot_ids": list(shots), "beat_ids": list(beats)})


def _mirror(direction, side):
    if side == "B" and direction in ("L", "R"):
        return "R" if direction == "L" else "L"
    return direction


def facing_direction(entry, positions, objects):
    """Master-frame screen direction a character faces: 'L', 'R' or 'N' (toward/away from camera)."""
    facing = entry.get("facing", "")
    me = entry["end"]
    if facing == "screen_left":
        return "L"
    if facing == "screen_right":
        return "R"
    target = None
    if facing.startswith("toward:") and facing[7:] in positions:
        target = positions[facing[7:]]
    elif facing.startswith("object:") and facing[7:] in objects:
        target = objects[facing[7:]]
    if target is None:
        return "N"
    dx = target["x"] - me["x"]
    return "R" if dx > FACE_EPS else ("L" if dx < -FACE_EPS else "N")


def analyze(plan, scene, san, names):
    """Return the analysis block for ``plan`` against the scene (authored) and its analysis ``san``."""
    issues = []
    beats = {b["id"]: b for b in scene.get("beats", [])}
    beat_ids = [b["id"] for b in scene.get("beats", [])]
    beat_idx = {b: i for i, b in enumerate(beat_ids)}
    elements = {e["id"]: e for e in scene["elements"]}
    objects = {o["id"]: o for o in plan["stage"]["objects"]}
    shots = plan["shots"]
    active = [s for s in shots if s["status"] != "rejected"]
    fps = plan.get("fps") or san.get("fps") or 24

    # ---- timeline -----------------------------------------------------------------------
    t, timeline = 0.0, []
    for n, s in enumerate(active, 1):
        timeline.append({"shot_id": s["shot_id"], "order": n, "start_seconds": round(t, 2), "end_seconds": round(t + s["duration_seconds"], 2),
                         "start_frame": round(t * fps), "duration_frames": max(1, round(s["duration_seconds"] * fps))})
        t += s["duration_seconds"]
    total = round(t, 2)
    script = san["estimated_seconds"]
    delta = round((total - script) / script, 3) if script else 0.0
    if active and delta > OVER_PCT:
        _issue(issues, "duration", "warning", f"Shots run {round(total - script, 1)} s ({round(delta * 100)}%) longer than the script estimate of {script} s.")
    if active and delta < UNDER_PCT:
        _issue(issues, "duration", "warning", f"Shots add up to {round(script - total, 1)} s ({round(-delta * 100)}%) less than the script estimate of {script} s.")

    # ---- references and ordering ----------------------------------------------------------
    for s in shots:
        if s["beat_id"] not in beats and s["status"] not in ("rejected", "needs_review"):
            _issue(issues, "reference", "error", f"{s['shot_id']} belongs to beat {s['beat_id']}, which no longer exists.", [s["shot_id"]])
        elif s["beat_id"] not in beats:
            _issue(issues, "reference", "error", f"{s['shot_id']} ({s['status']}) points at beat {s['beat_id']}, which no longer exists. Re-link or reject it.", [s["shot_id"]])
        for c in s.get("covers", []):
            if c not in elements:
                _issue(issues, "reference", "warning", f"{s['shot_id']} covers script line {c}, which no longer exists.", [s["shot_id"]])
    last_i = -1
    for s in active:
        i = beat_idx.get(s["beat_id"])
        if i is None:
            continue
        if i < last_i:
            _issue(issues, "order", "warning", f"{s['shot_id']} is placed before an earlier beat's shots; it is out of script order.", [s["shot_id"]], [s["beat_id"]])
        last_i = max(last_i, i)

    # ---- coverage ---------------------------------------------------------------------------
    covered = {c for s in active for c in s.get("covers", [])}
    beat_cov = []
    for bid in beat_ids:
        ids = [s["shot_id"] for s in active if s["beat_id"] == bid]
        beat_cov.append({"beat_id": bid, "shots": ids, "covered": bool(ids)})
        if not ids:
            _issue(issues, "coverage", "error", f"Beat '{beats[bid]['title']}' has no shots.", beats=[bid])
    unc_dialogue = [e["id"] for e in scene["elements"] if e["type"] == "dialogue" and e["id"] not in covered]
    for eid in unc_dialogue:
        e = elements[eid]
        _issue(issues, "coverage", "warning", f"No shot covers {names.get(e['character_id'], '?')}'s line \"{e['text'][:40]}\" ({eid}); is it heard off-screen?")
    unc_action = [e["id"] for e in scene["elements"] if e["type"] == "action" and e["id"] not in covered]

    # ---- purpose and variety ------------------------------------------------------------------
    purposes = Counter(s["purpose"] for s in active)
    if len(active) >= 4 and purposes and purposes.most_common(1)[0][1] / len(active) > 0.6:
        _issue(issues, "purpose", "warning", f"Most shots share one purpose ('{purposes.most_common(1)[0][0]}'); check each shot earns its place.")
    sig = lambda s: (s["size"], s["angle"], s["movement"], s["framing"], s["camera_side"], tuple(sorted(s["subject"])))
    sizes = Counter(s["size"] for s in active)
    run, longest, run_ids, best_ids = 0, 0, [], []
    prev = None
    for s in active:
        if prev is not None and s["size"] == prev["size"]:
            run += 1; run_ids.append(s["shot_id"])
        else:
            run, run_ids = 1, [s["shot_id"]]
        if run > longest:
            longest, best_ids = run, list(run_ids)
        prev = s
    if longest >= 3:
        _issue(issues, "variety", "warning", f"{longest} consecutive shots use the same size ({sizes.most_common(1)[0][0]}); vary the framing.", best_ids)
    for a, b in zip(active, active[1:]):
        if sig(a) == sig(b):
            _issue(issues, "variety", "warning", f"{a['shot_id']} and {b['shot_id']} are the same setup back to back (jump-cut risk).", [a["shot_id"], b["shot_id"]])
    distinct = len({sig(s) for s in active})
    if len(active) >= 4 and sizes and sizes.most_common(1)[0][1] / len(active) > 0.5:
        _issue(issues, "variety", "warning", f"More than half of the shots are {sizes.most_common(1)[0][0]}; the scene lacks shot-size variety.")
    if len(active) >= 4 and distinct / len(active) < 0.5:
        _issue(issues, "variety", "warning", f"Only {distinct} distinct setups across {len(active)} shots; the shot list is repetitive.")
    variety = {"sizes": dict(sizes), "angles": dict(Counter(s["angle"] for s in active)), "movements": dict(Counter(s["movement"] for s in active)),
               "framings": dict(Counter(s["framing"] for s in active)), "distinct_setups": distinct,
               "variety_score": round(distinct / len(active), 2) if active else 0, "longest_same_size_run": longest,
               "close_ups": sum(1 for s in active if s["size"] in ("ECU", "CU")), "wide": sum(1 for s in active if s["size"] in ("WS", "EWS"))}

    # ---- pacing ---------------------------------------------------------------------------------
    avg_all = round(total / len(active), 2) if active else 0
    approach = plan["approach"]
    sens = approach.get("intensity_sensitivity", 0.5)
    pacing = []
    for bid in beat_ids:
        bs = [s for s in active if s["beat_id"] == bid]
        inten = beats[bid].get("intensity", 5)
        avg = round(sum(s["duration_seconds"] for s in bs) / len(bs), 2) if bs else None
        expected = round(approach["avg_shot_seconds"] * (1.2 - 0.9 * sens * inten / 10), 2)
        pacing.append({"beat_id": bid, "intensity": inten, "shots": len(bs), "avg_shot_seconds": avg, "expected_shot_seconds": expected})
    if beat_ids and active:
        peak = max(pacing, key=lambda p: p["intensity"])
        if peak["avg_shot_seconds"] and peak["avg_shot_seconds"] > avg_all and peak["shots"] >= 1 and len(active) >= 4:
            _issue(issues, "pacing", "warning", f"The peak beat ('{beats[peak['beat_id']]['title']}') is not cut tighter than the scene average ({peak['avg_shot_seconds']} s vs {avg_all} s).", beats=[peak["beat_id"]])

    # ---- blocking -----------------------------------------------------------------------------------
    bk = {b["beat_id"]: b for b in plan["blocking"]}
    char_ids = set(names)
    present, last_end, positions_by_beat = {}, {}, {}
    for bid in beat_ids:
        entry = bk.get(bid)
        if not entry:
            _issue(issues, "blocking", "warning", f"No blocking for beat '{beats[bid]['title']}'.", beats=[bid])
            continue
        positions_by_beat[bid] = {c["character_id"]: c["end"] for c in entry["characters"]}
        for c in entry["characters"]:
            cid = c["character_id"]
            label = names.get(cid, cid)
            if cid not in char_ids:
                _issue(issues, "blocking", "error", f"Blocking places unknown character {cid}.", beats=[bid]); continue
            entering = bool(c.get("entrance"))
            if entering and present.get(cid):
                _issue(issues, "blocking", "error", f"{label} enters in '{beats[bid]['title']}' but is already on stage.", beats=[bid])
            if not entering and cid in last_end:
                if not present.get(cid):
                    _issue(issues, "blocking", "error", f"{label} reappears in '{beats[bid]['title']}' after leaving, with no entrance.", beats=[bid])
                else:
                    p, s0 = last_end[cid], c["start"]
                    if abs(p["x"] - s0["x"]) > JUMP_TOLERANCE or abs(p["y"] - s0["y"]) > JUMP_TOLERANCE:
                        _issue(issues, "blocking", "error", f"{label} jumps position at the start of '{beats[bid]['title']}' (no movement shown).", beats=[bid])
            present[cid] = not c.get("exit")
            last_end[cid] = c["end"]
            target = c.get("facing", "")
            if target.startswith("toward:") and target[7:] not in char_ids:
                _issue(issues, "blocking", "warning", f"{label} faces unknown character {target[7:]}.", beats=[bid])
            if target.startswith("object:") and target[7:] not in objects:
                _issue(issues, "blocking", "warning", f"{label} faces unknown object {target[7:]}.", beats=[bid])
    for cid in scene["characters"]:
        if cid in char_ids and cid not in last_end:
            _issue(issues, "blocking", "warning", f"{names.get(cid, cid)} is in the scene but has no blocking.")

    # ---- continuity ---------------------------------------------------------------------------------------
    last_side, neutral = None, False
    for s in active:
        side = s["camera_side"]
        if side == "axis":
            neutral = True
            continue
        if last_side is not None and side != last_side:
            motivated = bool(s.get("axis_cross"))
            if not (neutral or motivated or s["purpose"] == "establish"):
                _issue(issues, "axis", "error",
                       f"{s['shot_id']} crosses the 180° line from side {last_side} to side {side} with no neutral (on-axis) shot or motivated move before it; left and right will flip.",
                       [s["shot_id"]], [s["beat_id"]])
        last_side, neutral = side, False
    for a, b in zip(active, active[1:]):
        if a["beat_id"] != b["beat_id"] or a["camera_side"] != b["camera_side"] or a["camera_side"] == "axis":
            continue
        if len(a["subject"]) == 1 and len(b["subject"]) == 1 and a["subject"] != b["subject"] and \
                a["framing"] in ("single", "over_shoulder") and b["framing"] in ("single", "over_shoulder"):
            pos = positions_by_beat.get(a["beat_id"])
            entry = bk.get(a["beat_id"])
            if pos and entry:
                dirs = {}
                for c in entry["characters"]:
                    dirs[c["character_id"]] = _mirror(facing_direction(c, pos, {k: {"x": o["x"], "y": o["y"]} for k, o in objects.items()}), a["camera_side"])
                da, db = dirs.get(a["subject"][0], "N"), dirs.get(b["subject"][0], "N")
                if da == "N" or db == "N" or da == db:
                    _issue(issues, "eyeline", "warning", f"Eyelines between {a['shot_id']} and {b['shot_id']} do not meet (they face {da} and {db} on screen); intended avoidance?", [a["shot_id"], b["shot_id"]], [a["beat_id"]])
    for a, b in zip(active, active[1:]):
        if a["camera_side"] == b["camera_side"] and a["subject"] and a["subject"] == b["subject"] and a["angle"] == b["angle"] \
                and a["framing"] == b["framing"] and a["size"] != b["size"] and abs(SIZE_RANK[a["size"]] - SIZE_RANK[b["size"]]) <= 1 \
                and b.get("transition_in", "cut") == "cut":
            _issue(issues, "jump_cut", "warning", f"{a['shot_id']} to {b['shot_id']}: same subject and angle with almost the same size is a jump cut; change the size by two steps or the angle.", [a["shot_id"], b["shot_id"]])
    for s in active:
        pos = positions_by_beat.get(s["beat_id"])
        if pos is None:
            continue
        for sub in s["subject"]:
            if sub in char_ids and sub not in pos:
                _issue(issues, "presence", "error", f"{s['shot_id']} frames {names.get(sub, sub)}, who is not on stage in this beat.", [s["shot_id"]], [s["beat_id"]])

    per_shot = []
    for tl, s in zip(timeline, active):
        entry = bk.get(s["beat_id"])
        facing = {}
        if entry:
            pos = {c["character_id"]: c["end"] for c in entry["characters"]}
            for c in entry["characters"]:
                facing[c["character_id"]] = _mirror(facing_direction(c, pos, {k: {"x": o["x"], "y": o["y"]} for k, o in objects.items()}), s["camera_side"])
        per_shot.append({**tl, "screen_facing": facing})

    status = Counter(s["status"] for s in shots)
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    unreviewed = status.get("proposed", 0) + status.get("needs_review", 0)
    return {
        "timeline": per_shot, "total_seconds": total, "script_seconds": script, "duration_delta": delta, "avg_shot_seconds": avg_all,
        "coverage": {"beats": beat_cov, "uncovered_beats": [b["beat_id"] for b in beat_cov if not b["covered"]],
                     "uncovered_dialogue": unc_dialogue, "uncovered_action": unc_action},
        "variety": variety, "purposes": dict(purposes), "pacing": pacing,
        "status_summary": {"approved": status.get("approved", 0), "rejected": status.get("rejected", 0),
                           "proposed": status.get("proposed", 0), "needs_review": status.get("needs_review", 0)},
        "issues": issues,
        "readiness": {"errors": errors, "warnings": warnings, "unreviewed": unreviewed,
                      "ready_for_approval": errors == 0 and unreviewed == 0 and bool(active),
                      "advice": "Advice only: you can approve a plan with open issues; the reasons are recorded."},
    }
