# CB2B implementation report: Lighting Lab

Scope: **CB2B only**. Costume, Casting and Dreambox integration are not started. Dreambox (port 8000) and Ideator were not touched; Craftbox stays on `127.0.0.1:8099`.

## 0. How this report was produced (read first)

When this session began, a near-complete CB2B implementation was already on disk (engine, service, API routes, browser UI, schemas and three test files), left by an earlier session with no report, no samples and no docs, and with 3 failing browser tests. I treated it as the starting point rather than rewriting it. In this session I: ran the baseline, reviewed the code, fixed what the tests exposed (section 6), generated the samples and sample tests, reviewed the editor visually, and wrote the docs. I did not re-derive every line of the earlier work, so the backend behaviour is evidenced by its tests (section 5) rather than by my own line-by-line audit.
Inputs read: the roadmap, `ui-standard.md`, the CB2A report and acceptance checklist, and the CB2B source. I did **not** read the CB1 implementation report in full; CB1 behaviour was checked through its passing tests and through how CB2B consumes it.

## 1. Baseline and CB2A outstanding items

- Baseline at start: 240 tests, 237 passing, 3 failing (all in `test_browser_light.py`, the new Lighting Lab tests). The 195 pre-CB2B tests passed.
- CB2A outstanding items: every box in `docs/cb2a-acceptance-checklist.md` is still unticked (manual review is yours). **No blocker for CB2B**: the Lighting Lab only reads art treatments. The CB2A manual UI-text review (section 7 there) remains owed, and the Lighting Lab inherits any wording problems in shared pieces (for example the glossary pattern).
- The CB2A report named cross-scene continuity (same room across scenes) as the natural CB2B subject. The CB2B brief asked for Lighting instead; cross-scene location/prop continuity was **not** built (see section 9).

## 2. What exists

A **Lighting Lab** tab: an 8-step wizard for one scene. A *lighting plan* is one complete lighting design of a scene; each plan is lit for one art treatment and uses the director's plan for actors, shots and cameras.

| Step | What the user does |
|---|---|
| 1 Scene | Pick project, revision, scene, art design, director's plan, and a starting point (preset, blank, or a saved setup); open saved plans |
| 2 Conditions | Time of day, weather, mood words, narrative purpose; checked against the art design |
| 3 Lights | Top-down editor on the art layout: drag to move, drag the arrow handle to turn, keyboard (arrows, `[` `]`), numbers for every parameter; glow, cones, shadow arrows, actors, cameras |
| 4 Shots | Per-shot changes on top of the shared scene setup; reasons; add a shot-only light; copy changes to other shots; camera wedge |
| 5 Checks | Continuity advice with a stated fix; accept a warning for a shot |
| 6 Comparison | Two plans side by side: layouts, settings table, stated effect with "because:", differences |
| 7 Review | Submit, approve or reject (CB0 approval), per-item approval, change impact, rebase |
| 8 Export | Working exports always; manifest after approval with explicit recorded overrides; save a setup for reuse |

Lights support roles key, fill, backlight, rim, practical, ambient and motivated; natural or artificial source; position, height, rotation, tilt, intensity, colour temperature, beam angle, softness and falloff (inverse-square, linear, none); an optional link to a set piece in the art layout (`motivated_by`, `practical_object_id`).

### Requirement coverage

| Requirement | Where |
|---|---|
| Scene-level and shot-level plans | `lights` (scene setup) plus `adjustments` per shot; shared setup is never edited by a shot change |
| Light parameters, natural/artificial, time, weather, mood, purpose | `filmcraft.light.v1`, `conditions` in `filmcraft.lighting_plan.v1` |
| Interactive editor reusing Art Lab | Overlay on `Art.kit.layoutSvg`; no second layout editor or asset store |
| Zones and shadows, not presented as simulation | Glow and arrows labelled "approximate preview, not a simulation"; every export carries a `model_note` |
| Continuity | Rules in section 4 |
| Two treatments for *The Closing Hour* | Presets `warm_naturalistic`, `cool_dramatic`; samples in `samples/light/` |
| CB1 shot plans and stable ids | Lights and adjustments keyed by scene, beat, shot, light and set-piece ids; source hashes stored |
| Art vs lighting data separated | Lighting files carry only treatment id, name and hash; tested on the samples |
| Revisions, comparison, validation, approval, exports | CB0 experiments/runs/approval and `derived_exports`; no new tables |
| Reuse across shots and scenes; approved versions preserved | Copy-to-shots; `filmcraft.lighting_setup.v1`; rebase makes a new version |

## 3. Compatibility decisions (please confirm)

