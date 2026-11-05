"""Set layout helpers: classification, footprints, geometry, colour maths and the starting presets.

Coordinates are the Direction Lab's stage coordinates (0..1, x left to right as the master camera sees it, y back wall to
audience side), so blocking positions from a direction plan can be drawn and tested on the same plan without conversion.
"""
import math
import re

ARCH = ("door", "window", "wall", "stairs", "staircase", "arch", "column", "entrance", "gate")
FURN = ("counter", "desk", "table", "bar", "shelf", "shelves", "bookcase", "bookshelf", "chair", "armchair", "sofa", "couch", "bench", "stool", "cabinet", "bed", "wardrobe")
FOOTPRINT = {"door": (0.07, 0.09), "window": (0.14, 0.04), "wall": (0.20, 0.03), "counter": (0.24, 0.10), "desk": (0.18, 0.10), "table": (0.16, 0.12), "bar": (0.30, 0.08),
             "shelf": (0.40, 0.06), "shelves": (0.40, 0.06), "bookcase": (0.30, 0.07), "bookshelf": (0.30, 0.07), "chair": (0.07, 0.07), "armchair": (0.10, 0.10), "sofa": (0.20, 0.10),
             "couch": (0.20, 0.10), "bench": (0.16, 0.06), "stool": (0.05, 0.05), "cabinet": (0.12, 0.07), "bed": (0.22, 0.30), "wardrobe": (0.14, 0.08)}
DEFAULT_SLOT = {"door": (0.08, 0.88), "counter": (0.74, 0.42), "desk": (0.74, 0.42), "table": (0.70, 0.45), "bar": (0.74, 0.42), "shelf": (0.50, 0.08), "shelves": (0.50, 0.08),
                "bookcase": (0.50, 0.08), "window": (0.18, 0.06), "stairs": (0.90, 0.30)}
STOP = {"worn", "shop", "with", "and", "the", "old", "small", "large", "little", "this", "that"}


def words(name):
    return re.findall(r"[a-z]+", (name or "").lower())


def classify(name):
    """'architecture', 'furniture' or 'prop' for a named object."""
    w = set(words(name))
    if w & set(ARCH):
        return "architecture"
    if w & set(FURN):
        return "furniture"
    return "prop"


def footprint(name):
    for w in words(name):
        if w in FOOTPRINT:
            return FOOTPRINT[w]
    return (0.10, 0.08)


def slot(name):
    for w in words(name):
        if w in DEFAULT_SLOT:
            return DEFAULT_SLOT[w]
    return None


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def rect(o):
    return (o["x"] - o["w"] / 2, o["y"] - o["h"] / 2, o["x"] + o["w"] / 2, o["y"] + o["h"] / 2)


def overlap_area(a, b):
    ra, rb = rect(a), rect(b)
    w = min(ra[2], rb[2]) - max(ra[0], rb[0])
    h = min(ra[3], rb[3]) - max(ra[1], rb[1])
    return max(0.0, w) * max(0.0, h)


def inside(o, x, y, pad=0.0):
    r = rect(o)
    return r[0] - pad <= x <= r[2] + pad and r[1] - pad <= y <= r[3] + pad


def segment_hits(o, p, q):
    """Liang-Barsky: does the segment p-q cross the object's rectangle?"""
    x0, y0, x1, y1 = rect(o)
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pn, qn in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pn == 0:
            if qn < 0:
                return False
        else:
            t = qn / pn
            if pn < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t0 <= t1


def rgb(hex_):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(hex_):
    r, g, b = rgb(hex_)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def warmth(hex_):
    r, _, b = rgb(hex_)
    return (r - b) / 255


def saturation(hex_):
    r, g, b = (v / 255 for v in rgb(hex_))
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


def distance(h1, h2):
    a, b = rgb(h1), rgb(h2)
    return math.dist(a, b) / math.dist((0, 0, 0), (255, 255, 255))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:24] or "x"


