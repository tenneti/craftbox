# Choreography

**Group:** Visual Production

**Purpose:** Movement beats and timed blocking for songs and scenes

**MVP:** Map choreography and blocking to frame ranges, tempos and music cues.

**Dreambox target:** Scene Maker / Music Lab

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
