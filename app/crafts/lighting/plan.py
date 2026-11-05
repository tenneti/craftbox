"""Lighting plan documents: presets, drafting from an art treatment and the director's plan, normalising, per-shot resolution.

A lighting plan holds only lighting data. The art treatment it was designed for is referenced (ids and hashes in ``source.art``),
never copied; the lights point at set pieces by their stable object ids.
"""
import copy
import math
import re

from app.crafts.lighting import geo
from app.hashing import sha256

ROLES = ["key", "fill", "backlight", "rim", "practical", "ambient", "motivated"]
SOURCES = ["natural", "artificial"]
TIMES = ["dawn", "day", "golden_hour", "dusk", "night"]
WEATHER = ["unspecified", "clear", "overcast", "rain", "fog", "snow"]
FALLOFFS = ["inverse_square", "linear", "none"]
STATUSES = ["proposed", "approved", "needs_review"]
LIGHT_FIELDS = ["name", "role", "source", "kind", "x", "y", "height_m", "rotation_deg", "tilt_deg", "intensity", "color_temp_k", "beam_angle_deg", "softness",
                "falloff", "enabled", "motivated_by", "practical_object_id", "narrative_purpose", "notes"]
CHANGE_FIELDS = ["x", "y", "height_m", "rotation_deg", "tilt_deg", "intensity", "color_temp_k", "beam_angle_deg", "softness", "enabled"]

# plausible colour temperature (Kelvin) for a natural source at each time of day; artificial sources may be anything
NATURAL_K = {"dawn": (2500, 6500), "day": (4800, 7500), "golden_hour": (2500, 5200), "dusk": (2500, 7500), "night": (2000, 9000)}
SUN_UP = {"dawn": True, "day": True, "golden_hour": True, "dusk": True, "night": False}

PRESETS = {
    "warm_naturalistic": {
        "name": "A — Warm, naturalistic, intimate",
        "summary": "Soft, low, warm light that seems to come from the lamps in the room and the street outside. People stay close together in one pool of light.",
        "intent": "Make the shop feel lived in and safe, so the tension between the two people is the only thing that is not comfortable.",
        "art_preset": "warm_nostalgia",
        "ambient_k": 2900, "ambient": 0.18,
        "purpose": "Warmth that comes from the room itself, so the audience believes in the place before it believes in the argument.",
    },
    "cool_dramatic": {
        "name": "B — Cool, restrained, dramatic",
        "summary": "One hard, cool light from the street cuts into a dark room. Very little fill, so faces are half in shadow and there is space between people.",
        "intent": "Keep the room cold and the people apart; the single warm lamp is the only place that feels like the past.",
        "art_preset": "emotional_distance",
        "ambient_k": 6200, "ambient": 0.03,
        "purpose": "Restraint: say less with the light, and let shadow carry the distance.",
    },
    "blank": {"name": "Blank plan", "summary": "No lights yet. Add them one at a time.", "intent": "", "art_preset": None, "ambient_k": 4000, "ambient": 0.1, "purpose": ""},
}

TIME_WORDS = [("pre-dawn", "dawn"), ("dawn", "dawn"), ("sunrise", "dawn"), ("morning", "day"), ("afternoon", "day"), ("day", "day"), ("noon", "day"), ("golden", "golden_hour"),
              ("sunset", "dusk"), ("dusk", "dusk"), ("evening", "dusk"), ("night", "night"), ("midnight", "night")]
WEATHER_WORDS = [("rain", "rain"), ("storm", "rain"), ("drizzle", "rain"), ("fog", "fog"), ("mist", "fog"), ("snow", "snow"), ("overcast", "overcast"), ("cloud", "overcast"), ("clear", "clear"), ("sun", "clear")]


def slug(text):
    return re.sub(r"[^A-Z0-9]+", "-", str(text).upper()).strip("-")


def guess_time(*texts):
    for t in texts:
        low = (t or "").lower()
        for word, key in TIME_WORDS:
            if re.search(r"\b" + re.escape(word), low):
                return key
    return "night"


def guess_weather(*texts):
    for t in texts:
        low = (t or "").lower()
        for word, key in WEATHER_WORDS:
            if word in low:
                return key
    return "unspecified"


