// Craftbox UI, following guidelines/ui-standard.md: a 5-step wizard (New experiment) + a History view.
const {el, call} = ui;
const byId = id => document.getElementById(id);

// ---- state ---------------------------------------------------------------------------------
// W = drafts and position. Persisted to localStorage so a reload reopens where the work is (U4).
// R = per-session data fetched from the server (never trusted across reloads) and view feedback.
const STORE_KEY = 'craftbox.wizard.v1';
const W = {v: 1, step: 1, craftId: null, expId: null, inputs: {}, saved: null,
  draft: {name: '', notes: '', input: undefined, reviewer: '', note: '', filter: ''}};
const R = {crafts: [], exp: null, latest: null, busy: null, errors: {}, notice: {}, tryOut: null, history: {selected: null, compare: []}};

function persist() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(W)); } catch (e) { /* storage unavailable: drafts live for this session only */ }
}
function restore() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    if (saved && saved.v === 1) { Object.assign(W, saved, {draft: {...W.draft, ...saved.draft}}); }
  } catch (e) { /* ignore a corrupt or unavailable store */ }
}

const S = ui.steps([
  {short: 'Choose a craft', title: 'choose a craft', intro: 'A craft is one filmmaking job, such as writing a scene, planning camera shots or cutting a rough edit. Pick the one you want to try. Three are ready to run; the other 20 are planned and are shown so you can see what is coming. You will enter some input, run it, review the result and, if you like it, export it for Dreambox. Nothing leaves this computer.'},
  {short: 'Enter input', title: 'enter your input', intro: 'Give the craft something to work on. A working example is already filled in, so you can just name the experiment and save it. Saving stores your input exactly as it is; it does not run anything yet. You can also try the input without saving.'},
  {short: 'Run', title: 'run it', intro: 'Running applies the craft to your saved input and records the result. A run never changes your input, and every run is kept. Run it again to check that you get the same answer, which is what makes an experiment repeatable.'},
  {short: 'Review', title: 'review the result', intro: 'Decide whether this result is good enough to keep. Submit it for review, then approve or reject it with your name. Approval is always your decision; nothing is approved automatically.'},
  {short: 'Export', title: 'export and finish', intro: 'An approved result can be exported as a file that Dreambox will be able to read later. Exporting does not send anything to Dreambox and does not change Dreambox. When you are done, start another experiment or look back through your History.'},
]);

const craftById = id => R.crafts.find(c => c.id === id) || null;
const currentCraft = () => craftById(W.craftId);
const isPilot = c => !!c && c.status === 'pilot';
const short = h => (h || '').slice(0, 10);
const when = iso => iso ? iso.replace('T', ' ').replace(/\.\d+Z$/, 'Z') : '';
const badge = text => el('span', {class: `badge b-${text}`}, text);
const latestRun = () => (R.exp && R.exp.runs.length) ? R.exp.runs[R.exp.runs.length - 1] : null;

function sameJson(a, b) {
  try { return JSON.stringify(JSON.parse(a)) === JSON.stringify(JSON.parse(b)); } catch (e) { return a === b; }
}
function draftState() {
  if (!R.exp || !W.saved) return 'unsaved';
  const same = W.saved.craftId === W.craftId && W.saved.name === (W.draft.name || '').trim() &&
    W.saved.notes === (W.draft.notes || '') && sameJson(W.saved.input, W.draft.input);
  return same ? 'saved' : 'changed';
}
function reachedStep() {
  if (!isPilot(currentCraft())) return 1;
  if (!R.exp) return 2;
  return R.exp.runs.length ? 5 : 3;
}

// ---- feedback helpers (U5, U6) -------------------------------------------------------------
function fail(key, message) {
  R.errors[key] = message; render(); ui.reveal(`error-${key}`);
}
async function withBusy(key, what, fn) {
  delete R.errors[key];
  R.busy = {key, what, startedAt: Date.now()};
  render();
  try { await fn(); }
  catch (e) { R.errors[key] = e.message; }
  finally { R.busy = null; render(); if (R.errors[key]) ui.reveal(`error-${key}`); }
}
const feedback = key => [
  R.busy && R.busy.key === key ? ui.progress({what: R.busy.what, startedAt: R.busy.startedAt}) : null,
  R.errors[key] ? ui.errorBox(R.errors[key], `error-${key}`) : null,
  R.notice[key] ? el('div', {class: 'notice', 'data-testid': `notice-${key}`, role: 'status'}, R.notice[key]) : null,
];
const busy = () => !!R.busy;

