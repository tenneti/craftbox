# Stunt Direction

**Group:** Visual Production

**Purpose:** Action beats, safe previsualization and specialist review gates

**MVP:** Create non-executable action blocking and review checklists; real stunts require qualified supervision.

**Dreambox target:** Previz / Scene Maker

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
