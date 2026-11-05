"""Screenwriting Lab engine: validates and analyses a screenplay document. Deterministic, no AI.

Input and output are both ``filmcraft.screenplay.v1``; the output adds an ``analysis`` block with
per-element timings, beat timings, scene durations, pacing, structure checks and content hashes that
downstream plans use to detect script changes. The estimate rates below are documented guesses.
"""
import copy
import json
import re

from app.crafts.screenwriting import story as story_audit
from app.hashing import sha256

SCHEMA = "filmcraft.screenplay.v1"
SPEECH_WPS = 2.7        # spoken words per second (guess; typical screen dialogue)
ACTION_WPS = 3.2        # action-line words read per second (guess)
DIALOGUE_GAP = 0.35     # seconds of breath/turn-taking after each line
MIN_ACTION = 1.2
PAREN_SECONDS = 0.6
TRANSITION_SECONDS = 0.5
SLOW_WPM, BRISK_WPM = 70, 120   # dialogue words per scene-minute (guess)
ACT_SHARE = {1: 0.25, 2: 0.5, 3: 0.25}
ACT_TOLERANCE = 0.2
SCENE_PROMPTS = ("synopsis", "objective", "conflict", "turning_point", "outcome")
BEAT_TEMPLATE = [  # (title, role, act, intensity, prompt)
    ("Setup", "setup", 1, 2, "Where are we, and what does {a} want at the start?"),
    ("Inciting moment", "inciting", 1, 3, "What disturbs the calm and starts the scene?"),
    ("Rising tension", "rising", 2, 5, "How does the conflict between {a} and {b} grow?"),
    ("Turning point", "turning_point", 2, 7, "What changes what {a} or {b} understands?"),
    ("Climax", "climax", 3, 9, "What is the hardest moment and the key choice?"),
    ("Resolution", "resolution", 3, 5, "How are things different at the end?"),
]


def words(text):
    return len(re.findall(r"[\w'’-]+", text or ""))


def element_seconds(el):
    kind = el["type"]
    if kind == "dialogue":
        base = words(el["text"]) / SPEECH_WPS + DIALOGUE_GAP
    elif kind == "action":
        base = max(MIN_ACTION, words(el["text"]) / ACTION_WPS)
    elif kind == "parenthetical":
        base = PAREN_SECONDS
    else:
        base = TRANSITION_SECONDS
    return round(base + float(el.get("pause_seconds") or 0), 2)


def short(h):
    return h[:16]


def element_hash(el):
    return short(sha256({k: el.get(k) for k in ("type", "character_id", "text", "pause_seconds")}))


def beat_hash(beat, hashes):
    fields = {k: beat.get(k) for k in ("title", "description", "emotion", "role", "act", "intensity", "character_states")}
    return short(sha256({"beat": fields, "elements": [hashes.get(e) for e in beat.get("element_ids", [])]}))


def scene_hash(scene):
    return short(sha256(scene))


def slugline(heading):
    time = (heading.get("time") or "").strip()
    return f"{heading['int_ext']} {heading['location'].strip().upper()}" + (f" - {time.upper()}" if time else "")


def _dupes(ids):
    seen, out = set(), []
    for i in ids:
        if i in seen and i not in out:
            out.append(i)
        seen.add(i)
    return out