// ---- wizard shell --------------------------------------------------------------------------
function go(n) {
  if (n < 1 || n > S.count || n > reachedStep()) return;
  W.step = n; R.errors = {}; R.notice = {}; persist(); render();
  if (n === 2) ensureInput();
}
function render() {
  ui.clearTimers();
  const n = W.step;
  const body = [stepChoose, stepInput, stepRun, stepReview, stepExport][n - 1]();
  const root = el('div', {id: 'wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': S.count, 'data-testid': 'wizard'},
    ui.stepper({defs: S.list(), current: n, reached: reachedStep(), onGo: go}),
    el('h1', {'data-testid': 'step-title'}, S.title(n)),
    el('p', {class: 'intro', 'data-testid': 'step-intro'}, S.intro(n)),
    body, el('div', {id: 'navhost'}));
  byId('wizard-mount').replaceChildren(root);
  renderNav();
}
function navSpec() {
  const n = W.step, craft = currentCraft(), latest = latestRun();
  const before = S.before(n);
  const back = before ? {label: `Back: ${before.short.toLowerCase()}`, onclick: () => go(n - 1)} : null;
  const next = {
    1: {label: 'Next: enter your input', disabled: !isPilot(craft),
      why: !craft ? 'Choose a craft above to continue.' : 'This craft is planned and cannot run yet. Choose one marked “Ready to run”.', onclick: () => { go(2); }},
    2: {label: 'Next: run it', disabled: draftState() !== 'saved' || busy(),
      why: draftState() === 'unsaved' ? 'Save the experiment first.' : 'You changed the input. Save again, or the run would use the earlier version.', onclick: () => go(3)},
    3: {label: 'Next: review the result', disabled: !latest || busy(), why: 'Run the experiment first. There is nothing to review yet.', onclick: () => go(4)},
    4: {label: 'Next: export and finish', disabled: !latest || busy(), why: 'Run the experiment first.', onclick: () => go(5)},
  }[n] || null;
  return {n, total: S.count, back, next};
}
function renderNav() {
  const host = byId('navhost');
  if (host) host.replaceChildren(ui.nav(navSpec()));
}

// ---- step 1: choose a craft ----------------------------------------------------------------
function selectCraft(craft) {
  if (W.craftId && W.craftId !== craft.id) {
    W.inputs[W.craftId] = W.draft.input;
    W.draft.input = W.inputs[craft.id];
    R.exp = null; R.latest = null; W.expId = null; W.saved = null; R.tryOut = null;
  }
  W.craftId = craft.id; persist(); render();
}
function stepChoose() {
  const field = ui.fields(W.draft, persist);
  const list = el('div', {class: 'craftlist', 'data-testid': 'craft-list'});
  const detail = el('div', {class: 'craftdetail', 'data-testid': 'craft-detail', 'aria-live': 'polite'});
  const paintList = () => {
    list.replaceChildren();
    const q = (W.draft.filter || '').toLowerCase();
    let shown = 0;
    const order = ['Story & Direction', 'Visual Production', 'Post-production', 'Production Operations'];
    const groups = [...new Set(R.crafts.map(c => c.group))].sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));
    for (const group of groups) {
      const matching = R.crafts.filter(c => c.group === group && `${c.name} ${c.description}`.toLowerCase().includes(q));
      if (!matching.length) continue;
      shown += matching.length;
      list.append(el('h3', {class: 'group'}, group), el('div', {class: 'cards'}, ...matching.map(c =>
        el('button', {type: 'button', class: `craftcard${W.craftId === c.id ? ' selected' : ''}${isPilot(c) ? '' : ' planned'}`, 'data-craft': c.id, 'aria-pressed': String(W.craftId === c.id), onclick: () => selectCraft(c)},
          el('span', {class: 'cname'}, c.name), el('span', {class: `badge ${isPilot(c) ? 'b-completed' : 'b-planned'}`}, isPilot(c) ? 'Ready to run' : 'Planned'),
          el('span', {class: 'cdesc'}, c.description)))));
    }
    if (!shown) list.append(el('p', {class: 'hint'}, 'No craft matches that search. Clear the search box to see all 23.'));
  };
  paintList();
  const c = currentCraft();
  if (c) {
    detail.append(el('h2', {}, c.name),
      el('p', {}, isPilot(c) ? 'Ready to run. Click “Next: enter your input” to continue.' : 'This craft is planned. It cannot run yet, so you cannot continue with it.'),
      el('p', {class: 'hint'}, `What it will do: ${c.mvp}`), el('p', {class: 'hint'}, `Where it will fit in Dreambox later: ${c.dreambox_target}`));
  } else {
    detail.append(el('p', {class: 'hint'}, 'No craft chosen yet. Click one of the cards above.'));
  }
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'choose-form'},
    el('div', {class: 'formrow'}, el('label', {for: 'craft-filter'}, 'Search'),
      field('filter', '', {id: 'craft-filter', type: 'search', placeholder: 'Find a craft…', 'data-testid': 'craft-filter', onedit: paintList})),
    list, detail);
}

