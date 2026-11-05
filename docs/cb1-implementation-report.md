# CB1 implementation report: Screenwriting and Direction Lab

Date: 2026-11-01 · Scope: CB1 only (CB2 not started; Dreambox and Ideator not touched or read) · Version: 0.3.0

## 1. Summary

CB1 adds a **Scene Lab**: an eight-step browser workflow (Story idea → Screenplay → Scene breakdown → Dramatic beats → Blocking → Shot list → Director review → Approved export) built on CB0's experiment store. Every screenplay revision and every directing plan is an immutable experiment/run with a parent link, so history, comparison, approval and export reuse CB0 rather than duplicate it. Everything is deterministic and rule-based; there is no AI, no network call and no rendering. Craftbox still runs independently at `127.0.0.1:8099`.

**Results:** 146 automated tests pass (the 50 from CB0, unchanged in meaning, plus 96 new, 16 of them for the story process, see §10). A real launch through `start-craftbox.bat` on port 8099 ran the full flow in Edge with no JavaScript errors. A human has not yet worked through the manual checklist (§8).

## 2. Baseline and gaps found before building

- Baseline: 50/50 tests passing; 23 manifests; `direction` was `planned`; `screenwriting` only normalised a scene card.
- Roadmap vs. request: the roadmap's CB1 gate asks for *two 30–60 s scenes*; you asked for *one 60–90 s scene with two directorial approaches*. I followed your request. Roadmap items not done: "constraints for no-woman-on-screen / multiple-character scenes, chronology and location policies" (§7).
- CB0 limits that mattered: one input schema per craft, no way to link versions from the API, no store for derived exports. Each got a small additive change (§3).

## 3. Compatibility decisions (please confirm)

1. **No schema or route renamed.** `filmcraft.scene.v1`, `shot_plan.v1`, `edit_plan.v1` and all CB0 routes are unchanged. The CB0 scene-card mode of `screenwriting` still works and still outputs `filmcraft.scene.v1`.
2. **Screenwriting got a second mode, not a new craft.** A manifest `modes` entry selects `filmcraft.screenplay.v1` (input and output) when the payload says so. The craft count stays 23. `direction` moved from `planned` to `pilot` (so 4 pilots, 19 planned).
3. **New schemas keep the `filmcraft.` prefix:** `screenplay.v1`, `direction_plan.v1`, `scene_manifest.v1`, `shot_manifest.v1`, `blocking.v1`, `shot_list.v1`, `input.direction.v1`. Documented here as the migration-free extension of the existing namespace.
4. **Additive API/DB changes:** `parent_experiment_id` on `POST /api/experiments`; `?name=` on fixtures; migration 2 adds the append-only `derived_exports` table (a CB0 database upgrades in place; tested). Existing history is never altered.
5. **Crafts stay independent.** `direction` reads a *processed* screenplay artifact (timings and hashes come from it) and imports nothing from `screenwriting`; the service layer (`app/lab.py`) is the only place both are used together.
6. **Shot decisions live inside the plan** (`status`: proposed / approved / rejected / needs_review) so each decision is part of an immutable version; plan-level approval uses CB0's run lifecycle.
7. **Manifests are gated by approval, with explicit recorded overrides** (§5), rather than hard-blocked, following the UI standard's rule that advice may be overridden visibly.
8. **UI:** the Story Lab (§10) is the default tab and the Scene Lab is the second; the CB0 wizard moved to a "Single craft" tab, unchanged. The CB0 browser tests were scoped to that tab; their assertions are unchanged except the ready-pilot count (3 → 4).
9. **Version bumped to 0.3.0.**

## 4. What was built