def check_integrity(doc):
    """Return a list of human-readable integrity errors (empty when the document is sound)."""
    errors = []
    chars = {c["id"] for c in doc["characters"]}
    for d in _dupes([c["id"] for c in doc["characters"]]):
        errors.append(f"duplicate character id {d}")
    for c in doc["characters"]:
        for r in c.get("relationships", []):
            if r["character_id"] not in chars:
                errors.append(f"character {c['id']} has a relationship with unknown character {r['character_id']}")
    scene_ids = [s["id"] for s in doc["scenes"]]
    for d in _dupes(scene_ids):
        errors.append(f"duplicate scene id {d}")
    seq_ids = [s["id"] for s in doc.get("sequences", [])]
    for d in _dupes(seq_ids):
        errors.append(f"duplicate sequence id {d}")
    placed = {}
    for seq in doc.get("sequences", []):
        for sid in seq.get("scene_ids", []):
            if sid not in scene_ids:
                errors.append(f"sequence {seq['id']} lists unknown scene {sid}")
            if sid in placed:
                errors.append(f"scene {sid} is in more than one sequence ({placed[sid]}, {seq['id']})")
            placed[sid] = seq["id"]
    acts = [a["act"] for a in doc.get("structure", {}).get("acts", [])]
    for d in _dupes(acts):
        errors.append(f"act {d} is defined twice")
    all_elements, all_beats = [], []
    for scene in doc["scenes"]:
        sid = scene["id"]
        if scene.get("sequence_id") and scene["sequence_id"] not in seq_ids:
            errors.append(f"scene {sid} refers to unknown sequence {scene['sequence_id']}")
        for c in scene["characters"]:
            if c not in chars:
                errors.append(f"scene {sid} lists unknown character {c}")
        ids = [e["id"] for e in scene["elements"]]
        all_elements += ids
        for e in scene["elements"]:
            if e["type"] == "dialogue":
                if not e.get("character_id") or e["character_id"] not in chars:
                    errors.append(f"{e['id']}: dialogue needs a speaker who is a known character")
                if not (e["text"] or "").strip():
                    errors.append(f"{e['id']}: dialogue line is empty")
            elif e["type"] == "parenthetical" and e.get("character_id") and e["character_id"] not in chars:
                errors.append(f"{e['id']}: parenthetical names unknown character {e['character_id']}")
            elif e["type"] == "action" and not (e["text"] or "").strip():
                errors.append(f"{e['id']}: action line is empty")
        in_beat = {}
        for b in scene.get("beats", []):
            all_beats.append(b["id"])
            for eid in b.get("element_ids", []):
                if eid not in ids:
                    errors.append(f"beat {b['id']} refers to unknown element {eid}")
                if eid in in_beat:
                    errors.append(f"element {eid} is in two beats ({in_beat[eid]}, {b['id']})")
                in_beat[eid] = b["id"]
    for d in _dupes(all_elements):
        errors.append(f"duplicate element id {d}")
    for d in _dupes(all_beats):
        errors.append(f"duplicate beat id {d}")
    return errors


