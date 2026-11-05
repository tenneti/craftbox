# Art Direction

**Group:** Visual Production

**Purpose:** Set, prop and location bible with per-scene continuity

**MVP:** Associate backgrounds, props, set palette and period with each scene.

**Dreambox target:** Asset Library / Scene Maker

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
