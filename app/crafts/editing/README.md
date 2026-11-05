# Editing

**Group:** Post-production

**Purpose:** Edit decision list, rough cut timeline and timing QC

**MVP:** Make sequential timeline metadata from approved shots; media remains externally referenced.

**Dreambox target:** Dreambox Editor

**Status:** pilot

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