1. Schema ids keep the `filmcraft.*` prefix: `filmcraft.light.v1`, `.lighting_plan.v1`, `.lighting_setup.v1`, `.lighting_instructions.v1`, `.lighting_manifest.v1`. Existing schemas and endpoints are unchanged; everything is additive.
2. One craft, two modes: `lighting` is a single craft whose manifest declares a `setup` mode (as `art_direction` does). The craft status moves from `planned` to `pilot`; the dashboard now reads **6 ready of 23**.
3. Coordinates are the CB1 stage coordinates (0..1, y from back wall to audience), so no conversion between blocking, art layout and lights.
4. Approval is on the run (CB0): approving one plan never touches another. A new version is a new experiment with a parent link.
5. Advice never blocks work. Manifest export needs approval, and each advice condition (`acknowledge_stale`, `allow_open_findings`, `allow_pending`, `allow_unapproved_art`) needs an explicit choice that is written into the file.
6. A manifest for a plan whose art treatment is not approved is allowed only with `allow_unapproved_art`.
7. Dreambox mapping is prepared, not performed: `import_policy.auto_import = false`; the manifest has `cinematography`, `previz` and `scene_maker` sections, and says Scene Maker's own lighting fields were not audited.
8. Version stays 0.3.0 (not bumped, as in CB2A).
9. The sample plan names are "Warm, naturalistic, intimate" and "Cool, restrained, dramatic". The built-in preset names carry an "A —" / "B —" prefix; the sample names are those given in the brief.

## 4. Continuity checks (advice only)

