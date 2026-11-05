# Craftbox — standalone development and Dreambox integration roadmap

**Version:** 1.1 (Craftbox rename) · **Date:** 2026-11-01 · **Audience:** Dreambox / Ideator development with Claude Code or Codex

## 0. Decision

Build **Craftbox** as a separate local-first project, **not** 23 new Dreambox menu items and not 23 microservices. Register each of the traditional 23 non-music film crafts as an independently testable **craft plugin**; develop reusable engines in shared foundations and expose stable JSON artifact contracts. Promote each plugin into Dreambox only after passing automated, manual and integration tests. Use the existing Dreambox Scene Maker, Previz, Asset Library/Importer, Editor, Creative Multiplier, rendering engines, comedy/lip-sync workflows and upcoming Ideator Music Lab rather than duplicating them.

**Naming and compatibility (Craftbox rename):** Craftbox is the product, repository, UI and documentation name. The recommended working directory is `craftbox-starter` (later `craftbox`). The first milestone is now called **CB0** (equivalent to the earlier FL0), with CB1–CB5 corresponding to FL1–FL5. Craft IDs, API endpoints, port 8099, module imports, the Dreambox integration design and the 23-craft scope remain unchanged. The original pilot JSON schema IDs (`filmcraft.scene.v1`, `filmcraft.shot_plan.v1`, `filmcraft.edit_plan.v1`) are **retained intentionally** for compatibility with existing fixtures, tests and generated outputs. Do **not** blindly replace `filmcraft.*` with `craftbox.*`: introduce any new namespace using a declared schema version, migration and Dreambox importer support. There is no requirement to rename schema IDs just because the application name changed.

**Scope note:** In the Indian film industry, the traditional “24 crafts” include physical occupations and logistical jobs; the classification is not universal. This roadmap follows a common 24-item list with *music direction* excluded. Digital tools cannot replace a driver, makeup artist, performer, safety supervisor, or production crew. For those roles, build planning, continuity, resource and reference workflows. `production_support` is an inclusive name for the historically gendered “production women” craft.

**Starter status, as delivered:** 23 manifests/folders, three real non-AI metadata pilot engines (`screenwriting`, `cinematography`, `editing`) and 20 explicit `NotImplementedError` placeholders. It is an architecture experiment, **not** a production filmmaking suite. Automated tests cover the small starter. No real video/audio generation, GPU inference, orchestration, or Dreambox connectivity has been implemented.

## 1. Product design and navigation

A standalone Windows-hosted browser application, defaulting to `http://127.0.0.1:8099`, with:

- **Dashboard:** all 23 crafts, group, readiness state, recent experiment outcomes, target Dreambox workflow.
- **Craft Workspace:** input form or JSON input; fixture chooser; manual controls; live preview when an engine supports it; compare A/B variants; Run; inspect output; Export JSON/media.
- **Experiment Runs:** input snapshot, versioned engine/config, artifacts, metrics, costs, provider, provenance and human approval state.
- **Asset Browser:** references to licensed/user-owned media; independent asset IDs, checksums, provenance, rights/consent and character IDs. Do not directly reuse Dreambox's asset directories or database.
- **Continuity Center:** shared character/location/costume/prop/lighting/music cue continuity checks across crafts.
- **Promotion Center:** `draft → review → approved → exported → imported → superseded`. Explicit manual approval is mandatory; automatic Dreambox publication is prohibited.
- **Studio Settings:** local model and optional provider settings, concurrency=1 by default, budgets/quotas, dependency health, preset definitions, export mappings, schema versions.

Start with a manual JSON workflow (in the included starter), then create craft-specific UI once a pilot's real workflows justify it. Do not create a generic “JSON-only” UI as the final product.

## 2. Mapping the 23 crafts to useful digital modules

Group counts match the starter UI: Story & Direction (5), Visual Production (7), Post-production (4), Production Operations (7). Priority `P0` = develop next; `P1` = after first integrated vertical slice; `P2` = later or real-production-only.

