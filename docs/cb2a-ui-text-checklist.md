# CB2A: UI text compliance checklist (written before implementation)

Source: `guidelines/ui-standard.md`, read in full from disk on 2026-11-01 (48 lines, rules U1-U9, a markup contract, a helper list and a review checklist).

## What the standard does and does not say about text

It is a **behaviour and structure standard**. It contains **no** rules about tone, voice, capitalisation, punctuation, sentence length, word choice or terminology lists. So the checklist below applies *only* the rules that exist, and every wording choice beyond them is mine, not the standard's. Anything marked **(mine)** is a house choice made for clarity and is reported as such, not as a requirement of the standard.

## Rules that constrain UI text, and how each will be applied

| # | Rule (quoted or closely paraphrased) | Applied to | Check |
|---|---|---|---|
| U1 | Title reads `Step N of M: <what you do here>`; every step except the first has **Back**; every step except the last has **Next** "whose label says what comes next" (example: "Next: answer the questions"); the last step "ends with explicit buttons for where to go" | Page and step titles, Back/Next labels, last-step buttons | **Automatic**: title pattern; Back/Next exist and start with `Back:` / `Next:`; last step has no Next and has at least two explicit buttons. **Manual**: whether each label really names what comes next |
| U2 | One primary Save per screen with `data-ui="save"`; no per-row Save; at most one extra variant | Save buttons and their labels | **Automatic**: at most one `save` per form and per screen (existing contract) |
| U3 | After Save what you typed stays and "shows its state ('saved', 'changed, not saved yet')"; moving on is a separate explicit button | State lines beside Save | **Automatic**: a state line is present on every Save screen and uses the words "saved" or "not saved yet" / "changed, not saved yet". **Manual**: wording reads naturally |
| U4 | Input is never lost: redraw, failed request and reload keep it; the page reopens where the work is | Validation messages and recovery text | **Automatic** (browser tests): reload and failed-save keep input. Text is not tested for this rule |
| U5 | Errors, results and progress appear "inside the card of the action", never only at the top of the page; **a disabled button says why** | Validation errors, warnings, progress text, disabled buttons | **Automatic**: every error box is inside a form card; every disabled button has a reason (visible text beside it or a `title`). **Manual**: the message names the problem and the fix |
| U6 | No silent waits: a progress panel says what is happening and for how long | Loading and busy messages | **Automatic**: the progress panel appears for a delayed request and names the action |
| U7 | Paid or network actions: estimate then confirm | n/a for CB2A (no paid or network calls) | Recorded as not applicable |
| U8 | "A short line at the top of each step explains it in plain words; **empty states say what to do**; **no jargon without a gloss**" | Step intros, empty states, glossary | **Automatic**: each step has an intro (6-90 words); every empty state contains an action; every jargon term used on a screen has a gloss on that screen (list in the test). **Manual**: "read it cold" |
| U9 | "A gate or check may recommend, never block silently; override is explicit and recorded" | Advice vs. blocking wording; stale-design and rights warnings; exports | **Automatic**: analysis findings never disable Save; an advised export needs a visible override control. **Manual**: advice is worded as advice and says how to recover |

## Beyond the standard (requested in the task, applied as house choices)

These come from your brief ("tooltips, help text, accessibility labels", "consistent terminology", "actionable warnings") and are **not** in `ui-standard.md`:
- **(mine)** Every field has a programmatically associated label; icon-only buttons have an accessible name. Automatic check.
- **(mine)** Consistent terms across the Art Lab; the names are listed in the glossary and the report.
- **(mine)** Each warning states the problem, why it matters and one way to recover. Manual check.
- **(mine)** Plain verbs on buttons ("Save art direction version", "Add a prop"), no abbreviations unless glossed.

## Known deviations from the standard (carried over, documented)
1. `assert_ui_contract` lives in `tests/ui_contract.py`, not `tests/ui/ui_contract.py` (so `unittest discover -s tests` can import it). Since CB1.
2. The standard names Dreambox helpers (`window.ui`, `W.draft`, `core/jobqueue.py`). Craftbox uses its own equivalents in `app/static/ui.js`. U6's job queue is not built because every Craftbox action finishes in milliseconds; the progress panel still shows.
3. The standard says draft state lives in `W.draft`; Craftbox keeps drafts in each lab's persisted store (`L`, and `ART` for the Art Lab).

## Sign-off sections to be completed in `docs/cb2a-implementation-report.md` → "UI Text Compliance"
Guidelines applied · screens inspected · automated checks done · manual checks remaining · deviations.