def process(payload):
    """Validate and analyse a screenplay document. Returns (data, warnings)."""
    doc = json.loads(json.dumps(payload))  # deep copy; never mutate the caller's object
    doc.pop("analysis", None)
    problems = check_integrity(doc)
    if problems:
        raise ValueError("screenplay problems: " + "; ".join(problems[:8]) + (f" (+{len(problems) - 8} more)" if len(problems) > 8 else ""))
    warnings = []
    doc.setdefault("revision", {"number": 1, "note": ""})
    doc["revision"].setdefault("number", 1)
    doc["project"].setdefault("fps", 24)
    fps = doc["project"]["fps"]
    names = {c["id"]: c["name"] for c in doc["characters"]}
    scenes_out, total_seconds, all_dialogue_words = [], 0.0, 0
    for scene in doc["scenes"]:
        scene["slugline"] = slugline(scene["heading"])
        for e in scene["elements"]:
            sp = e.get("character_id")
            if e["type"] == "dialogue" and sp not in scene["characters"]:
                scene["characters"].append(sp)
                warnings.append(f"{scene['id']}: {names[sp]} speaks but was not listed in the scene's characters; added")
        computed = [element_seconds(e) for e in scene["elements"]]
        raw_total = sum(computed)
        override = scene.get("estimated_seconds_override")
        scale = (override / raw_total) if override and raw_total else 1.0
        total = round(override if override else raw_total, 2)
        t, el_out, hashes, dur_by_id = 0.0, [], {}, {}
        for e, d in zip(scene["elements"], computed):
            d = round(d * scale, 2)
            h = element_hash(e)
            hashes[e["id"]] = h
            dur_by_id[e["id"]] = (round(t, 2), d)
            el_out.append({"id": e["id"], "type": e["type"], "start_seconds": round(t, 2), "duration_seconds": d, "hash": h})
            t += d
        beats_out, last_start = [], -1.0
        covered = set()
        for b in scene.get("beats", []):
            ids = b.get("element_ids", [])
            covered.update(ids)
            starts = [dur_by_id[i][0] for i in ids]
            dur = round(sum(dur_by_id[i][1] for i in ids), 2)
            start = min(starts) if starts else None
            if start is not None:
                if start < last_start:
                    warnings.append(f"{scene['id']}: beat {b['id']} is out of script order")
                last_start = start
            beats_out.append({"id": b["id"], "start_seconds": start, "duration_seconds": dur, "intensity": b.get("intensity"),
                              "role": b.get("role"), "act": b.get("act"), "element_ids": ids, "hash": beat_hash(b, hashes)})
            if not ids:
                warnings.append(f"{scene['id']}: beat '{b['title']}' has no script elements yet")
        uncovered = [e["id"] for e in scene["elements"] if e["id"] not in covered]
        if scene.get("beats") and uncovered:
            warnings.append(f"{scene['id']}: {len(uncovered)} script element(s) are not in any beat")
        missing = [k for k in SCENE_PROMPTS if not (scene.get(k) or "").strip()]
        if missing:
            warnings.append(f"{scene['id']}: not yet filled in: {', '.join(m.replace('_', ' ') for m in missing)}")
        if not scene["elements"]:
            warnings.append(f"{scene['id']}: the scene has no script elements yet")
        d_words = sum(words(e["text"]) for e in scene["elements"] if e["type"] == "dialogue")
        d_secs = sum(x["duration_seconds"] for x, e in zip(el_out, scene["elements"]) if e["type"] == "dialogue")
        wpm = round(d_words / total * 60, 1) if total else 0.0
        label = "slow" if wpm < SLOW_WPM else ("brisk" if wpm > BRISK_WPM else "measured")
        speaking = {}
        for x, e in zip(el_out, scene["elements"]):
            if e["type"] == "dialogue":
                s = speaking.setdefault(e["character_id"], {"lines": 0, "seconds": 0.0})
                s["lines"] += 1; s["seconds"] = round(s["seconds"] + x["duration_seconds"], 2)
        micro = {}
        for b in beats_out:
            if b["act"]:
                micro[b["act"]] = micro.get(b["act"], 0) + b["duration_seconds"]
        beat_total = sum(micro.values())
        micro_out = [{"act": a, "seconds": round(micro.get(a, 0), 2), "share": round(micro.get(a, 0) / beat_total, 3) if beat_total else 0,
                      "expected_share": ACT_SHARE[a]} for a in (1, 2, 3)]
        if beat_total:
            for m in micro_out:
                if abs(m["share"] - m["expected_share"]) > ACT_TOLERANCE:
                    warnings.append(f"{scene['id']}: act {m['act']} takes {round(m['share'] * 100)}% of the scene's beats (three-act guide is {round(m['expected_share'] * 100)}%)")
        scenes_out.append({
            "scene_id": scene["id"], "scene_hash": scene_hash(scene), "slugline": scene["slugline"],
            "estimated_seconds": total, "fps": fps, "duration_frames": round(total * fps),
            "pacing": {"label": label, "dialogue_words": d_words, "dialogue_words_per_minute": wpm,
                       "dialogue_share": round(d_secs / total, 3) if total else 0, "action_share": round(1 - d_secs / total, 3) if total else 0},
            "completeness": {"missing": missing, "has_beats": bool(scene.get("beats")), "uncovered_elements": uncovered},
            "elements": el_out, "beats": beats_out, "speaking": speaking,
            "intensity_curve": [{"beat_id": b["id"], "start_seconds": b["start_seconds"], "intensity": b["intensity"]} for b in beats_out],
            "micro_structure": micro_out})
        total_seconds += total
        all_dialogue_words += d_words
    # project-level three-act structure: acts -> sequences -> scenes
    seq_by_act = {}
    for seq in doc.get("sequences", []):
        seq_by_act.setdefault(seq.get("act"), []).append(seq)
    sec_of = {s["scene_id"]: s["estimated_seconds"] for s in scenes_out}
    acts_out, notes = [], []
    for a in (1, 2, 3):
        scene_ids = [sid for seq in seq_by_act.get(a, []) for sid in seq.get("scene_ids", [])]
        secs = round(sum(sec_of.get(sid, 0) for sid in scene_ids), 2)
        label = next((x.get("label") for x in doc.get("structure", {}).get("acts", []) if x["act"] == a), None)
        acts_out.append({"act": a, "label": label, "scene_ids": scene_ids, "seconds": secs,
                         "share": round(secs / total_seconds, 3) if total_seconds else 0, "expected_share": ACT_SHARE[a]})
        if not scene_ids:
            notes.append(f"Act {a} has no scenes yet (information only)")
    unplaced = [s["id"] for s in doc["scenes"] if s["id"] not in {sid for a in acts_out for sid in a["scene_ids"]}]
    if unplaced and doc.get("sequences"):
        warnings.append(f"scenes not in any sequence: {', '.join(unplaced)}")
    base = {k: v for k, v in doc.items() if k not in ("analysis", "revision")}
    doc["analysis"] = {
        "screenplay_hash": short(sha256(base)),
        "totals": {"scenes": len(doc["scenes"]), "characters": len(doc["characters"]), "sequences": len(doc.get("sequences", [])),
                   "elements": sum(len(s["elements"]) for s in doc["scenes"]), "dialogue_words": all_dialogue_words,
                   "estimated_seconds": round(total_seconds, 2)},
        "structure": {"acts": acts_out, "notes": notes},
        "scenes": scenes_out,
        "model": {"speech_words_per_second": SPEECH_WPS, "action_words_per_second": ACTION_WPS, "dialogue_gap_seconds": DIALOGUE_GAP,
                  "note": "Duration is a rule-based estimate, not a measurement. Set estimated_seconds_override to fix a scene's length."},
        "warnings": list(warnings),
        "story": story_audit.audit(doc, scenes_out),
    }
    return doc, warnings


