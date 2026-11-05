# Craftbox ↔ Dreambox overlap audit (read-only)

Date: 2026-11-01 · Craftbox 0.3.0 (CB0 + CB1) · Dreambox: `E:\...\allPython\dreambox` as it stood on that date · Roadmap reference: `craftbox-roadmap.md` §4 ("read-only code audit before new craft implementation").

**Keep this file handy.** It is the starting point for CB2 scoping and for the CB5 Dreambox import adapter. Nothing in Dreambox or Ideator was changed or run; everything below comes from reading code, status documents and the API reference. Items marked **[verify]** were not read closely enough to rely on.

---

## 1. Verdicts at a glance

| Craftbox feature (CB1) | Closest Dreambox equivalent | Overlap | Verdict | Action |
|---|---|---|---|---|
| **Story Lab**: six-phase story audit (31 checks) | Idea gater `backend/screenwright/gate.py` (6 dimensions, 20 criteria, AI-judged rank, suggestions, "weave in") + the 518-question story bank + mechanical and judgement script checks | **High**: same source material (see §4.1) | **Redundant for integration.** Freeze. | Do not extend, do not port. Keep as an offline, deterministic experiment and as a worksheet that produces the *answers* the gate judges. |
| **Screenwriting Lab**: manual screenplay editor, per-line IDs, revisions, Fountain round trip, timings and hashes | Screenwright screenplay generator (AI drafts by sequence, hand-edit one scene, lock, table read, `history/screenplay-vNN.md`) and Scene Maker script reader (`scene_maker/script.py`, stable block IDs, "adds, never removes") | **Partial**: different method (manual structured document vs AI-drafted text blocks) | **Keep as an authoring-side tool; integrate by export.** | Export a Scene-Maker-friendly script and the scene manifest; do not duplicate Dreambox's generator. See §5 gotchas. |
| **Dramatic beats**, three-act and pacing analysis | Screenwright outline rows (scene, seconds, change +/-, setups/payoffs, strands) and `beats.py` (novel hand-off) **[verify]** | **Partial** | **Keep**; map beats to Scene Maker `shot.beat` and to the outline rows. | Decide in CB5 whether beats are an import or only a reference. |
| **Direction Lab: shot planning** (approach presets, purposes, coverage of every beat and line) | Three places: Screenwright `shotcards.py` (rule-based cards, previz vocabulary), Scene Maker's AI Director plan, Previz "Describe a scene" (`engine/breakdown.py`) | **Medium** on the mechanics, **low** on intent | **Keep**, but expect to hand off *into* these structures. | Map to Scene Maker shots (§5.2). |
| **Direction Lab: continuity checks** (180° line with neutral shots, eyelines, jump cuts) | Previz `engine/continuity.py`: `LINE_180`, `SCREEN_DIRECTION`, `JUMP_CUT`, `LENS_SIMILAR`, `MOTION_CONFLICT`, `HEIGHT_JUMP`, `ENVIRONMENT`, `SUBJECT_SIDE`, with *Flip Shot* and *Move Camera* repairs | **Real overlap I missed earlier** (see §2) | **Partly redundant.** | Reuse Previz's checker after import; keep Craftbox's two-character axis, eyeline and coverage rules only as a pre-import gate. |
| **Direction Lab: multi-character blocking** (paths, entrances, exits, eyelines per beat) | Previz Shot JSON holds **one subject per shot** (position, facing, head, pose, motion) | **Low** | **Unique to Craftbox.** | Keep. Export a per-shot subject placement that can seed a Previz Shot JSON. |
| **Direction Lab: script-vs-shot coverage gaps**, purpose per shot, pacing vs beat intensity, two-approach comparison | None found | None found | **Unique to Craftbox.** | Keep. |
| **Change tracking**: script-change impact on shots and rebase that preserves approved work | Scene Maker revisions (`expectedRevision`, `history/rev_N.json`), shot `locked`/`planApproved`; `plan_history.py` is music-video plan snapshots and diff | **Low** (they version, they do not trace script → shot dependency) | **Unique to Craftbox.** | Keep; this is the strongest reason to integrate. |
| **Versions, approval, export manifests** (CB0 core) | Scene Maker revisions, shot/scene states, sign-off checklist | Medium | **Keep**: Craftbox is the *staging* layer before anything reaches Dreambox. | None. |
| **Optional AI adapters** (ChatGPT, Gemini, Venice; all disabled) | `backend/ai` choice layer, `/api/ai/choices`, `safe_complete`, estimate → confirm → run, Venice dollar limits | **High** | **Redundant.** | Do not build real adapters in Craftbox. If AI is wanted later, run it in Dreambox's layer. Keep the interface stub or delete it. |
| **UI standard** (wizard, Back/Next, one Save, advice) | Dreambox originated `guidelines/ui-standard.md`; `docs/ui-standard-status.md` | n/a | **Consistent.** | None. |

