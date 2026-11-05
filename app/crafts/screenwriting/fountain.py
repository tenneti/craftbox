"""Readable screenplay format (Fountain-style) export and import for the Screenwriting Lab.

Round-trips: project id/title/logline/genre/theme, character ids and names, scene ids (as Fountain scene
numbers ``#SC-001#``), headings, synopsis (``= ...``), objective/conflict/turning point/outcome (notes),
and every action / dialogue / parenthetical / transition line with its speaker.
Not carried by this format (use the JSON export for them): beats, props, sequences/acts, timings, hashes.
"""
import re

HEADING = re.compile(r"^\.?(INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?)[ .]\s*(.+?)(?:\s+#([A-Za-z0-9][\w.-]*)#)?\s*$", re.I)
NOTE = re.compile(r"\[\[(.*?)\]\]", re.S)
TITLE_KEYS = {"title": "title", "project-id": "project_id", "characters": "characters", "logline": "logline", "genre": "genre",
              "theme": "theme", "credit": None, "author": None, "source": None, "draft date": None, "contact": None, "fps": "fps"}
NOTE_FIELDS = ("objective", "conflict", "turning_point", "outcome")
INT_EXT = {"INT": "INT.", "EXT": "EXT.", "INT/EXT": "INT/EXT.", "EXT/INT": "EXT/INT.", "I/E": "INT/EXT."}


def _one_line(text):
    return re.sub(r"\s*\n\s*", " ", (text or "").strip())


def export(doc):
    names = {c["id"]: c["name"] for c in doc["characters"]}
    p = doc["project"]
    out = [f"Title: {p['title']}", f"Project-ID: {p['id']}"]
    for key in ("logline", "genre", "theme"):
        if p.get(key):
            out.append(f"{key.capitalize()}: {_one_line(p[key])}")
    out.append("Characters: " + "; ".join(f"{c['id']}={c['name']}" for c in doc["characters"]))
    out.append("")
    for scene in doc["scenes"]:
        h = scene["heading"]
        head = f"{h['int_ext']} {h['location'].strip().upper()}" + (f" - {h['time'].strip().upper()}" if (h.get("time") or "").strip() else "")
        out += [f"{head} #{scene['id']}#", ""]
        if (scene.get("synopsis") or "").strip():
            out += [f"= {_one_line(scene['synopsis'])}", ""]
        for key in NOTE_FIELDS:
            if (scene.get(key) or "").strip():
                out.append(f"[[{key}: {_one_line(scene[key])}]]")
        if any((scene.get(k) or "").strip() for k in NOTE_FIELDS):
            out.append("")
        els = scene["elements"]
        i = 0
        while i < len(els):
            e = els[i]
            text = re.sub(r"\n\s*\n", "\n", e["text"].strip())
            if e["type"] == "dialogue":
                out += [names[e["character_id"]].upper(), *text.split("\n"), ""]
            elif e["type"] == "parenthetical":
                nxt = els[i + 1] if i + 1 < len(els) else None
                if nxt and nxt["type"] == "dialogue" and nxt.get("character_id") == e.get("character_id"):
                    body = re.sub(r"\n\s*\n", "\n", nxt["text"].strip())
                    out += [names[nxt["character_id"]].upper(), f"({text.strip('()')})", *body.split("\n"), ""]
                    i += 1
                else:
                    out += [f"({text.strip('()')})", ""]
            elif e["type"] == "transition":
                out += [f"> {text.upper()}", ""]
            else:
                out += [_one_line(text), ""]
            i += 1
    return "\n".join(out).rstrip() + "\n"


def _is_cue(line):
    core = re.sub(r"\(.*?\)", "", line).strip()
    return bool(core) and core == core.upper() and re.search(r"[A-Z]", core) and len(core) <= 40 and not core.endswith("TO:")