// ---- step 2: enter input (one Save) ---------------------------------------------------------
async function ensureInput() {
  if (W.draft.input || !W.craftId) return;  // already has text (typed or restored); empty means "load the example"
  try {
    const example = JSON.stringify(await call(`/api/crafts/${encodeURIComponent(W.craftId)}/fixture`), null, 2);
    if (W.draft.input) return;  // the user typed while the example was loading: never overwrite their text
    W.draft.input = example;
    persist(); render();
  } catch (e) { R.errors.input = `Could not load the example input: ${e.message}`; render(); }
}
function parseDraft() {
  try { return JSON.parse(W.draft.input || ''); } catch (e) { return {__error: e.message}; }
}
function stateText() {
  const s = draftState();
  if (s === 'saved') return `Saved as “${W.saved.name}”. What you typed is still shown above. Click “Next: run it”.`;
  if (s === 'changed') return 'Changed, not saved yet. Saving creates a new experiment; the earlier one stays exactly as it was.';
  return 'Not saved yet.';
}
function stepInput() {
  const craft = currentCraft(), field = ui.fields(W.draft, persist);
  const stateLine = el('p', {class: `state s-${draftState()}`, 'data-testid': 'save-state', 'aria-live': 'polite'}, stateText());
  const saveBtn = el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'experiment-save', onclick: saveExperiment}, 'Save experiment');
  const paint = () => {
    stateLine.textContent = stateText(); stateLine.className = `state s-${draftState()}`;
    const same = draftState() === 'saved';
    saveBtn.disabled = same || busy(); saveBtn.title = same ? 'Nothing has changed since the last save.' : '';
    renderNav();
  };
  paint();
  const tryOut = R.tryOut && R.tryOut.craftId === W.craftId ? R.tryOut : null;
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'input-form'},
    el('h2', {}, craft.name),
    el('div', {class: 'formrow'}, el('label', {for: 'exp-name'}, 'Name'), field('name', '', {id: 'exp-name', maxlength: '120', placeholder: 'e.g. Platform opening, 28 mm wide', 'data-testid': 'exp-name', onedit: paint})),
    el('div', {class: 'formrow'}, el('label', {for: 'exp-notes'}, 'Notes (optional)'), field('notes', '', {id: 'exp-notes', maxlength: '5000', placeholder: 'Anything you want to remember about this attempt', 'data-testid': 'exp-notes', onedit: paint})),
    el('label', {for: 'input', class: 'block'}, 'Input (JSON) — an example is filled in; change anything you like'),
    field('input', '', {id: 'input', spellcheck: 'false', 'data-testid': 'input-json', onedit: paint}, 'textarea'),
    stateLine,
    ...feedback('input'),
    el('div', {class: 'buttons'},
      el('button', {type: 'button', id: 'load', 'data-testid': 'reload-example', onclick: reloadExample, disabled: busy()}, 'Reset to the example'),
      el('button', {type: 'button', id: 'run', 'data-testid': 'try-input', onclick: tryInput, disabled: busy(), title: 'Runs once and shows the result below. Nothing is saved.'}, 'Try without saving'),
      saveBtn),
    ...feedback('save'), ...feedback('try'),
    tryOut ? el('div', {class: 'tryout', 'data-testid': 'try-output'}, el('p', {class: 'hint'}, tryOut.text), el('pre', {id: 'output'}, tryOut.json)) : null);
}
function reloadExample() {
  W.draft.input = undefined; R.tryOut = null; R.errors = {}; persist(); render(); ensureInput();
}
async function tryInput() {
  const input = parseDraft();
  if (input.__error) return fail('try', `The input is not valid JSON: ${input.__error}`);
  await withBusy('try', 'Running without saving', async () => {
    const r = await call(`/api/crafts/${encodeURIComponent(W.craftId)}/run`, 'POST', input);
    R.tryOut = {craftId: W.craftId, text: `Worked: ${r.artifact_type}, ${r.warnings.length} warning(s). Not saved.`, json: JSON.stringify(r.artifact, null, 2)};
  });
}
async function saveExperiment() {
  const input = parseDraft(), name = (W.draft.name || '').trim();
  if (input.__error) return fail('save', `The input is not valid JSON: ${input.__error}`);
  if (!name) { fail('save', 'Give the experiment a name first.'); byId('exp-name')?.focus(); return; }
  await withBusy('save', 'Saving', async () => {
    const exp = await call('/api/experiments', 'POST', {craft_id: W.craftId, name, input, notes: W.draft.notes || ''});
    R.exp = exp; R.latest = null; W.expId = exp.id; R.tryOut = null;
    W.saved = {craftId: W.craftId, name, notes: W.draft.notes || '', input: W.draft.input};
    persist();
  });
}

