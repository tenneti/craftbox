# CB0 implementation report

Date: 2026-11-01 · Scope: CB0 only (CB1 not started) · Version: 0.2.0

## 1. Baseline (before changes)

- Starter inspected: 23 manifests/folders, 3 pilot engines (`screenwriting`, `cinematography`, `editing`), 20 `NotImplementedError` placeholders, FastAPI server, single-page JSON UI, 7 unittest tests (all passing).
- Cross-check against roadmap: the 23 craft IDs in the roadmap table match the folders and manifests exactly; all manifests share one key set; statuses are `pilot` (3) / `planned` (20).

### Gaps and inconsistencies found

| Finding | Resolution |
|---|---|
| No persistence, no approval workflow (README/roadmap require them in CB0) | Implemented (§3). |
| No JSON Schemas; only ad-hoc checks in engines | Added schemas + validation (§3). |
| `engine_version` hard-coded inside `execute()` | Now a module constant, stored with every run. |
| Malformed pilot payloads could surface as **404** (engine `KeyError`) or **500** (`AttributeError`) on `POST /api/crafts/{id}/run` | Engine `KeyError`/`AttributeError` are converted to `ValueError` → **422**. Behavior for all valid and previously-422 inputs is unchanged. |
| README said "no database writes"; roadmap mentions `ruff`, CI, content-addressed asset store, signed manifests | README updated; ruff/CI/asset store/signing **not done** (§6). |
| Roadmap names states `exported → imported → superseded` | `imported`/`superseded` need the Dreambox adapter and versioning; not implemented (§6). |
| Roadmap's richer envelope fields (`settings`, `provider`, `estimated_cost`, …) | Not added to the engine envelope (nothing to record without AI). Hashes, schema/engine versions, timing and approval fields are stored as run columns instead. |

## 2. Compatibility decisions (please confirm)

1. **Schema IDs untouched.** `filmcraft.scene.v1`, `filmcraft.shot_plan.v1`, `filmcraft.edit_plan.v1` are unchanged. New CB0 schemas reuse the `filmcraft.` prefix (`filmcraft.input.<craft>.v1`, and the roadmap-listed `filmcraft.export_manifest.v1`) rather than introducing a `craftbox.*` namespace.
2. **Original routes unchanged.** `POST /api/crafts/{id}/run` stays stateless ("Quick run"); persistence is opt-in via `/api/experiments`. `/health` gained fields but kept the old ones.
3. **Manifests extended additively** with `input_schema`/`output_schema` on the three pilots only (existing tests that check `contract_version` still pass). Planned crafts make no schema claims.
4. **Schema validation is stricter on the new path only.** The experiment API validates input against the schema (e.g. `fps` must be an integer) while the legacy quick-run keeps the engines' lenient coercion (`"24"` is still accepted there).
5. **Approval lives on runs, not experiments.** An experiment's input is immutable; each execution is a run that is reviewed independently. Roadmap says "run-level approval state"; this follows it.
6. **Port**: 8099 default (as in the roadmap); 8000 is refused; non-loopback hosts refused.
7. **Data location**: `./data` inside the project (git-ignored) by default; overridable. Because this project sits in Dropbox, moving it out is recommended (README note).

## 3. What was implemented

**Experiment lifecycle** — create → run (repeatable) → submit for review → approve / reject (rejected runs can be resubmitted) → export. Illegal transitions return 409; approval needs a reviewer; rejection needs a note. Failed engine runs are recorded (status `failed`, approval `none`) and cannot be reviewed. Planned crafts cannot have experiments (409).

**Persistence (SQLite, stdlib)** — tables `experiments`, `runs`, `run_events`, `exports`; ordered migrations via `PRAGMA user_version` (a database from a newer Craftbox is refused). Triggers make runs' content columns, experiment inputs, the event log and exports immutable and block every `DELETE`. Writes use one immediate transaction each. No API keys are stored anywhere.

**Versioned schemas** — 4 shared schemas (`scene`, `shot_plan`, `edit_plan`, `export_manifest`) + 3 input schemas, exposed at `/api/schemas`. A small dependency-free validator implements the JSON Schema subset used and **raises on any unsupported keyword**, so a schema can never be silently under-enforced. Input is checked before saving; the artifact is checked after running (a mismatch becomes a failed run with details).

**Reproducibility** — SHA-256 of canonical JSON for inputs and for `{artifact_type, artifact, warnings}` (run IDs/timestamps excluded). The UI and API show whether repeated runs agree; *Verify* re-executes a stored input and compares hashes (and records an event), so engine changes that alter outputs are detected.

**Comparison** — structural diff of inputs and artifacts for two completed runs of the same craft, across experiments. Lists of objects are matched by `shot_id`/`id`/`scene_id`/`speaker_id` where unique (so reordering is not noise), otherwise by index. Capped at 500 changes.

