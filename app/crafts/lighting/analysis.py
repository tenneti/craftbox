"""Lighting analysis: approximate levels on the people, measures that explain a plan's feel, and the continuity and geometry checks.

Every number is a planning approximation (see ``geo``), not a physical simulation. Findings are advice: ``attention`` for a likely
mistake, ``note`` for something worth a look. Nothing here changes a plan.
"""
import math

from app.crafts.lighting import geo, plan as pl

GRID = [(0.15 + 0.7 * i / 11, 0.2 + 0.7 * j / 9) for j in range(10) for i in range(12)]
LOW = 0.12


def _issue(rule, severity, message, fix, **refs):
    return {"rule": rule, "severity": severity, "message": message, "fix": fix, **refs}


def solids_of(art, skip=()):
    return [geo.rect_of(o) for o in art["layout"]["objects"] if o.get("solid") and o["id"] not in skip]


def sample(lights, stage, solids, point):
    """Level, colour temperature and per-light parts at one point of the stage."""
    parts, blocked, total, m = {}, {}, 0.0, 0.0
    for l in lights:
        v, b = geo.light_at(l, stage, point, solids)
        parts[l["id"]], blocked[l["id"]] = v, b
        total += v
        m += v * geo.mired(l["color_temp_k"])
    kelvin = round(1e6 / (m / total)) if total > 0.005 else None
    return {"level": total, "kelvin": kelvin, "parts": parts, "blocked": blocked}


def _look_bearing(stage, at, facing, others, objects):
    if facing.startswith("toward:") and facing[7:] in others:
        return geo.bearing(stage, at, others[facing[7:]]["end"])
    if facing.startswith("object:"):
        o = next((o for o in objects if o["id"] == facing[7:]), None)
        if o:
            return geo.bearing(stage, at, (o["x"], o["y"]))
    return 0.0       # facing the audience, which is where the camera usually is


def subject_read(lights, stage, art, point, look_bearing, solids):
    s = sample(lights, stage, solids, point)
    face, key_face, fill_face, shadow = 0.0, 0.0, 0.0, None
    for l in lights:
        v = s["parts"][l["id"]]
        if v <= 0:
            continue
        to_light = geo.bearing(stage, point, (l["x"], l["y"])) if l.get("positional", True) else look_bearing
        f = 0.35 + 0.65 * max(0.0, math.cos(math.radians(geo.angle_diff(look_bearing, to_light))))
        face += v * f
        if l["role"] in ("key", "motivated") and v * f > key_face:
            key_face = v * f
            shadow = round(geo.bearing(stage, (l["x"], l["y"]), point), 0) if l.get("positional", True) else None
        elif l["role"] in ("fill", "ambient"):
            fill_face += v * f
    ratio = round(min(99.0, (key_face + fill_face) / max(fill_face, 0.01)), 1) if key_face > 0.03 else None
    return {"level": round(s["level"], 3), "face_level": round(face, 3), "kelvin": s["kelvin"], "key_fill_ratio": ratio, "shadow_deg": shadow, "blocked_lights": sorted(k for k, v in s["blocked"].items() if v and s["parts"][k] > 0)}


def key_of(lights):
    on = [l for l in lights if l.get("enabled", True) and l["role"] in ("key", "motivated") and l.get("positional", True)]
    on.sort(key=lambda l: (l["role"] != "key", -l["intensity"]))
    return on[0] if on else None


def camera_side_of(stage, shot, light):
    pv = shot.get("previz") or {}
    c, t = pv.get("camera_position"), pv.get("target")
    if not c or not t:
        return None
    ax, ay = geo.metres(stage, t["x"] - c["x"], t["y"] - c["y"])
    vx, vy = geo.metres(stage, light["x"] - c["x"], light["y"] - c["y"])
    cross = ax * vy - ay * vx
    return "right" if cross > 0.05 else ("left" if cross < -0.05 else "centre")


