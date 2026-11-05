# Technical Unit

**Group:** Production Operations

**Purpose:** Transcoding, rendering, media inspection, proxy and technical QC

**MVP:** Manage media profiles, render jobs and deterministic validation.

**Dreambox target:** Render Pipeline / QC

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