### Screenwriting Lab (`app/crafts/screenwriting/`, UI steps 1–4)
- **Document model** `filmcraft.screenplay.v1`: project, characters (motivation, want, need, flaw, relationships, emotional arc), three-act structure, sequences, scenes (heading, objective, conflict, turning point, outcome, props), script elements (action / dialogue / parenthetical / transition, each with a permanent ID, optional pause), beats (role, act, intensity, emotion, per-character emotional state, owned elements).
- **Engine** (`screenplay.py`): integrity checks with clear errors (duplicate IDs, unknown speakers, a line in two beats, bad sequence/scene links…); work-in-progress documents are accepted with *warnings* instead of failures. Computes per-line and per-beat timings, scene duration and frames, pacing label, dialogue/action share, a micro three-act balance per scene, project-level act coverage, and content hashes (line, beat, scene, screenplay).
- **Story idea → outline** (`skeleton`): rule-based template of three acts, one scene and six beats; it writes no story text.
- **Readable script** (`fountain.py`): Fountain-style export/import. Round-trips project ID, character IDs and names, scene IDs (`#SC-001#`), headings, synopsis, objective/conflict/turning point/outcome, and every line with speaker. Plain scripts with no metadata also import, receiving new IDs.
- **UI:** characters editor, line editor (add/move/delete, type, speaker, pause), scene and sequence management with reordering, beat editor with intensity curve, estimates panel, JSON and script import/export, revision history with side-by-side comparison, and a guard so unsaved work is never replaced silently.

### Direction Lab (`app/crafts/direction/`, UI steps 5–8)
- **Plan model** `filmcraft.direction_plan.v1`: approach, interpretation and intent, stage (objects, 180° axis), per-beat blocking (start/end, path, facing, eyeline, entrance, exit, posture, action), and shots (beat link, covered lines, purpose + purpose note, size, angle, movement, framing, camera side, lens, subjects, duration, transition, status, previz and storyboard metadata).
- **Every shot has a purpose:** `purpose` and a `purpose_note` of at least 8 characters are required by the schema, so a shot without one cannot be saved.
- **Two presets, same script, genuinely different** (`approaches.py`): *A, Intimate* (close, handheld, short shots, crosses the axis once at the climax through a neutral shot) and *B, Observational* (wide, still, long takes, never crosses the axis). Approaches are numeric data; the average shot length can be overridden.
- **Generator** (`generator.py`): reads beat timings and intensities, shortens shots as intensity rises, splits turning-point and climax beats into one shot per speaker or change of kind, adds a reveal insert and a reaction at the turning point, avoids repeating a size/angle or creating jump cuts, and writes a *different* purpose note per shot (each quotes the line it covers).
- **Analysis** (`analysis.py`): timeline and duration vs. script; coverage (beats with no shot; dialogue with no shot); variety (size, setup and purpose repetition); pacing vs. beat intensity; blocking (teleporting, double entrance, reappearing after exit, unknown targets); continuity (**180° line crossing without a neutral or motivated shot**, eyelines that do not meet, jump cuts, framing someone who is not on stage). Issues are `error` or `warning` and are advice; they never block saving.
- **Editable plan UI:** stage diagram (click to move a character), numeric positions, paths, facing and eyeline notes, entrances/exits; shot table with edit, add, copy, delete, reorder, approve, reject; "Check this plan" (saves nothing); director review with metrics, pacing table, per-shot decisions, "approve all undecided" (explicit), two-approach comparison, plan approval with reviewer and note.
- **Cinematography/Editing hand-off:** the `shot-plan` export is a valid `filmcraft.shot_plan.v1` (it carries `beat_id` and purpose); a test feeds it to the existing Editing pilot.

### Change tracking (the integrity requirement)
- Each plan stores the beat and line hashes it was built from. `GET /api/lab/plans/{id}/impact` compares them with a newer screenplay and lists changed, removed and added beats and lines, the **shots that depend on them**, and any new dialogue that has no shot.
- **Rebase** creates a *new* plan version on the newer screenplay: only affected shots become `needs_review` (their earlier status is kept in `previous_status`); unaffected approved shots keep their approval; removed beats leave their shots in place as `needs_review` errors rather than deleting them. The original plan, its approval and its exports are untouched (tested).
- Reordering scenes changes no scene hash, so plans do not go stale (tested).

