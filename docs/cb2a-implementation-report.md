# CB2A implementation report: Art Direction Lab

Scope: **CB2A only**. Lighting, Costume, Casting and Dreambox integration are not started. Dreambox (port 8000) and Ideator were not touched, restarted or called; Craftbox stays on `127.0.0.1:8099`.

## 1. Summary

Two new tabs, **Art Lab** (an 8-step wizard for one scene) and **Art Library** (project-level style profiles and the asset register). A *treatment* is one complete design of a scene: location, set layout, props, visual style. The Closing Hour has two sample treatments, **A "Warm nostalgia"** and **B "Emotional distance"**, built on the same unchanged screenplay, each editable, reviewable and approvable on its own.

Everything is rule-based and deterministic: no AI, no network, no images are rendered.

| Step | What the user does |
|---|---|
| 1 Scene | Pick the project, scene, optional direction plan, and a starting point (preset, blank, or a saved style profile); name and draft the treatment |
| 2 Location | Name, interior/exterior, real/fictional, description, period, constraints; checked against the script's slugline |
| 3 Set layout | 2D top-down editor on the CB1 stage (0..1 coordinates). Drag or arrow-key to move; edit size, kind, solid flag; actors and cameras from the blocking are shown, the 180° line is drawn |
| 4 Props | Extracted from the script (with the lines and shots that mention them) plus a manual inventory; position, per-beat or per-shot states, continuity checks, add/remove/edit |
| 5 Visual style | Palette, textures, materials, period, themes, shot variations (which keep the overall style and say what differs), asset references |
| 6 Comparison | Two treatments side by side: palettes, layouts, measures, a plain statement of how each is likely to feel and "because:" the number it rests on |
| 7 Review | Submit, approve or reject (CB0 approval), per-item approval, change impact, rebase |
| 8 Export | Working exports always; manifests only after approval, with an explicit recorded override for advice |

## 2. Baseline

The baseline run before CB2A work passed (the figure recorded at the time is not in my notes; the pre-existing suites now total 146 tests, 111 backend and 35 browser, after the small count adjustments in section 3). Final: **195 tests, all passing** (see section 6).

## 3. Compatibility decisions (please confirm)

1. **Schema ids keep the `filmcraft.*` prefix**, matching CB0/CB1: `filmcraft.art_direction.v1`, `.style_profile.v1`, `.asset_register.v1`, `.art_direction_manifest.v1`, `.asset_reference_manifest.v1`, `.storyboard_metadata.v1`. Existing schemas and APIs are unchanged; everything is additive.
2. **One craft, three modes.** `art_direction` is a single craft whose manifest declares `modes` (treatment, `style_profile`, `asset_register`); the payload `schema` selects the input and output schema. Style profiles and the register therefore use the same experiment/run/approval/history machinery as everything else, with no new tables beyond reusing CB0's `derived_exports` for manifests.
3. **Layout coordinates are CB1's stage coordinates** (x left→right, y back wall→audience, camera side A = audience), so a design can be laid over the blocking without conversion.
4. **Design is tied to permanent ids**: scene id, beat ids, element ids, shot ids, and the CB1 stage object ids. Source hashes (scene, beats, elements, plan, blocking) are stored in the treatment, which is how outdated designs are detected.
5. **Approval is on the run (CB0)**, so approving Treatment A never touches Treatment B. A new version of a treatment is a new experiment with a parent link; the approved one is never overwritten.
6. **Asset files live in a content-addressed store** (`data/assets/<sha[:2]>/<sha>.<ext>`). Only PNG, JPEG, GIF and WebP (by magic bytes, not by file name), up to 8 MB, no SVG; served with `nosniff`. The register records source, owner, licence, rights status and allowed usage. Files are never uploaded anywhere.
7. **Dreambox mapping is prepared, not performed.** Manifests carry `import_policy.auto_import = false` and a note that a Dreambox-owned adapter must validate and stage the import.
8. **Advice never blocks work.** Findings (`attention` / `note`) never disable Save. Only manifest exports are gated (approval is required), and the advice-type conditions can be overridden by an explicit choice that is written into the file (`acknowledge_stale`, `allow_open_findings`, `allow_pending`).
9. Exports are cached per run and kind (CB0 behaviour): asking again returns the earlier file, never a new one.
10. The generic **single-craft wizard still lists 23 crafts, 5 ready** (Art Direction is the fifth pilot); two existing tests were adjusted accordingly (`test_cb0_api`, `test_cb1_api` counts, and `test_browser` card selectors scoped to the New-experiment view because Art Lab uses the same card style).

