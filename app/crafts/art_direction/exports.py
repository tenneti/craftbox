"""Art direction exports: the approved art direction manifest, the asset reference manifest, storyboard/previz metadata and a prop list.

Builders are pure; the service supplies run, approval and register context. Nothing is rendered and nothing is written to Dreambox.
"""
import csv
import io
import math

from app.crafts.art_direction import layout as lay
from app.hashing import sha256

APPLICATION = "craftbox"
IMPORT_POLICY = {"auto_import": False, "requires_user_confirmation": True,
                 "note": "A Dreambox-owned adapter must validate schema, IDs, hashes and asset rights and stage the import; nothing is imported automatically."}
LIGHT_WORDS = {"lamp", "candle", "lantern", "light", "sconce", "chandelier"}
PREVIZ_PLACES = [("platform", "RAILWAY_PLATFORM"), ("station", "RAILWAY_PLATFORM"), ("train", "TRAIN_INTERIOR"), ("cafe", "CAFE"), ("shop", "CAFE"), ("store", "CAFE"), ("bar", "CAFE"),
                 ("office", "OFFICE"), ("street", "STREET"), ("park", "PARK"), ("road", "ROAD"), ("terrace", "TERRACE"), ("balcony", "TERRACE"),
                 ("room", "ROOM"), ("house", "ROOM"), ("home", "ROOM"), ("kitchen", "ROOM"), ("bedroom", "ROOM")]
DREAMBOX_KIND = {"image": "image", "texture": "texture", "background": "background", "design": "design", "reference": "reference"}


def previz_hint(art):
    text = " ".join([art["location"]["name"], art["location"].get("description", "")]).lower()
    preset = next((p for w, p in PREVIZ_PLACES if w in text), "EMPTY_STAGE")
    return {"environment_preset": preset, "basis": "keywords in the location name and description", "verify": "preset names taken from Dreambox's Previz status document, not from its code"}


def _lights(art):
    out = [{"id": o["id"], "name": o["name"], "x": o["x"], "y": o["y"], "source": "layout"} for o in art["layout"]["objects"] if set(lay.words(o["name"])) & LIGHT_WORDS]
    out += [{"id": p["id"], "name": p["name"], "x": (p["position"] or {}).get("x"), "y": (p["position"] or {}).get("y"), "source": "prop"} for p in art["props"] if set(lay.words(p["name"])) & LIGHT_WORDS]
    return out


def _facts(art):
    facts = []
    for p in art["props"]:
        for st in p.get("states", []):
            facts.append(f"{p['name']}: {st['where']} ({st['at_kind']} {st['at_id']})" + (f", {st['note']}" if st.get("note") else ""))
    return facts


def integration(art):
    st, loc = art["style"], art["location"]
    return {
        "lighting": {"palette": st.get("palette", []), "time_of_day": loc.get("environment", {}).get("time_of_day", ""), "weather": loc.get("environment", {}).get("weather", ""),
                     "atmosphere": loc.get("environment", {}).get("atmosphere", ""), "practical_lights": _lights(art), "windows": [o["id"] for o in art["layout"]["objects"] if "window" in lay.words(o["name"])]},
        "costume": {"palette": st.get("palette", []), "period": st.get("period", {}), "materials": st.get("materials", []), "textures": [t["name"] for t in st.get("textures", [])],
                    "note": "Wardrobe should be checked against this palette; the Costume craft is not built yet."},
        "cinematography": {"layout": {"width_m": art["layout"].get("width_m"), "depth_m": art["layout"].get("depth_m"), "objects": [{"id": o["id"], "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"], "solid": o.get("solid", False)} for o in art["layout"]["objects"]]},
                           "variations": [{"shot_id": v["shot_id"], "summary": v.get("summary", ""), "hide": v.get("hide_prop_ids", []), "show": v.get("show_prop_ids", [])} for v in art.get("variations", [])]},
        "scene_maker": {"location": {"name": loc["name"], "description": loc.get("description", ""), "lighting": loc.get("environment", {}).get("atmosphere", ""), "time": loc.get("environment", {}).get("time_of_day", ""),
                                     "weather": loc.get("environment", {}).get("weather", "")},
                        "props": [{"name": p["name"], "description": p.get("description", "")} for p in art["props"]], "continuity_facts": _facts(art),
                        "verify": "Scene Maker prop and location shapes were not read closely; see docs/dreambox-overlap-audit.md section 7"},
    }


def _common(ctx, kind, san):
    return {"manifest_id": f"{kind}-{ctx['run_id']}", "exported_at": ctx["exported_at"],
            "source": {"application": APPLICATION, "version": ctx["app_version"], "run_id": ctx["run_id"], "experiment_id": ctx["experiment_id"], "source_status": ctx.get("source_status", "current")},
            "approval": ctx["approval"], "overrides": ctx.get("overrides", []), "provenance": {"ai_used": False, "source": "local-manual"}, "import_policy": IMPORT_POLICY}