// ---- step 3: run ---------------------------------------------------------------------------
async function refreshExp() {
  R.exp = await call(`/api/experiments/${W.expId}`);
  const run = latestRun();
  R.latest = run ? await call(`/api/runs/${run.id}`) : null;
}
async function runNow() {
  await withBusy('run', 'Running', async () => {
    delete R.notice.run;
    await call(`/api/experiments/${R.exp.id}/run`, 'POST');
    await refreshExp();
  });
}
async function verifyNow() {
  await withBusy('run', 'Checking the result is reproducible', async () => {
    const v = await call(`/api/runs/${latestRun().id}/verify`, 'POST');
    R.notice.run = v.matches ? 'Verified: running the saved input again gives exactly the saved result.' : 'MISMATCH: running the saved input again gives a different result than was saved.';
    await refreshExp();
  });
}
function runResult() {
  const run = latestRun();
  if (!run) return el('p', {class: 'hint', 'data-testid': 'run-empty'}, 'Not run yet. Click “Run experiment”.');
  const r = R.exp.reproducibility;
  const repro = r.completed_runs < 2 ? 'Run it a second time to check that the result is repeatable.'
    : (r.reproducible ? `Repeatable: ${r.completed_runs} runs gave identical results.` : `Not repeatable: ${r.distinct_outputs} different results across ${r.completed_runs} runs.`);
  return el('div', {class: 'result', 'data-testid': 'run-result'},
    el('div', {class: 'runhead'}, el('strong', {}, `Run ${run.seq}`), badge(run.run_status), el('span', {class: 'hint'}, `${run.duration_ms} ms · result ${short(run.output_sha256)}`)),
    run.error ? el('p', {class: 'err'}, `The craft rejected this input: ${run.error.message}. Go back, fix the input and save again.`) : null,
    run.warnings.length ? el('ul', {class: 'warn'}, ...run.warnings.map(w => el('li', {}, w))) : null,
    el('p', {class: 'hint', id: 'repro', 'data-testid': 'repro'}, repro),
    R.latest && R.latest.envelope ? el('details', {open: true}, el('summary', {}, 'Result (JSON)'), el('pre', {'data-testid': 'run-output'}, JSON.stringify(R.latest.envelope.artifact, null, 2))) : null);
}
function stepRun() {
  const runs = R.exp.runs, latest = latestRun();
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'run-form'},
    el('h2', {}, `Run “${R.exp.name}”`),
    el('p', {class: 'hint'}, `${R.exp.craft_id} · input ${short(R.exp.input_hash)} · ${runs.length} run(s) so far`),
    el('div', {class: 'buttons'},
      el('button', {type: 'button', class: 'primary', id: 'rerun', 'data-testid': 'run-experiment', onclick: runNow, disabled: busy()}, runs.length ? 'Run again' : 'Run experiment'),
      el('button', {type: 'button', 'data-testid': 'verify-run', onclick: verifyNow, disabled: busy() || !latest || latest.run_status !== 'completed',
        title: !latest ? 'Run the experiment first.' : 'Re-runs the saved input and compares it with the saved result.'}, 'Check it is repeatable')),
    !latest ? el('p', {class: 'why'}, '“Check it is repeatable” becomes available after the first run.') : null,
    ...feedback('run'), runResult());
}

