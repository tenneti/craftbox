"""Rule-based draft of a director's plan from a processed scene. Deterministic: same input, same plan.

The planner reads beat timings and intensities from the screenplay analysis, then chooses blocking and
coverage from the approach's knobs. It never writes story text; every shot gets a templated purpose note
that names the beat and characters. Everything it produces is a proposal the director can edit.
"""
import math
import re

from app.crafts.direction import approaches as ap

PURPOSE_LABEL = {
    "establish": "Establish", "reveal": "Reveal", "emphasize_emotion": "Emphasize emotion", "reaction": "Reaction",
    "connect": "Connect", "follow_movement": "Follow movement", "insert_detail": "Insert detail",
    "show_distance": "Show distance", "transition": "Transition", "closure": "Closure",
}
ENTER_WORDS = ("enters", "walks in", "arrives", "steps in", "comes in")
EXIT_WORDS = ("steps out", "leaves", "exits", "walks out", "goes out")
MOVE_WORDS = ("enters", "walks", "turns", "steps", "crosses", "moves", "stops", "rises", "sits", "turns to go")
REACT_WORDS = ("laughs", "trembles", "stops", "watches", "stares", "hesitates", "smiles", "looks")


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def pt(x, y):
    return {"x": round(clamp(x), 3), "y": round(clamp(y), 3)}


def band(intensity):
    return "low" if intensity < 4 else ("mid" if intensity < 7 else "high")


def stage_for(scene, names):
    slots = {"door": (0.08, 0.88), "counter": (0.74, 0.42), "desk": (0.74, 0.42), "table": (0.7, 0.45), "bar": (0.74, 0.42),
             "shelf": (0.5, 0.08), "shelves": (0.5, 0.08), "bookcase": (0.5, 0.08), "window": (0.18, 0.06), "lamp": (0.88, 0.2), "sign": (0.14, 0.82)}
    objs, free = [], []
    for p in scene.get("props", []):
        key = next((k for k in slots if k in p["name"].lower()), None)
        if key:
            objs.append({"id": p["id"], "name": p["name"], "x": slots[key][0], "y": slots[key][1]})
        else:
            free.append(p)
    for k, p in enumerate(free, 1):
        objs.append({"id": p["id"], "name": p["name"], "x": round(k / (len(free) + 1), 2), "y": 0.12})
    if not any("door" in o["name"].lower() for o in objs):
        objs.append({"id": "P-DOOR", "name": "Door", "x": 0.08, "y": 0.88})
    chars = [c for c in scene["characters"]]
    axis = {"between": chars[:2], "note": "Line between the two main characters; camera side A is the audience (master) side."} if len(chars) >= 2 else {}
    return {"width_m": 6.0, "depth_m": 5.0, "layout_note": "Normalised 0-1 plan: x left to right as the master camera sees it, y back wall to audience.",
            "objects": objs, "axis": axis}


def _find(objs, *words):
    for o in objs:
        if any(w in o["name"].lower() for w in words):
            return o
    return None