# ---- the director's plan: blocking and cameras -------------------------------------------------------------------------------------------------
def beat_positions(plan):
    """{beat_id: {character_id: {start, end, facing}}} from the direction plan's blocking."""
    out = {}
    for b in (plan or {}).get("blocking", []):
        out[b["beat_id"]] = {c["character_id"]: {"start": (c["start"]["x"], c["start"]["y"]), "end": (c["end"]["x"], c["end"]["y"]), "facing": c.get("facing") or ""} for c in b.get("characters", [])}
    return out


def shot_index(plan):
    return {s["shot_id"]: s for s in (plan or {}).get("shots", []) if s.get("status") != "rejected"}


def camera_hash(shot):
    return sha256({"previz": shot.get("previz"), "side": shot.get("camera_side"), "size": shot.get("size"), "beat": shot.get("beat_id")})[:12]


def blocking_hashes(plan):
    """One hash per beat of where each character starts, ends and faces (rounded, so a note or a tiny nudge does not count as a change)."""
    return {b["beat_id"]: sha256([(c["character_id"], round(c["start"]["x"], 2), round(c["start"]["y"], 2), round(c["end"]["x"], 2), round(c["end"]["y"], 2), c.get("facing") or "") for c in b["characters"]])[:12]
            for b in (plan or {}).get("blocking", [])}


def object_hashes(art):
    return {o["id"]: sha256({k: o.get(k) for k in ("x", "y", "w", "h", "solid", "kind", "name")})[:12] for o in art["layout"]["objects"]}


def source_block(screenplay, scene, san, art, plan, ref=None):
    return {"project_id": screenplay["project"]["id"], "scene_id": scene["id"], "screenplay_revision": (screenplay.get("revision") or {}).get("number", 1),
            "scene_hash": san["scene_hash"], "beat_hashes": {b["id"]: b["hash"] for b in san["beats"]},
            "art": {"treatment_id": art["treatment"]["id"], "treatment_name": art["treatment"]["name"], "art_hash": (art.get("analysis") or {}).get("art_hash", ""),
                    "object_hashes": object_hashes(art), "time_of_day": (art["location"].get("environment") or {}).get("time_of_day", ""),
                    "stage": {"width_m": art["layout"]["width_m"], "depth_m": art["layout"]["depth_m"]}},
            "plan": {"plan_hash": ((plan or {}).get("analysis") or {}).get("plan_hash", ""), "blocking_hashes": blocking_hashes(plan), "camera_hashes": {k: camera_hash(s) for k, s in shot_index(plan).items()}} if plan else None,
            "ref": ref or {}}


# ---- drafting -----------------------------------------------------------------------------------------------------------------------------------
def _find(art, *words, kinds=None):
    for o in art["layout"]["objects"]:
        low = o["name"].lower()
        if any(w in low for w in words) and (kinds is None or o["kind"] in kinds):
            return o
    return None


def _subject_centre(plan, art):
    pos = beat_positions(plan)
    pts = [p["end"] for b in pos.values() for p in b.values()]
    if pts:
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (0.5, 0.56)


def _light(i, name, role, source, kind, x, y, aim, stage, **kw):
    rot = round(geo.bearing(stage, (x, y), aim), 1)
    d = {"id": i, "name": name, "role": role, "source": source, "kind": kind, "x": round(x, 2), "y": round(y, 2), "height_m": kw.pop("height_m", 2.0), "rotation_deg": rot, "tilt_deg": kw.pop("tilt_deg", -20),
         "intensity": 0.5, "color_temp_k": 3200, "beam_angle_deg": 60, "softness": 0.5, "falloff": {"mode": "inverse_square", "range_m": 8.0}, "enabled": True, "motivated_by": "", "practical_object_id": "",
         "narrative_purpose": "", "notes": "", "status": "proposed"}
    d.update(kw)
    return d


def _clamp01(v):
    return max(0.02, min(0.98, v))


def _clear_spot(candidates, centre, art, stage):
    """The first candidate position that is outside every solid set piece and has a clear line to the people."""
    solids = [geo.rect_of(o) for o in art["layout"]["objects"] if o.get("solid")]
    for c in candidates:
        if not any(geo.inside(r, c[0], c[1], 0.02) or geo.segment_hits(c, centre, r) for r in solids):
            return c
    return candidates[0]