def art_manifest(ctx, art, screenplay):
    san = next(s for s in screenplay["analysis"]["scenes"] if s["scene_id"] == art["scene_id"])
    m = {"schema": "filmcraft.art_direction_manifest.v1", **_common(ctx, "adm", san), "project": {"id": screenplay["project"]["id"], "title": screenplay["project"]["title"]},
         "scene": {"id": art["scene_id"], "slugline": san["slugline"], "fps": san["fps"]},
         "treatment": art["treatment"], "location": art["location"], "layout": art["layout"], "props": art["props"], "style": art["style"], "variations": art.get("variations", []),
         "integration": integration(art), "hashes": {"scene_hash": san["scene_hash"], "art_hash": art["analysis"]["art_hash"]}}
    m["manifest_sha256"] = sha256(m)
    return m


def asset_manifest(ctx, art, register, file_status):
    reg = {a["id"]: a for a in (register or {}).get("assets", [])}
    used = {}
    for t in art["style"].get("textures", []):
        if t.get("asset_id"):
            used.setdefault(t["asset_id"], []).append(f"texture:{t['id']}")
    for p in art["props"]:
        for a in p.get("asset_ids", []):
            used.setdefault(a, []).append(f"prop:{p['id']}")
    for a in art.get("asset_ids", []):
        used.setdefault(a, []).append(f"treatment:{art['treatment']['id']}")
    rows = []
    for aid, by in sorted(used.items()):
        a = reg.get(aid)
        if a is None:
            continue
        rows.append({"id": a["id"], "name": a["name"], "kind": a["kind"], "sha256": a["sha256"], "filename": a.get("filename", ""), "size_bytes": a.get("size_bytes"), "mime": a.get("mime", ""),
                     "source": a["source"], "rights": a["rights"], "usage": a.get("usage", {}), "used_by": by, "file_present": bool(file_status.get(a["sha256"])),
                     "dreambox_hint": {"library_kind": DREAMBOX_KIND.get(a["kind"], "reference"), "suggested_tags": sorted(set(a.get("tags", []) + [art["treatment"]["id"].lower(), art["scene_id"].lower(), a["kind"]])),
                                       "copy_policy": "Reference only. Craftbox never writes to the Dreambox library; an adapter decides whether to copy the file."}})
    cleared = sum(1 for r in rows if r["rights"]["status"] == "cleared")
    m = {"schema": "filmcraft.asset_reference_manifest.v1", **_common(ctx, "arm", None), "project_id": art["project_id"], "scene_id": art["scene_id"], "treatment_id": art["treatment"]["id"],
         "assets": rows, "summary": {"assets": len(rows), "rights_cleared": cleared, "rights_open": len(rows) - cleared, "missing_from_register": sorted(set(used) - set(reg))}}
    m["manifest_sha256"] = sha256(m)
    return m


def storyboard_metadata(art, plan):
    pal = art["style"].get("palette", [])
    variations = {v["shot_id"]: v for v in art.get("variations", [])}
    props = {p["id"]: p for p in art["props"]}
    objs = art["layout"]["objects"]
    shots = []
    for s in (plan or {}).get("shots", []):
        if s["status"] == "rejected":
            continue
        v = variations.get(s["shot_id"])
        hide, show = set((v or {}).get("hide_prop_ids", [])), set((v or {}).get("show_prop_ids", []))
        visible = [pid for pid, p in props.items() if (s["shot_id"] in p.get("shot_ids", []) or pid in show) and pid not in hide]
        tgt = (s.get("previz") or {}).get("target") or {"x": 0.5, "y": 0.5}
        near = sorted(objs, key=lambda o: math.dist((o["x"], o["y"]), (tgt["x"], tgt["y"])))[:4]
        shots.append({"shot_id": s["shot_id"], "beat_id": s["beat_id"], "camera_side": s["camera_side"], "size": s["size"], "palette": (v or {}).get("palette") or pal,
                      "variation": ({"id": v["id"], "summary": v.get("summary", ""), "status": v["status"]} if v else None),
                      "props_visible": [{"id": i, "name": props[i]["name"], "position": props[i]["position"]} for i in visible],
                      "set_objects_in_view": [{"id": o["id"], "name": o["name"], "kind": o["kind"]} for o in near],
                      "camera_layout": (s.get("previz") or {}).get("camera_position"), "texture_notes": [t["name"] for t in art["style"].get("textures", [])][:3]})
    return {"schema": "filmcraft.storyboard_metadata.v1", "project_id": art["project_id"], "scene_id": art["scene_id"], "treatment_id": art["treatment"]["id"],
            "location": {"name": art["location"]["name"], "kind": art["location"]["kind"]}, "previz_hint": previz_hint(art), "shots": shots,
            "note": "Metadata only. Craftbox draws no pictures; a storyboard or previz tool turns this into frames."}


def prop_csv(art):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["id", "name", "kind", "status", "x", "y", "scenes", "shots", "script_lines", "states", "assets"])
    for p in art["props"]:
        pos = p.get("position") or {}
        w.writerow([p["id"], p["name"], p.get("kind", "prop"), p["status"], pos.get("x", ""), pos.get("y", ""), "; ".join(p.get("scene_ids", [])), "; ".join(p.get("shot_ids", [])),
                    "; ".join(p.get("mentions", [])), "; ".join(f"{s['at_kind']} {s['at_id']}: {s['where']}" for s in p.get("states", [])), "; ".join(p.get("asset_ids", []))])
    return out.getvalue()