## 4. What was built

**Engine** (`app/crafts/art_direction/`): `layout.py` (geometry, presets, colour maths), `props.py` (extraction from the script with a small vocabulary), `treatment.py` (draft from preset, normalise, source blocks), `analysis.py` (findings, measures, readings), `impact.py` (what changed since the design was made, rebase), `exports.py`, `engine.py` (`run`, `run_style`, `run_register`).

**Checks that produce advice**: entrance or exit object missing from the layout; an object standing on an actor's blocking path; set pieces overlapping; heading says INT./EXT. but the layout disagrees; the script mentions a prop or a piece of architecture the design lacks; a prop marked gone that reappears, or shown in a shot after it was gone; palette uses a word the project avoids, or lacks a required one; asset with open rights or a missing file.

**Change handling**: a script change flags only the props and items whose script lines changed; a change to the direction plan's blocking flags the layout. Rebase creates a new treatment version: affected items become `needs_review` (the earlier status is kept in `previous_status`), everything else keeps its approval, and the original is left untouched.

**Treatment readings** are explicit measures (palette warmth, brightness, saturation, objects in the middle of the stage, personal props, gap and obstructions at the peak of the scene), each shown with a "because:" line. They are rule-based, and the report does not claim they predict an audience.

**Exports** (all validated against their schema before being returned):
- `art-direction-json`, `prop-list-csv`, `storyboard-metadata`: always available.
- `art-direction-manifest`, `asset-reference-manifest`: approved treatments only, with sections prepared for Lighting, Costume, Cinematography and Dreambox Scene Maker (`integration`), a previz hint per shot, and the recorded `overrides`.

**API (additive)**: `GET /api/art/presets`, `GET /api/art/projects/{id}`, `POST /api/art/draft | save | analyze`, `GET /api/art/treatments/{id}/impact`, `POST /api/art/treatments/{id}/rebase`, `GET /api/art/compare`, `GET /api/art/styles`, `GET /api/art/assets`, `POST /api/assets/upload`, `POST /api/assets/from-path`, `GET /api/assets/{sha}/file`. Exports go through the existing `POST /api/runs/{id}/exports/{kind}`.

## 5. The test scenario: "The Closing Hour"

Screenplay unchanged; both treatments drafted from it and from the sample intimate direction plan.

| | A: Warm nostalgia | B: Emotional distance |
|---|---|---|
| Palette | Aged oak, candlelight amber, faded cream, oxblood leather, moss green | Pale ash, slate blue, cold white, graphite, steel grey |
| Layout | Furnished: armchair, rug, lamp, photographs, stacked books; shelf and counter as the script describes | Open: bench, floor lamp; shelf scaled to 0.55, counter shifted 0.10 |
| Palette warmth | +0.26 | −0.06 |
| Average saturation | 0.45 | 0.12 |
| Objects in the middle of the stage | 5 | 0 |
| Personal props | 3 (tea cup, reading glasses, framed photograph) | 0 |
| Reading | "intimate and remembered", "lived in", "shared history" | "detached and quiet", "restrained", "space between people reads as distance" |

Samples in `samples/art/` (regenerate with `scripts/make_art_samples.py`): per treatment the art direction JSON, storyboard metadata, prop list CSV, art direction manifest and asset reference manifest, plus the A-vs-B comparison. Treatment A references one registered picture (a generated 8×8 swatch).

## 6. Test results

| Suite | Tests | Result |
|---|---|---|
| CB0 API, CB1 engines/API/samples, base engines | 111 | pass |
| `test_cb2a_engines.py` | 19 | pass |
| `test_cb2a_api.py` | 14 | pass |
| `test_cb2a_samples.py` | 5 | pass |
| Browser: single-craft, Scene Lab, Story Lab | 35 | pass |
| `test_browser_art.py` (Art Lab + Art Library) | 11 | pass |
| **Total** | **195** | **pass** |

(The last full run covered 190 tests; the 5 sample tests were added after it and pass on their own.) Browser tests start a fresh server and database per test on a free port. They never use 8000 or 8099 or your `data/` folder.

Failures met and fixed while building: the glossary check found jargon without a gloss (fixed with a per-screen "Words used on this screen" built from the words actually on the screen); a Save button that stayed disabled after typing in the Art Library; the old browser test counted cards across all tabs; several test expectations were wrong (a clean treatment has nothing pending to override, so the override path is tested with a changed script, and exports are cached per run).

## 7. UI Text Compliance

