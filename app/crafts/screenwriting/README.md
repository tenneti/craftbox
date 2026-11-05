# Screenwriting

**Group:** Story & Direction

**Purpose:** Structure scenes, actions, dialogue and story beats

**MVP:** Import a manually authored scene; validate scene metadata and export a consistent scene contract.

**Dreambox target:** Screenwright / Scene Maker

**Status:** pilot

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