// ---- step 4: review ------------------------------------------------------------------------
async function decide(kind) {
  const reviewer = (W.draft.reviewer || '').trim(), note = (W.draft.note || '').trim();
  if (kind !== 'submit-review' && !reviewer) return fail('review', 'Enter your name as reviewer first.');
  if (kind === 'reject' && !note) return fail('review', 'Add a note explaining why you are rejecting this result.');
  await withBusy('review', kind === 'submit-review' ? 'Submitting' : (kind === 'approve' ? 'Approving' : 'Rejecting'), async () => {
    await call(`/api/runs/${latestRun().id}/${kind}`, 'POST', {reviewer, note});
    await refreshExp();
  });
}
function action(label, testid, kind, enabled, why, cls = '') {
  return el('span', {class: 'act'},
    el('button', {type: 'button', class: cls, 'data-testid': testid, onclick: () => decide(kind), disabled: !enabled || busy(), title: enabled ? null : why}, label),
    enabled ? null : el('span', {class: 'why'}, why));
}
function stepReview() {
  const field = ui.fields(W.draft, persist), run = latestRun(), s = run ? run.approval_status : null;
  const statusText = {none: 'This run failed, so there is nothing to review. Go back, fix the input, save and run again.',
    draft: 'Waiting for you to submit it for review.', review: 'Submitted. Waiting for your decision: approve or reject.',
    approved: 'Approved. You can export it on the next step.', exported: 'Approved and already exported.',
    rejected: 'Rejected. This is advice, not a dead end: change the input and run again, or submit it again if you rejected it by mistake.'}[s] || '';
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'review-form'},
    el('h2', {}, `Review run ${run.seq} of “${R.exp.name}”`),
    el('p', {}, el('span', {}, 'Status: '), badge(s === 'none' ? 'failed' : s)),
    el('p', {class: 'hint', 'data-testid': 'review-status'}, statusText),
    run.reviewer || run.review_note ? el('p', {class: 'hint'}, `Last decision by ${run.reviewer || '—'}${run.review_note ? ': ' + run.review_note : ''}`) : null,
    el('div', {class: 'formrow'}, el('label', {for: 'reviewer'}, 'Your name'), field('reviewer', '', {id: 'reviewer', maxlength: '80', placeholder: 'Reviewer name (needed to approve or reject)', 'data-testid': 'reviewer'})),
    el('div', {class: 'formrow'}, el('label', {for: 'review-note'}, 'Note'), field('note', '', {id: 'review-note', maxlength: '2000', placeholder: 'Required when rejecting; optional otherwise', 'data-testid': 'review-note'})),
    el('div', {class: 'buttons'},
      action('Submit for review', 'submit-review', 'submit-review', s === 'draft' || s === 'rejected',
        s === 'none' ? 'A failed run cannot be reviewed.' : 'Already submitted or decided.'),
      action('Approve', 'approve', 'approve', s === 'review', 'Submit for review first.', 'primary'),
      action('Reject', 'reject', 'reject', s === 'review', 'Submit for review first.')),
    ...feedback('review'));
}

// ---- step 5: export and finish -------------------------------------------------------------
async function exportNow() {
  await withBusy('export', 'Exporting', async () => {
    const m = await call(`/api/runs/${latestRun().id}/export`, 'POST');
    saveFile(`${m.manifest_id}.manifest.json`, JSON.stringify(m, null, 2));
    R.notice.export = `Exported. The file “${m.manifest_id}.manifest.json” was saved to your browser’s Downloads folder (fingerprint ${short(m.manifest_sha256)}). Nothing was sent to Dreambox.`;
    await refreshExp();
  });
}
function saveFile(name, text) {
  const url = URL.createObjectURL(new Blob([text], {type: 'application/json'}));
  const a = el('a', {href: url, download: name});
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
function resetWizard() {
  Object.assign(W, {step: 1, expId: null, saved: null});
  Object.assign(W.draft, {name: '', notes: '', input: undefined, note: ''});
  W.inputs = {};
  R.exp = null; R.latest = null; R.errors = {}; R.notice = {}; R.tryOut = null; persist(); render();
}
function stepExport() {
  const run = latestRun(), s = run.approval_status, ok = s === 'approved' || s === 'exported';
  return el('div', {},
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'export-form'},
      el('h2', {}, 'Export for Dreambox'),
      el('p', {class: 'hint'}, `Status: ${s === 'none' ? 'failed' : s}. Only approved results can be exported.`),
      el('div', {class: 'buttons'},
        el('span', {class: 'act'},
          el('button', {type: 'button', class: 'primary', 'data-testid': 'export-manifest', onclick: exportNow, disabled: !ok || busy(), title: ok ? null : 'Approve the result first.'}, s === 'exported' ? 'Download the manifest again' : 'Export manifest'),
          ok ? null : el('span', {class: 'why'}, 'Go back to Review and approve this result first.'))),
      ...feedback('export')),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'finish-form'},
      el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'},
        el('button', {type: 'button', 'data-testid': 'new-experiment', onclick: resetWizard}, 'Start a new experiment'),
        el('button', {type: 'button', 'data-testid': 'open-history', onclick: () => showView('history')}, 'Open History (compare runs, look back)'))));
}