def centre_of(subjects, beat):
    pts = [beat[sj["character_id"]]["end"] for sj in subjects if sj["character_id"] in beat]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def shot_rows(doc, art, plan, stage, solids):
    names = {}
    rows = []
    pos = pl.beat_positions(plan)
    for s in (plan or {}).get("shots", []):
        if s.get("status") == "rejected":
            continue
        lights, adj = pl.resolve_shot(doc, s["shot_id"])
        key = key_of(lights)
        beat = pos.get(s["beat_id"], {})
        subjects = []
        for cid in s.get("subject") or list(beat):
            if cid not in beat:
                continue
            b = beat[cid]
            look = _look_bearing(stage, b["end"], b["facing"], beat, art["layout"]["objects"])
            sr = subject_read(lights, stage, art, b["end"], look, solids)
            st = subject_read(lights, stage, art, b["start"], _look_bearing(stage, b["start"], b["facing"], beat, art["layout"]["objects"]), solids)
            subjects.append({"character_id": cid, "level_start": st["face_level"], "level_end": sr["face_level"], "kelvin": sr["kelvin"], "key_fill_ratio": sr["key_fill_ratio"], "shadow_deg": sr["shadow_deg"], "blocked_lights": sr["blocked_lights"]})
        rows.append({"shot_id": s["shot_id"], "beat_id": s["beat_id"], "size": s["size"], "camera_side": s["camera_side"], "adjusted": bool(adj), "lights_on": [l["id"] for l in lights if l.get("enabled", True) and l["intensity"] > 0],
                     "key_id": key["id"] if key else None, "key_kelvin": key["color_temp_k"] if key else None, "key_intensity": key["intensity"] if key else None,
                     "key_side": camera_side_of(stage, s, key) if key else None, "key_bearing": round(geo.bearing(stage, (key["x"], key["y"]), centre_of(subjects, beat)), 0) if key and subjects else None, "subjects": subjects,
                     "fixtures_in_frame": pl.fixtures_in_frame(lights, s, stage), "reason": (adj or {}).get("reason", ""), "accepted": (adj or {}).get("accepted_findings", [])})
    return rows