**Guidelines applied.** `guidelines/ui-standard.md` was read in full from disk (48 lines) before implementation. A checklist was written first: `docs/cb2a-ui-text-checklist.md`. The standard covers behaviour and structure (U1-U9), **not** tone, wording or terminology, so those choices are mine and are marked as such in the checklist.

**Screens inspected.** All 8 Art Lab steps with the warm sample, and both Art Library steps, were rendered in Chromium and checked by the automated checks below. I looked at screenshots of steps 3 (set layout) and 6 (comparison, empty state) by eye. I did **not** look at every step in every state (invalid, stale, rejected, mid-upload).

**Automated checks done** (`assert_ui_contract` plus the new `assert_ui_text`, run on every step the browser tests reach):
- U1: title reads `Step N of M: …` with something after the colon; Back/Next present where required and labelled `Back:` / `Next:`; the last step ends with explicit destination buttons.
- U2: at most one Save per form and per screen.
- U3: every Save screen shows a state line.
- U5: errors sit inside the card of the action; every disabled button says why.
- U8: each step has an intro of 6-90 words; every empty state contains an action word; each jargon term from a fixed list (`treatment`, `set layout`, `blocking`, `continuity`, `palette`, `previz`, `manifest`, `rebase`, `storyboard`, `beat`, `asset`) that appears on a screen has a gloss on that same screen.
- U4 (input survives a failed save and a reload) and U9 (advice never blocks Save; override is explicit and recorded in the file) are covered by browser and API tests of behaviour, not of text.
- Form fields have associated labels; icon-only controls have names (house choice).

**Manual checks remaining (not claimed as done).** Whether every Next label really names what comes next; whether warnings read naturally and each states problem, reason and recovery; whether the glosses are actually clear to someone who has never seen the app ("read it cold"); the plain-words quality of the intros; keyboard-only use of the layout editor in a real browser session; screen-reader behaviour; contrast of the small SVG labels. The jargon list is a fixed list, so a jargon word not on it is not caught.

**Deviations.**
1. `assert_ui_contract` lives in `tests/ui_contract.py`, not `tests/ui/ui_contract.py` (so `unittest discover -s tests` can import it). Since CB1.
2. The standard names Dreambox helpers (`window.ui`, `W.draft`, `core/jobqueue.py`); Craftbox uses its own equivalents in `app/static/ui.js`. U6's job queue is not built because every action here finishes in milliseconds; the progress panel is still shown and tested.
3. U7 (estimate then confirm) is not applicable: nothing is paid or networked.
4. Draft state is kept in each lab's persisted store rather than `W.draft`.
5. The glossary is a short block at the foot of each step; it is an addition to the standard's "gloss" rule, not a separate requirement.

**Not claimed:** full UI compliance. Automated checks cover only what can be measured objectively; the rest needs a person to read the screens.

## 8. Limitations and not built

- The layout editor is a 2D plan: no rotation, no snapping, no undo beyond reloading the saved version. Labels on a crowded plan can overlap (seen on the warm sample at step 3).
- Prop extraction uses the scene's own prop inventory plus a small fixed vocabulary of everyday objects; anything else must be added by hand. It does not understand pronouns or implied objects.
- Readings are a handful of rules over palette and layout; they do not judge lighting, texture, scale or lens.
- No rendering, no image generation, no thumbnails of the design. Uploaded pictures are only registered and displayed.
- Rights fields record what the user says; nothing verifies a licence.
- One scene per treatment. Cross-scene continuity (the same room in two scenes, or a prop that travels) is recorded per prop but only checked within a scene. This is the natural subject for CB2B.
- The two manifests are not consumed by anything yet; Lighting, Costume and Cinematography sections are placeholders prepared from the data we have.
- Exports are cached per run: to change one, save a new version.
- Version number was not bumped (still 0.3.0).

## 9. What needs your manual verification

See `docs/cb2a-acceptance-checklist.md`. Highest value: read the eight steps cold; drag and keyboard-move pieces on the layout; approve Treatment B and confirm A stays in draft; change the script and watch both the warning and the rebase; try an export before and after approval.

## 10. Recommended next steps

1. Review and confirm the compatibility decisions in section 3.
2. Walk the acceptance checklist, then decide whether to bump the version to 0.4.0.
3. CB2B: cross-scene continuity (locations and props that span scenes), the gap identified in `docs/dreambox-overlap-audit.md`, before Lighting and Costume.
4. When integrating with Dreambox, write the Dreambox-side adapter against the manifests; keep `auto_import` false.