## 2. Correction to what I told you earlier

I said I found no equivalent of the 180° / continuity checks. That was wrong. After reading `backend/previz/engine/continuity.py`, Dreambox already checks, pairwise between neighbouring shots: the 180° line, screen-direction reversal, jump cuts, near-identical lenses, conflicting camera moves, camera-height jumps, environment changes inside a scene, and a subject jumping sides of the frame. The difference is the *model*:

| | Previz continuity | Craftbox continuity |
|---|---|---|
| Subject | **One** subject per shot; the 180° side is derived from the camera azimuth relative to that subject | **Two or more** characters; the axis is the line between the first two |
| Neutral shots | Not modelled: any side change warns | A shot on the axis allows the crossing; a flagged "motivated" move also allows it |
| Eyelines between characters | None found | Reverse singles must face opposite ways on screen |
| Script link | None | Every beat and dialogue line must be covered; each shot has a purpose |
| Blocking across beats | None | Teleporting, double entrances and re-appearing after an exit are errors |
| Repairs | *Flip Shot*, *Move Camera* | None (advice only) |

Net: for **single-subject camera continuity** Dreambox is ahead and Craftbox should not compete. For **dialogue scenes with two or more people, script coverage and blocking**, Craftbox adds checks Dreambox does not have.

## 3. What Dreambox contains (inventory with file references)

**Screenwright** (`backend/screenwright/`, API `/api/screenwright/...`, page `#/screenwright`, status `docs/screenwright-status.md`, `docs/idea-gater-status.md`)
- `gate.py`: six dimensions, 20 criteria (1.1-6.3), a fixed list of 28 devices, scoring (yes/partly/no → dimension score → rank, thresholds 0.75 / 0.35 / 0.25, guesses by their own admission), history, "stale" detection by brief hash. Not offered for micro or music-video kinds.
- `bank.py`, `project.py`, `coverage.py`, `interview.py`, `brief.py`: 518 template questions, `story-project.md` with `ID | src | answer` lines, brief extraction with quote verification, next-question interview.
- `outline.py`, `screenplay.py`, `checks.py`, `derive.py`: step outline with code checks, scene-by-scene AI drafting with format lint and a rewrite, mechanical checks (running time ±10%, setups/payoffs, bible locations, Never-show scan), judgement checks through the chosen tool, table read, lock, `history/screenplay-vNN.md`.
- `cards.py`, `shotcards.py`, `handoff.py`: scene cards, dialogue table, breakdown, cost estimate; deterministic shot cards (pacing → shots per scene; wide opening shot for a new place; close-up with push-in at an emotional jump; no repeated angle/movement; vocabulary shared with Previz); **hand-off that creates NEW Scene Maker scenes** (never edits existing ones) and writes `handoff.json`.
- `cast.py`, `novel.py`, `unfinished.py`, `folder.py`, `adapt.py`, `chapters.py`, `summaries.py`: cast, novel adaptation, half-written novels, folder runner **[verify details]**.
- Isolation contract: only `ALLOWED_IMPORTS` seams (`backend.ai`, `backend.director.llm`, `backend.scene_maker`, `backend.previz`, `backend.venice`, `backend.creative`, `backend.core`), enforced by `tests/test_screenwright_isolation.py`; data under `<data folder>/screenwright/<project>/`.
- All AI steps have an estimate → `confirm: true` → run flow and offline fakes (`DREAMBOX_FAKE_LLM=1`). Dreambox's own status says none has been run with a real tool yet.