def analyze(doc, scene, san, art, plan, names):
    stage = {"width_m": art["layout"]["width_m"], "depth_m": art["layout"]["depth_m"]}
    solids = solids_of(art)
    objs = {o["id"]: o for o in art["layout"]["objects"]}
    issues = []
    L = doc["lights"]
    on = [l for l in L if l["enabled"] and l["intensity"] > 0]
    cond = doc["conditions"]
    art_time = pl.guess_time((art["location"].get("environment") or {}).get("time_of_day"), scene.get("slugline"))

    # ---- conditions and time-of-day assumptions ----
    if (art["location"].get("environment") or {}).get("time_of_day", "").strip() and art_time != cond["time_of_day"]:
        issues.append(_issue("time_of_day_mismatch", "attention", f"The art design says “{art['location']['environment']['time_of_day']}” but this plan is for {cond['time_of_day'].replace('_', ' ')}.",
                             "Change the time of day here to match, or change it in the Art Lab so both crafts agree."))
    lo, hi = pl.NATURAL_K[cond["time_of_day"]]
    for l in L:
        if not l["enabled"]:
            continue
        if l["source"] == "natural" and l["kind"] in ("sun", "daylight", "window_daylight") and not pl.SUN_UP[cond["time_of_day"]]:
            issues.append(_issue("sun_at_night", "attention", f"{l['name']} ({l['id']}) is sunlight, but the time of day is {cond['time_of_day']}.", "Change its kind to moon or street light, switch it off, or change the time of day.", light_id=l["id"]))
        elif l["source"] == "natural" and l.get("positional", True) and not (lo <= l["color_temp_k"] <= hi):
            issues.append(_issue("natural_colour", "note", f"{l['name']} ({l['id']}) is natural light at {l['color_temp_k']} K; at {cond['time_of_day'].replace('_', ' ')} natural light is usually {lo}-{hi} K.",
                                 "Change the colour temperature, or mark the source as artificial if it is a lamp outside.", light_id=l["id"]))
    if not on:
        issues.append(_issue("no_lights", "attention", "No light is switched on.", "Add a light, or switch one on.", ))
    elif not any(l["role"] in ("key", "motivated", "practical") and l["intensity"] >= 0.2 for l in on):
        issues.append(_issue("no_main_light", "attention", "No light is strong enough to be the main light.", "Raise the intensity of a key, motivated or practical light to 0.2 or more."))

    # ---- placement and set geometry ----
    for l in L:
        for field, label in (("motivated_by", "motivated by"), ("practical_object_id", "attached to")):
            ref = l.get(field)
            if ref and ref not in objs:
                issues.append(_issue("unknown_object", "attention", f"{l['name']} ({l['id']}) is {label} “{ref}”, which is not in the art design.", "Choose a set piece that exists, or clear the link. If the piece was removed in the Art Lab, rebase this plan.", light_id=l["id"]))
        if l.get("practical_object_id") in objs:
            o = objs[l["practical_object_id"]]
            if geo.dist_m(stage, (l["x"], l["y"]), (o["x"], o["y"])) > 0.35:
                issues.append(_issue("practical_moved", "attention", f"{l['name']} ({l['id']}) should sit on {o['name']}, but it is {geo.dist_m(stage, (l['x'], l['y']), (o['x'], o['y'])):.1f} m away from it.",
                                     f"Move the light onto {o['name']} at {o['x']:.2f}, {o['y']:.2f}, or move the piece in the Art Lab.", light_id=l["id"]))
        if l.get("motivated_by") in objs and l["role"] in ("key", "motivated", "backlight", "rim"):
            o = objs[l["motivated_by"]]
            if geo.dist_m(stage, (l["x"], l["y"]), (o["x"], o["y"])) > 3.0:
                issues.append(_issue("motivation_far", "note", f"{l['name']} ({l['id']}) is meant to come from {o['name']} but stands {geo.dist_m(stage, (l['x'], l['y']), (o['x'], o['y'])):.1f} m from it.", f"Move it closer to {o['name']} so the audience can believe the source.", light_id=l["id"]))
        if l.get("positional", True):
            for o in art["layout"]["objects"]:
                if o.get("solid") and o["id"] not in (l.get("practical_object_id"), l.get("motivated_by")) and geo.inside(geo.rect_of(o), l["x"], l["y"]):
                    issues.append(_issue("light_inside_set", "attention", f"{l['name']} ({l['id']}) stands inside {o['name']}.", "Move the light out of the piece, or attach it to the piece as a practical.", light_id=l["id"], object_id=o["id"]))
        if l["enabled"] and l.get("positional", True) and max(geo.light_at(l, stage, p, ())[0] for p in GRID) < 0.03:
            issues.append(_issue("light_lights_nothing", "note", f"{l['name']} ({l['id']}) puts almost no light on the playing area.", "Aim it at the actors, widen the beam, or increase its range.", light_id=l["id"]))

    # ---- shots: continuity between related shots, frame geometry ----
    rows = shot_rows(doc, art, plan, stage, solids) if plan else []
    for i, r in enumerate(rows):
        for lid in r["fixtures_in_frame"]:
            l = next(x for x in pl.resolve_shot(doc, r["shot_id"])[0] if x["id"] == lid)
            issues.append(_issue("fixture_in_frame", "attention", f"{l['name']} ({lid}) would be seen in shot {r['shot_id']} ({r['size']}).", "Switch it off or move it for this shot with a shot adjustment, or choose a tighter shot.", shot_id=r["shot_id"], light_id=lid))
        if i:
            prev = rows[i - 1]
            if prev["camera_side"] != r["camera_side"] or not prev["key_id"] or not r["key_id"]:
                continue
            why = r["reason"]
            sev = "note" if why else "attention"
            tail = f" (intended: {why})" if why else ""
            if prev["key_bearing"] is not None and r["key_bearing"] is not None and geo.angle_diff(prev["key_bearing"], r["key_bearing"]) > 70:
                issues.append(_issue("key_direction_jump", sev, f"The key light reaches the people from a different direction in {prev['shot_id']} and {r['shot_id']} ({geo.angle_diff(prev['key_bearing'], r['key_bearing']):.0f} degrees apart); cutting between them makes the light jump{tail}.",
                                     "Keep the key where it was across these shots, or add a shot adjustment that explains the change.", shot_id=r["shot_id"], previous_shot_id=prev["shot_id"]))
            dk = abs((prev["key_kelvin"] or 0) - (r["key_kelvin"] or 0))
            if dk > 600:
                issues.append(_issue("colour_jump", "attention" if dk > 1200 and not why else "note", f"The key light changes by {dk} K between {prev['shot_id']} and {r['shot_id']}{tail}.", "Use the same colour temperature across related shots, or give the change a reason.", shot_id=r["shot_id"], previous_shot_id=prev["shot_id"]))
            if prev["key_intensity"] and r["key_intensity"] and max(prev["key_intensity"], r["key_intensity"]) / max(min(prev["key_intensity"], r["key_intensity"]), 0.01) > 1.8:
                issues.append(_issue("intensity_jump", "note", f"The key light changes brightness a lot between {prev['shot_id']} and {r['shot_id']}{tail}.", "Match the brightness across related shots, or give the change a reason.", shot_id=r["shot_id"], previous_shot_id=prev["shot_id"]))
    # ---- people moving through the plan ----
    seen = set()
    for r in rows:
        for sj in r["subjects"]:
            k = (r["beat_id"], sj["character_id"])
            if k in seen:
                continue
            seen.add(k)
            nm = names.get(sj["character_id"], sj["character_id"])
            if sj["level_start"] >= 0.25 and sj["level_end"] < LOW:
                issues.append(_issue("moves_out_of_light", "attention", f"{nm} walks out of the lit area during beat {r['beat_id'].split('-')[-1]} (shot {r['shot_id']}).", "Move or widen a light so the path stays lit, adjust the blocking, or accept the shadow on purpose with a shot adjustment.", beat_id=r["beat_id"], character_id=sj["character_id"], shot_id=r["shot_id"]))
            elif sj["level_start"] > 0.05 and sj["level_end"] < sj["level_start"] * 0.4 and sj["level_end"] < 0.25:
                issues.append(_issue("moves_into_shadow", "note", f"{nm} moves into much darker light during beat {r['beat_id'].split('-')[-1]} (shot {r['shot_id']}).", "Fine if the shadow is intended; otherwise raise the fill or add a light near the end of the path.", beat_id=r["beat_id"], character_id=sj["character_id"], shot_id=r["shot_id"]))
            for bl in sj["blocked_lights"]:
                if next((l for l in L if l["id"] == bl), {}).get("role") in ("key", "motivated"):
                    issues.append(_issue("beam_blocked", "note", f"A solid set piece sits between {bl} and {nm} during beat {r['beat_id'].split('-')[-1]}.", "Move the light or the piece, or accept a shadow from the piece.", beat_id=r["beat_id"], character_id=sj["character_id"], light_id=bl))
    for r in rows:
        for sj in r["subjects"]:
            if sj["key_fill_ratio"] and sj["key_fill_ratio"] > 8:
                issues.append(_issue("ratio_extreme", "note", f"The key to fill ratio on {names.get(sj['character_id'], sj['character_id'])} in {r['shot_id']} is {sj['key_fill_ratio']}:1; the shadow side will be very dark.", "Raise the fill if you want to see that side of the face.", shot_id=r["shot_id"]))
                break
    accepted = {a["shot_id"]: a for a in doc.get("adjustments", []) if a.get("accepted_findings")}
    for i in issues:
        a = accepted.get(i.get("shot_id"))
        if a and i["rule"] in a["accepted_findings"] and i["severity"] == "attention":
            i["severity"] = "note"
            i["message"] += f" (accepted for this shot{': ' + a['reason'] if a.get('reason') else ''})"
            i["accepted"] = True
    issues = _dedupe(issues)

    # ---- measures ----
    m = metrics(doc, art, plan, stage, solids, rows, names)
    reading = readings(doc, m)
    att = sum(1 for i in issues if i["severity"] == "attention")
    pending = sum(1 for l in L if l["status"] == "needs_review") + sum(1 for a in doc.get("adjustments", []) if a["status"] == "needs_review")
    advice = ("Ready for review." if not att and not pending else f"{att} item(s) need attention and {pending} are waiting for review before this plan should be approved.")
    return {"issues": issues, "metrics": m, "reading": reading, "shots": rows, "readiness": {"attention": att, "notes": len(issues) - att, "pending_review": pending, "advice": advice},
            "model_note": "Levels are relative planning estimates (0 is dark, 1 is full), not measured light or a physical simulation."}