**Export manifests** — `filmcraft.export_manifest.v1`: craft/experiment/run IDs, engine and schema versions, input and output hashes, the artifact, approval block (reviewer, timestamp, note), `media_references` (referenced IDs + count of unresolved offline media), provenance (`ai_used: false`), warnings, `import_policy` (`auto_import: false`) and a `manifest_sha256`. Only approved runs; exporting is idempotent (the stored manifest is returned byte-for-byte). `signature` is `null` (see §6).

**Browser UI** — original workspace kept (Quick run, fixtures, JSON export) plus *Save & run experiment*; new **Experiments** view: filters, history table, details (input snapshot, reproducibility, runs with warnings/errors), review panel, Submit/Approve/Reject/Export/Verify/History actions, run-output viewer, duplicate, edit-as-new, cross-experiment run comparison. All DOM is built with `textContent` (no `innerHTML`). Reviewer/note entries survive re-renders.

**Operations** — structured JSON logging (stderr + rotating `data/logs/craftbox.log`; request IDs, timings, lifecycle events); global error handling (unhandled errors → JSON 500 with request ID and logged traceback); 1 MB request body limit (413); `scripts/check_env.py`; `start-craftbox.bat`; `python -m app.run` launcher.

**Port and process isolation** — default `127.0.0.1:8099`; `CRAFTBOX_PORT`/`CRAFTBOX_HOST`/`CRAFTBOX_DATA_DIR`; port-in-use detection by a connect probe (never touches the owner); own `.venv`, database, logs.

## 4. Test results

| Suite | Tests | Result |
|---|---|---|
| Original engine/registry tests (`tests/test_engines.py`) | 7 | pass, unmodified |
| Backend/API (`tests/test_cb0_api.py`) | 30 | pass |
| Browser, Edge via Playwright (`tests/test_browser.py`, one fresh server and database per test) | 13 | pass (repeated runs, no flakes) |
| **Total** | **50** | **all pass** (`python -m unittest discover -s tests`, ~17 s) |

Backend coverage: schema positives/negatives/unknown keywords; full lifecycle for each of the 3 pilots; illegal transitions; reject rules; export gating, idempotency, hash check, unresolved-media reporting; failed runs; invalid/unknown/malformed IDs; filters and pagination; metadata edits; rerun determinism, verify (including a simulated engine change), compare (variants, identical, cross-craft, failed); persistence across app restart; SQL-level attempts to delete/alter history are rejected; newer-DB refusal; 413; legacy endpoints and the 422-not-404/500 fix; config validation, loopback enforcement, port-in-use detection and launcher exit code.