| # | Craft ID | Traditional craft | Useful lab experiment and tangible output | Dreambox integration target | Priority |
|---|---|---|---|---|---|
| 1 | `direction` | Direction | Scene intent, blocking, emotional beats, shot decisions, take-review notes, approval cards | Scene Maker / Director | P0 |
| 2 | `screenwriting` | Script writing | Screenplay import/editor, scene IDs, story beats, dialogue, pacing and scene change analysis; `.scene.json` | Screenwright / Scene Maker | P0 (pilot) |
| 3 | `casting` | Casting | Character bible, role/performer reference, consent, reference-shot tests, character identity/version lock | Character Library | P0 |
| 4 | `junior_artists` | Junior artists | Background role registry, crowd placements, scene continuity, privacy/likeness controls | Character Library / Scene Maker | P1 |
| 5 | `junior_artist_agent` | Junior artist agency | Crowd requirements and sourcing/permissions matrix; does not hire people | Production Board | P2 |
| 6 | `cinematography` | Cinematography | Coverage and lens planner, camera placements, shot list, framing storyboard; `.shot_plan.json` | Previz / Scene Maker | P0 (pilot) |
| 7 | `art_direction` | Art direction | Set bible, prop/architecture palettes, virtual set layout and continuity | Asset Library / Scene Maker | P0 |
| 8 | `stunts` | Stunt direction | Safe action beats, shot-safe blocking and specialist signoff checklist | Previz / Scene Maker | P1 |
| 9 | `choreography` | Choreography | Beat-grid movement/blocking cues synchronized to song/MIDI or score | Scene Maker / Music Lab | P1 |
| 10 | `lighting` | Lighting/light technicians | Deterministic 2D/3D rig presets, motivated light sources, look references, continuity rules | Previz | P0 |
| 11 | `makeup` | Makeup/hair | Character appearance states and transition/continuity matrix | Character Library | P1 |
| 12 | `costume` | Costume | Wardrobe bible, approved outfit versions, per-scene wardrobe continuity | Character Library / Asset Library | P0 |
| 13 | `editing` | Editing | Shot-to-rough-cut planner, shot order and pacing, offline timeline/OTIO export | Dreambox Editor | P0 (pilot) |
| 14 | `dubbing` | Dubbing | ADR cue sheet, dialogue timeline, manual takes, sync/phoneme QC; optional approved TTS | Comedy/lip-sync / Scene Maker | P0 |
| 15 | `audiography` | Audiography | Sound layers, ambience/Foley cue graph, dialog/music/SFX balance previews | Music Lab / Audio Engine | P0 |
| 16 | `publicity` | Publicity design | Poster and thumbnail variations, trailer excerpt map, deliverable packages | Social Features / Creative Multiplier | P1 |
| 17 | `still_photography` | Still photography | Frame extractor, approved continuity stills, contact sheets, metadata | Asset Library / Image Extractor | P1 |
| 18 | `production_executive` | Production executive | Time, cost, credit/provider consumption, production constraints, schedule | Production Board | P0 |
| 19 | `studio_workers` | Studio workers | Digital set-build task cards, asset requests, scene assembly readiness | Asset Library / Scene Maker | P2 |
| 20 | `production_assistants` | Production assistants | Shot checklist, call sheets, dependency and continuity signoff | Production Board | P1 |
| 21 | `cinema_drivers` | Cinema drivers | Physical-shoot transport schedule and gear logistics; optional for digital films | Production Board | P2 |
| 22 | `technical_unit` | Technical unit | Proxy/transcode jobs, render manifests, media QC, audio/video spec checks | Render Pipeline / QC | P0 |
| 23 | `production_support` | Historical production women/set support | Set readiness, safety, welfare and support operations, with gender-neutral roles | Production Board | P2 |

The **music craft** remains Ideator + Music Lab (songs, MIDI, raga-aware score, BGM cues and sync). It participates as an external integration, not a 24th plugin in this repository.

## 3. Architectural boundaries

```
Standalone Craftbox (own repo, own venv, own process)
  Browser UI + API (localhost:8099)
     ├── Craft Registry (23 manifest.json files)
     ├── Craft Runner + Review/Experiment Store
     ├── Common Canonical Schema (Project/Scene/Shot/Character/Asset/Cue/Timeline)
     ├── Continuity & QC Engine
     ├── Optional AI Provider Adapters (text-only first, switchable off)
     ├── Optional Rendering Adapters (FFmpeg / Blender / audio)
     └── Craft Plugins (one folder, fixture and test suite per craft)
                      │
                 Export package
                versioned JSON + media references + checksums
                      │
           Dreambox-owned Import Adapter
                      │
         Existing Dreambox features and asset storage
```

**No circular imports.** No `import dreambox` from Craftbox. No direct shared SQLite database, no shared mutable asset folder, and no unversioned pickle serialization. Allow JSON export/import as the first integration method; optional authenticated HTTP bridge later. Dreambox may own adapters into *its* existing Django app without requiring Craftbox's FastAPI runtime in production. Keep one local port and avoid concurrent GPU jobs by default.