def _dedupe(issues):
    seen, out = set(), []
    for i in issues:
        k = (i["rule"], i["message"])
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def metrics(doc, art, plan, stage, solids, rows, names):
    L = [l for l in doc["lights"] if l["enabled"] and l["intensity"] > 0]
    wsum = sum(l["intensity"] for l in L) or 1.0
    mean_k = round(1e6 / (sum(l["intensity"] * geo.mired(l["color_temp_k"]) for l in L) / wsum)) if L else None
    keys = [l for l in L if l["role"] in ("key", "motivated")]
    key_soft = round(sum(l["softness"] for l in keys) / len(keys), 2) if keys else None
    area = sorted(sample(L, stage, solids, p)["level"] for p in GRID)
    p10, p90 = area[len(area) // 10], area[-len(area) // 10 - 1]
    ratios = [sj["key_fill_ratio"] for r in rows for sj in r["subjects"] if sj["key_fill_ratio"]]
    peak = ((plan or {}).get("interpretation") or {}).get("key_moment_beat_id")
    peak_ratios = [sj["key_fill_ratio"] for r in rows if r["beat_id"] == peak for sj in r["subjects"] if sj["key_fill_ratio"]]
    sources = [l for l in doc["lights"] if l["role"] != "ambient"]
    motivated = [l for l in sources if l.get("motivated_by") or l.get("practical_object_id") or l["source"] == "natural" or l["role"] in ("practical", "motivated")]
    roles = {}
    for l in doc["lights"]:
        roles[l["role"]] = roles.get(l["role"], 0) + 1
    return {"lights": len(doc["lights"]), "lights_on": len(L), "by_role": roles, "natural_sources": sum(1 for l in doc["lights"] if l["source"] == "natural"), "mean_kelvin": mean_k,
            "key_kelvin": round(sum(l["color_temp_k"] for l in keys) / len(keys)) if keys else None, "key_softness": key_soft,
            "key_fill_ratio": round(sum(ratios) / len(ratios), 1) if ratios else None, "peak_key_fill_ratio": round(sum(peak_ratios) / len(peak_ratios), 1) if peak_ratios else None,
            "contrast": round(min(99.0, p90 / max(p10, 0.02)), 1), "shadow_fraction": round(sum(1 for v in area if v < LOW) / len(area), 2), "mean_level": round(sum(area) / len(area), 2),
            "motivated_fraction": round(len(motivated) / len(sources), 2) if sources else None, "separation_lights": roles.get("backlight", 0) + roles.get("rim", 0),
            "adjusted_shots": len(doc.get("adjustments", [])), "shots": len(rows)}


def readings(doc, m):
    out = []
    k = m["mean_kelvin"]
    if k:
        if k < 3500:
            out.append({"text": "Warm light: the room reads as intimate and safe.", "because": f"average colour {k} K"})
        elif k > 5000:
            out.append({"text": "Cool light: the room reads as detached and restrained.", "because": f"average colour {k} K"})
        else:
            out.append({"text": "Neutral colour: the light does not push a mood by colour alone.", "because": f"average colour {k} K"})
    r = m["key_fill_ratio"]
    if r:
        if r >= 4:
            out.append({"text": "High contrast: deep shadows on one side of each face, a dramatic and guarded feeling.", "because": f"key to fill ratio {r}:1"})
        elif r <= 2.5:
            out.append({"text": "Low contrast: gentle, even light that keeps faces open.", "because": f"key to fill ratio {r}:1"})
        else:
            out.append({"text": "Moderate contrast: some modelling on faces without hiding them.", "because": f"key to fill ratio {r}:1"})
    if m["key_softness"] is not None:
        out.append({"text": "Soft key: skin looks kind and edges are quiet." if m["key_softness"] >= 0.6 else ("Hard key: crisp edges and clear shadows, more tension." if m["key_softness"] <= 0.35 else "Medium-soft key."), "because": f"average key softness {m['key_softness']}"})
    if m["shadow_fraction"] >= 0.25:
        out.append({"text": "Much of the playing area is in shadow, which leaves space and mystery around the people.", "because": f"{round(m['shadow_fraction'] * 100)}% of the playing area is dark"})
    elif m["shadow_fraction"] <= 0.05:
        out.append({"text": "The playing area is evenly lit; the whole room is visible.", "because": f"{round(m['shadow_fraction'] * 100)}% of the playing area is dark"})
    if m["motivated_fraction"] is not None:
        out.append({"text": "Most light has a visible reason (lamps, doors, windows): naturalistic." if m["motivated_fraction"] >= 0.6 else "Much of the light has no visible reason: stylised.", "because": f"{round(m['motivated_fraction'] * 100)}% of the lights are tied to a source in the room or outside it"})
    if m["peak_key_fill_ratio"] and m["key_fill_ratio"] and abs(m["peak_key_fill_ratio"] - m["key_fill_ratio"]) / m["key_fill_ratio"] > 0.25:
        out.append({"text": "The light changes at the peak of the scene, so the key moment is marked by the lighting.", "because": f"ratio {m['peak_key_fill_ratio']}:1 at the peak against {m['key_fill_ratio']}:1 on average"})
    return out
