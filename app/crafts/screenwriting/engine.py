"""Screenwriting craft. Not an AI screenwriter.

Two modes, chosen by the payload: a manual scene card (CB0, ``filmcraft.scene.v1`` output) or a whole
screenplay document for the Screenwriting Lab (``filmcraft.screenplay.v1`` in and out).
"""
from app.crafts.screenwriting import screenplay


def run(payload: dict) -> dict:
    if isinstance(payload, dict) and payload.get("schema") == screenplay.SCHEMA:
        return screenplay.run(payload)
    return _run_scene_card(payload)


def _run_scene_card(payload: dict) -> dict:
    project_id = str(payload.get("project_id", "")).strip()
    scene_id = str(payload.get("scene_id", "")).strip()
    slugline = str(payload.get("slugline", "")).strip()
    action = str(payload.get("action", "")).strip()
    if not (project_id and scene_id and slugline and action):
        raise ValueError("project_id, scene_id, slugline and action are required")
    if not slugline.upper().startswith(("INT.", "EXT.", "INT/EXT.", "EXT/INT.")):
        raise ValueError("slugline must start with INT., EXT., INT/EXT. or EXT/INT.")
    fps = int(payload.get("fps", 24))
    duration_seconds = float(payload.get("estimated_seconds", 30))
    if not 1 <= fps <= 120 or not 1 <= duration_seconds <= 3600:
        raise ValueError("invalid fps or estimated_seconds")
    lines = payload.get("dialogue", [])
    if not isinstance(lines, list):
        raise ValueError("dialogue must be a list")
    speakers = {str(c.get("id", "")) for c in payload.get("characters", [])}
    for line in lines:
        if line.get("speaker_id") not in speakers:
            raise ValueError("dialogue speaker_id must appear in characters")
    data = {
        "schema": "filmcraft.scene.v1", "project_id": project_id, "scene_id": scene_id,
        "slugline": slugline, "action": action, "characters": payload.get("characters", []),
        "dialogue": lines, "synopsis": str(payload.get("synopsis", "")),
        "fps": fps, "duration_frames": round(duration_seconds * fps),
    }
    return {"artifact_type": "scene", "data": data, "warnings": []}