def base_lights(preset, art, plan, stage):
    """The shared scene setup for a preset, placed relative to the art treatment's own objects (found by name) and the blocking."""
    centre = _subject_centre(plan, art)
    lamp = _find(art, "lamp")
    door = _find(art, "door")
    dx, dy = (door["x"], door["y"]) if door else (0.08, 0.88)
    lx, ly = (lamp["x"], lamp["y"]) if lamp else (0.8, 0.36)
    L = []
    if preset == "warm_naturalistic":
        L = [
            _light("L-KEY", "Soft key, motivated by the lamp", "key", "artificial", "softbox", *_clear_spot([(_clamp01(lx - 0.06), _clamp01(ly + 0.3)), (0.9, 0.7), (0.74, 0.97), (0.96, 0.5)], centre, art, stage), centre, stage, intensity=0.75, color_temp_k=2900, beam_angle_deg=80, softness=0.8,
                   motivated_by=lamp["id"] if lamp else "", narrative_purpose="Shapes both faces as if the lamp were doing the work.", height_m=2.1),
            _light("L-LAMP", "Table lamp (visible in the room)", "practical", "artificial", "practical_lamp", lx, ly, centre, stage, intensity=0.5, color_temp_k=2700, beam_angle_deg=120, softness=0.9, height_m=1.1, tilt_deg=0,
                   practical_object_id=lamp["id"] if lamp else "", narrative_purpose="The visible reason for the warmth.", falloff={"mode": "inverse_square", "range_m": 6.0}),
            _light("L-FILL", "Soft fill from the audience side", "fill", "artificial", "bounce", 0.22, 0.95, centre, stage, intensity=0.32, color_temp_k=3000, beam_angle_deg=110, softness=1.0, narrative_purpose="Keeps shadows gentle so nobody looks threatened.", height_m=1.6),
            _light("L-RIM", "Warm backlight from the shelves", "backlight", "artificial", "fresnel", 0.18, 0.2, centre, stage, intensity=0.35, color_temp_k=2800, beam_angle_deg=50, softness=0.5, narrative_purpose="Separates the people from the shelves with a soft edge.", height_m=2.4),
            _light("L-DOOR", "Street light through the door", "motivated", "natural", "street", dx + 0.02, dy - 0.06, centre, stage, intensity=0.25, color_temp_k=2800, beam_angle_deg=70, softness=0.6,
                   motivated_by=door["id"] if door else "", narrative_purpose="Reminds us of the rain outside and of how little time is left.", falloff={"mode": "inverse_square", "range_m": 7.0}, height_m=1.8),
            _light("L-AMB", "Warm room glow", "ambient", "artificial", "ambient", 0.5, 0.5, centre, stage, intensity=PRESETS[preset]["ambient"], color_temp_k=PRESETS[preset]["ambient_k"], beam_angle_deg=180, softness=1.0, positional=False,
                   narrative_purpose="A low base level so shadows never go fully black.", falloff={"mode": "none", "range_m": 10.0}),
        ]
    elif preset == "cool_dramatic":
        fl = _find(art, "lamp")
        fx, fy = (fl["x"], fl["y"]) if fl else (0.92, 0.12)
        L = [
            _light("L-KEY", "Hard cool key from the street", "key", "natural", "street", *_clear_spot([(0.04, 0.78), (0.04, 0.7), (0.04, 0.5), (0.04, 0.3), (0.5, 0.97), (0.96, 0.7)], centre, art, stage), centre, stage, intensity=1.0, color_temp_k=5200, beam_angle_deg=50, softness=0.25,
                   motivated_by=door["id"] if door else "", narrative_purpose="A single hard light from outside: half of each face stays dark.", height_m=2.0, falloff={"mode": "inverse_square", "range_m": 9.0}),
            _light("L-FILL", "Barely-there fill", "fill", "artificial", "bounce", 0.5, 0.97, centre, stage, intensity=0.05, color_temp_k=6000, beam_angle_deg=140, softness=1.0, narrative_purpose="Only enough to keep the shadow side from going black.", height_m=1.6),
            _light("L-RIM", "Cold backlight", "backlight", "artificial", "fresnel", 0.8, 0.08, centre, stage, intensity=0.45, color_temp_k=7000, beam_angle_deg=35, softness=0.2, narrative_purpose="A thin cold edge that cuts each person out of the dark.", height_m=2.5),
            _light("L-LAMP", "Floor lamp, the only warm light", "practical", "artificial", "practical_lamp", fx, fy, centre, stage, intensity=0.18, color_temp_k=3200, beam_angle_deg=70, softness=0.8, height_m=1.5, tilt_deg=0,
                   practical_object_id=fl["id"] if fl else "", narrative_purpose="One small warm pool that belongs to the past.", falloff={"mode": "inverse_square", "range_m": 4.0}),
            _light("L-AMB", "Cold room level", "ambient", "natural", "ambient", 0.5, 0.5, centre, stage, intensity=PRESETS[preset]["ambient"], color_temp_k=PRESETS[preset]["ambient_k"], beam_angle_deg=180, softness=1.0, positional=False,
                   narrative_purpose="Very low, so the room stays dark.", falloff={"mode": "none", "range_m": 10.0}),
        ]
    for l in L:
        l.setdefault("positional", True)
    return L