def parse(text, project_id=None, title=None):
    """Parse a Fountain-style script into a ``filmcraft.screenplay.v1`` document (no analysis)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        raise ValueError("the script is empty")
    lines = text.split("\n")
    meta, i = {}, 0
    while i < len(lines) and re.match(r"^[A-Za-z][A-Za-z -]*:\s*\S", lines[i]):
        key, _, val = lines[i].partition(":")
        mapped = TITLE_KEYS.get(key.strip().lower(), None)
        if mapped:
            meta[mapped] = val.strip()
        i += 1
    body = "\n".join(lines[i:])
    chars, order = {}, []   # uppercase name -> {id, name}

    def add_char(name, cid=None):
        key = name.strip().upper()
        if key not in chars:
            used = {c["id"] for c in chars.values()}
            n = len(chars) + 1
            while cid is None and f"C-{n:03d}" in used:
                n += 1
            chars[key] = {"id": cid or f"C-{n:03d}", "name": name.strip()}
            order.append(key)
        return chars[key]

    for pair in filter(None, (x.strip() for x in meta.get("characters", "").split(";"))):
        if "=" in pair:
            cid, _, nm = pair.partition("=")
            add_char(nm, cid.strip())
    scenes, current, used_ids = [], None, set()

    def new_scene(h):
        nonlocal current
        m = HEADING.match(h)
        ie = INT_EXT[re.sub(r"\.", "", m.group(1).upper())]
        loc, _, tm = m.group(2).rpartition(" - ") if " - " in m.group(2) else (m.group(2), "", "")
        sid = m.group(3) or f"SC-{len(scenes) + 1:03d}"
        n = len(scenes) + 1
        while sid in used_ids:
            n += 1; sid = f"SC-{n:03d}"
        used_ids.add(sid)
        current = {"id": sid, "sequence_id": "SEQ-1", "heading": {"int_ext": ie, "location": loc.strip().upper(), "time": tm.strip().upper()},
                   "synopsis": "", "objective": "", "conflict": "", "turning_point": "", "outcome": "", "characters": [], "props": [], "elements": [], "beats": []}
        scenes.append(current)

    def element(kind, text, cid=None):
        eid = f"{current['id']}-E{len(current['elements']) + 1:02d}"
        current["elements"].append({"id": eid, "type": kind, "character_id": cid, "text": text})

    for block in re.split(r"\n\s*\n", body):
        blines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not blines or blines[0].startswith("==="):
            continue
        first = blines[0].strip()
        if HEADING.match(first) and not first.startswith("(") and (first.startswith(".") or re.match(r"^(INT|EXT|I/E)", first, re.I)):
            new_scene(first)
            blines = blines[1:]
            if not blines:
                continue
            first = blines[0].strip()
        if current is None:
            continue
        for note in NOTE.finditer("\n".join(blines)):
            k, _, v = note.group(1).partition(":")
            if k.strip().lower() in NOTE_FIELDS:
                current[k.strip().lower()] = v.strip()
        blines = [l for l in blines if not NOTE.fullmatch(l.strip())]
        if not blines:
            continue
        if blines[0].startswith("="):
            current["synopsis"] = blines[0].lstrip("= ").strip()
            continue
        first = blines[0].strip()
        if first.startswith(">") and not first.endswith("<"):
            element("transition", first.lstrip("> ").strip()); continue
        if first.upper() == first and first.endswith("TO:"):
            element("transition", first); continue
        if first.startswith("!"):
            blines[0] = first[1:]; first = blines[0]
        elif _is_cue(first) and len(blines) > 1 and not first.startswith("("):
            cue = re.sub(r"\s*\(.*?\)\s*$", "", first.lstrip("@")).strip()
            c = add_char(cue)
            speech = []
            for l in blines[1:]:
                l = l.strip()
                if re.fullmatch(r"\(.*\)", l) and not speech:
                    element("parenthetical", l[1:-1].strip(), c["id"])
                else:
                    speech.append(l)
            if speech:
                element("dialogue", " ".join(speech), c["id"])
            continue
        if re.fullmatch(r"\(.*\)", first) and len(blines) == 1:
            element("parenthetical", first[1:-1].strip()); continue
        element("action", " ".join(l.strip() for l in blines))
    if not scenes:
        raise ValueError("no scene headings found (a heading looks like 'INT. KITCHEN - NIGHT')")
    char_list = [chars[k] for k in order]
    for sc in scenes:
        text_all = " ".join(e["text"] for e in sc["elements"] if e["type"] == "action").upper()
        sc["characters"] = [c["id"] for c in char_list
                            if any(e.get("character_id") == c["id"] for e in sc["elements"])
                            or re.search(r"\b" + re.escape(c["name"].upper()) + r"\b", text_all)]
    pid = project_id or meta.get("project_id") or re.sub(r"[^a-z0-9]+", "-", (title or meta.get("title") or "imported").lower()).strip("-") or "imported"
    return {
        "schema": "filmcraft.screenplay.v1",
        "project": {"id": pid, "title": title or meta.get("title") or "Imported script", "logline": meta.get("logline", ""),
                    "genre": meta.get("genre", ""), "theme": meta.get("theme", ""), "story_idea": "", "fps": int(meta.get("fps") or 24)},
        "revision": {"number": 1, "note": "Imported from a readable script"},
        "characters": [{"id": c["id"], "name": c["name"], "role": "", "description": "", "motivation": "", "want": "", "need": "", "flaw": "",
                        "relationships": [], "emotional_arc": {"start": "", "end": ""}} for c in char_list],
        "structure": {"acts": [{"act": 1, "label": "Setup", "purpose": ""}, {"act": 2, "label": "Confrontation", "purpose": ""}, {"act": 3, "label": "Resolution", "purpose": ""}]},
        "sequences": [{"id": "SEQ-1", "title": "Imported scenes", "act": 1, "summary": "", "scene_ids": [s["id"] for s in scenes]}],
        "scenes": scenes,
    }
