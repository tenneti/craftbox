# Casting

**Group:** Story & Direction

**Purpose:** Character bible, performer references, permissions and look tests

**MVP:** Maintain a versioned character casting bible and approved performance/likeness assets.

**Dreambox target:** Character Library

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