Browser coverage: 23-craft dashboard, planned crafts disabled, all 3 pilots (Editing fed by Cinematography's real output), invalid JSON, schema failure, name required, approve + export (downloaded manifest checked) + history, reject needs note, rerun/verify/compare within and across experiments, filters, duplicate, edit-as-new; zero JS errors asserted on every test.

### Live validation (Windows, real launch)

- Dreambox was listening on 127.0.0.1:8000 (PID 3548) before, during and after; it was never started, stopped, modified or sent any request (only the listener table was read).
- `start-craftbox.bat` launched Craftbox on `127.0.0.1:8099` (loopback only): `/health` → `{"status":"ok","standalone":true,"module_count":23,"app":"craftbox","version":"0.2.0","database":"ok"}`.
- A real Edge session against :8099 loaded all 23 crafts, ran Screenwriting and Cinematography, opened the Experiments tab; no JS errors. This smoke test was read-only (no experiments written).
- A second launch while 8099 was busy printed "already in use … Craftbox will not stop it" and exited non-zero; `CRAFTBOX_PORT=8000` and `CRAFTBOX_HOST=0.0.0.0` were refused with explicit messages. The listener table was unchanged afterwards.
- I then stopped only the Craftbox process I had started; Dreambox (PID 3548) remained listening on 8000.
- `examples/pipeline.py` still produces the 14-second, 2-clip offline edit plan.

## 5. Architecture

```
Browser UI (static) ──► FastAPI (server.py) ──► ExperimentService (experiments.py)
                              │                        │            │
                              │                 core.execute()   SQLite (db.py)
                              │                  (unchanged)     experiments · runs · run_events · exports
                              ▼                        │
                        validation.py ◄── schemas/ + crafts/<id>/input.schema.json
```

`core.py` and the engines remain the pure, synchronous contract; everything stateful sits in the service layer, so a craft can still be developed and run with nothing but `execute()`.

## 6. Limitations and unimplemented capabilities

- **Not done from the roadmap CB0 list:** `ruff` configuration and CI; content-addressed asset copy/reference store; Windows `setup` script beyond `start-craftbox.bat` + `scripts/check_env.py`; Studio Settings/Asset Browser/Continuity/Promotion Center pages (the Experiments view covers promotion states only partly).
- **Lifecycle:** `imported` and `superseded` states are not implemented (need Dreambox adapter/versioning). Exporting makes a run `exported`; there is no "un-export".
- **Manifests are hashed, not signed** (`signature: null`). `manifest_sha256` detects accidental change, not tampering.
- **No authentication** — localhost only by design; do not expose. No payload size limit for chunked requests without `Content-Length`.
- **Schemas are lightweight prototypes** (as the roadmap warns); no migration tooling for artifact schemas yet. The validator supports only the keyword subset in use.
- **Not tested:** other browsers than Edge/Chromium; macOS/Linux; concurrent multi-user access; Dropbox-sync behavior of the SQLite file; large histories (listing is paginated and indexed but untested at scale); mobile layout was not reviewed visually.
- **Manual QC:** the browser suite checks behavior, not visual polish. The manual checklist (`docs/manual-testing-checklist.md`) still needs a human pass; I have not watched the UI through a full manual session.
- Deliverable 1–7 craft standards are *infrastructure-ready* but only the 3 pilots can exercise them; none has a rich preview or quality rubric yet (`docs/development-standards.md`).
- Other incidental notes: `data/` is git-ignored and the project is not a git repository here; the lazy `app.server:app` attribute keeps tests from touching `./data`.

## 7. Recommended next steps

1. Review the §2 decisions and this report; run the manual checklist once.
2. Decide the Dropbox question: relocate `CRAFTBOX_DATA_DIR` outside synced folders.
3. Add `ruff` + a minimal CI workflow, and the content-addressed asset store, to finish the CB0 list.
4. CB1 (after your go-ahead): `direction` craft (first new engine through the checklist in `docs/development-standards.md`), scene-ID preserving screenwriting import, shot-to-beat links and a coverage-gap checker.
5. Start the read-only Dreambox audit from roadmap §4 before designing the CB5 import adapter; keep the manifest schema as the contract.

## 8. UI revision (after first review): conformance with `guidelines/ui-standard.md`

Feedback: the first UI did not explain what each feature did or what came next. The UI was rebuilt as a five-step wizard (Choose a craft → Enter input → Run → Review → Export) plus a History view. The standard's helper library (`ui.js`, `jobqueue`, `W.draft`) belongs to Dreambox and was not available, so Craftbox has its own equivalent: `app/static/ui.js` (`window.ui`: `call`, `fields`, `steps`, `stepper`, `nav`, `errorBox`, `reveal`, `progress`) and `tests/ui_contract.py::assert_ui_contract`, which every wizard-step browser test calls.

| Rule | How it is met |
|---|---|
| U1 wizard, Back/Next | 5 numbered steps, stepper, "Step N of 5: …" titles; Back on steps 2–5, Next on steps 1–4, labelled with where they lead; step 5 ends with explicit "Start a new experiment" / "Open History". |
| U2 one Save | Only step 2 saves, with one primary **Save experiment** (`data-testid=experiment-save`). Run, Approve, Export etc. are actions, not Saves. |
| U3 saving never clears | Text stays after Save; status line shows "Saved" / "Changed, not saved yet"; moving on is a separate Next. Because experiment inputs are immutable, saving an edited input creates a *new* experiment, and the screen says so. |
| U4 input never lost | Drafts live in one store (`W.draft`) mirrored to localStorage; redraws, failed requests (tested by aborting the request) and reloads keep them; the wizard reopens at the step where the work is (tested). A late-arriving example can no longer overwrite typed text. |
| U5 feedback beside control | Errors, notices and progress render inside the card of the action (tests assert the error is inside the form); disabled buttons show their reason beside them. |
| U6 no silent waits | A progress panel with elapsed time (`data-ui=progress`) appears for every request (tested with a 1.2 s delayed run). All current actions finish in milliseconds, so no background job queue was built. |
| U7 estimate then confirm | Not applicable: CB0 makes no paid or network calls. |
| U8 say what happens next | Every step opens with a plain-words intro; empty states say what to do; jargon is glossed ("repeatable", "manifest"). |
| U9 advice is advice | Rejection advice ("change the input and re-run, or resubmit") is non-blocking; Next from Run/Review is never blocked by an opinion. Approval before export is a Craftbox safety rule (roadmap), not advice, and the reason is shown beside the disabled button. |

**Deviations (each with reason):**
1. `tests/ui_contract.py` instead of `tests/ui/ui_contract.py` so `unittest discover -s tests` can import it without a package.
2. History is a two-pane list/detail view, not a wizard: it is a lookup screen with no form to save. It still has explanatory intro text and empty states. Review/approve actions live only in the wizard (one place), and History links into it ("Continue in the wizard").
3. No `core/jobqueue.py` equivalent (see U6).
4. The standard references Dreambox files; none were read or modified.

Behavior changes versus the first UI: the sidebar craft list became step 1; "Quick run" is now "Try without saving"; approve/reject/export moved out of History into the wizard; the History tab keeps verify, event log, compare, duplicate. The API is unchanged.