`colour_jump`, `intensity_jump` and `key_direction_jump` between related shots; `time_of_day_mismatch`, `sun_at_night`, `natural_colour` (light that does not fit the stated conditions); `light_inside_set`, `beam_blocked`, `fixture_in_frame` (set geometry and camera); `practical_moved`, `unknown_object`, `motivation_far`, `light_lights_nothing`, `no_lights`, `no_main_light`, `ratio_extreme`; `moves_into_shadow` and `moves_out_of_light` (an actor's blocking leaves the established light). A stated reason on a shot's adjustment turns a warning into a note ("intended: ..."); an explicit accept is recorded in the plan.

**Upstream change** (`impact.py`): a script change flags only the adjustments of changed beats; a blocking or camera change flags only the shots it touches; an art change flags the lights tied to that set piece. **Rebase** creates a new version: affected items go to `needs_review`, everything else keeps its decision, and the original is untouched.

## 5. The scenario: *The Closing Hour*

Same screenplay and director's plan; each plan lit for its own art treatment. Numbers are from `samples/light/treatments-A-vs-B.comparison.json`.

| | A: Warm, naturalistic, intimate | B: Cool, restrained, dramatic |
|---|---|---|
| Lit for art treatment | Warm nostalgia | Emotional distance |
| Lights on / natural sources | 6 / 1 | 5 / 2 |
| Key light | 2850 K, softness 0.7 | 5200 K, softness 0.25 |
| Average colour temperature | 2842 K | 5245 K |
| Key to fill ratio (people) | 2.0 : 1 (2.6 at the peak) | 4.3 : 1 |
| Share of playing area in shadow | 0 % | 42 % |
| Average level (0-1) | 0.55 | 0.25 |
| Lights with a visible reason | 60 % | 50 % |
| Stated effect | warm, intimate and safe; gentle, even; kind skin; the peak is marked by the light | cool, detached, restrained; deep shadows, guarded; hard edges; space around the people |
| Open findings | 0 | 0 attention, 2 notes |

Each stated effect is a fixed rule over a measure and is shown with a "because:" line. They describe what the lighting is likely to suggest; they do not predict an audience and do not rank the plans. **Whether they feel right is a creative judgment for you.**

Samples (`scripts/make_light_samples.py` regenerates them): per plan the plan JSON, per-shot instructions, light schedule CSV and approved manifest (no overrides needed, because the matching art treatment is approved first); the A-vs-B comparison; one reusable setup.

## 6. Defects found and fixed this session

| Found by | Defect | Fix |
|---|---|---|
| Browser test 07 | In the Shots step, changing a value left "Use the scene setup" and the "Why this shot is different" field stale (the reason box stayed disabled while the hint said to change a setting first) until some later redraw | Redraw, with focus and caret kept, when a field flips between "same as scene" and "changed here" |
| Browser test 07 | After ticking a shot to copy to, "Copy the changes" stayed disabled | Redraw on the tick |
| Visual review | "New light" and "Seems to come from" selects collapsed to a blank sliver beside long hint text | CSS in the Lighting Lab only: select minimum width, hint can wrap |
| Browser test 04 | Test dragged a lamp that was below the visible window | Test scrolls it into view |
| Browser test 04 | Test used Python `round`, which rounds halves to even; the browser rounds up | Test uses floor(x + 0.5) |
| Browser test 01 | Test assumed no art design is pre-selected; the page intentionally pre-selects the newest | Test now asserts the default, then clears it |
| Browser test 01 | Race: opening the tab and Refresh both reload lists and the late one re-applied the default | Test waits for the network to settle (real use is unaffected) |

## 7. Test results

Command: `.venv\Scripts\python.exe -m unittest discover -s tests` (browser tests drive installed Edge or Chrome; fresh server and database per test on a free port, never 8000 or 8099 or your `data/`).

| Suite | Tests | Result |
|---|---|---|
| CB0, CB1, CB2A, Story Lab, base engines and their browser suites | 195 | pass |
| `test_cb2b_engines.py` | 22 | pass |
| `test_cb2b_api.py` | 12 | pass |
| `test_cb2b_samples.py` | 8 | pass |
| `test_browser_light.py` | 11 | pass |
| **Total** | **248** | **pass** (100 s) |

Coverage of the brief: light positioning, rotation and saved parameters (engine manual-positioning test; browser 04 and reload); shot continuity (engine continuity tests; browser 08); blocking and camera changes (engine impact tests, API upstream tests); alternative treatments and independent approval (API lifecycle, browser 09); approval preserved through rebase (API upstream, browser 11); exports, validation and overrides (API export tests, browser 10, samples).

## 8. UI text compliance summary

**Standard.** `guidelines/ui-standard.md` was read in full. It governs behaviour and structure (U1-U9), not tone or terminology, so wording beyond those rules is my own choice, not a requirement. The CB2A checklist (`docs/cb2a-ui-text-checklist.md`) was reused, since the rules are unchanged.

**Automated, run on every step the browser tests reach** (`assert_ui_contract`, `assert_ui_text` with a Lighting jargon list added):
- U1: `Step N of 8: ...` title; Back and Next on every step except first and last; labels start `Back:` / `Next:`; last step has explicit destination buttons.
- U2/U3: one primary Save per form; a state line ("Saved." / "Changed, not saved yet.") beside it; typing survives a failed save (test 06) and a reload (tests 03, 04).
- U5: errors inside the card of the action (`error-draft`, `error-save`, ...); every disabled button states why.
- U8: each step has an intro; empty states contain an action; jargon on screen (blocking, beat, lighting plan, motivated, colour temperature, beam angle, softness, falloff, key light, scene setup, shot adjustment, ...) has a same-screen gloss built from the words actually shown.
- U9: advice never disables Save; every override is a visible control and is written into the export.

**Looked at by eye** (screenshots in Chromium at 1280 px): steps 3 (both treatments), 4 and 6. I did not look at steps 1, 2, 5, 7 and 8 by eye this session, nor at error, stale, rejected or mobile-width states. The first screenshots exposed the select defect in section 6; I re-ran the capture after the fix and viewed steps 4 and 6 only.

**Not checked / remaining for a person:** whether each Next label really names the next step; whether warnings read naturally and state problem, reason and fix; whether the glosses make sense cold; keyboard-only use of the editor in a real session; screen-reader behaviour; contrast of the small SVG labels. The jargon list is fixed, so a jargon word not on it is not caught. Spelling is British ("colour", "metres"), a house choice.

**Deviations** (same as CB2A): `assert_ui_contract` lives in `tests/ui_contract.py`; Craftbox uses its own `app/static/ui.js` instead of Dreambox's `window.ui`/`W.draft`; U6's job queue is unused because every action finishes in milliseconds (the progress panel is still shown); U7 does not apply (nothing is paid or networked). New this milestone: none.

**Not claimed:** full UI compliance.

## 9. Limitations and not built

- The shadow arrows and glow are a quick geometric preview (direction, beam, softness, falloff, solid set pieces). No light bounce, colour mixing beyond a weighted average, real shadow casting, exposure or lens response. They must not be read as a render.
- Plan labels overlap on a crowded layout (seen on the warm sample); the warm plan's overlapping beam cones are busy. No zoom, snapping or undo beyond reloading the saved version.
- Cross-scene lighting continuity is limited to what a reused setup carries; there is no check that the same room is lit consistently across two different scenes, and no cross-scene location/prop continuity (the CB2A recommendation).
- Time-of-day and weather rules are a small fixed set (for example sunlight at night). There are only three starting presets (warm naturalistic, cool dramatic, blank); anything else is built by hand.
- Light data was mapped to Dreambox/Scene Maker/Previz by design only; Scene Maker's own lighting fields were not audited, and no adapter exists.
- Exports are cached per run and kind (CB0 behaviour): to change one, save a new version.
- Creative judgment (does it look good, is the mood right) is not measured by anything here.

## 10. Needs your manual review

`docs/cb2b-acceptance-checklist.md`. Highest value: place and drag lights on the warm and cool plans and ask whether the glow and shadow arrows are a useful sketch; read the comparison cold; approve B only; revise the script and watch the warning and the rebase; read all eight steps against your own wording standard.

## 11. Recommended next steps

1. Confirm the compatibility decisions (section 3) and walk the CB2A and CB2B checklists.
2. Cross-scene continuity (location, props, lighting) for two scenes in the same room at different times of day, which is also the CB2 roadmap gate.
3. Then Costume and Casting, reusing the same art/lighting separation and manifest pattern.
4. Before any Dreambox work, audit Scene Maker's lighting fields and write the adapter on the Dreambox side against the manifests; keep `auto_import` false.
