# Lighting / Light Technicians

**Group:** Visual Production

**Purpose:** Lighting map, sources, intensity and mood references

**MVP:** Editable lighting plans for one scene, laid on the art treatment's set layout and the director's blocking and cameras, with shot adjustments, continuity checks, treatment comparison and approved exports.

**Dreambox target:** Previz / Scene Maker

**Status:** pilot (CB2B)

## Craft contract

`engine.run(payload)` has two modes chosen by the payload: a lighting plan (`filmcraft.lighting_plan.v1`) and a reusable setup (`filmcraft.lighting_setup.v1`).
Deterministic, no AI, no rendering, no imports from other crafts. Levels and shadows are planning estimates, not a physical simulation.
Modules: `plan.py` (presets, normalising), `geo.py` (geometry), `analysis.py` (checks, measures, readings), `impact.py` (upstream change, rebase), `exports.py`.
See `docs/cb2b-implementation-report.md`.
