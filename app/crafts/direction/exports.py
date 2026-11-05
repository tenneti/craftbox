"""Direction exports: blocking, shot list, Cinematography-compatible shot plan and the two Dreambox-bound
manifests (scene manifest, shot manifest). Builders are pure; the service layer supplies run/approval context.
"""
import csv
import io

from app.hashing import sha256

APPLICATION = "craftbox"
IMPORT_POLICY = {"auto_import": False, "requires_user_confirmation": True,
                 "note": "A Dreambox-owned Scene Maker adapter must validate schema, IDs and hashes and stage the import; nothing is imported automatically."}
MOVEMENT_LABEL = {"push_in": "push in", "pull_out": "pull out"}


def active_shots(plan):
    return [s for s in plan["shots"] if s["status"] != "rejected"]


def blocking_export(plan, scene):
    titles = {b["id"]: b for b in scene.get("beats", [])}
    return {"schema": "filmcraft.blocking.v1", "project_id": plan["project_id"], "scene_id": plan["scene_id"], "stage": plan["stage"],
            "beats": [{"beat_id": b["beat_id"], "title": titles.get(b["beat_id"], {}).get("title", ""), "intensity": titles.get(b["beat_id"], {}).get("intensity"),
                       "notes": b.get("notes", ""), "characters": b["characters"]} for b in plan["blocking"]]}


def shot_list_export(plan, names):
    tl = {t["shot_id"]: t for t in plan["analysis"]["timeline"]}
    rows = []
    for s in plan["shots"]:
        t = tl.get(s["shot_id"])
        rows.append({"shot_id": s["shot_id"], "order": t["order"] if t else None, "status": s["status"], "beat_id": s["beat_id"], "purpose": s["purpose"],
                     "purpose_note": s["purpose_note"], "size": s["size"], "angle": s["angle"], "movement": s["movement"], "framing": s["framing"],
                     "camera_side": s["camera_side"], "lens_mm": s.get("lens_mm"), "subjects": [names.get(x, x) for x in s["subject"]],
                     "covers": s.get("covers", []), "duration_seconds": s["duration_seconds"], "start_seconds": t["start_seconds"] if t else None,
                     "transition_in": s.get("transition_in", "cut"), "review_note": s.get("review_note", "")})
    return {"schema": "filmcraft.shot_list.v1", "project_id": plan["project_id"], "scene_id": plan["scene_id"], "fps": plan["fps"],
            "approach": plan["approach"]["name"], "total_seconds": plan["analysis"]["total_seconds"], "shots": rows}


def shot_list_csv(listing):
    out = io.StringIO()
    cols = ["order", "shot_id", "status", "beat_id", "purpose", "size", "angle", "movement", "framing", "camera_side", "lens_mm", "duration_seconds",
            "start_seconds", "subjects", "covers", "transition_in", "purpose_note", "review_note"]
    w = csv.writer(out, lineterminator="\n")
    w.writerow(cols)
    for r in listing["shots"]:
        w.writerow([("; ".join(r[c]) if isinstance(r[c], list) else r[c]) for c in cols])
    return out.getvalue()


def shot_plan_export(plan, names):
    """filmcraft.shot_plan.v1, so the existing Cinematography/Editing pilots can consume a director's plan."""
    fps = plan["fps"]
    shots, total = [], 0
    for s in active_shots(plan):
        frames = max(1, round(s["duration_seconds"] * fps))
        total += frames
        shots.append({"shot_id": s["shot_id"], "scene_id": plan["scene_id"], "shot_type": s["size"], "duration_frames": frames,
                      "lens_mm": float(s.get("lens_mm") or 50), "camera_movement": MOVEMENT_LABEL.get(s["movement"], s["movement"]),
                      "subject": ", ".join(names.get(x, x) for x in s["subject"]) or s["framing"], "media_asset_id": None, "beat_id": s["beat_id"],
                      "purpose": s["purpose"]})
    return {"schema": "filmcraft.shot_plan.v1", "project_id": plan["project_id"], "scene_id": plan["scene_id"], "fps": fps, "shots": shots, "total_frames": total}