def skeleton(idea):
    """Turn a story idea into an empty-but-structured screenplay (rule-based template, no text generation)."""
    title = (idea.get("title") or "").strip()
    if not title:
        raise ValueError("a title is required")
    pid = idea.get("project_id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "project"
    chars_in = [c for c in idea.get("characters", []) if (c.get("name") or "").strip()]
    if not chars_in:
        raise ValueError("add at least one character")
    characters = [{"id": f"C-{i:03d}", "name": c["name"].strip(), "role": c.get("role", ""), "want": c.get("want", ""),
                   "motivation": "", "need": "", "flaw": "", "description": "", "relationships": [], "emotional_arc": {"start": "", "end": ""}}
                  for i, c in enumerate(chars_in, 1)]
    a = characters[0]["name"]
    b = characters[1]["name"] if len(characters) > 1 else "the other"
    arc = idea.get("emotional_arc") or {}
    beats = [{"id": f"SC-001-B{i}", "title": t, "description": p.format(a=a, b=b), "emotion": "", "role": r, "act": act,
              "intensity": inten, "element_ids": [], "character_states": {}}
             for i, (t, r, act, inten, p) in enumerate(BEAT_TEMPLATE, 1)]
    if arc.get("start"):
        beats[0]["emotion"] = arc["start"]
    if arc.get("end"):
        beats[-1]["emotion"] = arc["end"]
    scene = {"id": "SC-001", "sequence_id": "SEQ-1",
             "heading": {"int_ext": idea.get("int_ext") or "INT.", "location": (idea.get("location") or "LOCATION").strip(), "time": (idea.get("time") or "DAY").strip()},
             "synopsis": idea.get("logline", ""), "objective": f"{a} wants {characters[0]['want']}".strip() if characters[0]["want"] else "",
             "conflict": f"{b} wants {characters[1]['want']}".strip() if len(characters) > 1 and characters[1]["want"] else "",
             "turning_point": "", "outcome": "", "characters": [c["id"] for c in characters], "props": [], "elements": [], "beats": beats}
    return {
        "schema": SCHEMA,
        "project": {"id": pid, "title": title, "logline": idea.get("logline", ""), "genre": idea.get("genre", ""), "theme": idea.get("theme", ""),
                    "story_idea": idea.get("story_idea", ""), "fps": 24},
        "revision": {"number": 1, "note": "Created from a story idea"},
        "story": {"pillars": {"setting": (idea.get("location") or "").strip(), "protagonist_id": characters[0]["id"],
                              "antagonist_id": characters[1]["id"] if len(characters) > 1 else None, "antagonist_note": "", "supporting_ids": [c["id"] for c in characters[2:]],
                              "core_conflict": "", "plot": "", "theme": idea.get("theme", "")}},
        "characters": characters,
        "structure": {"acts": [{"act": 1, "label": "Setup", "purpose": "Introduce the people, place and desire."},
                               {"act": 2, "label": "Confrontation", "purpose": "Raise the stakes until something must change."},
                               {"act": 3, "label": "Resolution", "purpose": "Show the consequence of the choice."}]},
        "sequences": [{"id": "SEQ-1", "title": "Opening sequence", "act": 1, "summary": "", "scene_ids": ["SC-001"]}],
        "scenes": [scene],
    }


def run(payload):
    data, warnings = process(payload)
    return {"artifact_type": "screenplay", "data": data, "warnings": warnings}