### Exports and Dreambox preparation
- Working files, available any time: screenplay JSON, readable script, blocking (`filmcraft.blocking.v1`), shot list (JSON and CSV), Cinematography-compatible shot plan.
- **Scene manifest** (`filmcraft.scene_manifest.v1`: scene, characters, timed lines, beats, blocking, stage, interpretation) and **shot manifest** (`filmcraft.shot_manifest.v1`: approved shots with frame-accurate start/duration, camera, previz and storyboard metadata, continuity summary, excluded shots) are produced only from an **approved** plan, are hashed (`manifest_sha256`), carry the approval, source hashes and `auto_import: false`, and are stored immutably (second request returns the identical file).
- If the script changed after the plan, or shots are undecided, the export is refused with an explanation; `acknowledge_stale` / `allow_pending` overrides export anyway, and the override is written into the file and the event log.

### Optional AI adapters (interface only)
`app/ai_adapters.py` defines the adapter contract for ChatGPT, Gemini and Venice: off by default, proposals only (validated like manual input, never auto-applied), credentials from environment variables only, estimate-then-confirm before any paid call. The three remote adapters raise `AdapterDisabled`; a test asserts no socket is opened. `local-rules` wraps the deterministic planner and demonstrates the interface. No paid API is called anywhere.

## 5. The test scene: "The Closing Hour"

Original; two characters (Nila, Arjun), one location (a bookshop at closing time). **84 s** (2,016 frames at 24 fps), 24 lines (14 dialogue, 9 action, 1 parenthetical, plus a pause before the last answer), 7 beats with intensity 2-3-5-7-8-10-6, three-act balance 25/50/24%.

| Measure | Plan A: Intimate | Plan B: Observational |
|---|---|---|
| Shots (in the approved sample, after one rejection in A) | 21 | 13 |
| Average shot | 3.83 s | 6.35 s |
| Close-ups (ECU/CU) / wides (WS/EWS) | 9 / 2 | 3 / 4 |
| Camera moves (not static) | 16 | 4 |
| Camera sides used | A, axis, B | A |
| Distinct setups / variety score | 20 / 0.95 | 12 / 0.92 |
| Continuity errors / warnings | 0 / 0 | 0 / 0 |

Emotional progression, dialogue and action, blocking and eyelines (the two close in distance as intensity rises, from 0.43 apart at the first beat to 0.14 at the climax), shot variety and sequencing, duration (each plan within about 5% of the script), script revision (revision 2 changes one line, affecting exactly four shots in Plan A) and approach comparison are each covered by automated tests; whether the *creative result is good* needs your eyes (§8).

Sample exports: `samples/` (17 files plus 4 in `change-tracking/`; regenerate with `python scripts/make_samples.py`).

## 6. Test results

| Suite | Tests | Result |
|---|---|---|
| CB0 engines (`test_engines.py`) | 7 | pass, unmodified |
| CB0 API (`test_cb0_api.py`) | 30 | pass (one helper learned about the Direction craft) |
| CB0 browser (`test_browser.py`) | 13 | pass (selectors scoped to the Single craft tab; ready-pilot count 4) |
| CB1 engines (`test_cb1_engines.py`, includes 9 story-audit tests) | 49 | pass |
| CB1 API (`test_cb1_api.py`) | 19 | pass |
| CB1 samples (`test_cb1_samples.py`) | 6 | pass |
| CB1 browser (`test_browser_cb1.py`) | 15 | pass in repeated runs |
| Story Lab browser (`test_browser_story.py`) | 7 | pass in repeated runs |
| **Total** | **146** | **all pass** (`python -m unittest discover -s tests`, about 45 s) |

What is covered: screenplay integrity, determinism and hashing (a one-line edit changes exactly that line's and beat's hash); scene card mode unchanged; Fountain round trip; both presets valid, deterministic, fully covered, varied and clean; **planted errors flagged** (line crossing, eyelines, position jump, double entrance, missing coverage, repetition); impact, rebase, removed beats, unplanned dialogue; exports valid and consistent; manifests gated, idempotent, immutable and override-recorded; a CB0 database upgrading in place; remote AI adapters unable to open a socket; and, in the browser, every one of the eight steps through `assert_ui_contract`, errors appearing beside the Save button with typing preserved, reload recovery, the unsaved-work guard, and the approve → script change → stale → rebase scenario.