**Scene Maker** (`backend/scene_maker/`, API `/api/scene-maker` with 73 routes, page `#/scene-maker`, status `docs/scene-maker-status.md`)
- Scene file `scene.json` (`schemaVersion` "1.0.0"; `store.blank()`): `brief`, `direction`, `production`, `characters[]` (with `looks[]`: name, outfit, locked, refs, approved), `location` (name, description, lighting, time, weather, refs), `props[]`, `shots[]`, `dialogue[]`, `timeline`, `comments`, `continuity {in, out, facts, ideas}`, `reviewVersions`, `source` (set by the Screenwright hand-off).
- Revisions: every save is the next `revision`; `expected_revision` mismatch raises `REVISION_CONFLICT`; each old revision is kept in `history/rev_N.json`.
- Shot (`shots.new_shot`): `shotType` (13 values), `coverageRole` (8), `priority` (essential/useful/optional), `plannedFrames`, `cast[]`, `lookIds[]`, `camera {movement, lens, direction, eyeline}`, `dialogueIds[]`, `keyframePrompt`, `motionPrompt`, `negative[]`, `continuity[]`, `strategy` (7), `status` (12 states), `planApproved`, `locked`, `previz {enabled, shotSpecId, approvedKeyframe, animatic, approved, state}`, `provenance {source, by, at}`. A shot with `locked` or an approved take is never changed by the Director or a bulk action.
- Script reader `script.py`: plain-text, Fountain-like. Dialogue lines are matched by **(speaker, text)** and only *added*, never removed.
- Not built, per its own status: cross-scene or film-level continuity, OpenTimelineIO, Fountain beyond plain-text conventions, speech synthesis or lip-sync, real-provider video clips.

**Previz Generator** (`backend/previz/`, API `/api/previz`, page `#/previz`, status `docs/previz-status.md`)
- Shot JSON with one subject (`position`, `height_m`, `facing_degrees`, `head_degrees`, `pose`, `motion`), camera (8 sizes, 11 angles, 17 movements, lens/sensor/field of view), 10 environments (incl. railway platform, cafe, train interior), 9 light presets, 16 prop types, modes BLOCKING / REFERENCE_CARD / 2_5D.
- Outputs: frames, camera options, keyframes with metadata, animatic, storyboard PNG/PDF.
- `engine/coverage.py`, `engine/continuity.py`, `engine/breakdown.py` (text → shots, keyword-based, English only).
- `scene_maker/previz_link.py::map_shot` builds a previz shot from a Scene Maker shot's **own words** (`shotType` → size/angle, `camera.movement` / `.direction` / `.eyeline` / `.lens` text, place, time of day), so any Scene Maker shot becomes previz-able without a bespoke adapter.

**Other relevant modules** (read only at heading level): `backend/creative/` (the one asset library and catalog), `backend/labs/looklab.py` (Look Lab: colour-grade and lettering variants for lyric/title frames, **not** film looks), `backend/plan_history.py` (snapshot and diff of music-video plans), `backend/ai/` (tool choice layer), `backend/references.py`, `backend/locations.py` **[verify both]**.

## 4. Detail on the main overlaps

### 4.1 Story Lab vs the idea gate

Both derive from the same checklist (`guidelines/StoryIdeaEvaluationChecklist.md` on the Dreambox side, `guidelines/story-process.md` on this side).

