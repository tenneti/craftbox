# Craft development standards

Every craft must eventually satisfy all seven. CB0 provides the shared infrastructure; each craft proves them individually. Status of the three pilots is in the CB0 report.

| # | Requirement | How Craftbox supports it | Per-craft obligation |
|---|---|---|---|
| 1 | Independent development and execution | One folder per craft (`app/crafts/<id>/`): `manifest.json`, `engine.py`, `fixture.json`, `input.schema.json`. Engines only import the standard library. | No imports from other crafts or Dreambox. Handoffs happen through versioned artifacts. |
| 2 | Manual inputs without AI | `ai_default: false` in every manifest; `provenance.ai_used` recorded; CB0 makes no network calls. | The manual path must be complete and useful on its own. |
| 3 | Optional AI-assisted workflows | None in CB0. | AI must sit behind a switchable adapter, default off, never silently rewriting approved material, with provider/model/cost recorded in provenance. |
| 4 | Repeatable experiments with saved parameters | Immutable experiment input, `input_hash`, deterministic `output_sha256`, *Verify*, reproducibility indicator. | Engines must be deterministic for a given input (or record seeds/model versions as parameters). |
| 5 | Output previews and quality evaluation | Output JSON view, warnings, A/B diff. | Add a craft-specific preview and a documented human QC rubric (roadmap §8); passing unit tests is not a substitute. |
| 6 | User approval before integration or publication | `draft → review → approved/rejected → exported`, reviewer + note, append-only event log. No auto-import. | None; do not bypass the lifecycle. |
| 7 | Reusable exports compatible with Dreambox | `filmcraft.export_manifest.v1` with artifact, hashes, approval, media references and import policy. | Declare an `output_schema`; keep IDs (`project_id`, `scene_id`, `shot_id`, …) stable across handoffs. |

## Adding a craft (checklist)

1. Replace the placeholder `engine.py`; keep `run(payload) -> {"artifact_type", "data", "warnings"}`.
2. Add `fixture.json` and `input.schema.json` (`$id: filmcraft.input.<craft>.v1`); add the output schema to `app/schemas/` if it is a new artifact type.
3. In `manifest.json` set `status: "pilot"`, `input_schema`, `output_schema`.
4. Add unit tests (valid, invalid, determinism), an experiment lifecycle test and, if it has UI-specific behavior, a browser test.
5. Raise the maturity level only when the roadmap's gate evidence exists (`planned → prototype → pilot → validated → dreambox-ready → integrated`).

## Rules that must not regress

- Never rename schema IDs, craft IDs or routes without a migration plan.
- Never delete or rewrite run history; add new migrations instead of editing old ones.
- Never store API keys in the database or logs.
- Planned crafts must keep failing loudly (HTTP 409).
