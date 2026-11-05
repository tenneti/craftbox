"""Stable, local-first craft runner. Dreambox code does not belong here."""
import importlib
import json
from pathlib import Path
from uuid import uuid4

CRAFT_DIR = Path(__file__).parent / "crafts"
ENGINE_VERSION = "0.1.0"


def all_crafts():
    return sorted(
        (json.loads(p.read_text(encoding="utf-8")) for p in CRAFT_DIR.glob("*/manifest.json")),
        key=lambda m: (m["group"], m["name"]),
    )


def get_craft(craft_id):
    if not isinstance(craft_id, str) or not craft_id.replace("_", "").isalnum():
        raise KeyError("invalid craft ID")
    file = CRAFT_DIR / craft_id / "manifest.json"
    if not file.is_file():
        raise KeyError("unknown craft")
    return json.loads(file.read_text(encoding="utf-8"))


def get_fixture(craft_id, name=None):
    get_craft(craft_id)
    if name is not None and not name.isalnum():
        raise KeyError("invalid fixture name")
    f = CRAFT_DIR / craft_id / (f"fixture.{name}.json" if name else "fixture.json")
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def execute(craft_id, payload):
    manifest = get_craft(craft_id)
    if manifest["status"] != "pilot":
        raise NotImplementedError(f"{craft_id}: pilot engine not yet implemented")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    engine = importlib.import_module(f"app.crafts.{craft_id}.engine")
    try:
        result = engine.run(payload)
    except (KeyError, AttributeError) as exc:
        # Malformed payload shape inside an engine is an input error, not a missing resource.
        raise ValueError(f"malformed input: {exc!r}") from exc
    if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
        raise RuntimeError("engine returned invalid result contract")
    return {
        "contract_version": "1.0", "run_id": str(uuid4()), "craft_id": craft_id,
        "engine_version": ENGINE_VERSION, "approval_status": "draft",
        "artifact_type": result["artifact_type"], "artifact": result["data"],
        "warnings": result.get("warnings", []),
        "provenance": {"source": "local-manual", "ai_used": False},
    }