| Craftbox Story Lab item | Dreambox gate criterion |
|---|---|
| Five pillars (setting, characters, core conflict, plot, theme) | 1.1 |
| Minimal narrative test | 1.2 |
| Master plot arc | 6.1 (and 1.3, trajectory) |
| Canonical script breach | 2.1 |
| 15-second hook (timing checked against the script) | 2.2 |
| Defamiliarization lens | 2.3 |
| Vulnerability calibration | 3.1 |
| Empathy target (bounded / ambassadorial / broadcast) | 3.2 |
| Agency and effort | 3.3, 4.4 |
| Consciousness representation | 3.4 |
| Unity of opposites | 4.1 |
| Expectation gap | 4.2 |
| Information gap | 5.1 |
| Subtext / iceberg (dialogue density checked against the script) | 5.2 |
| Labov's six elements; story circle (beat order checked) | 6.2, 5.3 ("so what?"), 6.3 (price paid) |
| Phase 6: draft, outside feedback, polish, flight-simulator verification | **No gate criterion.** Dreambox judges the idea; its nearest counterparts are the screenplay checks, table read and lock |

19 of the 20 criteria are covered; only 4.3 (tension, trust and curiosity together) has no Craftbox item.

Different in kind: Dreambox **judges** an idea with an AI and scores it; Craftbox is a **worksheet** the writer fills in, with advice. They are complements in principle (answers first, judgement second), but not complementary enough to justify maintaining both. Possible later bridge: pre-fill the Dreambox story bank from Craftbox answers **[verify bank section IDs before promising this]**.

### 4.2 Screenplay authoring

| | Dreambox | Craftbox |
|---|---|---|
| How it is written | AI drafts scene bodies one sequence at a time; one scene can be changed by hand (`PUT .../screenplay/scene/{sid}`); locked scripts cannot be redrafted | Manual, line by line, every line has a permanent ID |
| Versions | `history/screenplay-vNN.md` at lock; Scene Maker revisions | Every save is a revision with a parent link and comparison |
| Timing | Planning figures 205 / 250 / 300 words per page | 2.7 spoken and 3.2 action words per second, per line and beat |
| Change tracking | Locked-story-item conflict (`LOCK_CONFLICT`) stops drafting | Script line and beat hashes drive per-shot impact |
| Readable format | Plain-text conventions only | Fountain-style export/import that keeps scene and character IDs |

## 5. Integration design notes (for CB5; nothing here is built)

### 5.1 The importer lives inside Dreambox

Follow the Screenwright pattern. A small isolated package (for example `backend/craftbox_import/`) with:
- an `ALLOWED_IMPORTS` list limited to `backend.scene_maker` and `backend.previz` (plus `backend.core`), and an isolation test like `test_screenwright_isolation.py`;
- data under `<data folder>/craftbox_import/`, never inside another feature's folder;
- **dry run first** (what would be created, the mapping, the warnings, nothing written), then **staging** (NEW scenes only, as `screenwright/handoff.py` does), then a human confirmation; a feature flag; a recorded rollback (archive the created scenes; Scene Maker has `archive`);
- idempotency keyed on the manifest: put `{"app": "craftbox", "manifest_id", "manifest_sha256", "scene_hash"}` in the scene's `source`, and refuse or report a duplicate. Note that Screenwright's own hand-off is **not** idempotent (it creates new scenes every time), so this must be added, not copied.
- refuse unless: both schema ids and versions are known, `manifest_sha256` re-computes, `approval.status` is approved or exported, `import_policy.auto_import` is false, and the scene hash in the shot manifest equals the scene manifest's.

### 5.2 Field mapping: Craftbox manifests → Scene Maker

Scene manifest (`filmcraft.scene_manifest.v1`) → `smstore.blank(...)`:

