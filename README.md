# Craftbox — standalone craft experiment lab (CB0)

Craftbox is a **separate, local-first application** for experimenting with the 23 traditional (non-music) filmmaking crafts before any proven capability is promoted into Dreambox. It never imports Dreambox code, never shares its database or files, and makes **no AI or network calls**.

Status: **CB0 foundation, CB1 Screenwriting + Direction Lab, CB2A Art Direction Lab and CB2B Lighting Lab complete.** All 23 crafts have a folder, manifest and entry point. Six non-AI pilot engines are executable — **Screenwriting**, **Direction**, **Cinematography**, **Editing**, **Art Direction**, **Lighting**. The other 17 are explicitly `planned` and cannot report success. See [docs/cb0-implementation-report.md](docs/cb0-implementation-report.md) [docs/cb1-implementation-report.md](docs/cb1-implementation-report.md) and [docs/cb2a-implementation-report.md](docs/cb2a-implementation-report.md) and [docs/cb2b-implementation-report.md](docs/cb2b-implementation-report.md).

## Quick start (Windows)

Double-click or run **`start-craftbox.bat`** in the project root. It creates `.venv` on first use (installing `requirements.txt`), activates Craftbox's own environment and launches the server at <http://127.0.0.1:8099>.

Manual equivalent (PowerShell):

```powershell
cd path\to\craftbox
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.run          # http://127.0.0.1:8099
```

Optional developer setup (tests, browser tests, environment check):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\check_env.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Browser tests drive Microsoft Edge (or Chrome) already installed on Windows through Playwright; no browser download is needed. If Playwright or a browser is missing they are skipped, not failed.

## Running Craftbox and Dreambox together

| | Dreambox | Craftbox |
|---|---|---|
| URL | `http://127.0.0.1:8000` | `http://127.0.0.1:8099` |
| Virtual env | its own | `craftbox\.venv` |
| Database | its own | `craftbox\data\craftbox.db` |
| Logs | its own | `craftbox\data\logs\craftbox.log` |

- Start them in any order, in separate terminals; they do not depend on each other.
- Craftbox **never stops, restarts or contacts** another server. If port 8099 is taken, it exits with a clear message (exit code 3) instead of killing the owner.
- Craftbox refuses to use port 8000 (reserved for Dreambox) and refuses non-loopback hosts (it has no authentication).
- Stopping Craftbox: press `Ctrl+C` in its window. That does not affect Dreambox.

### Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `CRAFTBOX_PORT` | `8099` | Port, 1024–65535, not 8000 |
| `CRAFTBOX_HOST` | `127.0.0.1` | Loopback only unless `CRAFTBOX_ALLOW_REMOTE=1` (not recommended) |
| `CRAFTBOX_DATA_DIR` | `<project>\data` | Database and logs location |
| `CRAFTBOX_LOG_LEVEL` | `INFO` | Python log level |
| `CRAFTBOX_NO_BROWSER` | unset | Set to `1` to stop the launcher opening your browser |

```powershell
$env:CRAFTBOX_PORT = 8100; .\start-craftbox.bat      # PowerShell
set CRAFTBOX_PORT=8100 && start-craftbox.bat         # cmd
```

