---
id: <SHORT-ID>              # e.g. AI-CURATOR; used in test names and commit messages
title: <Feature name>
status: draft               # draft | ready | in-progress | done  (ready only when §15 passes)
depends_on: []              # other feature ids or files this needs
supersedes: []
size_budget: "§1-§9 header part <= 1,500 tokens; each slice card <= 1,000; whole file <= 8,000; the rest goes to guidelines/<id>/appendix-*.md"
---
# <Feature name>

> **GUIDE (delete every `> GUIDE` line before setting `status: ready`; they cost tokens on every read).**
> Order is stable-first: §1-§8 never change once `ready`, so Claude Code's prompt cache keeps hitting. Later changes are **appended to §14**, never edited into the middle. Progress and findings go in `docs/<id>-status.md`, never here.
> Write tables and one-line requirements, not prose. Point to code as `path::symbol` instead of describing it. Put mock-ups, research, long examples and alternatives in the appendix and link them.

## 1. Kickoff (paste into Claude Code)
```text
Read guidelines/<file>.md sections 1-8 and slice card <Sn> only. Inspect the repo as section 4 says before coding.
Implement <Sn> only. No paid or network calls in tests. Run the commands in the card.
Stop after <Sn> and report in the section 13 format. Do not start the next slice.
```
> GUIDE: one slice per session. Start each slice in a fresh session (`/clear`) so the context is §1-§8 + one card, not the history of the last slice.

## 2. Intent (<= 120 words)
- **Problem:** <who is stuck, doing what, today>
- **Outcome:** <what the user can do when this ships, in one sentence>
- **Success metric:** <measurable: "N of M sample assets get accepted tags", "render under X s", "no extra paid retries">
- **Why now / depends on:** <one line>

## 3. Scope
| In | Out (non-goals) | Assumptions (each is a default Claude may rely on) |
|---|---|---|
| <capability> | <tempting thing NOT to build> | <decision already taken, so do not ask> |

## 4. Repo contract (verify before coding)
> GUIDE: fill this by asking Claude Code to explore the repo (an Explore sub-agent is cheapest). Status is what the code does today, not what a spec says.

| Area | `path::symbol` | Status (available / partial / planned) | Action (reuse / extend / avoid) |
|---|---|---|---|
| <e.g. library filters> | `backend/creative/browse.py::select` | available | reuse |

- **New files only:** `<path>` (purpose) ...
- **Do not touch:** <modules, files, behaviours that must stay byte-for-byte as they are>
- **Follow:** `CLAUDE.md` rules that matter here (list the 3-5, do not copy them).

## 5. Invariants and safety (this feature only)
- <e.g. user data is never overwritten or deleted automatically; additions are reversible>
- <e.g. no secret in files, logs or browser; keys only from environment variables>
- <e.g. paid, network or destructive actions need an explicit user step; tests use fakes (`DREAMBOX_FAKE_*`)>
- <e.g. Windows first; `pathlib`; no shell-specific code>

## 6. Requirements
| ID | Requirement (one testable sentence) | Pri (M/S/C) | Slice | Test |
|---|---|---|---|---|
| R1 | <The user can ...> | M | S0 | T1 |

## 7. Contracts
### 7.1 UX
- **UI standard:** follows `guidelines/ui-standard.md` (wizard or paged tabs, Back and Next on every step, one Save per form, input never lost, feedback beside the control). List each deviation and why, or write "none".
- **Entry:** <exact nav path and route, e.g. top bar "X" -> `#/x`; how it is discoverable>
- **Screens and states:** | screen | empty | loading | error | success | (one row each)
- **Controls (stable `data-testid`):** | control | testid | does what | enabled when |

### 7.2 Data
| Thing | Location / schema (fields, types, enums) | Version | Written by | Rollback |
|---|---|---|---|---|
> GUIDE: say what existing files and records are NOT changed. Old data must still load.

### 7.3 API
| Method path | Request | Response | Errors (code -> meaning) |
|---|---|---|---|

### 7.4 Rules and defaults
| Rule / threshold | Default | Why | Tuned? (measured / guess) |
|---|---|---|---|