| Craftbox | Scene Maker |
|---|---|
| `project.title` + `scene.id` | `name`, `code` (from the scene id) |
| `scene.synopsis`, `scene.objective`, `scene.outcome` | `brief.synopsis`, `brief.objective`, `brief.endState` |
| `scene.estimated_seconds`, `scene.fps` | `brief.targetSeconds`, `fps` |
| `interpretation.tone`, `interpretation.visual_motifs` | `direction.mood`, `direction.visualStyle` |
| `approach.name` / pace | `direction.cameraStyle` / `direction.pace` **[verify allowed values]** |
| `scene.heading.location`, `.time` | `location.name`, `location.time` |
| `scene.props[]` | `props[]` **[verify prop shape]** |
| `characters[]` | `characters[]`: `name`, `role`, `description` (+ one default look) |
| dialogue `elements[]` | `dialogue[]` (`speakerId`, `text`, `note` from a parenthetical); matched by (speaker, text), see gotcha 3 |
| `blocking`, `stage` | no Scene Maker field; keep under `scene["craftbox"]` for reference and previz seeding |
| `source.manifest_id`, hashes | `source` |

Shot manifest (`filmcraft.shot_manifest.v1`) → `smshots.new_shot(...)`:

| Craftbox shot | Scene Maker shot |
|---|---|
| `size` + `framing` | `shotType`: ECU→`extreme_close_up`, CU→`close_up`, MCU→`medium_close_up`, MS→`medium`, MWS→`master`, WS→`wide`, EWS→`establishing` (the same table `screenwright/handoff.py` uses); `framing` `over_shoulder`→`over_the_shoulder`, `two_shot`→`two_shot`, `insert`→`insert` override |
| `purpose` | `coverageRole`: establish→`establishing`; connect, emphasize_emotion→`dialogue`; reaction→`reaction`; reveal, insert_detail→`insert`; show_distance, follow_movement, closure→`master` or `cutaway` **[decide]**; transition→`transition` |
| `duration_frames` | `plannedFrames` |
| `subject[]` | `cast[]` (character IDs created by the scene import) and `lookIds` via `default_looks` |
| `movement`, `lens_mm`, `angle`, blocking eyeline text | `camera {movement, lens: "50 mm", direction, eyeline}`; these words are what `previz_link.map_shot` reads |
| `storyboard.description`, `purpose_note`, beat title and emotion | `action`, `beat`, `emotion`, `keyframePrompt` |
| `continuity.issues` for the shot | `continuity[]` |
| `status: approved` | `planApproved: true` (leave `locked` false unless the user locks it) |
| beat intensity ≥ 8 | `priority: essential` (like Screenwright's HERO tag) |
| shot id, `covers`, `beat_id`, `manifest_id` | `provenance {"source": "craftbox", "by": shot_id}` and `shot["craftbox"] = {...}` (mirrors `shot["screenwright"]`) so a later re-import can match shots |
| `previz.*` | do not copy raw; let Dreambox's *Configure Shot* build the previz shot from the words |

### 5.3 Gotchas found while reading (fix on whichever side is cheaper)

1. **Heading suffix.** Craftbox's readable script writes `INT. PAGE & CANDLE BOOKSHOP - NIGHT #SC-001#`. Scene Maker's `HEADING` regex captures everything after ` - ` as the time, giving `night #sc-001#`. Add a "plain" export flavour (no scene-number suffix) or have the importer strip it.
2. **Extra lines become action.** The title page (`Title:`, `Project-ID:`, `Characters:`), `= synopsis` lines and `[[objective: ...]]` notes would be read as ACTION or NOTE blocks. The plain flavour should omit them; the structured scene manifest carries that information anyway.
3. **No ID round trip for dialogue.** Scene Maker keys dialogue by (speaker, text) and assigns its own `dlg_` and `blk_` IDs, so Craftbox element IDs do not survive. The importer must keep its own table (element ID ↔ `dlg_…`), matched by speaker and text and falling back to order.
4. **Additive only.** `merge_into` never removes lines, so re-importing a revised script into the same scene accumulates old lines. Use a new scene per import (the Screenwright pattern) and link by `source`.
5. **Names.** Scene Maker title-cases cue names (`NILA` → `Nila`); characters are matched case-insensitively, which is compatible.
6. **Frame rates.** Both use 24 fps by default; `previz_link` falls back to 24 for unusual rates.
7. **Vocabulary is closed.** Scene Maker rejects unknown `shotType` / `coverageRole` / `strategy` values (see `shots.py` constants), so the mapping must be total.

## 6. What this means for CB2

The roadmap's CB2 is: `art_direction`, `lighting`, `costume`, `casting`, "basic appearance consistency checks"; **gate**: two scenes with the same character at different times of day, a deliberately changed outfit or prop is caught, a legitimately approved change is not flagged.

Dreambox already has, per scene: characters with **looks** (outfit, locked, approved, references), a **location** (lighting, time, weather), **props**, a scene-level `continuity {in, out, facts, ideas}`, Previz environments and nine light presets, and the Creative asset library. It explicitly lacks **cross-scene and film-level continuity**.

Recommended CB2 scope, in order of value:
1. **Cross-scene continuity checker (the gap).** A project-level bible of *states* (a character's outfit, hair/makeup, injuries and carried props per scene; set dressing; lighting and time of day), with a checker that flags an unapproved change between consecutive scenes and accepts an approved one. This is the only roadmap item where Dreambox is demonstrably empty.
2. **Thin editors only for the data the checker needs.** Do not build full art-direction, lighting or wardrobe tools that Previz, the Creative library and Scene Maker's looks already own.
3. **Export to Dreambox's own fields**: `characters[].looks[]`, `props[]`, `location.lighting`, `continuity.in/out/facts`.
4. **Skip for now:** a lighting designer (Previz presets), look boards (Look Lab and the Creative library), casting and likeness work beyond a consent/reference record (rights need a Dreambox-side decision; Scene Maker's characters already carry `rights`).

Before building each CB2 craft, repeat §3's check for that craft (30 minutes): list the Dreambox module, say what it lacks, and build only that.

## 7. Open questions (answer before CB5, or before CB2 where noted)

1. Should the **Story Lab** be deleted, frozen or kept as an offline fallback? (This audit recommends freeze.)
2. Is a **manual, ID-stable screenplay editor** wanted in Dreambox at all, or is Craftbox the only place for it? That decides whether the importer needs to handle revisions of an already-imported scene.
3. How should `purpose` map to `coverageRole` for `follow_movement`, `show_distance` and `closure` (§5.2)?
4. Does Dreambox want **blocking** (paths, entrances) as a new Scene Maker field, or is it reference-only?
5. For CB2: is a **project-level continuity bible** acceptable as a new Dreambox feature, or should it stay a Craftbox report that only writes `continuity.facts`?
6. **[verify]** exact shapes of Scene Maker `props`, `direction.pace`/`cameraStyle` allowed values, `location.lighting`; `references.py` / `locations.py` roles; Ideator (not audited at all).

## 8. Limits of this audit

- Read: `screenwright/gate.py` (criteria), `handoff.py`, `scene_maker/store.py`, `shots.py`, `script.py`, `previz_link.py::map_shot`, `previz/engine/continuity.py`, the status documents for Screenwright, the idea gate, Scene Maker and Previz, and the API reference route list. Skimmed by name or heading only: everything else in §3 marked **[verify]**.
- Nothing was executed; Dreambox's tests were not run. Dreambox's own status says several AI paths have only been exercised with offline fakes.
- Ideator was not audited.
- Dreambox may have changed since 2026-11-01. Refresh with: `grep -rn "continuity\|coverage" backend/previz/engine`, `grep -n "SHOT_TYPES\|COVERAGE\|STRATEGIES" backend/scene_maker/shots.py backend/scene_maker/store.py`, and `ls backend/screenwright`.
