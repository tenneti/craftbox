# Studio Workers / Set Fabrication

**Group:** Production Operations

**Purpose:** Digital set-build instructions, fabrication tasks and assets

**MVP:** Manage virtual set assembly tasks and real-world build references.

**Dreambox target:** Asset Library / Scene Maker

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