> **Dropbox note:** this project may live in a Dropbox folder. SQLite files are safest outside synced folders; set `CRAFTBOX_DATA_DIR=%LOCALAPPDATA%\Craftbox` if you see sync conflicts. Stop Craftbox before moving or restoring `data\`.

## Story Lab (CB1): developing an idea into a story-worthy narrative

The **Story Lab** tab (the default) turns the six-phase process in [guidelines/story-process.md](guidelines/story-process.md) into a six-step wizard:

1. **Concept**: the five pillars, the minimal narrative test, a master plot shape.
2. **Hook**: the canonical breach, the 15-second hook, a defamiliarization lens.
3. **Empathy**: vulnerability, consciousness mode, empathy target, agency and effort.
4. **Conflict**: unity of opposites, expectation and information gaps, subtext.
5. **Structure**: Labov's six parts and the eight-step story circle.
6. **Revision**: first draft, outside feedback, polishing, flight-simulator check.

Your answers are saved inside the screenplay project (each Save is a revision). An **advice-only** check beside each step tells you what is still missing; some checks look at your script (does the hook land in the first 15 s? is the dialogue too dense for subtext? do the story-circle beats move forward?). Nothing blocks you, and no story text is generated.

## Scene Lab (CB1): from story idea to approved shot plan

The **Scene Lab** tab is an eight-step wizard that develops one scene end to end. Every step opens with a plain-words explanation, has Back/Next, one Save, and keeps what you typed.

| Step | You do | What you get |
|---|---|---|
| 1. Story idea | Describe the idea, open a saved project, or load the sample **"The Closing Hour"** (original, 84 s, two characters, one bookshop) | An editable three-act outline, or a finished example |
| 2. Screenplay | Write characters and script lines (action, dialogue, parentheticals); import/export JSON or a readable script | Permanent IDs for every line; each Save is a new **revision** you can compare and reopen |
| 3. Scene breakdown | Objective, conflict, turning point, outcome; order scenes; sequences and acts | Length and pacing estimate (rule-based, not measured) |
| 4. Dramatic beats | Beats with emotion, intensity and the script lines they contain | An intensity curve the director uses |
| 5. Blocking | Pick a directing approach (A intimate / B observational) and draft | Director's reading of the scene, plus blocking per beat: positions, paths, entrances, exits, eyelines, on a stage diagram |
| 6. Shot list | Edit, add, copy, reorder, approve or reject shots; every shot states its purpose | Continuity, coverage and variety checks (e.g. crossing the 180° line) |
| 7. Director review | Check coverage and pacing against the beats, compare approaches, handle script changes, approve or reject the plan | Plan approval recorded with your name |
| 8. Export | Download files | Screenplay JSON, readable script, blocking, shot list (JSON/CSV), Cinematography-compatible shot plan, and the **scene** and **shot manifests** for a future Dreambox Scene Maker adapter |

Every save creates a new version; earlier versions, approvals and exports are never changed. If the script changes after a plan was made, the plan is flagged and a **rebase** creates a new plan version in which only the shots that depend on changed lines return to review. Plans are rule-based proposals: there is no AI and no network call. Optional AI adapters (ChatGPT, Gemini, Venice) exist only as a disabled interface (`GET /api/ai/adapters`). Sample exports are in [samples/](samples/README.md); a manual acceptance checklist is in [docs/cb1-acceptance-checklist.md](docs/cb1-acceptance-checklist.md).

## Art Lab (CB2A): from approved scene to approved design

The **Art Lab** tab is an eight-step wizard: scene, location, set layout (a 2D plan on the director's stage), props (extracted from the script, with continuity), visual style, comparison of two treatments, review, export. The **Art Library** tab holds project-wide style profiles and the asset register (pictures with source, owner and rights). Nothing is rendered and no AI is used; checks are advice, and only manifest exports wait for approval. Sample exports for "The Closing Hour" (Warm nostalgia vs Emotional distance) are in `samples/art/`; regenerate with `.venv\Scripts\python.exe scripts\make_art_samples.py`. Acceptance steps: [docs/cb2a-acceptance-checklist.md](docs/cb2a-acceptance-checklist.md).

## Single-craft experiments and History

The **Single craft** tab runs any one pilot craft through the five-step wizard below (CB0); **History** is where all saved experiments, from either tab, are looked at again.

The single-craft wizard (each step tells you what it is for and what comes next):

| Step | What you do | What happens |
|---|---|---|
| 1. Choose a craft | Click one of the 23 crafts (four say "Ready to run"; the 19 planned ones cannot run). | Nothing is created yet. |
| 2. Enter input | Name the experiment, edit the example JSON if you like, press **Save experiment**. *Try without saving* runs it once and shows the result without recording anything. | Saving freezes the input (validated against its versioned schema). Your text stays on screen; a line says "Saved" or "Changed, not saved yet". |
| 3. Run | **Run experiment**. Run again to check the result is repeatable, or use **Check it is repeatable**. | Every run is recorded and never changed. |
| 4. Review | Enter your name, **Submit for review**, then **Approve** or **Reject** (rejection needs a note). | Approval is always your decision. A rejected result can be changed, re-run, or resubmitted. |
| 5. Export | **Export manifest** (approved results only), then start a new experiment or open History. | Downloads a hashed `filmcraft.export_manifest.v1` file for a future Dreambox adapter. Nothing is sent to Dreambox. |

Back and Next are on every step, and a disabled button always says why. Your drafts are remembered: reload the page and you return to the same step with what you typed.

**History** lists every saved experiment. Select one to see its input and runs, **Check it is repeatable**, read the event log, **Compare** any two finished runs of the same craft (even from different experiments), **Duplicate** it, or **Continue in the wizard** at the right step.

Nothing is ever deleted: run records and the event log are append-only (enforced by SQLite triggers). The UI follows `guidelines/ui-standard.md`; see the conformance table in [docs/cb0-implementation-report.md](docs/cb0-implementation-report.md).

## API

Original (unchanged): `GET /health`, `GET /api/crafts`, `GET /api/crafts/{id}`, `GET /api/crafts/{id}/fixture`, `POST /api/crafts/{id}/run`, `GET /docs`.

Added in CB0:

- `GET /health` now also reports `app`, `version`, `database` (additive fields only; suitable for monitoring)
- `GET /api/system`, `GET /api/schemas`, `GET /api/schemas/{schema_id}`
- `POST/GET /api/experiments`, `GET/PATCH /api/experiments/{id}`, `POST /api/experiments/{id}/run`, `POST /api/experiments/{id}/duplicate`
- `GET /api/runs/{id}`, `GET /api/runs/{id}/events`, `POST /api/runs/{id}/verify`
- `POST /api/runs/{id}/submit-review | approve | reject | export`, `GET /api/runs/{id}/manifest`
- `GET /api/compare?run_a=&run_b=`

Added in CB2A (Art Lab; all additive): `GET /api/art/presets`, `GET /api/art/projects/{id}`, `POST /api/art/draft | save | analyze`, `GET /api/art/treatments/{id}/impact`, `POST /api/art/treatments/{id}/rebase`, `GET /api/art/compare`, `GET /api/art/styles`, `GET /api/art/assets`, `POST /api/assets/upload | from-path`, `GET /api/assets/{sha}/file`; export kinds `art-direction-json`, `prop-list-csv`, `storyboard-metadata`, `art-direction-manifest`, `asset-reference-manifest` on the existing exports route.

Added in CB1 (Scene Lab; all additive):

- `GET /api/crafts/{id}/fixture?name=screenplay` (named fixtures); `POST /api/experiments` accepts `parent_experiment_id` (version chains)
- `GET /api/lab/projects`, `GET /api/lab/projects/{project_id}` (revisions, plans, stale flags), `GET /api/lab/approaches`
- `POST /api/lab/idea`, `POST /api/lab/analyze/screenplay`, `POST /api/lab/import/fountain`, `POST /api/lab/export/fountain`
- `POST /api/lab/direction/draft`, `POST /api/lab/direction/save`, `POST /api/lab/direction/analyze`
- `GET /api/lab/plans/{experiment_id}/impact`, `POST /api/lab/plans/{experiment_id}/rebase`, `GET /api/lab/compare-plans?run_a=&run_b=`
- `POST /api/runs/{run_id}/exports/{kind}[?override=acknowledge_stale&override=allow_pending]`, kinds: `screenplay-json`, `script`, `blocking`, `shot-list`, `shot-list-csv`, `shot-plan`, `scene-manifest`, `shot-manifest`
- `GET /api/ai/adapters`, `POST /api/ai/adapters/{name}/suggest` (disabled except `local-rules`)

Errors use `{"detail": ...}`: 404 unknown, 409 state conflict (e.g. planned craft, unapproved export), 422 invalid input (with `errors[].path/message`), 413 body over 1 MB.

## Layout

```
start-craftbox.bat      # launcher using Craftbox's own .venv
app/
  run.py                # launcher: config check, port-in-use check, uvicorn
  config.py             # env-based configuration
  core.py               # manifest registry and engine dispatch (unchanged contract)
  server.py             # FastAPI app (original routes + CB0 routes)
  experiments.py        # lifecycle, hashing, diff, export (service layer)
  db.py                 # SQLite + versioned migrations + immutability triggers
  validation.py         # dependency-free JSON Schema subset validator
  logging_setup.py      # structured JSON logging
  schemas/              # artifact + export manifest schemas (filmcraft.*.v1)
  crafts/<craft_id>/    # manifest.json, README, engine.py, fixture.json, input.schema.json (pilots)
  crafts/screenwriting/ # + screenplay.py (Screenwriting Lab), fountain.py (readable script), fixture.screenplay.json (sample)
  crafts/direction/     # engine, approaches, generator (blocking + shots), analysis (continuity), impact (rebase), exports
  lab.py                # Scene Lab service: versions, impact, rebase, gated exports
  ai_adapters.py        # optional AI adapter interface (disabled; no network)
  static/               # browser UI: index.html, ui.js (shared helpers), lab.js + lab-direction.js (Scene Lab), main.js (single-craft wizard + History)
