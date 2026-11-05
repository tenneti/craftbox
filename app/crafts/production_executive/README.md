# Production Executive

**Group:** Production Operations

**Purpose:** Scheduling, cost forecasts and production dependencies

**MVP:** Estimate costs, track resources and build production milestones.

**Dreambox target:** Production Board

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