**Live check:** `start-craftbox.bat` on the default port 8099 (throwaway data folder), health `ok`, full flow in Edge (sample → save → draft both approaches → check → review), no JavaScript errors; only that process was stopped afterwards. Dreambox was **not running** during this check, so simultaneous running was not re-verified in CB1 (the port logic is unchanged from CB0, where it was).

## 7. Limitations and not built

- **Not built (roadmap CB1):** constraint policies (no-woman-on-screen, multi-character rules, chronology, location policies); a separate "alternate takes" object (revisions and alternative plans serve this role).
- **Quality of generated plans is heuristic.** The blocking and shot planner follow documented rules (distance shrinks with intensity, sizes tighten with intensity, etc.); they produce clean, varied, purposeful plans but they are not a substitute for a director. The duration model (2.7 spoken and 3.2 action words per second, 0.35 s per line) and the pacing and act thresholds are guesses, marked as such in the output.
- **Geometry is simplified.** The 180° rule uses the line between the first two characters; scenes with three or more characters are only partly modelled. Eyeline checks apply to consecutive single or over-the-shoulder shots only. Previz camera positions are derived approximations for later tools, not a calibrated camera.
- **Direction UI is per scene.** Choose the scene in steps 2–4; step 5 drafts a plan for the selected scene. Only the single-scene sample was exercised in the browser for directing; multi-scene *screenplay* handling (add, reorder, sequences) is tested.
- **Fountain format limits:** beats, props, sequences, acts and timings are not in the readable script (use JSON for those); a standalone parenthetical re-imports without its speaker.
- **Stage editing** is by numbers and click-to-place; there is no drag-and-drop.
- **Manifests are validated against Craftbox's own schemas only.** No Dreambox adapter exists. A later read-only audit ([dreambox-overlap-audit.md](dreambox-overlap-audit.md)) maps the manifests to Scene Maker's fields and lists gotchas; the mapping is still a proposal to confirm in CB5. Manifests are hashed, not signed.
- **Not tested:** browsers other than Edge/Chromium, small screens (layout has narrow-screen rules but was not reviewed), very large screenplays (hundreds of scenes), concurrent editing.
- **Carried over from CB0:** no authentication (localhost only), no ruff/CI, no content-addressed asset store, SQLite inside a Dropbox folder (see the README).
- **Exports download through the browser;** Craftbox does not write to a chosen folder.
- The earlier `using-craftbox.html` guide in Downloads describes CB0 only.

## 8. What needs your manual verification

Use [cb1-acceptance-checklist.md](cb1-acceptance-checklist.md) (about 25 minutes). The points no test can judge: whether the two approaches read as genuinely different treatments, whether the shot purposes and notes are useful, whether the blocking and stage diagram match how you picture the scene, whether the explanations on each step are clear, and whether the manifests contain what a Scene Maker import will need.

## 9. Recommended next steps

1. Run the checklist; note which generated choices you would change, so the approach knobs can be tuned.
2. Decide the constraint-policy and multi-character questions before extending the generator.
3. Pick the CB2 starting craft (`art_direction`, `lighting`, `costume`, `casting`) per the roadmap; the prop and stage objects added here are the natural hook for art direction.
4. ~~Start the read-only Dreambox audit~~ Done: [dreambox-overlap-audit.md](dreambox-overlap-audit.md). Its §6 recommends the CB2 scope (cross-scene continuity) and §7 lists the decisions still open.
5. Add a drag-and-drop stage editor and multi-character axis handling only if the checklist shows they matter.

## 10. Story development process (`guidelines/story-process.md`)

**Finding.** Before this change the Screenwriting feature followed the process only in part. It captured a theme, each character's want, need and flaw, a three-act outline and dramatic beats, but none of the required inputs of Phases 2-6 and only fragments of Phase 1. It also began writing without asking whether the idea was a story at all.

**What was added.** A **Story Lab** (the new default tab, before the Scene Lab): a six-step wizard, one step per phase, editing a new optional `story` block inside the same `filmcraft.screenplay.v1` document. The answers are therefore versioned, comparable and recoverable like the script. Saving creates a screenplay revision. **Story answers never change the scene hash, so they cannot make a directing plan stale** (tested). Each step shows an advice-only check from `analysis.story`: rule-based, and it never blocks saving, planning or approval, following the UI standard's "advice is advice".