def _common(ctx, kind, plan, scene_an):
    return {"manifest_id": f"{kind}-{ctx['run_id']}", "exported_at": ctx["exported_at"],
            "source": {"application": APPLICATION, "version": ctx["app_version"], "run_id": ctx["run_id"], "experiment_id": ctx["experiment_id"],
                       "source_status": ctx.get("source_status", "current")},
            "approval": ctx["approval"], "hashes": {"scene_hash": scene_an["scene_hash"], "plan_hash": plan["analysis"]["plan_hash"],
                                                    "screenplay_hash": plan["source"]["screenplay_hash"]},
            "overrides": ctx.get("overrides", []), "provenance": {"ai_used": False, "source": "local-manual"}, "import_policy": IMPORT_POLICY}


def scene_manifest(ctx, plan, screenplay):
    scene = next(s for s in screenplay["scenes"] if s["id"] == plan["scene_id"])
    san = next(s for s in screenplay["analysis"]["scenes"] if s["scene_id"] == plan["scene_id"])
    timings = {e["id"]: e for e in san["elements"]}
    m = {"schema": "filmcraft.scene_manifest.v1", **_common(ctx, "scm", plan, san),
         "project": {k: v for k, v in screenplay["project"].items()},
         "scene": {"id": scene["id"], "slugline": scene["slugline"], "heading": scene["heading"], "synopsis": scene.get("synopsis", ""),
                   "objective": scene.get("objective", ""), "conflict": scene.get("conflict", ""), "turning_point": scene.get("turning_point", ""),
                   "outcome": scene.get("outcome", ""), "fps": san["fps"], "duration_frames": san["duration_frames"], "estimated_seconds": san["estimated_seconds"],
                   "pacing": san["pacing"], "props": scene.get("props", [])},
         "characters": [c for c in screenplay["characters"] if c["id"] in scene["characters"]],
         "elements": [{**e, "start_seconds": timings[e["id"]]["start_seconds"], "duration_seconds": timings[e["id"]]["duration_seconds"]} for e in scene["elements"]],
         "beats": scene.get("beats", []), "blocking": plan["blocking"], "stage": plan["stage"], "interpretation": plan["interpretation"]}
    m["manifest_sha256"] = sha256(m)
    return m


def shot_manifest(ctx, plan, screenplay):
    san = next(s for s in screenplay["analysis"]["scenes"] if s["scene_id"] == plan["scene_id"])
    names = {c["id"]: c["name"] for c in screenplay["characters"]}
    keep = [s for s in plan["shots"] if s["status"] == "approved" or (s["status"] == "proposed" and "allow_pending" in ctx.get("overrides", []))]
    fps, t_frames, shots = plan["fps"], 0, []
    for n, s in enumerate(keep, 1):
        frames = max(1, round(s["duration_seconds"] * fps))
        shots.append({"shot_id": s["shot_id"], "order": n, "beat_id": s["beat_id"], "covers": s.get("covers", []), "purpose": s["purpose"], "purpose_note": s["purpose_note"],
                      "size": s["size"], "angle": s["angle"], "movement": s["movement"], "framing": s["framing"], "camera_side": s["camera_side"],
                      "lens_mm": s.get("lens_mm"), "subjects": s["subject"], "subject_names": [names.get(x, x) for x in s["subject"]],
                      "transition_in": s.get("transition_in", "cut"), "start_frame": t_frames, "duration_frames": frames, "status": s["status"],
                      "previz": s["previz"], "storyboard": s["storyboard"]})
        t_frames += frames
    a = plan["analysis"]
    m = {"schema": "filmcraft.shot_manifest.v1", **_common(ctx, "shm", plan, san), "project_id": plan["project_id"], "scene_id": plan["scene_id"], "fps": fps,
         "approach": plan["approach"], "shots": shots,
         "excluded": {"rejected": [s["shot_id"] for s in plan["shots"] if s["status"] == "rejected"],
                      "needs_review": [s["shot_id"] for s in plan["shots"] if s["status"] == "needs_review"],
                      "pending": [s["shot_id"] for s in plan["shots"] if s["status"] == "proposed" and s["shot_id"] not in {x["shot_id"] for x in shots}]},
         "totals": {"shots": len(shots), "frames": t_frames, "seconds": round(t_frames / fps, 2)},
         "continuity": {"errors": a["readiness"]["errors"], "warnings": a["readiness"]["warnings"], "issues": a["issues"]},
         "interpretation": plan["interpretation"]}
    m["manifest_sha256"] = sha256(m)
    return m
