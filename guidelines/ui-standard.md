# UI standard (every new feature page)

Read this before writing any page. It is short on purpose. A feature file (`guidelines/feature-template.md` section 7.1) states "follows ui-standard.md" or lists each deviation and why.
The pattern was learned the hard way in Screenwright (`backend/api/static/screenwright.js`): inputs lost on every save, errors shown at the top of a long page, silent waits, Save buttons on every row. Do not repeat it.

## Rules
| # | Rule | Check |
|---|---|---|
| U1 | **A wizard or paged tabs, never one long page.** More than one screen of input = numbered steps with a stepper and a title `Step N of M: <what you do here>`. Every step except the first has **Back**; every step except the last has **Next** whose label says what comes next ("Next: answer the questions"). The last step ends with explicit buttons for where to go. | Back and Next exist on every step |
| U2 | **One Save per form, page or section.** A primary Save (`data-testid="<feature>-save"`) saves everything on that screen. No Save per row or field. At most one extra variant of the same Save ("Save, using suggestions"). | one primary Save per screen |
| U3 | **Saving never clears, moves or surprises.** What you typed stays after Save and shows its state ("saved", "changed, not saved yet"). Moving to another step or section is a separate, explicit button. | type, Save: still there |
| U4 | **Input is never lost.** Drafts live in a store (`W.draft`) that every redraw reads, survive a failed request, and what is saved is shown again after a reload. A page reopens where the work is. | redraw, error, reload keep it |
| U5 | **Feedback sits beside the control.** Errors, estimates, results and progress appear inside the card of the action, scrolled into view; never only at the top of the page. A disabled button says why. | trigger an error: it is next to the button |
| U6 | **No silent waits.** Anything over about two seconds runs in the background (`core/jobqueue.py` or `extract_job.py`) with a progress panel (what, elapsed time), can be left and returned to, and keeps its result. | long action shows a panel |
| U7 | **Paid or network actions: estimate, then confirm.** Nothing is sent before the writer sees what and at what cost. Local tools need no cap. | estimate before send |
| U8 | **Say what happens next.** A short line at the top of each step explains it in plain words; empty states say what to do; no jargon without a gloss. | read it cold |
| U9 | **Advice is advice.** A gate or check may recommend, never block silently; override is explicit and recorded. | override is a visible control |

## Markup contract (so a test can check it)
Put these attributes on the elements (they are in addition to `data-testid`): wizard root `data-ui="wizard"`; stepper `data-ui="stepper"`; Back `data-ui="back"`; Next `data-ui="next"`; the primary Save `data-ui="save"`; each form or section `data-ui="form"`; progress panel `data-ui="progress"`.
`tests/ui/ui_contract.py::assert_ui_contract(page)` checks a rendered step: at most one `save` per `form`, a `back` unless it is the first step, a `next` unless it is the last, and a `stepper` in a wizard. Every new feature's browser test calls it on each step.

## Build it the easy way: `backend/api/static/ui.js` (`window.ui`)
Do not rewrite these, call them. Load order: `ui.js` after the page helpers (`h`, `api`) and before your page script (see `index.html`).
| Helper | Rule | Use |
|---|---|---|
| `ui.call(path, method, body)` | - | a JSON request through `api()` |
| `ui.fields(store)` -> `field(key, init, props, tag)` | U3, U4 | text fields whose typed text lives in `store` (e.g. `W.draft`), so a redraw never empties them |
| `ui.steps(defs, include)` | U1 | the step list: `title(n, text)` ("Step N of M: ..."), `after(n)`, `before(n)`, `list()`; a step can be hidden per project |
| `ui.stepper({...})`, `ui.nav({...})` | U1, U2 | the step bar and the Back / Next row, already marked with `data-ui` (`saveNext` marks a Next that is also the Save) |
| `ui.estimateBox(est, {...})` | U5, U7 | what would be sent and cost, the spending cap, Confirm and Cancel |
| `ui.progress({...})` | U6 | the background-work panel with elapsed time (`ui.mm`) |
| `ui.errorBox(err, where, testid)`, `ui.reveal(testid)` | U5 | an error beside the control that failed, scrolled into view |
| `ui.poller()` | U6 | one polling timer, so a redraw cannot start two |
| `ui.oneLine(v)` | - | line breaks and a lone `|` become ` / ` when an answer must be one line |
If a helper you need is missing, add it to `ui.js` (with a case in `tests/ui/test_ui_helpers.py`), not to your page. `test_screenwright_pages_use_the_shared_helpers` fails if a page grows its own copy of the JSON call, the minutes formatter, `oneLine` or the estimate box.

## Pages that do not follow it yet
These predate the standard and are not wizards; do not copy them. Move one over when you next change it. The Screenwright Story tab, its idea check and its estimate and progress panels follow it. Still long pages of cards: the Screenwright Screenplay, Shots, Folder runner and Novel tabs (they use the shared estimate, progress and error helpers, but have no Back and Next), and everything outside Screenwright (Studio, the music-video form, Scene Maker, Creative, and the rest).

## Review checklist (paste in the PR or the slice report)
- [ ] Wizard or paged tabs; Back and Next on every step; first step no Back, last step no Next
- [ ] One primary Save per screen; no per-row Save
- [ ] Typed text survives Save, a failed request and a reload; saved values reappear
- [ ] Errors, estimates and progress next to the button; long work in the background with a panel
- [ ] Estimate then confirm for any paid or network step
- [ ] `assert_ui_contract` called in the browser test of every step
