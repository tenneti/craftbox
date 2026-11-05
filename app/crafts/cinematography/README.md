# Cinematography

**Group:** Visual Production

**Purpose:** Shot composition, lens and camera movement plan

**MVP:** Accept a scene and manually specified shots; output a validated shot plan.

**Dreambox target:** Previz / Scene Maker

**Status:** pilot

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
