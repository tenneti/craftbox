# Still Photography

**Group:** Production Operations

**Purpose:** Continuity stills, frame grabs and production look book

**MVP:** Capture approved visual references and record scene/shot provenance.

**Dreambox target:** Asset Library / Image Extractor

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