def make_blocking(scene, san, names, stage):
    chars = scene["characters"]
    objs = stage["objects"]
    door = _find(objs, "door") or objs[0]
    first_actions = " ".join(e["text"] for e in scene["elements"][:4] if e["type"] == "action").lower()
    visitor = next((c for c in chars if names[c].lower() in first_actions and any(w in first_actions for w in ENTER_WORDS)), None)
    last_text = " ".join(e["text"] for e in scene["elements"][-3:] if e["type"] == "action").lower()
    exits = visitor if (visitor and any(w in last_text for w in EXIT_WORDS)) else None
    host = next((c for c in chars if c != visitor), chars[0] if chars else None)
    anchor = _find(objs, "counter", "desk", "table", "bar") or {"x": 0.7, "y": 0.5}
    host_pos = pt(anchor["x"] - 0.04, anchor["y"] + 0.14)
    others = [c for c in chars if c not in (visitor, host)]
    prop_focus = next((o for o in objs if o["id"] != door["id"]), door)
    blocking, prev_end = [], {}
    beats = scene.get("beats", [])
    for k, beat in enumerate(beats):
        inten = beat.get("intensity", 5)
        role = beat.get("role")
        dial = [e for e in scene["elements"] if e["id"] in beat.get("element_ids", []) and e["type"] == "dialogue"]
        exchange = len({e["character_id"] for e in dial}) >= 2
        d = 0.50 - 0.036 * inten
        ends = {}
        if host:
            ends[host] = pt(host_pos["x"] - (0.04 if inten >= 8 else 0), host_pos["y"])
        if visitor:
            if role == "resolution" and exits:
                ends[visitor] = pt(door["x"] + 0.06, door["y"] - 0.04)
            else:
                ends[visitor] = pt(ends[host]["x"] - d if host else 0.4, (ends[host]["y"] if host else 0.6) + (0.05 if k % 2 else 0.0))
        for j, c in enumerate(others):
            ends[c] = pt(0.45 + 0.1 * j, 0.78)
        if not visitor and len(chars) >= 2 and host:   # nobody enters: everyone is already in the room
            for j, c in enumerate([x for x in chars if x != host]):
                ends[c] = pt(ends[host]["x"] - d - 0.1 * j, ends[host]["y"] + 0.04)
        entries = []
        for c in chars:
            end = ends.get(c)
            if end is None:
                continue
            entering = bool(visitor == c and k == 0)
            start = pt(door["x"] + 0.02, door["y"]) if entering else prev_end.get(c, end)
            other = next((x for x in chars if x != c), None)
            if exchange or inten >= 6 or role in ("turning_point", "climax"):
                facing = f"toward:{other}" if other else f"object:{prop_focus['id']}"
            elif role == "resolution" and c == visitor and exits:
                facing = f"object:{door['id']}"
            else:
                facing = f"object:{prop_focus['id']}"
            mid = pt((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2 + 0.04)
            moved = math.hypot(start["x"] - end["x"], start["y"] - end["y"]) > 0.12
            tgt = facing.split(":", 1)[1]
            is_exit = bool(role == "resolution" and exits == c)
            entries.append({"character_id": c, "start": start, "end": end, "path": [start, mid, end] if moved else [start, end], "facing": facing,
                            "posture": "tense" if inten >= 7 else ("guarded" if inten >= 4 else "composed"),
                            "action": ("enters through the door" if entering else ("leaves through the door" if is_exit else ("moves closer" if moved else "holds position"))),
                            "eyeline": {"target": tgt, "note": ""}, "entrance": {"from": door["id"]} if entering else None,
                            "exit": {"to": door["id"]} if is_exit else None})
            prev_end[c] = end
        blocking.append({"beat_id": beat["id"], "notes": f"Intensity {inten}: " + ("characters close the distance." if inten >= 6 else "distance is kept."), "characters": entries})
    return blocking, {"visitor": visitor, "host": host}


def _lens(size, scale):
    return round(ap.LENS_BY_SIZE[size] * scale / 5) * 5


def previz(shot, positions, side, objects):
    """Camera placement metadata for later previz tools (derived, in stage units / metres)."""
    subs = [positions[s] for s in shot["subject"] if s in positions]
    if subs:
        tx = sum(p["x"] for p in subs) / len(subs); ty = sum(p["y"] for p in subs) / len(subs)
    elif positions:
        tx = sum(p["x"] for p in positions.values()) / len(positions); ty = sum(p["y"] for p in positions.values()) / len(positions)
    else:
        tx, ty = 0.5, 0.5
    dist = ap.CAMERA_DISTANCE[shot["size"]]
    cx, cy = (tx, ty + dist) if side == "A" else ((tx, ty - dist) if side == "B" else (clamp(tx - dist, -1, 2), ty))
    fov = round(math.degrees(2 * math.atan(18 / shot.get("lens_mm", 50))), 1)
    return {"camera_position": {"x": round(cx, 3), "y": round(cy, 3), "height_m": ap.HEIGHT_M[shot["angle"]]},
            "target": {"x": round(tx, 3), "y": round(ty, 3)}, "fov_deg": fov, "lens_mm": shot.get("lens_mm"), "movement": shot["movement"],
            "notes": ""}


def _snippet(covers, els):
    """A short quote of the first script line a shot covers, so notes differ from shot to shot."""
    if not covers or covers[0] not in els:
        return ""
    text = " ".join(els[covers[0]]["text"].split())
    ellipsis = "…" if len(text) > 48 else ""
    return f"Covers: “{text[:48]}{ellipsis}”."


def _board(shot, names):
    who = " and ".join(names.get(s, s) for s in shot["subject"]) or "the room"
    return {"description": f"{shot['size']} {shot['framing'].replace('_', ' ')}, {shot['angle']} angle, {shot['movement'].replace('_', ' ')}: {who}.", "frame_ref": None}


def _note(purpose, subj, beat, names, extra=""):
    who = " and ".join(names.get(s, s) for s in subj) or "the space"
    text = {
        "establish": f"Establish the room and the two people in it before anything is said ({beat['title']}).",
        "reveal": f"Reveal what changes the scene: hold on {who} as it lands ({beat['title']}).",
        "emphasize_emotion": f"Hold on {who} so the audience reads the feeling directly ({beat['title']}).",
        "reaction": f"Show {who} taking in what was just said or shown ({beat['title']}).",
        "connect": f"Keep both people in the exchange so we feel the pull between them ({beat['title']}).",
        "follow_movement": f"Follow {who}'s movement so we see where the distance changes ({beat['title']}).",
        "insert_detail": f"Detail of an object that carries meaning in this beat ({beat['title']}).",
        "show_distance": f"Frame {who} apart to show the space still between them ({beat['title']}).",
        "transition": f"Neutral on-axis shot that lets the camera change sides without breaking the geometry ({beat['title']}).",
        "closure": f"Close the scene on {who} and leave the question open ({beat['title']}).",
    }[purpose]
    return (text + (" " + extra if extra else "")).strip()


def draft_shots(scene, san, names, approach, blocking, stage, roles):
    els = {e["id"]: e for e in scene["elements"]}
    san_el = {e["id"]: e for e in san["elements"]}
    san_beats = {b["id"]: b for b in san["beats"]}
    objs = stage["objects"]
    shots, n_total = [], 0
    last_beat = scene["beats"][-1]["id"] if scene.get("beats") else None
    cross = approach.get("axis_cross_at_climax")
    pre = approach.get("preset", approach["id"])
    pos_by_beat = {b["beat_id"]: {c["character_id"]: c["end"] for c in b["characters"]} for b in blocking}
    counter = {"size": 0, "move": 0, "angle": 0, "size2": 0}
    prev = None
    side_now = "A"

    def add(beat, group, subject, size, movement, angle, framing, side, purpose, note_extra, dur, covers):
        nonlocal prev, n_total
        n_total += 1
        if prev and prev["camera_side"] == side and subject and prev["subject"] == subject and prev["angle"] == angle and prev["framing"] == framing                 and abs(ap.SIZES.index(prev["size"]) - ap.SIZES.index(size)) <= 1:
            angle = "high" if angle == "eye" else "eye"   # same subject, near-same size: change the angle to avoid a jump cut
        shot = {"shot_id": f"{scene['id']}-S{n_total:02d}", "beat_id": beat["id"], "covers": covers, "purpose": purpose,
                "purpose_note": _note(purpose, subject, beat, names, (note_extra + " " + _snippet(covers, els)).strip()), "size": size, "angle": angle, "movement": movement,
                "framing": framing, "camera_side": side, "lens_mm": _lens(size, approach.get("lens_scale", 1.0)), "subject": subject,
                "duration_seconds": max(1.0, round(dur * 2) / 2), "transition_in": "cut", "intensity": beat.get("intensity", 5), "status": "proposed", "review_note": ""}
        shot["previz"] = previz(shot, pos_by_beat.get(beat["id"], {}), side, objs)
        shot["storyboard"] = _board(shot, names)
        shots.append(shot); prev = shot
        return shot

    def pick(options, key, avoid=None):
        for _ in range(len(options)):
            v = options[counter[key] % len(options)]; counter[key] += 1
            if avoid is None or v != avoid:
                return v
        return options[0]

    for bi, beat in enumerate(scene.get("beats", [])):
        bid = beat["id"]
        inten = beat.get("intensity", 5)
        role = roles.get(bid)
        b_an = san_beats[bid]
        ids = [i for i in beat.get("element_ids", []) if i in els]
        if not ids:
            continue
        dur = max(b_an["duration_seconds"], 1.0)
        sens = approach["intensity_sensitivity"]
        target = approach["avg_shot_seconds"] * (1.2 - 0.9 * sens * inten / 10)
        n = int(max(1, min(round(dur / target), len(ids), 5)))
        if role in ("turning_point", "climax"):   # peak beats: every change of kind or speaker gets its own shot
            groups, last_key = [], None
            for i in ids:
                key = (els[i]["type"], els[i].get("character_id") if role == "climax" else None)
                if key != last_key:
                    groups.append([])
                groups[-1].append(i); last_key = key
        else:
            groups = [[] for _ in range(n)]
            t0 = san_el[ids[0]]["start_seconds"]
            for i in ids:
                mid = san_el[i]["start_seconds"] + san_el[i]["duration_seconds"] / 2 - t0
                groups[min(n - 1, int(mid / (dur / n)))].append(i)
            groups = [g for g in groups if g]
        bnd = band(inten)
        for gi, g in enumerate(groups):
            gdur = sum(san_el[i]["duration_seconds"] for i in g)
            dials = [els[i] for i in g if els[i]["type"] == "dialogue"]
            actions = [els[i] for i in g if els[i]["type"] == "action"]
            text = " ".join(e["text"] for e in actions).lower()
            first_shot = not shots
            is_last_group = bid == last_beat and gi == len(groups) - 1
            side = side_now
            if cross and role == "climax" and gi == 0:
                side = "axis"
            elif cross and role == "climax":
                side_now = side = "B"
            elif cross and role == "resolution" and gi == 0 and side_now == "B":
                side = "axis"
            elif cross and role == "resolution":
                side_now = side = "A"
            speaker = dials[0]["character_id"] if dials else None
            listener = next((c for c in scene["characters"] if c != speaker), None)
            mentioned = [c for c in scene["characters"] if names[c].lower() in text]
            sizes = approach["size_by_band"][bnd]; moves = approach["movement_by_band"][bnd]; angles = approach["angle_by_band"][bnd]
            if first_shot:
                add(beat, g, list(scene["characters"]), approach["establish"]["size"], approach["establish"]["movement"], "eye", "wide", "A",
                    "establish", "", gdur, g)
                shots[-1]["transition_in"] = "fade"
                continue
            if is_last_group:
                size = "EWS" if pre == "observational" else "WS"
                s = add(beat, g, list(scene["characters"]), size, "static", "eye", "wide", side if side != "axis" else "A", "closure", "", gdur, g)
                s["transition_in"] = approach.get("closing_transition", "cut")
                continue
            if role == "climax" and cross and gi == 0:
                s = add(beat, g, list(scene["characters"]), "MS", "push_in", "eye", "two_shot", "axis", "transition", "", gdur, g)
                continue
            if role == "resolution" and cross and gi == 0 and side == "axis":
                add(beat, g, list(scene["characters"]), "MWS", "track", "eye", "two_shot", "axis", "follow_movement", "", gdur, g)
                continue
            if dials:
                who = [speaker]
                framing = approach["exchange_framing"][bnd]
                size = pick(sizes, "size", prev["size"] if prev else None)
                if framing == "two_shot" and role not in ("turning_point", "climax"):
                    size = pick(["MWS", "WS", "MS"], "size2", prev["size"] if prev else None)
                    who = [speaker, listener] if listener else [speaker]
                if len({d["character_id"] for d in dials}) >= 2:
                    framing = "two_shot"; who = [c for c in scene["characters"] if c in {d["character_id"] for d in dials}]
                    size = "MS" if pre == "intimate" or role in ("turning_point", "climax") else pick(["MWS", "WS", "MS"], "size2", prev["size"] if prev else None)
                move = pick(moves, "move"); angle = pick(angles, "angle")
                if prev and prev["subject"] == who and prev["size"] == size and prev["angle"] == angle:
                    size = pick(sizes, "size", size)
                purpose = "connect" if framing in ("two_shot", "over_shoulder") else ("emphasize_emotion" if inten >= 7 else "connect")
                if framing == "two_shot" and size in ("WS", "MWS", "EWS") and inten < 7:
                    purpose = "show_distance"
                if prev and prev["subject"] != who and framing == "single" and not (prev["framing"] == "single"):
                    purpose = "emphasize_emotion"
                add(beat, g, who, size, move, angle, framing, side, purpose, "", gdur, g)
                continue
            # action-only group
            hits = [w for w in re.findall(r"\b(book|paperback|ticket|sign|shelf|letter|photo|key|cup|phone)\b", text)]
            if hits and (role in ("turning_point", "climax") or "inside" in text or "opens" in text):
                size = "ECU" if role == "turning_point" else "CU"
                total = gdur
                ins = add(beat, g, [], size, "static", "high" if role == "turning_point" else "eye", "insert", "A" if side == "axis" else side,
                          "reveal" if role in ("turning_point", "climax") else "insert_detail", f"Object: {hits[-1]}.", max(1.0, total - 1.5), g)
                if approach.get("reaction_on_peak") and role == "turning_point":
                    who = [c for c in scene["characters"] if names[c].lower() in text] or ([listener] if listener else [])
                    who = who[:1]
                    ins["duration_seconds"] = max(1.0, round((total - 1.5) * 2) / 2)
                    add(beat, [], who, "CU", pick(moves, "move"), "eye", "single", side if side != "axis" else "A", "reaction", "", 1.5, [])
                continue
            move_hit = any(w in text for w in MOVE_WORDS)
            react_hit = any(w in text for w in REACT_WORDS)
            who = mentioned[:1] if (react_hit and mentioned) else list(scene["characters"])
            if move_hit and not react_hit:
                size = pick(sizes, "size", prev["size"] if prev else None)
                add(beat, g, mentioned[:1] or list(scene["characters"]), size, "track" if "track" in moves or inten >= 4 else pick(moves, "move"), "eye",
                    "single" if mentioned[:1] else "wide", side, "follow_movement", "", gdur, g)
            elif react_hit:
                size = pick(sizes, "size", prev["size"] if prev else None)
                add(beat, g, who[:1] or list(scene["characters"]), size, pick(moves, "move"), pick(angles, "angle"), "single" if who[:1] else "wide", side,
                    "reaction", "", gdur, g)
            else:
                add(beat, g, list(scene["characters"]), "WS" if inten < 5 else "MWS", pick(moves, "move"), "eye", "wide" if inten < 5 else "two_shot", side,
                    "show_distance" if inten < 5 else "connect", "", gdur, g)
    return shots


def interpretation(scene, approach, names, who, beats):
    visitor, host = who["visitor"], who["host"]
    v = names.get(visitor or "", None) or names.get(host or "", "the visitor")
    h = names.get(host or "", "the host") if visitor else (names.get(scene["characters"][1], "the other") if len(scene["characters"]) > 1 else "the other")
    peak = max(scene.get("beats", [{"id": None, "intensity": 0}]), key=lambda b: b.get("intensity", 0))
    return {
        "summary": " ".join(x for x in (scene.get("synopsis", ""), scene.get("objective", ""), scene.get("conflict", ""), scene.get("outcome", "")) if x).strip() or "Scene summary to be written.",
        "directorial_intent": approach["intent"].format(visitor=v, host=h),
        "tone": approach["tone"],
        "visual_motifs": list(approach["motifs"]),
        "emotional_arc": [{"beat_id": b["id"], "emotion": b.get("emotion", ""), "intensity": b.get("intensity", 5)} for b in beats],
        "key_moment_beat_id": peak["id"],
    }