Suggested module contract (stable across all crafts):

```python
# Each app/crafts/<craft_id>/engine.py
# Pure metadata engines run synchronously. Heavy generators later use queued jobs.
def run(payload: dict) -> dict:
    return {
        "artifact_type": "shot_plan",  # craft-specific
        "data": {"schema": "filmcraft.shot_plan.v1", "project_id": "...", "scene_id": "..."},
        "warnings": [],
    }
```

Outer engine envelope should include `contract_version`, `craft_id`, `engine_version`, `run_id`, `approval_status`, `artifact_type`, `artifact`, `warnings` and `provenance`. The starter does this for the three pilots. In subsequent milestones add `schema_version`, normalized `settings`, `input_hash`, `output_sha256`, `license`, `rights`, `source_asset_ids`, `duration_frames`, `fps_num/fps_den`, `timebase`, `model_name`, `provider`, `estimated_cost`, `actual_cost`, `created_at`, `run_status`, `reviewer` and `approval_timestamp`.

Canonical shared identifiers: `project_id`, `sequence_id`, `scene_id`, `shot_id`, `character_id`, `location_id`, `asset_id`, `cue_id`, `timeline_id`. **Do not use mutable names as identifiers.** Every module must preserve IDs through handoffs. Define a scene's script order separately from shooting order and timeline order. For a long film, support multi-sequence scenes and a film-level timeline, rather than treating one music video as the entire project.

Reference data schemas: `filmcraft.project.v1`, `filmcraft.scene.v1`, `filmcraft.shot_plan.v1`, `filmcraft.look.v1`, `filmcraft.asset_reference.v1`, `filmcraft.character_state.v1`, `filmcraft.music_cue.v1`, `filmcraft.sound_cue.v1`, `filmcraft.edit_plan.v1`, `filmcraft.review.v1`, `filmcraft.export_manifest.v1`. Document JSON Schema and migrations before first Dreambox import; the starter's lightweight objects are prototypes, not the final schemas.

### Approval/export rules

1. Generate or manually create a proposal, never overwrite its source.
2. Record inputs, source rights/consent, engine configuration and tool/provider version.
3. Run schema tests + quality checks + preview; show blockers and warnings separately.
4. User explicitly approves a named version; export signed/hashed manifest with referenced assets.
5. Dreambox import adapter validates schemas, IDs, allowed media roots, files and checksums; imports into a *staging* project namespace.
6. User confirms merge/replace; adapter performs an idempotent write with rollback and provenance.
7. Any failure leaves the original Dreambox project unchanged. Preserve prior imported versions.

## 4. Reuse current Dreambox capabilities

Do a **read-only code audit** before new craft implementation and record: exact Dreambox feature route, underlying service/module, schema, artifact paths, tests, ownership and integration gaps. In particular audit Scene Maker, Previz, Screenwright, Character/Persona handling, Asset Importer M5, Creative Multiplier/Blend Lab, current editor timeline, lip-sync/comedy C1, existing rendering pipelines, Music Lab/Ideator proposals and whichever AI provider adapters actually exist. Do not assume a feature is absent because its UI is hidden. Reuse proven engines instead of cloning them. The lab may prototype a new adapter or behavior while Dreambox retains its engine.

## 5. Phased roadmap with go/no-go gates

### CB0 — Foundation (first milestone)

- Establish separate Git repository, Python environment, standalone UI, health endpoint, 23 manifests and pure module runner.
- Keep three pilot contracts running: manually written scene → camera plan → rough-cut metadata.
- Add JSON Schema files, fixture validation, `ruff`, automated CI, 23-module discoverability test.
- Save runs in local SQLite (metadata) with content-addressed local asset copy/reference store; never store API keys in this DB.
- Add immutable run log, A/B comparison and explicit approval workflow.
- Add Windows PowerShell setup and environment dependency checker.

**Gate CB0:** 23 discoverable entries; no false “implemented” entries; three pilots run; broken inputs fail clearly; no Dreambox code imported; no network needed; Windows browser preview and tests pass.

### CB1 — Director + Story handoff

- Improve screenwriting import (plain text, Fountain where feasible, manually authored screenplay) and preserve scene/character IDs.
- Add `direction` craft: story goal, emotional arc, shot intentions, blocking and coverage notes.
- User-editable scene ordering, alternate takes, constraints for no-woman-on-screen or multiple-character scenes, chronology and location policies.
- Link camera shot plan to director beats. Add script-vs-shot coverage gap checker.

