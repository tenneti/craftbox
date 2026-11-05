# Craftbox CB0 — manual browser checklist (about 10 minutes)

Setup: run `start-craftbox.bat` (it opens <http://127.0.0.1:8099>). To keep test experiments out of your real history, first `set CRAFTBOX_DATA_DIR=%TEMP%\craftbox-manual`. Dreambox on port 8000 may stay running throughout.

## Startup and isolation
- [ ] Page loads: header says **23 crafts · 3 ready to run**; the stepper shows 5 steps; no red banner.
- [ ] <http://127.0.0.1:8099/health> shows `"status":"ok"` and `"database":"ok"`.
- [ ] Dreambox at `http://127.0.0.1:8000` still works.
- [ ] Starting `start-craftbox.bat` a second time says "already in use" and does not disturb the first instance or Dreambox.

## Reading it cold (UI standard)
- [ ] Every step has a title "Step N of 5: …" and a plain sentence saying what it is for.
- [ ] Step 1 has no Back; step 5 has no Next; every other step has both, and the labels say where they lead ("Next: run it").
- [ ] Any disabled button has a yellow reason beside it (try step 1 with no craft; step 4 Approve before submitting).

## Step 1 — choose
- [ ] Groups appear as Story & Direction, Visual Production, Post-production, Production Operations; the list scrolls and Next stays visible.
- [ ] Click a planned craft (e.g. Lighting): "Planned", Next disabled with a reason.
- [ ] Search "camera" narrows the list; nonsense text shows "No craft matches that search".
- [ ] Click **Screenwriting**, then **Next: enter your input**.

## Step 2 — input (one Save)
- [ ] The example input is filled in. Exactly one primary button, **Save experiment**.
- [ ] Press Save with no name: the error appears right under the buttons and your text is unchanged.
- [ ] Break the JSON, press **Try without saving**: error beside the button, text unchanged. Reset it with **Reset to the example**.
- [ ] **Try without saving** on valid input shows a result and "Not saved"; History stays empty.
- [ ] Name it "Manual 1", press **Save experiment**: status line says Saved; your text is still there; Save is greyed with a reason; Next is enabled.
- [ ] Edit the name: status says "Changed, not saved yet"; Next is disabled with a reason. Save again, then **Next: run it**.

## Steps 3–5 — run, review, export
- [ ] **Run experiment**: result appears in the same card (status, warnings, JSON). Run again: "Repeatable: 2 runs gave identical results".
- [ ] **Check it is repeatable**: message beside the button says Verified.
- [ ] Review: Approve/Reject are disabled until **Submit for review**. Approve with no name → error beside the buttons; add a name → approved; your name and note stay in the boxes.
- [ ] Reject path (new experiment): Reject with no note → error; with a note → Rejected, plus advice that you can change and re-run or resubmit.
- [ ] Step 5: **Export manifest** downloads `mf-….manifest.json` (open it: reviewer set, `auto_import: false`) and says nothing was sent to Dreambox.
- [ ] **Start a new experiment** returns to step 1; the craft you used is still highlighted.

## Nothing lost
- [ ] On step 2 type a name and change the input, then reload the page (F5): same step, same text.
- [ ] Reload while on step 4 or 5: you return to that step for the same experiment.

## History
- [ ] The table lists your experiments; filters by craft and approval work; an empty state explains what to do.
- [ ] Select an experiment: **View result**, **Event log** and **Check it is repeatable** work on a run.
- [ ] Save two Cinematography experiments with different `lens_mm`, run both, tick one run in each (selection persists across experiments), **Compare**: the changed lens appears in the differences.
- [ ] **Duplicate** creates "… (copy)"; **Continue in the wizard** opens at the right step (Run if never run, Review if waiting, Export if approved).

## Persistence and logs
- [ ] Stop Craftbox (Ctrl+C), start again: history, approvals and exports are still there.
- [ ] `data\logs\craftbox.log` contains JSON lines for requests and lifecycle events; no secrets.

## Not covered (by design in CB0)
Real media, AI generation, rendering, Dreambox import, authentication, the 20 planned crafts.