def base_adjustments(preset, plan, lights, stage):
    """A few shot-specific changes that keep the shared scene setup: close-ups and the peak of the scene."""
    out, shots = [], list((plan or {}).get("shots", []))
    peak = ((plan or {}).get("interpretation") or {}).get("key_moment_beat_id")
    ids = {l["id"] for l in lights}
    for s in shots:
        if s.get("status") == "rejected":
            continue
        ch = []
        if preset == "warm_naturalistic" and s["size"] in ("CU", "ECU") and "L-KEY" in ids:
            ch.append({"light_id": "L-KEY", "softness": 1.0})
            why = "Close-up: the key goes fully soft so skin looks gentle."
        elif preset == "warm_naturalistic" and s["beat_id"] == peak and "L-KEY" in ids:
            ch.append({"light_id": "L-KEY", "intensity": 0.85, "color_temp_k": 2750})
            why = "The peak of the scene: a little brighter and warmer, as if the lamp had been turned up."
        elif preset == "cool_dramatic" and s["beat_id"] == peak and "L-FILL" in ids:
            ch.append({"light_id": "L-FILL", "intensity": 0.02})
            why = "The peak of the scene: the shadow side goes deeper."
        elif preset == "cool_dramatic" and s["size"] in ("CU", "ECU") and "L-KEY" in ids:
            ch.append({"light_id": "L-KEY", "intensity": 0.85})
            why = "Close-up: the key eases off so the eyes stay readable."
        else:
            why = ""
        hidden = fixtures_in_frame(lights, s, stage) if s.get("previz") else []
        for lid in hidden:
            l = next(x for x in lights if x["id"] == lid)
            pv = s["previz"]
            top = geo.frame_limits(stage, pv["camera_position"], pv.get("fov_deg", 40), pv["camera_position"].get("height_m", 1.6), (l["x"], l["y"]))[1]
            ch = [c for c in ch if c["light_id"] != lid]
            if top + 0.3 <= 4.5:
                ch.append({"light_id": lid, "height_m": round(top + 0.3, 1)})
                why = (why + " " if why else "") + f"{lid} is raised to {round(top + 0.3, 1)} m so it stays above this wide frame."
            else:
                ch.append({"light_id": lid, "enabled": False})
                why = (why + " " if why else "") + f"{lid} would be seen in this wide view, so it is switched off for this shot."
        if not ch:
            continue
        out.append({"id": f"ADJ-{s['shot_id'].split('-')[-1]}", "shot_id": s["shot_id"], "reason": why, "changes": ch, "added_lights": [], "status": "proposed"})
    return out


