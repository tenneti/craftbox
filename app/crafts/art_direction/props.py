"""Prop extraction from a screenplay scene (and its direction plan). Deterministic keyword matching, no AI."""
import re

from app.crafts.art_direction import layout as lay

VOCAB = {"ticket": "Ticket", "coat": "Coat", "lamp": "Lamp", "umbrella": "Umbrella", "letter": "Letter", "key": "Key", "cup": "Cup", "phone": "Phone", "photograph": "Photograph",
         "photo": "Photograph", "candle": "Candle", "bag": "Bag", "scarf": "Scarf", "glasses": "Glasses", "book": "Book", "paperback": "Paperback", "suitcase": "Suitcase", "ring": "Ring"}
LIGHT = {"lamp", "candle", "lantern", "light"}
ALIAS = {"paperback": ("book", "paperback"), "book": ("book", "paperback"), "photograph": ("photo", "photograph"), "photo": ("photo", "photograph")}


def keywords(name):
    ws = [w for w in lay.words(name) if len(w) >= 4 and w not in lay.STOP]
    out = []
    for w in ws:
        out.extend(ALIAS.get(w, (w,)))
    return list(dict.fromkeys(out))


def mentions_of(scene, kws):
    hits = []
    for e in scene["elements"]:
        low = set(re.findall(r"[a-z]+", (e["text"] or "").lower()))
        if any(k in low or k + "s" in low for k in kws):
            hits.append(e["id"])
    return hits


def extract(scene, plan):
    """Return a list of prop dicts (script source) for the scene: scene.props that are not furniture or architecture, plus vocabulary hits."""
    stage = {o["id"]: o for o in ((plan or {}).get("stage") or {}).get("objects", [])}
    shots = (plan or {}).get("shots", [])
    props, used = [], set()

    def shots_for(ments):
        return [s["shot_id"] for s in shots if s["status"] != "rejected" and set(s.get("covers", [])) & set(ments)]

    for p in scene.get("props", []):
        if lay.classify(p["name"]) != "prop":
            continue
        kws = keywords(p["name"]) or [p["name"].lower()]
        ments = mentions_of(scene, kws)
        pos = None
        if p["id"] in stage:
            o = stage[p["id"]]
            pos = {"x": o["x"], "y": o["y"]}
        props.append({"id": p["id"], "name": p["name"], "source": "script", "kind": "practical" if set(lay.words(p["name"])) & LIGHT else "prop", "description": "", "position": pos, "mentions": ments,
                      "scene_ids": [scene["id"]], "shot_ids": shots_for(ments), "states": [], "asset_ids": [], "status": "proposed", "notes": ""})
        used.update(kws)
    for word, label in VOCAB.items():
        if word in used or any(word in keywords(x["name"]) for x in props):
            continue
        ments = mentions_of(scene, [word])
        if not ments or label.lower() in {x["name"].lower() for x in props}:
            continue
        used.update(ALIAS.get(word, (word,)))
        props.append({"id": f"PR-{lay.slug(label).upper()}", "name": label, "source": "script", "kind": "practical" if word in LIGHT else "prop", "description": "", "position": None, "mentions": ments,
                      "scene_ids": [scene["id"]], "shot_ids": shots_for(ments), "states": [], "asset_ids": [], "status": "proposed", "notes": ""})
    return props


def architecture_mentions(scene, layout_objects):
    """Architecture or furniture the script names that the layout does not have yet (advice only)."""
    have = {w for o in layout_objects for w in lay.words(o["name"])}
    out = []
    for e in scene["elements"]:
        for w in set(re.findall(r"[a-z]+", (e["text"] or "").lower())):
            if (w in lay.ARCH or w in lay.FURN) and w not in have and w not in out:
                out.append(w)
    return out
