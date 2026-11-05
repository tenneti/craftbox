# Makeup and Hair

**Group:** Visual Production

**Purpose:** Character appearance continuity per scene and time of day

**MVP:** Maintain makeup look, change events and approval reference images.

**Dreambox target:** Character Library

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