docs/                   # implementation report, manual test checklist, development standards
scripts/check_env.py    # environment checker
scripts/make_samples.py # regenerates ./samples by running the real workflow
samples/                # sample screenplay, readable script, two direction plans, blocking, shot lists, manifests, change tracking
tests/                  # engine, backend/API and browser tests (+ ui_contract.py, the UI standard checker)
```

## Naming compatibility

Craftbox is the application name. Schema IDs such as `filmcraft.scene.v1`, craft IDs and API routes are retained as versioned technical contracts. Do not rename them without a migration and regression tests. New CB0 schemas follow the same prefix (`filmcraft.input.<craft>.v1`, `filmcraft.export_manifest.v1`).

## Integration rule

Before building any new craft or the Dreambox import adapter, read [docs/dreambox-overlap-audit.md](docs/dreambox-overlap-audit.md): what Dreambox already has (Screenwright, Scene Maker, Previz), which Craftbox features are redundant, unique or partial, the field mapping for the manifests, and known gotchas.

Do not import Dreambox internals here. When a craft passes manual evaluation, build an **adapter inside Dreambox** that reads the exported, versioned manifest; validate permissions, schema, IDs, media references and checksums; import idempotently into a staging area. Implement authentication and job isolation **before** any remote hosting.

## Next

See `craftbox-roadmap.md`. CB2B (Lighting) is done. Cross-scene continuity of locations and props, Costume, Casting and Dreambox integration have not been started.