**Gate CB1:** Make two 30–60-second sample scenes; revise scene order without losing assets/shot links; import/export round-trip preserves IDs; intentional continuity errors are flagged.

### CB2 — Visual continuity lab

- Add `art_direction`, `lighting`, `costume`, `casting` and basic appearance consistency checks.
- Scene mood palette, look-bible snapshot, character attire across scenes, lighting continuity and reference collection.
- Reuse Previz concepts where possible, but keep local deterministic SVG/2D presets first. Add Blender headless tests only when necessary.
- Ensure no real people or actor likeness without permissions; character reference asset licensing and generated-image provenance are explicit.

**Gate CB2:** Two scenes with same character, different times/daylighting; a deliberately changed outfit or prop is caught; a legitimately approved change is not flagged.

### CB3 — Editing, ADR and sound lab

- Expand offline edit plan to frame-accurate movie sequences, source trims, transitions, subtitles and multiple scene tracks.
- Consider **OpenTimelineIO** for editorial interchange and **FFmpeg** for media validation/rendering; OTIO references footage, it does not embed media.
- Add `dubbing` with timecoded dialogue cue sheets and user-supplied or authorized voices; sync checks and editorial approval.
- Add `audiography` with diegetic ambience, Foley and transitions, distinct from music. Support stem alignment and headroom/mix preview.
- Link Ideator raga/MIDI-derived BGM cues with story emotion, tempo maps, leitmotifs, scene duration and edit revisions. A revised cut must invalidate or recompute downstream cue alignment rather than silently drift.

**Gate CB3:** Export one 60–90-second clip assembled from owned/placeholder media; soundtrack cues align to scene/timecode; missing media is detected before render; all audio sources and rights are traceable.

### CB4 — Operations, render QA and production-scale features

- Add `technical_unit` as a robust proxy/media QC and render manifest service; `production_executive` and `production_assistants` to calculate dependencies, schedule, duration and credit spend.
- Introduce job queue for CPU/remote operations; local GPU concurrency limit 1, with per-job cancellation, checkpointing and retry.
- Add `stunts`, `choreography`, `still_photography`, `junior_artists`, `publicity`; develop logistics-only crafts only when needed for actual shoots.
- Add scene/sequence scale tests (10 scenes → 100 scenes → feature-film data load), project backups, relinking and partial renders.

**Gate CB4:** A 10-minute sequence can be reopened, validated, rendered in chunks, retried and reassembled without ID drift or missing provenance; cloud/provider spending caps are enforced.

### CB5 — Selective Dreambox integration

- Choose **one** high-value module: `direction` or `cinematography` into Scene Maker, or `editing` into the existing Editor. Do not integrate all modules at once.
- Implement a Dreambox-owned version-aware import adapter, a dry-run preview, staging mode, conflict resolution, undo and feature flag.
- Run a regression and compare old behavior with the new craft. Never mutate existing Scene Maker/Editor data until import is explicitly confirmed.
- Repeat promotion craft-by-craft, reusing the same adapter protocol.

**Gate CB5:** Approved craft artifact imports successfully; source is unmodified, ID mapping is recorded; importing twice is idempotent; schema mismatch refuses safely; rollback works; Dreambox regression passes.

## 6. The first cinematic benchmark

Create one **90-second romantic sequence** with three scenes: a solitary traveler on a platform, train interior with landscape transition, and arrival with a subtle emotional reveal. Use existing approved character reference and licensed backgrounds. Reuse the same scenario for every craft experiment so quality differences are comparable. Optionally use a second **30-second science-fiction** scene to test lighting, set and creature constraints, but do not add complexity until the first benchmark is useful.

Record: `scene_id` / `shot_id` preservation, coverage completeness, manual corrections, time from input to usable result, visual/story continuity error count, audio drift in frames, duration deviation, provider cost, GPU peak memory (where applicable), retry success, acceptance decision, rollback outcome and number of Dreambox changes required. Keep golden input/output fixtures and before/after previews. A test suite passing does **not** substitute for watching and listening to generated results.

## 7. Libraries and tool candidates (optional, not prerequisites)

