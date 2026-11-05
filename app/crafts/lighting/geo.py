"""Small 2D geometry and the approximate illumination model used by the Lighting craft.

Stage coordinates are the director's: 0..1, x left to right, y from the back wall (0) to the audience (1). One x unit is
``width_m`` metres and one y unit is ``depth_m`` metres. A light's ``rotation_deg`` is a compass on that plan:
0 = pointing at the audience, 90 = pointing right, 180 = pointing at the back wall, 270 = pointing left.

The model is an approximation for planning: a cone with soft edges, a distance falloff and a rough shadow test against solid
set pieces. It is not a physical simulation and says so wherever its numbers are shown.
"""
import math

REF_M = 1.5          # distance at which inverse-square light has its stated intensity
OCCLUDED = 0.35      # share of a light that still reaches a point behind a solid piece (bounce and wrap)


def metres(stage, x, y):
    return x * stage["width_m"], y * stage["depth_m"]


def dist_m(stage, a, b):
    ax, ay = metres(stage, a[0], a[1])
    bx, by = metres(stage, b[0], b[1])
    return math.hypot(ax - bx, ay - by)


def direction(rotation_deg):
    r = math.radians(rotation_deg)
    return math.sin(r), math.cos(r)


def bearing(stage, a, b):
    """Compass angle (0..360) of the line from point a to point b, in metres."""
    ax, ay = metres(stage, a[0], a[1])
    bx, by = metres(stage, b[0], b[1])
    return math.degrees(math.atan2(bx - ax, by - ay)) % 360


def angle_diff(a, b):
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rect_of(o):
    return (o["x"] - o["w"] / 2, o["y"] - o["h"] / 2, o["x"] + o["w"] / 2, o["y"] + o["h"] / 2)


def inside(rect, x, y, pad=0.0):
    return rect[0] - pad <= x <= rect[2] + pad and rect[1] - pad <= y <= rect[3] + pad


def segment_hits(a, b, rect):
    """True when the segment a-b passes through the rectangle (Liang-Barsky)."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - rect[0]), (dx, rect[2] - x0), (-dy, y0 - rect[1]), (dy, rect[3] - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


def in_view(stage, camera, target, fov_deg, point, reach_m=None):
    """True when ``point`` is inside the horizontal view wedge of a camera (plan view)."""
    c, t = (camera["x"], camera["y"]), (target["x"], target["y"])
    axis = bearing(stage, c, t)
    d = dist_m(stage, c, (point[0], point[1]))
    if d < 0.05:
        return True
    if reach_m is not None and d > reach_m:
        return False
    return angle_diff(bearing(stage, c, point), axis) <= fov_deg / 2


def frame_limits(stage, camera, fov_deg, height_m, point):
    """Lowest and highest height (metres) that the frame shows at ``point``; a level camera and a 16:9 frame are assumed."""
    d = dist_m(stage, (camera["x"], camera["y"]), point)
    half_v = math.atan(math.tan(math.radians(fov_deg) / 2) * 9 / 16)
    return height_m - d * math.tan(half_v), height_m + d * math.tan(half_v)


def light_at(light, stage, point, solids=()):
    """Relative level (0..1+) a single light puts on ``point``, and whether a solid piece is in the way."""
    if not light.get("enabled", True):
        return 0.0, False
    inten = light["intensity"]
    if not light.get("positional", True):
        return inten, False
    pos = (light["x"], light["y"])
    d = max(dist_m(stage, pos, point), 0.2)
    off = angle_diff(bearing(stage, pos, point), light["rotation_deg"])
    half = light["beam_angle_deg"] / 2
    inner = half * (1 - light["softness"])
    ang = 1.0 if off <= inner else smooth(1 - (off - inner) / max(half - inner, 1e-6)) if off < half else 0.0
    fall = light["falloff"]
    if fall["mode"] == "inverse_square":
        dist = min(1.0, (REF_M / d) ** 2) * min(1.0, 1.0 + (fall["range_m"] - d) / fall["range_m"]) if d < fall["range_m"] else 0.0
    elif fall["mode"] == "linear":
        dist = max(0.0, 1 - d / fall["range_m"])
    else:
        dist = 1.0
    blocked = any(segment_hits(pos, point, r) and not inside(r, pos[0], pos[1], 0.02) and not inside(r, point[0], point[1], 0.0) for r in solids)
    return inten * ang * dist * (OCCLUDED if blocked else 1.0), blocked


def mired(kelvin):
    return 1e6 / kelvin
