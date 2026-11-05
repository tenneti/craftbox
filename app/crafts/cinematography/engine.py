"""Explicit camera planning. It does not claim to generate imagery."""


def run(payload: dict) -> dict:
    scene = payload.get("scene", {})
    if scene.get("schema") != "filmcraft.scene.v1":
        raise ValueError("scene must be filmcraft.scene.v1")
    shots = payload.get("shots", [])
    if not shots or not isinstance(shots, list):
        raise ValueError("shots must be a nonempty list")
    shot_ids = set()
    normalized = []
    total = 0
    for s in shots:
        shot_id = str(s.get("shot_id", "")).strip()
        duration = int(s.get("duration_frames", 0))
        lens = float(s.get("lens_mm", 0))
        if not shot_id or shot_id in shot_ids or not (1 <= duration <= 100000) or not (1 <= lens <= 2000):
            raise ValueError("each shot requires unique shot_id, positive duration_frames and plausible lens_mm")
        shot_ids.add(shot_id)
        normalized.append({
            "shot_id": shot_id, "scene_id": scene["scene_id"],
            "shot_type": str(s.get("shot_type", "MS")), "duration_frames": duration,
            "lens_mm": lens, "camera_movement": str(s.get("camera_movement", "static")),
            "subject": str(s.get("subject", "")), "media_asset_id": s.get("media_asset_id"),
        })
        total += duration
    warnings = []
    if total > int(scene["duration_frames"]):
        warnings.append("planned shot duration exceeds the scene estimate")
    if any(s["media_asset_id"] is None for s in normalized):
        warnings.append("one or more shots have no media asset; timeline will be offline placeholders")
    return {"artifact_type": "shot_plan", "data": {
        "schema": "filmcraft.shot_plan.v1", "project_id": scene["project_id"],
        "scene_id": scene["scene_id"], "fps": scene["fps"], "shots": normalized,
        "total_frames": total,
    }, "warnings": warnings}
