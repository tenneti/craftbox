"""Build an offline edit plan, not a rendered video."""


def run(payload: dict) -> dict:
    plan = payload.get("shot_plan", {})
    if plan.get("schema") != "filmcraft.shot_plan.v1":
        raise ValueError("shot_plan must be filmcraft.shot_plan.v1")
    fps = int(plan["fps"])
    start = 0
    clips = []
    for s in plan["shots"]:
        frames = int(s["duration_frames"])
        if frames <= 0:
            raise ValueError("shot durations must be positive")
        clips.append({"shot_id": s["shot_id"], "start_frame": start, "duration_frames": frames,
                      "media_asset_id": s.get("media_asset_id"), "scene_id": plan["scene_id"]})
        start += frames
    warnings = ["offline clips present; bind approved media assets before rendering"] if any(c["media_asset_id"] is None for c in clips) else []
    return {"artifact_type": "edit_plan", "data": {"schema": "filmcraft.edit_plan.v1",
        "project_id": plan["project_id"], "scene_id": plan["scene_id"], "fps": fps,
        "clips": clips, "total_frames": start, "total_seconds": round(start/fps, 3)}, "warnings": warnings}