// ---- History view --------------------------------------------------------------------------
const VIEWS = ['story', 'lab', 'art', 'lib', 'light', 'new', 'history'];
function showView(view) {
  try { localStorage.setItem('craftbox.view', view); } catch (e) { /* storage unavailable */ }
  for (const v of VIEWS) {
    byId(`view-${v}`).hidden = v !== view;
    byId(`tab-${v}`).classList.toggle('active', v === view);
  }
  banner('');
  if (view === 'story') Story.show().catch(e => banner(`Could not load the Story Lab: ${e.message}`, 'error'));
  if (view === 'art') Art.show().catch(e => banner(`Could not load the Art Lab: ${e.message}`, 'error'));
  if (view === 'lib') Library.show().catch(e => banner(`Could not load the Art Library: ${e.message}`, 'error'));
  if (view === 'light') Light.show().catch(e => banner(`Could not load the Lighting Lab: ${e.message}`, 'error'));
  if (view === 'lab') Lab.show().catch(e => banner(`Could not load the Scene Lab: ${e.message}`, 'error'));
  if (view === 'history') loadExperiments().catch(e => banner(`Could not load History: ${e.message}`, 'error'));
}
function banner(message, kind = 'info') {
  const b = byId('banner'); b.textContent = message; b.className = `banner ${kind}`; b.hidden = !message;
}
async function loadExperiments() {
  const params = new URLSearchParams({limit: '100'});
  if (byId('f-craft').value) params.set('craft_id', byId('f-craft').value);
  if (byId('f-approval').value) params.set('approval_status', byId('f-approval').value);
  const page = await call(`/api/experiments?${params}`);
  const body = byId('exp-table').tBodies[0];
  body.replaceChildren();
  byId('exp-empty').hidden = page.items.length > 0;
  for (const e of page.items) {
    body.append(el('tr', {class: 'clickable' + (R.history.selected?.id === e.id ? ' selected' : ''), 'data-id': e.id, tabindex: '0', onclick: () => openHistory(e.id), onkeydown: ev => { if (ev.key === 'Enter') openHistory(e.id); }},
      el('td', {}, e.name), el('td', {}, e.craft_id), el('td', {}, String(e.run_count)),
      el('td', {}, e.latest_run_status ? badge(e.latest_approval === 'none' ? e.latest_run_status : e.latest_approval) : '—'), el('td', {}, when(e.created_at))));
  }
}
async function openHistory(id) {
  R.history.selected = await call(`/api/experiments/${id}`);
  renderDetail();
  for (const row of byId('exp-table').tBodies[0].rows) row.classList.toggle('selected', row.dataset.id === id);
}
function notice(text, kind = 'ok') {
  const n = byId('detail-notice');
  if (n) { n.textContent = text; n.className = `notice ${kind}`; n.hidden = !text; n.scrollIntoView?.({block: 'nearest'}); }
}
async function histAct(label, fn) {
  try { const msg = await fn(); await openHistory(R.history.selected.id); notice(msg || `${label} done.`); }
  catch (e) { notice(`${label} failed: ${e.message}`, 'error'); }
}
function renderDetail() {
  const e = R.history.selected, d = byId('detail');
  d.replaceChildren(el('h2', {}, e.name),
    el('p', {class: 'hint'}, `${e.craft_id} · input ${short(e.input_hash)} · created ${when(e.created_at)}${e.parent_experiment_id ? ' · copy of ' + short(e.parent_experiment_id) : ''}`));
  if (e.notes) d.append(el('p', {}, e.notes));
  d.append(el('div', {class: 'buttons'},
    el('button', {type: 'button', class: 'primary', id: 'continue-wizard', 'data-testid': 'continue-wizard', onclick: () => resume(e.id)}, 'Continue in the wizard'),
    el('button', {type: 'button', id: 'duplicate', 'data-testid': 'duplicate', onclick: () => histAct('Duplicate', async () => { const c = await call(`/api/experiments/${e.id}/duplicate`, 'POST', {}); await loadExperiments(); await openHistory(c.id); return `Created “${c.name}”.`; })}, 'Duplicate')),
    el('p', {class: 'hint'}, '“Continue in the wizard” picks up at the right step for this experiment (run, review or export). “Duplicate” makes an editable copy; this one stays unchanged.'),
    el('div', {id: 'detail-notice', class: 'notice', hidden: true, role: 'status', 'data-testid': 'detail-notice'}),
    el('details', {}, el('summary', {}, 'Input snapshot'), el('pre', {}, JSON.stringify(e.input, null, 2))),
    el('h3', {}, `Runs (${e.runs.length})`));
  if (!e.runs.length) d.append(el('p', {class: 'hint'}, 'No runs yet. Use “Continue in the wizard” to run it.'));
  for (const run of [...e.runs].reverse()) d.append(runCard(run, e));
  d.append(el('div', {class: 'buttons'}, el('button', {type: 'button', id: 'compare-btn', 'data-testid': 'compare', disabled: R.history.compare.length !== 2, onclick: doCompare}, `Compare the two selected runs (${R.history.compare.length}/2)`)),
    el('p', {class: 'hint', id: 'cmp-selection', 'data-testid': 'cmp-selection'}, R.history.compare.length
      ? `Selected: ${R.history.compare.map(x => x.label).join('  vs  ')}. You can switch to another experiment and tick a second run.`
      : 'To compare, tick two finished runs of the same craft. They can come from different experiments.'));
}
function runCard(run, e) {
  const status = run.approval_status === 'none' ? 'failed' : run.approval_status;
  const box = el('input', {type: 'checkbox', class: 'cmp', 'aria-label': `Select run ${run.seq} for comparison`, checked: R.history.compare.some(x => x.id === run.id), disabled: run.run_status !== 'completed',
    onchange: ev => { R.history.compare = ev.target.checked ? [...R.history.compare, {id: run.id, label: `${e.name} #${run.seq}`}].slice(-2) : R.history.compare.filter(x => x.id !== run.id); renderDetail(); }});
  const extra = el('div', {class: 'runextra'});
  const small = (text, cls, fn, enabled = true) => el('button', {type: 'button', class: cls, onclick: fn, disabled: !enabled}, text);
  return el('div', {class: 'run', 'data-run': run.id, 'data-status': status},
    el('div', {class: 'runhead'}, box, el('strong', {}, `Run ${run.seq}`), badge(status), el('span', {class: 'hint'}, `${when(run.created_at)} · ${run.duration_ms} ms · result ${short(run.output_sha256)}`)),
    run.error ? el('p', {class: 'err'}, run.error.message) : null,
    run.reviewer || run.review_note ? el('p', {class: 'hint'}, `Reviewer: ${run.reviewer || '—'}${run.review_note ? ' — ' + run.review_note : ''}`) : null,
    el('div', {class: 'buttons small'},
      small('View result', 'view-output', async () => { const r = await call(`/api/runs/${run.id}`); extra.replaceChildren(el('pre', {class: 'run-output'}, JSON.stringify(r.envelope, null, 2))); }, run.run_status === 'completed'),
      small('Check it is repeatable', 'verify', () => histAct('Check', async () => { const v = await call(`/api/runs/${run.id}/verify`, 'POST'); return v.matches ? 'Verified: running the saved input again gives exactly the saved result.' : 'MISMATCH: running the saved input again gives a different result.'; }), run.run_status === 'completed'),
      small('Event log', 'history', async () => { const ev = await call(`/api/runs/${run.id}/events`); extra.replaceChildren(el('ol', {class: 'events'}, ...ev.map(x => el('li', {}, `${when(x.created_at)} — ${x.event_type} (${x.actor})${x.detail.note ? ': ' + x.detail.note : ''}`)))); })),
    extra);
}
async function doCompare() {
  const [a, b] = R.history.compare.map(x => x.id), panel = byId('compare-panel'), body = byId('compare-body');
  try {
    const d = await call(`/api/compare?run_a=${a}&run_b=${b}`);
    body.replaceChildren(el('p', {id: 'cmp-summary', 'data-testid': 'cmp-summary'}, d.identical_output ? 'Outputs are identical.' : `Outputs differ (${d.artifact_changes.length} result change(s), ${d.input_changes.length} input change(s)).`),
      changeTable('Input changes', d.input_changes), changeTable('Result changes', d.artifact_changes));
    if (d.warning_changes.only_in_a.length || d.warning_changes.only_in_b.length) {
      body.append(el('p', {class: 'hint'}, `Warnings only in A: ${d.warning_changes.only_in_a.join('; ') || '—'} · only in B: ${d.warning_changes.only_in_b.join('; ') || '—'}`));
    }
    if (d.truncated) body.append(el('p', {class: 'hint'}, 'Showing the first 500 differences.'));
    panel.hidden = false; panel.scrollIntoView?.({block: 'nearest'});
  } catch (e) { notice(`Compare failed: ${e.message}`, 'error'); }
}
function changeTable(title, changes) {
  const t = el('table', {class: 'table diff'}, el('thead', {}, el('tr', {}, el('th', {}, title), el('th', {}, 'Change'), el('th', {}, 'A'), el('th', {}, 'B'))));
  const body = el('tbody'), fmt = v => v === undefined ? '' : JSON.stringify(v);
  for (const c of changes) body.append(el('tr', {}, el('td', {}, c.path), el('td', {}, c.change), el('td', {}, fmt(c.a)), el('td', {}, fmt(c.b))));
  if (!changes.length) body.append(el('tr', {}, el('td', {colspan: '4'}, 'No differences')));
  t.append(body); return t;
}