| Need | Candidate | Why/when |
|---|---|---|
| Backend and contracts | FastAPI, Pydantic/JSON Schema, pytest/unittest | Small standalone API; validate each craft independently |
| Media cutting/rendering | FFmpeg / ffprobe | Proven clip/audio operations and technical checks |
| Editorial interchange | OpenTimelineIO | Timeline structure, markers, clips and references across editors; not a video renderer |
| Scene boundary analysis | PySceneDetect | Evaluate/inspect existing clips and detect cuts, not creative editing |
| Geometry and virtual sets | Blender headless Python | Later deterministic previz, lighting tests and 3D renders; use only when 2D is insufficient |
| Color management | OpenColorIO | Later consistent views/transforms across image/video pipelines |
| Sound processing | librosa, soundfile, numpy/scipy or DAW-adjacent tools | Cue detection, waveform and level validation; do not confuse with full professional mix |
| Storyboard interfaces | Open Shot Designer, OpenFrame (as references) | Study shot-list, board and scheduling UX; check repo licenses and dependencies before copying code |
| AI text assistance | ChatGPT API / Gemini / Venice via swappable adapters | Optional creative alternatives: dialogue, coverage, continuity suggestions; default off and never silently rewrite approved material |
| Image/video providers | Existing Dreambox-approved providers | Use only for media generation when required; avoid duplicating integrations |

The initial three pilots require none of the heavier optional tools, GPU models or AI credits. A separate craft interface is useful even if its eventual engine is a library or provider adapter rather than newly invented code.

## 8. Test levels per craft

- **Unit:** invalid/missing fields, stable deterministic output for fixtures, frame/time arithmetic, malformed inputs, optional AI disabled behavior.
- **Contract:** required envelope fields, schema version and cross-craft ID stability; migration and unknown-version rejection.
- **Golden fixture:** saved input, expected artifact hash (excluding nondeterministic run IDs), snapshot comparison with meaningful semantic checks.
- **UI browser:** route, form load, validation, error handling, export and approval interactions; browser load-race tests to avoid flaky timeouts.
- **Integration:** export/import roundtrip; duplicate import; revoked consent; media relinking; undo; no source file overwrites.
- **Visual/audio human QC:** documented rubric for readability, pacing, shot variety, face/wardrobe/prop consistency, sound balance, sync and believable motion.
- **Safety/security:** path traversal, payload size limits, provider credential leakage, prompt injection in imported documents, rights/consent and person-likeness checks.
- **Performance:** CPU/RAM/VRAM/disk/remote cost, job duration, cancellation, retry and concurrent resource controls.

Levels: `planned` → `prototype` → `pilot` → `validated` → `dreambox-ready` → `integrated`. Don't promote on unit-test count alone; manual visual/audio approval is separately recorded.

## 9. Near-term order of implementation

1. Finish CB0 improvements and audit Dreambox's overlapping modules (read-only).
2. Implement `direction` with a real browser form and shot-intention handoff, then integrate a simple review workflow.
3. Add `art_direction` plus cross-scene prop/look continuity, then `lighting` and `costume` with deterministic presets.
4. Evolve `cinematography` from JSON into visual shot-planning UI and use it with Scene Maker/Previz exports.
5. Expand `editing`, then `dubbing`, `audiography` and MIDI/raga-to-BGM cue integration with Ideator.
6. Integrate only one approved vertical-slice capability into Dreambox, validate end to end, then repeat.

Skip/park actual transport, studio crew allocation and on-set welfare scheduling until physical production makes them relevant. The output target is a better **film pipeline**, not a 23/23 completion trophy.

## 10. Short first-step prompt for Claude Code/Codex

> I have placed the Craftbox starter and `craftbox-roadmap.md` in a standalone repository. Inspect both, without editing Dreambox. Run the existing unit tests and start the local FastAPI app; confirm all 23 craft manifests are discoverable and exactly three pilot engines are functional. Implement **CB0 only** next: JSON Schemas and schema validation for the three artifact types, local SQLite experiment history with input/output fingerprints, run-level approval state and export manifests, UI run history and diff, negative tests, and Windows setup checks. Preserve each craft folder's independence. No AI calls, no rendering and no Dreambox integration yet. Document any gaps; finish with test counts, observed browser results and a list of decisions requiring my input. Do not automatically promote or import output.

## Sources/references

- Traditional 24 crafts overview (music excluded for Craftbox): https://openfaceworldwide.com/2025/07/10/24-crafts-of-film-making/
- Additional Telugu industry overview: https://telugu.asianetnews.com/gallery/entertainment/cinema-24-crafts-which-craft-what-doing-in-shooting-film-federation-in-telugu-4bcl3ga
- OpenTimelineIO: https://opentimelineio.readthedocs.io/en/latest/
- PySceneDetect: https://www.scenedetect.com/docs/latest/
- OpenColorIO: https://opencolorio.org/
- Open Shot Designer: https://github.com/koosoli/OpenShotDesigner
- OpenFrame: https://github.com/kazim-45/openframe

