# Dubbing / ADR

**Group:** Post-production

**Purpose:** Dialogue replacement cue sheets, takes and sync review

**MVP:** Produce ADR markers and verify dialogue timing without cloning voices by default.

**Dreambox target:** Comedy / Lip-sync / Scene Maker

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