## 8. Budgets
- **Time and size:** <render/analysis time, memory, file sizes, page load>
- **Money:** <$ per run, per batch, ceiling, who approves, how it is recorded>
- **LLM use (only if the feature calls a model):** | step | model tier | effort | cached prefix | batch? | structured output | max tokens | est. cost |
  - Rules: cheapest tier that passes the checks, escalate only on doubt; stable prefix first (bible, schema, vocabulary) with the variable part last; count tokens and show the estimate before any bulk run; no automatic paid retry.
- **Privacy:** <what leaves the machine, under which policy, shown to the user before sending>

## 9. Slices
| Slice | Goal | Gate to start | Gate to finish | Est. size |
|---|---|---|---|---|
| S0 | <usable shell, no paid/network calls> | - | tests green, UI route verified | S |
| S1 | <core behaviour> | S0 accepted | ... | M |

### Slice card S<n>   (copy per slice; <= 1,000 tokens)
- **Goal:** <one sentence>  **Covers:** R1, R2
- **Touch:** `<files>` (new) / `<files>` (edit)
- **Steps (ordered, <= 7):** 1 ... 2 ...
- **Add tests:** `<test file>::<names>` -> T1, T2
- **Run:** `uv run ruff check .` / `uv run pytest -q -p no:cacheprovider <focused files>` / regression: `<files or --ignore=tests/ui>`
- **Done when (checkable):** <observable result 1> / <observable result 2>
- **Stop:** report per §13, then wait.

## 10. Test plan
> GUIDE: every requirement has at least one test id; every test id appears in a slice card.

| Test | Covers | Level (unit / api / browser / regression) | Fixture or fake | Expected |
|---|---|---|---|---|
| T1 | R1 | api | <fake provider / sample file> | <result> |

- **Always include:** valid and malformed input; permission/privacy/cost gate (blocked and allowed); original data unchanged; old data still loads; the nav entry is found from the real UI; no real network or paid call (assert it).
- **Gates:** focused tests per slice -> `uv run ruff check .` -> related regression -> full suite before `done` (`uv run pytest`, about 9 min; UI tests share one server, so leave shared settings as found).
- **Manual check (<= 10 steps, with expected result each):** 1 ... 
- **Performance / accessibility:** <only if relevant: limits and how measured>

## 11. Rollout and rollback
- **Default state:** <off / on; flag or setting name>  **Migration:** <none / what, with backup first>
- **Rollback:** <exact steps; what data stays>
- **Update when done:** one bullet in `CLAUDE.md` (<= 3 lines, link the status doc), `docs/<id>-status.md` (built / not built / limits).

## 12. Risks and open questions
| # | Item | Impact | Default chosen / mitigation | State (open / decided) |
|---|---|---|---|---|
> GUIDE: no row may be `open` when status becomes `ready`. A decision the owner has not made is written as a default Claude may use, marked "reverse if wrong".

## 13. Report format (Claude's end-of-slice message, <= 25 lines)
1. UI path and controls  2. What was built (bullets)  3. Tests run and results (counts, failures named)  4. Files added/changed (grouped)  5. Not built / limits  6. Data, migration and security notes  7. How to try it by hand (<= 5 steps)  8. Proposed next slice (not started)

## 14. Decision log (append-only; newest last)
| Date | Decision | Why | Sections affected |
|---|---|---|---|

## 15. Ready check (delete when passed)
- [ ] §2 metric is measurable  - [ ] §4 filled from the real repo  - [ ] every R has a T and a slice  - [ ] no open row in §12
- [ ] §7.1 follows `ui-standard.md` (or lists deviations), and the browser test calls `assert_ui_contract` on every step
  - [ ] each slice card <= 1,000 tokens and self-contained  - [ ] paid/network steps have an explicit user gate and a fake for tests
- [ ] nothing in §1-§8 depends on a long appendix  - [ ] all `> GUIDE` lines removed  - [ ] file within `size_budget`

**Appendix (not loaded by default):** `guidelines/<id>/appendix-ux.md` · `appendix-research.md` · `appendix-examples.md`
