# Production Assistants

**Group:** Production Operations

**Purpose:** Shot checklists, call sheets and continuity handoffs

**MVP:** Track shoot readiness, dependencies and shot status.

**Dreambox target:** Production Board

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
