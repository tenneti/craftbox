# CB2A acceptance checklist: Art Direction Lab

Start Craftbox (`start-craftbox.bat`), open `http://127.0.0.1:8099`. Dreambox on port 8000 is not needed and is not used.
Tick each box yourself; the automated tests do not replace this. Items marked **(text)** are the manual part of the UI text review.

## Automated (already passing, 195 tests)
- [x] Engines: drafts, props, continuity, layout checks, impact, rebase, exports, determinism (19)
- [x] API: independent treatments, comparison, validation, gated exports, uploads, style profiles (14)
- [x] Samples valid and in step with the engines (5)
- [x] Browser: all 8 Art Lab steps and the 2 Art Library steps, with the objective UI checks on each (11)
- [x] CB0, CB1 and Story Lab suites unchanged and passing

## 1. Scene and treatment (Art Lab step 1)
- [ ] The project, scene and direction plan lists fill in after pressing Refresh; an empty state tells you what to do **(text)**
- [ ] Choosing "Warm nostalgia" and pressing "Draft the treatment" creates a treatment and unlocks Next
- [ ] Reload the page: you land back on the same treatment

## 2. Location and layout (steps 2-3)
- [ ] Changing interior to exterior is flagged against the script's INT. heading as advice, not as a block
- [ ] Drag a piece on the plan; select a piece and use the arrow keys (0.01, Shift 0.05); edit numbers; add and delete a piece
- [ ] Drop the counter on an actor's path: you get advice, and Save still works
- [ ] The actors, cameras and the 180° line match the direction plan

## 3. Props (step 4)
- [ ] "Ticket" appears with the script lines and shots that mention it; add "Reading glasses!" by hand; remove it again
- [ ] Mark the ticket gone, then on the counter later: continuity advice names the two states and how to fix it
- [ ] A prop shown in a shot after it was marked gone is flagged

## 4. Visual style and Art Library (step 5, Art Library tab)
- [ ] Enter "red" as a colour: the error is beside Save, says what to change, and what you typed is kept
- [ ] Add a shot variation; the overall style stays and the difference is stated
- [ ] Create a style profile with a word to avoid; a treatment using it is flagged
- [ ] Upload a PNG; upload the same one again (reported as already registered); upload a renamed `.exe` as `.png` (refused)
- [ ] Fill in source, owner, rights and licence; the asset appears on step 5 with its rights state

## 5. Two treatments (steps 6-7)
- [ ] Draft "Emotional distance" for the same scene; the screenplay is unchanged
- [ ] Comparison shows both palettes, both layouts, the measures, and a "because:" line for each reading
- [ ] Approve B only: A stays in draft
- [ ] Approve is disabled until you submit for review, and the screen says why

## 6. Change and export (steps 7-8)
- [ ] Download the prop list, art direction JSON and storyboard notes before approval
- [ ] Manifest buttons are disabled before approval, with the reason beside them
- [ ] After approving, export the manifest; open it and check `auto_import` is false and the Lighting, Costume and Cinematography sections exist
- [ ] Revise the screenplay; the treatment shows "changed after this design was made"; "Rebase" keeps approved items and returns affected ones to review
- [ ] Exporting a manifest of a changed design asks for an explicit choice, and the choice is written in the file

## 7. UI text review (manual, not covered by tests) **(text)**
- [ ] Read every step cold: does the first line explain what to do here?
- [ ] Does each "Next: …" label say what the next step is?
- [ ] Does each warning say the problem, why it matters, and one way to recover?
- [ ] Are the "Words used on this screen" glosses clear without prior knowledge?
- [ ] Are terms used consistently (treatment, set layout, prop, beat, shot)?
- [ ] Keyboard only: can you reach and operate every control, including the layout editor?
- [ ] Are the small labels on the layout plan readable at your zoom level?

## 8. Safety
- [ ] Dreambox (8000) was not touched; Craftbox is on 8099 only
- [ ] Your existing `data/` was only added to (new experiments and an `assets/` folder), never deleted