// Reopen an experiment from History at the step where the work is (U4).
async function resume(id) {
  const exp = await call(`/api/experiments/${id}`);
  const craft = craftById(exp.craft_id);
  if (W.craftId && W.craftId !== exp.craft_id) W.inputs[W.craftId] = W.draft.input;
  W.craftId = exp.craft_id; W.expId = exp.id; R.exp = exp;
  W.draft.name = exp.name; W.draft.notes = exp.notes; W.draft.input = JSON.stringify(exp.input, null, 2);
  W.saved = {craftId: exp.craft_id, name: exp.name, notes: exp.notes, input: W.draft.input};
  await refreshExp();
  const run = latestRun();
  W.step = !run ? 3 : (run.run_status === 'failed' ? 3 : (['approved', 'exported'].includes(run.approval_status) ? 5 : 4));
  if (!isPilot(craft)) W.step = 1;
  R.errors = {}; R.notice = {}; persist();
  showView('new'); render();
}

// ---- startup -------------------------------------------------------------------------------
async function init() {
  R.crafts = await call('/api/crafts');
  byId('summary').textContent = `${R.crafts.length} crafts · ${R.crafts.filter(isPilot).length} ready to run`;
  for (const c of R.crafts.filter(isPilot)) byId('f-craft').append(el('option', {value: c.id}, c.name));
  restore();
  if (W.craftId && !craftById(W.craftId)) W.craftId = null;
  if (W.expId) {
    try { await refreshExp(); } catch (e) { W.expId = null; W.saved = null; R.exp = null; R.latest = null; }
  }
  if (W.step > reachedStep()) W.step = reachedStep();
  persist(); render();
  if (W.step === 2) ensureInput();
  try { await Art.init(); await Library.init(); await Light.init(); } catch (e) { /* the other tabs still work */ }
  try { await Lab.init(); } catch (e) { byId('lab-mount').replaceChildren(ui.errorBox(`The Scene Lab could not start: ${e.message}`, 'error-lab-startup')); }
  let saved = null;
  try { saved = localStorage.getItem('craftbox.view'); } catch (e) { /* ignore */ }
  if (saved && saved !== 'story' && VIEWS.includes(saved)) showView(saved);   // reopen on the tab where the work is
  document.body.dataset.ready = 'true';
}
for (const tab of document.querySelectorAll('.tab')) tab.addEventListener('click', () => showView(tab.dataset.view));
byId('refresh').addEventListener('click', () => loadExperiments().catch(e => banner(e.message, 'error')));
byId('f-craft').addEventListener('change', () => loadExperiments().catch(e => banner(e.message, 'error')));
byId('f-approval').addEventListener('change', () => loadExperiments().catch(e => banner(e.message, 'error')));
init().catch(e => { byId('wizard-mount').replaceChildren(ui.errorBox(`Craftbox could not start: ${e.message}`, 'error-startup')); document.body.dataset.ready = 'true'; });