| Phase and required input | Where it is captured | What the check does |
|---|---|---|
| 1 Five Pillars: setting, protagonist, supporting cast, antagonist, core conflict, plot, theme | Story Lab step 1; pre-filled when a project is started from an idea | Missing or too short; the protagonist cannot also be the antagonist; a two-hander without supporting cast is a note, not an error |
| 1 Minimal Narrative Test | Two events and the juncture joining them | All three needed; identical events are advice |
| 1 Master Plot Arc | The eight templates named in the process | Must be chosen |
| 2 Canonical Script Breach | The norm and how the story violates it | Both must be written |
| 2 The 15-Second Hook | Hook text plus the script line that delivers it | **Checked against the script**: the line must start within the first 15 s |
| 2 Defamiliarization Lens | Technique and how it is applied | Both must be written |
| 3 Vulnerability Calibration | Framing note and a distress-risk rating | A "high" rating gives advice |
| 3 Consciousness Representation | Free indirect discourse, interior monologue, psycho-narration, or behaviour and objects only | Must be chosen |
| 3 Strategic Empathy Target | Bounded, ambassadorial or broadcast | Must be chosen |
| 3 Agency and Effort | Hard choices, each with a cost; a note on any luck or rescue | A choice without a cost is advice |
| 4 Unity of Opposites | Why neither side can walk away | Must be written |
| 4 Expectation Gap | Decision points linked to beats, with the stakes they raise | At least two, each tied to a beat and raising the stakes |
| 4 Information Gap | What is withheld and the beat that reveals it | Reveal beat required; a fact revealed in the first beat is advice |
| 4 Subtext (Iceberg) | Surface line vs. the unspoken feeling, per script line | **Checked against the script**: dialogue denser than 110 spoken words a minute is advice |
| 5 Labov's six elements | Abstract, orientation, complicating action, evaluation, result, coda; each linkable to a beat | All six required |
| 5 Story Circle (8 steps) | You, Need, Go, Search, Find, Take, Return, Change; each linkable to a beat | **Checked against the script**: linked beats must move forward |
| 6 First Draft Sprint | Live count of script lines, link to the Scene Lab | Advice until a draft exists |
| 6 Outside Feedback | Notes from readers with open/addressed status | Open notes are advice |
| 6 Polishing and Proofreading | Prose, tone, word choice, structural consistency | Unticked items are listed |
| 6 Flight Simulator Verification | What the audience rehearses, the moral choice, a verified tick | Advice until verified |

31 checks in all. The sample "The Closing Hour" now carries an authored story block and scores 27 of 31. Phases 1-5 pass (supporting cast is an honest "none" for a two-hander). Phase 6 is left genuinely open: one unanswered peer note, one unticked polish item, flight simulator unverified.

**UI standard.** The Story Lab is its own wizard: 6 steps titled "Step N of 6", a plain-words intro per step, labelled Back and Next, one **Save story revision** per step, the audit beside the answers, and a last step that ends in explicit "Continue to the Scene Lab" and "Review phase 1 again" buttons. `assert_ui_contract` runs on all six steps. A reload now also reopens the **tab** you were on (a gap found while testing).

**Decisions.**
(a) A separate wizard rather than twelve steps in one: the six phases and the eight production steps are different kinds of work, and the earlier Scene Lab flow and tests stay as they were.
(b) The audit is advice only, so a story with open items can still be written, planned and approved; the open items are simply visible.
(c) The process's "Plot" is a free-text cause-and-effect summary; the scene's beats remain the detailed plot.
(d) The process addresses prose fiction and film, so the "consciousness" options include "behaviour and objects only" for a screenplay with no voice-over.
(e) The Story Lab generates no story content.

**Limits.** Most checks test completeness, not quality: they cannot tell whether a hook is gripping or a theme profound. The three script cross-checks (hook timing, subtext density, circle order) depend on the script and beats being filled in. The 110 words-a-minute and 15-second thresholds are guesses taken from the process document and are labelled as such. Only one scene (the sample) was exercised with a full story block. The phase 6 "peer review" is a log, not a sharing feature.
