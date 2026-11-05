# Transport / Cinema Drivers

**Group:** Production Operations

**Purpose:** Travel logistics and equipment movement plans

**MVP:** Optional logistics for physical shoots; deprioritize for wholly virtual films.

**Dreambox target:** Production Board

**Status:** planned

## Craft contract

Implement `run(payload: dict) -> dict` in `engine.py`. It must return a deterministic `artifact_type`, `data`, and `warnings`. No Dreambox imports or AI calls in the initial milestone. Add fixtures and unit tests before changing `status` to `pilot`.
