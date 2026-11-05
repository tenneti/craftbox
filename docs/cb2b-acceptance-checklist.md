# CB2B acceptance checklist: Lighting Lab

Start Craftbox (`start-craftbox.bat`), open `http://127.0.0.1:8099`, then open the **Lighting Lab** tab. Dreambox on port 8000 is not needed and is not used.
Tick each box yourself; the automated tests do not replace this. Items marked **(text)** are the manual part of the UI text review. Items marked **(creative)** are judgments no test can make.
Prerequisite: load the sample scene in the Scene Lab, make a director's plan, and draft the two Art Lab treatments (Warm nostalgia, Emotional distance).

## Automated (already passing, 248 tests)
- [x] Engines: presets, roles and parameters, geometry, shot adjustments, continuity rules, change impact, rebase, setups, exports (22)
- [x] API: independent plans per treatment, comparison, validation, upstream change, gated exports, setup reuse (12)
- [x] Samples valid, inert, art data not copied into lighting files (8)
- [x] Browser: all 8 Lighting Lab steps with the structure and text checks, drag/keyboard/number editing, persistence after reload (11)
- [x] CB0, CB1, CB2A and Story Lab suites unchanged and passing (195)

## Outstanding from CB2A (not yet ticked by you)
- [ ] `docs/cb2a-acceptance-checklist.md` sections 1-8 are all still unticked. None blocks CB2B (the Lighting Lab only reads approved or draft treatments), but the CB2A manual text review (section 7) is still owed.
- [ ] Decide whether the version stays 0.3.0 (it was not bumped for CB2A or CB2B)

## 1. Start a plan (step 1)
- [ ] Both art designs appear in "Art design to light"; the newest is pre-selected
- [ ] With the choice cleared, "Draft the lighting plan" explains what to choose, beside the button **(text)**
- [ ] Drafting "Warm, naturalistic, intimate" for Warm nostalgia unlocks Next
- [ ] Reload: you land back on the same plan

## 2. Conditions (step 2)
- [ ] Set time of day to "Day": the check says the art design says night, and how to fix it
- [ ] Mood words and narrative purpose are kept after Save and reload

## 3. Lights and the layout (step 3)
- [ ] The plan shows the art layout, the actors, the cameras, the 180° line, the glow and the dark shadow arrows
- [ ] Drag a light; drag the small circle on its arrow to turn it; select it and use the arrow keys (Shift for bigger steps) and `[` `]` to turn it
- [ ] Edit kelvin, intensity, beam, softness, height, falloff by number; Save; reload; values are back
- [ ] Add a rim light, drop it on the counter: advice that it stands inside a set piece, and Save still works
- [ ] Move the lamp light away from the lamp: advice that a practical should sit on its lamp
- [ ] **(creative)** Does the glow look like a believable "where is it brighter" sketch? The page says it is not a simulation: is that clear enough?

## 4. Shots (step 4)
- [ ] Pick a shot: the camera wedge shows what the lens sees
- [ ] Change one light's intensity for that shot: "Use the scene setup" and the reason box appear straight away; other shots and the scene setup are unchanged
- [ ] Copy the change to two other shots

## 5. Continuity checks (step 5)
- [ ] Set a different kelvin for the key in one shot: a colour-jump warning names the shots, the numbers and a fix
- [ ] Write a reason for that shot: the warning becomes a note ("intended: ...")
- [ ] Nothing is changed by the checks; Save is never blocked by advice

## 6. Two treatments (step 6)
- [ ] Compare A and B: settings table, stated effects each with "because:", and what differs
- [ ] **(creative)** A reads warm, intimate, gentle; B reads cool, restrained, dramatic. Do the numbers and the statements match what you see on the plans?

## 7. Review and change handling (step 7)
- [ ] Approve is disabled until you submit for review, and says why
- [ ] Approve B only: A stays in draft
- [ ] Revise the screenplay: the plan shows "changed after this lighting plan was made"; Rebase keeps unaffected items and sends affected ones back to review; the approved version is still there
- [ ] Change an actor's blocking: only the shots that actor is in are flagged

## 8. Export (step 8)
- [ ] Plan JSON, light schedule CSV and lighting instructions download before approval
- [ ] The manifest button is disabled before approval, with the reason beside it
- [ ] After approving with an unapproved art design, the manifest asks for an explicit choice, and the choice is written in the file (`overrides`)
- [ ] With the art design approved, a clean plan exports with no override; `auto_import` is false
- [ ] Open the exports: lighting files carry the art design only as an id, name and hash
- [ ] Keep the lights as a setup; start a new plan in the other treatment from it

## 9. UI text review (manual, not covered by tests) **(text)**
- [ ] Read every step cold: does the first line explain what to do here?
- [ ] Does each "Next: ..." label say what the next step is?
- [ ] Does each warning say the problem, why it matters and one way to recover?
- [ ] Are the "Words used on this screen" glosses clear to a newcomer? Is "colour temperature" gloss enough?
- [ ] Keyboard only: can you reach and operate every light and every field?
- [ ] Are the small labels on the plan readable? (On the warm sample they overlap; see report, limitations)
- [ ] Spelling: the Lighting Lab uses "colour" and "metres"; confirm that matches your house style

## 10. Safety
- [ ] Dreambox (8000) and Ideator were not touched; Craftbox is on 8099 only
- [ ] Your `data/` was only added to, never deleted