PRESETS = {
    "warm_nostalgia": {
        "name": "Warm nostalgia",
        "summary": "An intimate shop that has kept everything: aged wood, amber light, objects that belong to someone.",
        "intent": "Make the room feel lived in and remembered, so the characters' silence reads as history held close rather than distance.",
        "atmosphere": "Close, warm and a little dusty; the rain makes it feel sheltered.",
        "palette": [("Aged oak", "#8B5E3C", "dominant"), ("Candlelight amber", "#E0A85A", "accent"), ("Faded cream", "#F1E3C8", "light"),
                    ("Oxblood leather", "#6B2D2D", "accent"), ("Moss green", "#5E6B4A", "support")],
        "textures": [("Worn wood grain", "Scratched, polished by hands"), ("Cloth book spines", "Faded fabric covers, cracked gilt"), ("Soft paper", "Yellowed pages, dog-eared corners")],
        "materials": [("Aged oak", "matte, waxed"), ("Brass", "tarnished"), ("Worn leather", "creased"), ("Wool rug", "faded pattern")],
        "period": ("1980s, a shop that never modernised", "Hand-lettered signs, mismatched lamps, no screens."),
        "themes": ["memory", "warmth", "accumulation"], "mood_words": ["intimate", "nostalgic", "sheltered"],
        "kit": [("armchair", "Reading armchair", "furniture", 0.10, 0.10, True, [(0.90, 0.22), (0.88, 0.75), (0.12, 0.30)]),
                ("rug", "Worn rug", "decor", 0.30, 0.18, False, [(0.50, 0.55)]),
                ("lamp", "Table lamp", "decor", 0.04, 0.04, False, [(0.80, 0.36), (0.66, 0.36)]),
                ("photos", "Framed photographs", "decor", 0.14, 0.03, False, [(0.28, 0.04), (0.74, 0.04)]),
                ("stacks", "Stacked books", "decor", 0.07, 0.06, True, [(0.60, 0.28), (0.40, 0.22), (0.20, 0.45)])],
        "personal": [("Tea cup", "personal", (0.72, 0.43)), ("Reading glasses", "personal", (0.88, 0.20)), ("Framed photograph", "personal", (0.28, 0.06))],
        "modify": {},
    },
    "emotional_distance": {
        "name": "Emotional distance",
        "summary": "A restrained, almost empty shop: cool light, pale surfaces, space between the people.",
        "intent": "Leave room around the characters so the space itself says how far apart they have grown.",
        "atmosphere": "Quiet, cool and exposed; the rain is the only movement.",
        "palette": [("Pale ash", "#CFD6D9", "dominant"), ("Slate blue", "#5C6F80", "accent"), ("Cold white", "#F4F7F8", "light"),
                    ("Graphite", "#3A4046", "support"), ("Steel grey", "#8A949B", "support")],
        "textures": [("Smooth plaster", "Matte, unmarked walls"), ("Brushed metal", "Cool, even sheen")],
        "materials": [("Pale oak", "sealed, light"), ("Concrete", "smooth floor"), ("Glass", "clear")],
        "period": ("Contemporary, stripped back", "Almost no decoration; nothing personal on show."),
        "themes": ["distance", "restraint", "absence"], "mood_words": ["detached", "quiet", "exposed"],
        "kit": [("bench", "Single bench", "furniture", 0.16, 0.06, True, [(0.14, 0.62), (0.14, 0.30)]),
                ("floorlamp", "Floor lamp", "decor", 0.04, 0.04, False, [(0.92, 0.12)])],
        "personal": [],
        "modify": {"shelf_scale": 0.55, "counter_shift_x": 0.10},
    },
    "blank": {
        "name": "New treatment", "summary": "", "intent": "", "atmosphere": "",
        "palette": [], "textures": [], "materials": [], "period": ("", ""), "themes": [], "mood_words": [], "kit": [], "personal": [], "modify": {},
    },
}
PRESET_LABELS = {k: v["name"] for k, v in PRESETS.items()}