def fixtures_in_frame(lights, shot, stage):
    """Ids of stand-mounted lights (not practicals, outside sources or ambient) that a shot's camera would see, sideways and in height."""
    pv = shot.get("previz") or {}
    cam, tgt = pv.get("camera_position"), pv.get("target")
    if not cam or not tgt:
        return []
    reach = geo.dist_m(stage, (cam["x"], cam["y"]), (tgt["x"], tgt["y"])) + 1.5
    fov = pv.get("fov_deg", 40)
    out = []
    for l in lights:
        if not l.get("enabled", True) or not l.get("positional", True) or l["role"] in ("practical", "ambient", "motivated") or l["source"] == "natural":
            continue
        if geo.in_view(stage, cam, tgt, fov, (l["x"], l["y"]), reach):
            low, high = geo.frame_limits(stage, cam, fov, cam.get("height_m", 1.6), (l["x"], l["y"]))
            if low <= l["height_m"] <= high:
                out.append(l["id"])
    return out


def draft(scene, san, art, plan, preset_key, name, setup=None):
    stage = {"width_m": art["layout"]["width_m"], "depth_m": art["layout"]["depth_m"]}
    key = preset_key if preset_key in PRESETS or preset_key == "setup" else "blank"
    meta = PRESETS.get(key, PRESETS["blank"])
    env = art["location"].get("environment") or {}
    notes = []
    if key == "setup":
        if not setup:
            raise ValueError("no saved setup was given to start from")
        lights = copy.deepcopy(setup["setup"]["lights"])
        objs = {o["id"] for o in art["layout"]["objects"]}
        for l in lights:
            l["status"] = "proposed"
            for f in ("motivated_by", "practical_object_id"):
                if l.get(f) and l[f] not in objs:
                    notes.append(f"{l['id']}: the set piece “{l[f]}” is not in this scene's art treatment, so the link was cleared.")
                    l[f] = ""
        meta = {"name": setup["setup"]["name"], "summary": setup["setup"].get("summary", ""), "intent": "", "purpose": "", "ambient": 0.1, "ambient_k": 4000}
        adjustments = []
    else:
        lights = base_lights(key, art, plan, stage)
        adjustments = base_adjustments(key, plan, lights, stage)
    tod = guess_time(env.get("time_of_day"), scene.get("slugline"))
    weather = guess_weather(env.get("weather"), env.get("atmosphere"))
    pname = name or meta["name"]
    doc = {"schema": "filmcraft.lighting_plan.v1", "scene_id": scene["id"],
           "plan": {"id": f"LP-{slug(key if key != 'setup' else (setup or {}).get('setup', {}).get('id', 'setup'))}", "name": pname, "preset": key, "summary": meta["summary"], "intent": meta["intent"]},
           "conditions": {"time_of_day": tod, "weather": weather, "mood_words": list(art["style"].get("mood_words", []))[:6], "narrative_purpose": meta["purpose"] or scene.get("objective", "")},
           "lights": lights, "adjustments": adjustments}
    if key == "setup":
        doc["from_setup"] = {"setup_id": setup["setup"]["id"], "setup_name": setup["setup"]["name"], "setup_hash": sha256(setup["setup"]["lights"])[:16]}
    return doc, notes


# ---- normalising and per-shot resolution ------------------------------------------------------------------------------------------------------
def _num(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= v <= hi):
        raise ValueError(f"{what} must be a number from {lo} to {hi}")
    return v


def _light_in(l, i):
    d = copy.deepcopy(l)
    where = f"light {l.get('id', i)}"
    if d.get("role") not in ROLES:
        raise ValueError(f"{where}: role must be one of {', '.join(ROLES)}")
    if d.get("source") not in SOURCES:
        raise ValueError(f"{where}: source must be natural or artificial")
    d.setdefault("kind", "other"); d.setdefault("height_m", 2.0); d.setdefault("tilt_deg", -20); d.setdefault("enabled", True); d.setdefault("positional", d["role"] != "ambient")
    d.setdefault("motivated_by", ""); d.setdefault("practical_object_id", ""); d.setdefault("narrative_purpose", ""); d.setdefault("notes", ""); d.setdefault("status", "proposed")
    d.setdefault("falloff", {"mode": "inverse_square", "range_m": 8.0})
    _num(d["x"], -0.5, 1.5, f"{where}: x"); _num(d["y"], -0.5, 1.5, f"{where}: y"); _num(d["height_m"], 0, 12, f"{where}: height")
    d["rotation_deg"] = round(_num(d.get("rotation_deg", 0), 0, 360, f"{where}: rotation") % 360, 1)
    _num(d["tilt_deg"], -90, 90, f"{where}: tilt"); _num(d["intensity"], 0, 1, f"{where}: intensity"); _num(d["color_temp_k"], 1000, 20000, f"{where}: colour temperature")
    _num(d["beam_angle_deg"], 5, 360, f"{where}: beam angle"); _num(d["softness"], 0, 1, f"{where}: softness")
    if d["falloff"].get("mode") not in FALLOFFS:
        raise ValueError(f"{where}: falloff must be one of {', '.join(FALLOFFS)}")
    _num(d["falloff"].get("range_m", 8.0), 0.5, 60, f"{where}: falloff range")
    if d["status"] not in STATUSES:
        raise ValueError(f"{where}: status must be one of {', '.join(STATUSES)}")
    return d


