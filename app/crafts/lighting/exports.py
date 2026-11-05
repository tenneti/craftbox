"""Lighting exports: the plan itself, a light schedule (CSV), per-shot lighting instructions and the approved lighting manifest.

Builders are pure. Lighting data and art-direction data stay apart: exports carry only ids and hashes that point at the art treatment.
Nothing is rendered and nothing is written to Dreambox.
"""
import csv
import io

from app.crafts.lighting import plan as pl
from app.hashing import sha256

APPLICATION = "craftbox"
IMPORT_POLICY = {"auto_import": False, "requires_user_confirmation": True,
                 "note": "A Dreambox-owned adapter must validate schema, IDs and hashes and stage the import; nothing is imported automatically."}
MODEL_NOTE = "Positions and levels are planning estimates on the director's stage plan, not a physical lighting simulation."


def _light_row(l, stage):
    return {"id": l["id"], "name": l["name"], "role": l["role"], "source": l["source"], "kind": l["kind"], "enabled": l["enabled"], "stage": {"x": l["x"], "y": l["y"], "height_m": l["height_m"]},
            "metres": {"x": round(l["x"] * stage["width_m"], 2), "y": round(l["y"] * stage["depth_m"], 2), "z": l["height_m"]}, "rotation_deg": l["rotation_deg"], "tilt_deg": l["tilt_deg"],
            "intensity": l["intensity"], "color_temp_k": l["color_temp_k"], "beam_angle_deg": l["beam_angle_deg"], "softness": l["softness"], "falloff": l["falloff"], "positional": l.get("positional", True),
            "motivated_by": l.get("motivated_by", ""), "practical_object_id": l.get("practical_object_id", ""), "narrative_purpose": l.get("narrative_purpose", ""), "adjusted_for_shot": bool(l.get("adjusted"))}


def _art_ref(doc):
    a = doc["source"]["art"]
    return {k: a[k] for k in ("treatment_id", "treatment_name", "art_hash")}


def instructions(doc, art, plan, ctx):
    stage = {"width_m": art["layout"]["width_m"], "depth_m": art["layout"]["depth_m"]}
    shots = []
    rows = {r["shot_id"]: r for r in doc["analysis"]["shots"]}
    for s in (plan or {}).get("shots", []):
        if s.get("status") == "rejected":
            continue
        lights, adj = pl.resolve_shot(doc, s["shot_id"])
        pv = s.get("previz") or {}
        r = rows.get(s["shot_id"], {})
        shots.append({"shot_id": s["shot_id"], "beat_id": s["beat_id"], "size": s["size"], "angle": s.get("angle"), "camera_side": s["camera_side"], "lens_mm": s.get("lens_mm"),
                      "camera": {"position": pv.get("camera_position"), "target": pv.get("target"), "fov_deg": pv.get("fov_deg")},
                      "adjustment_id": adj["id"] if adj else None, "adjustment_reason": adj["reason"] if adj else "", "lights": [_light_row(l, stage) for l in lights if l["enabled"]],
                      "switched_off": [l["id"] for l in lights if not l["enabled"]], "key_light_id": r.get("key_id"), "key_side_of_camera": r.get("key_side"),
                      "subjects": r.get("subjects", []), "fixtures_in_frame": r.get("fixtures_in_frame", [])})
    return {"schema": "filmcraft.lighting_instructions.v1", "project_id": doc["project_id"], "scene_id": doc["scene_id"], "plan_id": doc["plan"]["id"], "plan_name": doc["plan"]["name"], "stage": stage,
            "conventions": {"stage_xy": "0..1; x left to right, y from the back wall (0) to the audience (1)", "rotation_deg": "0 faces the audience, 90 faces right, 180 faces the back wall, 270 faces left",
                            "intensity": "0 to 1, relative", "tilt_deg": "negative aims downward"},
            "conditions": doc["conditions"], "scene_setup": [_light_row(l, stage) for l in doc["lights"]], "shots": shots, "art_reference": _art_ref(doc),
            "model_note": MODEL_NOTE, "plan_hash": doc["analysis"]["plan_hash"], "generated_at": ctx["exported_at"]}


