# Junior Artist Agency

**Group:** Story & Direction

**Purpose:** Extras requirements, resource sourcing and approval workflow

**MVP:** Manage crowd requirements and releases; do not simulate actual hiring automatically.

**Dreambox target:** Production Board

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