def normalize(doc, scene, plan=None):
    d = copy.deepcopy(doc)
    d["schema"] = "filmcraft.lighting_plan.v1"
    d["scene_id"] = scene["id"]
    c = d["conditions"]
    if c.get("time_of_day") not in TIMES:
        raise ValueError(f"time of day must be one of {', '.join(TIMES)}")
    if c.get("weather") not in WEATHER:
        raise ValueError(f"weather must be one of {', '.join(WEATHER)}")
    c.setdefault("mood_words", []); c.setdefault("narrative_purpose", "")
    d["lights"] = [_light_in(l, i) for i, l in enumerate(d.get("lights", []))]
    ids = [l["id"] for l in d["lights"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"light ids must be unique; repeated: {', '.join(dup)}")
    shots = shot_index(plan) if plan else None
    seen = set()
    for a in d.get("adjustments", []):
        a.setdefault("reason", ""); a.setdefault("changes", []); a.setdefault("added_lights", []); a.setdefault("status", "proposed"); a.setdefault("accepted_findings", [])
        if a["shot_id"] in seen:
            raise ValueError(f"shot {a['shot_id']} has more than one adjustment; keep one and put every change in it")
        seen.add(a["shot_id"])
        if shots is not None and a["shot_id"] not in shots:
            raise ValueError(f"adjustment {a['id']}: shot {a['shot_id']} is not a shot of this scene's direction plan")
        if a["status"] not in STATUSES:
            raise ValueError(f"adjustment {a['id']}: status must be one of {', '.join(STATUSES)}")
        for ch in a["changes"]:
            if ch["light_id"] not in ids and ch["light_id"] not in [x["id"] for x in a["added_lights"]]:
                raise ValueError(f"adjustment {a['id']}: light {ch['light_id']} does not exist; add it to the scene setup first")
            for k in ch:
                if k != "light_id" and k not in CHANGE_FIELDS:
                    raise ValueError(f"adjustment {a['id']}: '{k}' cannot be changed per shot")
        a["added_lights"] = [_light_in(l, i) for i, l in enumerate(a["added_lights"])]
        clash = [l["id"] for l in a["added_lights"] if l["id"] in ids]
        if clash:
            raise ValueError(f"adjustment {a['id']}: added light ids clash with the scene setup: {', '.join(clash)}")
    return d


def resolve_shot(doc, shot_id):
    """The lights that are really on for one shot: the shared scene setup with that shot's changes applied. Nothing is modified."""
    lights = copy.deepcopy(doc["lights"])
    adj = next((a for a in doc.get("adjustments", []) if a["shot_id"] == shot_id), None)
    adjusted = set()
    if adj:
        extra = copy.deepcopy(adj["added_lights"])
        by = {l["id"]: l for l in lights + extra}
        for ch in adj["changes"]:
            for k, v in ch.items():
                if k != "light_id":
                    by[ch["light_id"]][k] = v
            adjusted.add(ch["light_id"])
        lights += extra
        adjusted |= {l["id"] for l in extra}
    for l in lights:
        l["adjusted"] = l["id"] in adjusted
    return lights, adj


def plan_hash(doc):
    return sha256({k: v for k, v in doc.items() if k not in ("analysis", "source", "note")})[:16]