def schedule_csv(doc, art, plan):
    stage = {"width_m": art["layout"]["width_m"], "depth_m": art["layout"]["depth_m"]}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["shot_id", "beat_id", "light_id", "name", "role", "source", "kind", "on", "x_m", "y_m", "height_m", "rotation_deg", "intensity", "color_temp_k", "beam_angle_deg", "softness", "falloff", "motivated_by", "changed_for_shot"])
    shots = [s for s in (plan or {}).get("shots", []) if s.get("status") != "rejected"] or [{"shot_id": "(scene)", "beat_id": ""}]
    for s in shots:
        lights = pl.resolve_shot(doc, s["shot_id"])[0] if s["shot_id"] != "(scene)" else doc["lights"]
        for l in lights:
            w.writerow([s["shot_id"], s["beat_id"], l["id"], l["name"], l["role"], l["source"], l["kind"], "yes" if l["enabled"] else "no", round(l["x"] * stage["width_m"], 2), round(l["y"] * stage["depth_m"], 2), l["height_m"],
                        l["rotation_deg"], l["intensity"], l["color_temp_k"], l["beam_angle_deg"], l["softness"], f"{l['falloff']['mode']} {l['falloff'].get('range_m', '')}m", l.get("motivated_by", ""), "yes" if l.get("adjusted") else ""])
    return buf.getvalue()


def _common(ctx, kind):
    return {"manifest_id": f"{kind}-{ctx['run_id']}", "exported_at": ctx["exported_at"],
            "source": {"application": APPLICATION, "version": ctx["app_version"], "run_id": ctx["run_id"], "experiment_id": ctx["experiment_id"], "source_status": ctx.get("source_status", "current")},
            "approval": ctx["approval"], "overrides": ctx.get("overrides", []), "provenance": {"ai_used": False, "source": "local-manual"}, "import_policy": IMPORT_POLICY}


def lighting_manifest(ctx, doc, art, plan, screenplay):
    san = next(s for s in screenplay["analysis"]["scenes"] if s["scene_id"] == doc["scene_id"])
    ins = instructions(doc, art, plan, ctx)
    m = {"schema": "filmcraft.lighting_manifest.v1", **_common(ctx, "lgm"), "project": {"id": screenplay["project"]["id"], "title": screenplay["project"]["title"]},
         "scene": {"id": doc["scene_id"], "slugline": san["slugline"], "fps": san["fps"]}, "plan": doc["plan"], "conditions": doc["conditions"], "lights": ins["scene_setup"], "adjustments": doc.get("adjustments", []),
         "art_reference": ins["art_reference"], "continuity": {"readiness": doc["analysis"]["readiness"], "metrics": doc["analysis"]["metrics"], "open_findings": [i for i in doc["analysis"]["issues"] if i["severity"] == "attention"]},
         "integration": {"cinematography": {"per_shot": [{"shot_id": s["shot_id"], "camera": s["camera"], "key_light_id": s["key_light_id"], "key_side_of_camera": s["key_side_of_camera"], "lights_on": [l["id"] for l in s["lights"]],
                                                         "fixtures_in_frame": s["fixtures_in_frame"]} for s in ins["shots"]],
                                          "note": "Camera data is copied for reference from the director's plan; the Cinematography craft owns it."},
                         "previz": {"stage": ins["stage"], "conventions": ins["conventions"], "scene_setup": ins["scene_setup"], "note": "Stage coordinates match the director's blocking, so lights can be placed in a previz scene without conversion."},
                         "scene_maker": {"time_of_day": doc["conditions"]["time_of_day"], "weather": doc["conditions"]["weather"], "mood": doc["conditions"]["mood_words"],
                                         "lights": [{"id": l["id"], "role": l["role"], "metres": l["metres"], "rotation_deg": l["rotation_deg"], "intensity": l["intensity"], "color_temp_k": l["color_temp_k"], "beam_angle_deg": l["beam_angle_deg"]} for l in ins["scene_setup"] if l["enabled"]],
                                         "verify": "Scene Maker's own lighting fields were not read closely; a Dreambox-owned adapter must map these."}},
         "hashes": {"scene_hash": san["scene_hash"], "plan_hash": doc["analysis"]["plan_hash"], "art_hash": ins["art_reference"]["art_hash"]}, "model_note": MODEL_NOTE}
    m["manifest_sha256"] = sha256(m)
    return m
