// Art Lab (CB2A): an 8-step wizard from choosing a scene to exporting an approved treatment, with a 2D set-layout editor.
// Follows guidelines/ui-standard.md (see docs/cb2a-ui-text-checklist.md). Needs ui.js and lab.js (shared project state).
const Art = (() => {
const {el, call} = ui;
const byId = id => document.getElementById(id);
const KEY = 'craftbox.art.v1';
const A = {v: 1, step: 1, projectId: null, sceneId: null, screenplayExp: null, planExp: '', styleExp: '', preset: 'warm_nostalgia', treatName: '', art: null, base: null, saved: null, note: '',
  sel: {obj: null, prop: null, beat: null, shot: null}, sub: {s5: 'palette'}, showCams: true, reviewer: '', rnote: '', cmp: ''};
const R = {projects: [], overview: null, sps: [], scenes: [], plans: [], planArt: null, spArt: null, presets: [], analysis: null, impact: null, runInfo: null, cmpResult: null, errors: {}, notice: {}, busy: null, armed: null, needs: {}, register: null, uid: 0};

const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(A)); } catch (e) { /* storage unavailable: drafts live for this session only */ } };
const restore = () => { try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.v === 1) Object.assign(A, s, {sel: {...A.sel, ...s.sel}, sub: {...A.sub, ...s.sub}}); } catch (e) { /* ignore */ } };

const GLOSS = {
  treatment: 'one complete design for how the scene looks. You can make several of the same scene and compare them.',
  'set layout': 'a top-down plan of the room: walls, doors, furniture and props.',
  blocking: 'where the director has the actors stand and move in each beat.',
  continuity: 'keeping things the same from shot to shot, such as where a prop is.',
  palette: 'the handful of colours the design is built from.',
  previz: 'a simple rough picture of a shot, made before filming.',
  manifest: 'a file that lists everything approved, so another tool can read it.',
  rebase: 'copy a design onto the newest script and plan, sending only the affected items back for review.',
  storyboard: 'a row of rough pictures that shows the shots in order.',
  beat: 'one emotional step of the scene.',
  asset: 'a picture or design file you keep for the project.',
};
const STEPS = ui.steps([
  {short: 'Scene', title: 'choose a scene and start a treatment', intro: 'Pick the scene you are designing and the director’s plan for where its people stand, then start a treatment. You can make several treatments of one scene and compare them. Nothing in the screenplay or the director’s plan is changed.'},
  {short: 'Location', title: 'describe the location', intro: 'Describe the place where the scene happens: what kind of place it is, its architecture, its doors and its atmosphere. Keep the name close to the scene heading so everyone means the same place. Saving makes a new version and keeps the earlier ones.'},
  {short: 'Set layout', title: 'arrange the set layout', intro: 'Arrange the room on a top-down plan. Drag a piece to move it, or select it and press the arrow keys. The plan uses the director’s stage, so you can see where the actors stand and walk. This is a plan, not a picture.'},
  {short: 'Props', title: 'track the props', intro: 'List every object the audience will notice. Props found in the script are filled in for you. Give each one a position, and say where it is as the scene goes on, so it never jumps between shots.'},
  {short: 'Visual style', title: 'define the visual style', intro: 'Choose the colours, textures, materials and period that give this treatment its look. You can change a single shot without leaving the overall look, and attach picture files you have registered.'},
  {short: 'Comparison', title: 'compare two treatments', intro: 'Put two treatments of this scene side by side. Each is compared on measures you can check, with a plain statement of how it is likely to feel and what that rests on.'},
  {short: 'Review', title: 'review the design and decide', intro: 'Read what the checks found, deal with anything that is out of date after a script or plan change, then approve or reject this treatment with your name. The checks are advice only and never stop you from approving.'},
  {short: 'Export', title: 'approve and export', intro: 'An approved treatment can be exported as files for later tools: the art direction, the assets it uses, notes for storyboards and a prop list. Nothing is sent to Dreambox or any other program.'},
]);
const TERMS = [['treatment', 'blocking'], ['treatment', 'beat', 'blocking'], ['set layout', 'blocking', 'beat', 'treatment'], ['continuity', 'blocking', 'beat'], ['palette', 'asset', 'treatment', 'beat'], ['treatment', 'palette'], ['treatment', 'rebase', 'continuity', 'set layout', 'blocking'], ['treatment', 'manifest', 'storyboard', 'previz', 'asset']];

// ---- element helpers (every field gets a real label: the standard asks for plain, findable controls) -------------------------------------
const uid = p => `${p}-${++R.uid}`;
function row(label, ctl, hint) {
  const lab = el('label', {}, label);
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(ctl.tagName)) { ctl.id = ctl.id || uid('f'); lab.setAttribute('for', ctl.id); }
  else { lab.id = uid('l'); ctl.setAttribute('role', 'group'); ctl.setAttribute('aria-labelledby', lab.id); }
  return el('div', {class: 'formrow'}, lab, ctl, hint ? el('span', {class: 'hint'}, hint) : null);
}
const touch = () => { persist(); afterEdit(); };
function bind(obj, key, props = {}, tag = 'input', conv) {
  const node = el(tag, props);
  node.value = obj[key] ?? '';
  node.addEventListener('input', () => { obj[key] = conv ? conv(node.value) : node.value; touch(); });
  return node;
}
const num = v => (v === '' ? null : Number(v));
function sel(obj, key, options, props = {}, opt = {}) {
  const node = el('select', props);
  for (const o of options) { const [v, label] = Array.isArray(o) ? o : [o, o]; node.append(el('option', {value: v}, label)); }
  node.value = obj[key] ?? '';
  node.addEventListener('change', () => { obj[key] = node.value === '' && opt.nullable ? null : node.value; touch(); if (opt.render) render(); });
  return node;
}
const btn = (label, fn, props = {}) => el('button', {type: 'button', onclick: fn, ...props}, label);
function guarded(label, key, fn, props = {}) {
  const armed = R.armed === key;
  return el('button', {type: 'button', class: armed ? 'danger' : '', onclick: () => { if (armed) { R.armed = null; fn(); } else { R.armed = key; render(); } }, ...props}, armed ? 'Click again to confirm' : label);
}
const jsonOf = o => JSON.stringify(o);
const dirty = () => (!A.art ? 'none' : (!A.saved ? 'unsaved' : (A.saved === jsonOf(A.art) ? 'saved' : 'changed')));
const STATE = {unsaved: 'Not saved yet. Saving makes a new version and keeps what you typed on screen.', saved: 'Saved. What you typed is still shown here.', changed: 'Changed, not saved yet. Saving makes a new version; earlier versions stay exactly as they were.'};
const when = iso => (iso ? iso.replace('T', ' ').replace(/\.\d+Z$/, 'Z') : '');
const badge = t => el('span', {class: `badge b-${t}`}, t);
const names = () => Object.fromEntries(((R.spArt && R.spArt.characters) || []).map(c => [c.id, c.name]));
const scene = () => R.spArt && R.spArt.scenes.find(s => s.id === A.sceneId);
const plan = () => R.planArt;
function nextId(prefix, existing) {
  const nums = existing.filter(x => x.startsWith(prefix)).map(x => parseInt(x.slice(prefix.length), 10)).filter(Number.isFinite);
  return prefix + String((nums.length ? Math.max(...nums) : 0) + 1);
}
function friendly(message) {   // turn a schema path into words and say how to recover
  const m = message.replace(/\$\./g, '').replace(/\[(\d+)\]/g, (_, n) => ` #${Number(n) + 1}`).replace(/\./g, ' › ');
  return `Cannot save yet: ${m}. Change the field it names, then press Save again. Nothing you typed was lost.`;
}

// ---- feedback beside the control (U5) ---------------------------------------------------------------------------------------------------
function fail(key, message) { R.errors[key] = message; render(); ui.reveal(`error-${key}`); }
async function withBusy(key, what, fn) {
  delete R.errors[key]; delete R.notice[key];
  R.busy = {key, what, startedAt: Date.now()}; render();
  try { await fn(); } catch (e) { R.errors[key] = key === 'save' ? friendly(e.message) : e.message; }
  finally { R.busy = null; render(); if (R.errors[key]) ui.reveal(`error-${key}`); }
}
const busy = () => !!R.busy;
const feedback = key => [R.busy && R.busy.key === key ? ui.progress({what: R.busy.what, startedAt: R.busy.startedAt}) : null,
  R.errors[key] ? ui.errorBox(R.errors[key], `error-${key}`) : null, R.notice[key] ? el('div', {class: 'notice ok', 'data-testid': `notice-${key}`, role: 'status'}, R.notice[key]) : null];
const glossaryBlock = terms => el('section', {class: 'glossary', 'data-testid': 'glossary'}, el('h3', {}, 'Words used on this screen'),
  el('dl', {}, ...terms.flatMap(t => [el('dt', {'data-gloss': t}, t), el('dd', {}, GLOSS[t])])));

const glossary = () => null;   // glossaries are built from the words actually on screen: see fillGlossary
function fillGlossary(root) {
  if (!root) return;
  const body = [...root.querySelectorAll('h1, h2, h3, .intro, .hint, label, button, p')].filter(e => !e.closest('.glossary')).map(e => e.textContent).join(' | ').toLowerCase();
  const terms = Object.keys(GLOSS).filter(t => new RegExp('\\b' + t + 's?\\b').test(body));
  const old = root.querySelector('.glossary'); if (old) old.remove();
  if (terms.length) root.insertBefore(glossaryBlock(terms), root.querySelector('#art-nav'));
}
// ---- data -----------------------------------------------------------------------------------------------------------------------------------
async function loadProjects() { try { R.projects = await call('/api/lab/projects'); } catch (e) { R.projects = []; } }
async function loadOverview() {
  if (!A.projectId) { R.overview = null; return; }
  try {
    R.overview = await call(`/api/art/projects/${encodeURIComponent(A.projectId)}`);
    const lab = await call(`/api/lab/projects/${encodeURIComponent(A.projectId)}`);
    R.sps = lab.screenplay_versions.filter(v => v.run_id); R.plans = lab.plans;
    R.register = R.overview.register;
  } catch (e) { R.overview = null; }
}
async function loadScreenplay(experimentId) {
  const exp = await call(`/api/experiments/${experimentId}`);
  const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
  if (!run) throw new Error('That screenplay revision has no completed run. Open it in the Scene Lab and save it again.');
  R.spArt = (await call(`/api/runs/${run.id}`)).envelope.artifact;
  R.scenes = R.spArt.scenes;
}
async function loadPlan(experimentId) {
  if (!experimentId) { R.planArt = null; return; }
  const exp = await call(`/api/experiments/${experimentId}`);
  const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
  R.planArt = run ? (await call(`/api/runs/${run.id}`)).envelope.artifact : null;
}
function adopt(r) {
  const run = r.run;
  if (run.run_status === 'failed') throw new Error(run.error.message);
  const a = run.envelope.artifact;
  A.base = {experimentId: r.experiment.id, runId: run.id};
  const doc = JSON.parse(JSON.stringify(a)); delete doc.analysis;
  A.art = doc; A.saved = jsonOf(doc); R.analysis = a.analysis; R.impact = null; R.runInfo = null; R.cmpResult = null;
  A.sceneId = a.scene_id;
  if (!A.sel.beat) A.sel.beat = ((scene() || {}).beats || [{}])[0].id || null;
  persist();
}
async function defaultPlan() {
  const plans = R.plans.filter(p => p.scene_id === A.sceneId && p.run_id);
  A.planExp = plans.length ? plans[plans.length - 1].experiment_id : '';
  await loadPlan(A.planExp);
}
async function draft() {
  if (!A.screenplayExp || !A.sceneId) return fail('draft', 'Choose a screenplay revision and a scene first.');
  if (!A.treatName.trim()) return fail('draft', 'Give the treatment a name first, for example “Warm nostalgia”.');
  await withBusy('draft', 'Drafting the treatment', async () => {
    await loadPlan(A.planExp);
    const r = await call('/api/art/draft', 'POST', {screenplay_experiment_id: A.screenplayExp, scene_id: A.sceneId, name: A.treatName.trim(), preset: A.preset, plan_experiment_id: A.planExp || null, style_experiment_id: A.styleExp || null});
    adopt(r); await loadOverview();
    R.notice.draft = `Drafted “${A.art.treatment.name}” with ${A.art.layout.objects.length} set pieces and ${A.art.props.length} props. Click “Next: describe the location” to continue.`;
  });
}
async function openTreatment(experimentId) {
  await withBusy('draft', 'Opening the treatment', async () => {
    const exp = await call(`/api/experiments/${experimentId}`);
    const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
    if (!run) throw new Error('That treatment has no completed run.');
    A.projectId = exp.input.screenplay.project.id; A.screenplayExp = (exp.input.source_ref || {}).screenplay_experiment_id || A.screenplayExp; A.planExp = (exp.input.source_ref || {}).plan_experiment_id || '';
    R.spArt = exp.input.screenplay; R.scenes = R.spArt.scenes; A.sceneId = exp.input.scene_id; R.planArt = exp.input.direction_plan || null;
    adopt({experiment: exp, run: await call(`/api/runs/${run.id}`)});
    await loadOverview(); await loadImpact();
    R.notice.draft = `Opened “${exp.name}”. Click “Next: describe the location” to continue.`;
  });
}
async function save() {
  const stamp = new Date().toISOString().slice(11, 16);
  const n = ((R.overview && R.overview.treatments.filter(t => t.treatment_id === A.art.treatment.id).length) || 0) + 1;
  await withBusy('save', 'Saving this version', async () => {
    const r = await call('/api/art/save', 'POST', {base_experiment_id: A.base.experimentId, art: A.art, name: `${A.art.treatment.name} v${n + 1}`, note: (A.note || '').trim() || `saved ${stamp}`});
    adopt(r); await loadOverview(); await loadImpact(); await loadRun();
    R.notice.save = `Saved as a new version of “${A.art.treatment.name}”. The earlier version is unchanged.`;
  });
}
async function check() {
  await withBusy('check', 'Checking the design', async () => {
    const out = await call('/api/art/analyze', 'POST', {base_experiment_id: A.base.experimentId, art: A.art});
    R.analysis = out.analysis; R.notice.check = `Checked: ${out.analysis.readiness.attention} item(s) need attention and ${out.analysis.readiness.notes} note(s). Nothing was saved.`;
  });
}
async function loadImpact() { if (!A.base) return; try { R.impact = await call(`/api/art/treatments/${A.base.experimentId}/impact`); } catch (e) { R.impact = null; } }
async function loadRun() { if (!A.base) { R.runInfo = null; return; } try { R.runInfo = await call(`/api/runs/${A.base.runId}`); } catch (e) { R.runInfo = null; } }
async function rebase() {
  await withBusy('rebase', 'Rebasing the treatment', async () => {
    const r = await call(`/api/art/treatments/${A.base.experimentId}/rebase`, 'POST', {});
    adopt(r); await loadOverview(); await loadImpact(); await loadRun();
    R.notice.rebase = `Created a new version on the latest script and plan. ${r.impact.affected_props.length + r.impact.affected_variations.length} item(s) that depend on changed material are back in review; everything else keeps its decision. The old version is unchanged.`;
  });
}

// ---- save block (U2, U3) ------------------------------------------------------------------------------------------------------------------
function saveBlock() {
  const s = dirty();
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(A, 'note', {maxlength: '200', placeholder: 'For example: moved the counter to open the floor', 'data-testid': 'art-note'})),
    el('p', {class: `state s-${s}`, 'data-testid': 'art-state', 'aria-live': 'polite'}, STATE[s] || ''),
    el('div', {class: 'buttons'}, el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'art-save', onclick: save, disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''}, 'Save art direction version')),
    ...feedback('save'));
}
function afterEdit() {
  for (const n of document.querySelectorAll('#view-art [data-testid="art-state"]')) { const s = dirty(); n.textContent = STATE[s] || ''; n.className = `state s-${s}`; }
  for (const b of document.querySelectorAll('#view-art [data-testid="art-save"]')) { const same = dirty() === 'saved'; b.disabled = same || busy(); b.title = same ? 'Nothing has changed since the last save.' : ''; }
  renderNav();
}

// ---- step 1: scene ----------------------------------------------------------------------------------------------------------------------------
function step1() {
  const proj = R.projects;
  const items = (R.overview && R.overview.treatments) || [];
  const started = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'start-form'}, el('h2', {}, 'Start a new treatment'),
    !proj.length ? el('p', {class: 'hint', 'data-empty': 'projects', 'data-testid': 'no-projects'}, 'There are no saved screenplays yet. Open the Scene Lab, load the sample scene and save it, then come back and press “Refresh the list”.') : null,
    row('Project', sel(A, 'projectId', [['', '— choose a project —'], ...proj.map(p => [p.project_id, p.title || p.project_id])], {'data-testid': 'a-project'}, {nullable: true, render: false}), 'Projects come from the Scene Lab.'),
    row('Screenplay revision', sel(A, 'screenplayExp', [['', '— choose a revision —'], ...R.sps.map(v => [v.experiment_id, `Revision ${v.revision}${v.note ? ' — ' + v.note : ''}`])], {'data-testid': 'a-sp'}, {nullable: true})),
    row('Scene', sel(A, 'sceneId', [['', '— choose a scene —'], ...R.scenes.map(s => [s.id, `${s.id} — ${s.slugline}`])], {'data-testid': 'a-scene'}, {nullable: true})),
    row('Director’s plan', sel(A, 'planExp', [['', '— none (use the script only) —'], ...R.plans.filter(p => p.scene_id === A.sceneId && p.run_id).map(p => [p.experiment_id, `${p.name} (${p.approach || 'plan'})`])], {'data-testid': 'a-plan'}), 'The plan supplies the stage, the actors’ blocking and the shot IDs.'),
    row('Starting point', el('div', {class: 'cards'}, ...R.presets.map(p => el('label', {class: 'craftcard' + (A.preset === p.id ? ' selected' : ''), 'data-testid': `preset-${p.id}`},
      el('input', {type: 'radio', name: 'preset', value: p.id, checked: A.preset === p.id, 'aria-label': p.name, onchange: () => { A.preset = p.id; if (!A.treatName.trim()) A.treatName = p.id === 'blank' ? '' : p.name; persist(); render(); }}),
      el('span', {class: 'cname'}, p.name), el('span', {class: 'cdesc'}, p.summary || 'Only the set pieces and props the script and plan already name.'))))),
    row('Project style profile', sel(A, 'styleExp', [['', '— none —'], ...((R.overview && R.overview.styles) || []).map(s => [s.experiment_id, s.name])], {'data-testid': 'a-style'}), 'Optional. Copies its palette, materials and period; its rules are then checked.'),
    row('Treatment name', bind(A, 'treatName', {maxlength: '120', placeholder: 'For example: Warm nostalgia', 'data-testid': 'a-name'})),
    el('div', {class: 'buttons'}, btn('Draft the treatment', draft, {class: 'primary', 'data-testid': 'a-draft', disabled: busy()}), btn('Refresh the list', async () => { await loadProjects(); await loadOverview(); render(); }, {'data-testid': 'a-refresh'})),
    ...feedback('draft'));
  const existing = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'open-form'}, el('h2', {}, 'Or open a saved treatment'),
    items.length ? el('table', {class: 'table'}, el('thead', {}, el('tr', {}, ...['Treatment', 'Scene', 'Status', 'Checks', ''].map(h => el('th', {}, h)))),
      el('tbody', {}, ...[...items].reverse().map(t => el('tr', {'data-testid': `tr-${t.experiment_id}`}, el('td', {}, t.name), el('td', {}, t.scene_id), el('td', {}, t.approval_status ? badge(t.approval_status) : '—', t.stale ? badge('out of date') : null),
        el('td', {}, t.attention != null ? `${t.attention} need attention, ${t.notes} notes` : '—'), el('td', {}, btn('Open', () => openTreatment(t.experiment_id), {'data-testid': `open-${t.experiment_id}`, disabled: busy()})))))) :
      el('p', {class: 'hint', 'data-empty': 'treatments', 'data-testid': 'no-treatments'}, 'No treatments saved for this project yet. Choose a starting point above and press “Draft the treatment”.'));
  return el('div', {}, started, existing);
}

// ---- step 2: location ---------------------------------------------------------------------------------------------------------------------------
function listEditor(items, makeNew, render1, addLabel, testid, emptyText) {
  return el('div', {}, !items.length ? el('p', {class: 'hint', 'data-empty': testid}, emptyText) : null,
    ...items.map((it, i) => el('div', {class: 'listcard', 'data-testid': `${testid}-${i}`}, render1(it, i), el('div', {class: 'buttons'}, guarded('Remove', `rm-${testid}-${i}`, () => { items.splice(i, 1); touch(); render(); }, {'aria-label': `Remove ${testid} ${i + 1}`})))),
    el('div', {class: 'buttons'}, btn(addLabel, () => { items.push(makeNew()); touch(); render(); }, {'data-testid': `add-${testid}`})));
}
function step2() {
  const L = A.art.location, env = L.environment = L.environment || {};
  const doors = A.art.layout.objects.filter(o => o.kind === 'architecture');
  const dopt = [['', '— choose —'], ...doors.map(o => [o.id, o.name])];
  const heading = scene() ? `${scene().slugline}` : '';
  L.entrances = L.entrances || []; L.exits = L.exits || []; L.architecture = L.architecture || []; L.details = L.details || [];
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'location-form'}, el('h2', {}, `${A.art.treatment.name}: the place`),
    heading ? el('p', {class: 'hint'}, `The script heading reads: ${heading}`) : null,
    row('Name of the place', bind(L, 'name', {'data-testid': 'loc-name', maxlength: '120'})),
    row('Inside or outside', sel(L, 'kind', [['interior', 'Interior (inside)'], ['exterior', 'Exterior (outside)']], {'data-testid': 'loc-kind'})),
    row('Real or invented', sel(L, 'setting', [['real', 'A real place'], ['fictional', 'An invented place']], {'data-testid': 'loc-setting'})),
    row('Description', bind(L, 'description', {rows: '3', 'data-testid': 'loc-desc', placeholder: 'What the place is and why these people are in it'}, 'textarea')),
    el('h3', {}, 'Architecture'), listEditor(L.architecture, () => ({id: nextId('ARCH-', L.architecture.map(a => a.id)), name: '', description: ''}), a => el('div', {}, row('Feature', bind(a, 'name', {'data-testid': 'arch-name', placeholder: 'For example: tall front window'})), row('Detail', bind(a, 'description'))),
      'Add an architectural feature', 'arch', 'No architecture listed yet. Press “Add an architectural feature” to describe walls, windows or ceilings.'),
    el('h3', {}, 'Entrances and exits'), el('p', {class: 'hint'}, 'Choose pieces from the set layout. The director’s blocking uses these doors, so the names must match.'),
    listEditor(L.entrances, () => ({object_id: '', name: '', note: ''}), e => el('div', {}, row('Entrance', sel(e, 'object_id', dopt, {'data-testid': 'entrance-select'}, {render: true})), row('Note', bind(e, 'note', {placeholder: 'For example: opens inward; bell rings'}))),
      'Add an entrance', 'entrance', 'No entrance yet. Press “Add an entrance” and choose the door the actors use.'),
    listEditor(L.exits, () => ({object_id: '', name: '', note: ''}), e => row('Exit', sel(e, 'object_id', dopt, {'data-testid': 'exit-select'}, {render: true})), 'Add an exit', 'exit', 'No exit yet. Press “Add an exit” and choose the door the actors leave by.'),
    el('h3', {}, 'Atmosphere'), row('Time of day', bind(env, 'time_of_day', {'data-testid': 'env-time'})), row('Weather', bind(env, 'weather', {placeholder: 'For example: steady rain'})),
    row('Atmosphere', bind(env, 'atmosphere', {rows: '2', 'data-testid': 'env-atmos'}, 'textarea')), row('Sounds', bind(env, 'sounds', {placeholder: 'For example: rain on glass, a ticking clock'})),
    el('h3', {}, 'Other details'), listEditor(L.details, () => '', (d, i) => row('Detail', el('input', {value: d, 'data-testid': 'detail-text', oninput: ev => { L.details[i] = ev.target.value; touch(); }})), 'Add a detail', 'detail', 'No extra details yet. Press “Add a detail” for anything else worth remembering about the place.'),
    findings('location', 'entrance'), el('hr'), saveBlock(), glossary(TERMS[1]));
}
function findings(...rules) {
  const list = ((R.analysis || {}).issues || []).filter(i => rules.includes(i.rule));
  if (!list.length) return null;
  return el('div', {class: 'auditbox', 'data-testid': 'findings'}, el('h3', {}, 'What the checks found (advice only)'), findingsList(list));
}
function findingsList(list) {
  return el('ul', {class: 'audit'}, ...list.map(i => el('li', {class: i.severity === 'attention' ? 'advice' : 'ok', 'data-rule': i.rule, 'data-severity': i.severity},
    el('span', {class: 'mark'}, i.severity === 'attention' ? '!' : 'i'), el('span', {}, el('span', {class: 'label'}, i.severity === 'attention' ? 'Needs attention: ' : 'Note: '), i.message, el('br'), el('span', {class: 'msg'}, `How to fix it: ${i.fix}`)))));
}

// ---- step 3: set layout editor -------------------------------------------------------------------------------------------------------------------
const W = 520, H = 380, PAD = 36;
const COLORS = ['#8e88ff', '#f2a65a', '#6fd3a8', '#e87aa7'];
const KIND_FILL = {architecture: '#3a4a6b', furniture: '#5b4a3a', decor: '#3d5a4a'};
function layoutSvg(doc, opts = {}) {
  const ns = 'http://www.w3.org/2000/svg';
  const mk = (t, a, txt) => { const n = document.createElementNS(ns, t); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); if (txt != null) n.textContent = txt; return n; };
  const svg = mk('svg', {viewBox: `${-PAD} ${-PAD} ${W + 2 * PAD} ${H + 2 * PAD + 14}`, class: 'stage layout', role: 'application', 'aria-label': opts.label || 'Set layout plan. Select a piece and use the arrow keys to move it.', 'data-testid': opts.testid || 'layout-svg'});
  svg.append(mk('rect', {x: 0, y: 0, width: W, height: H, class: 'floor'}));
  for (let i = 1; i < 5; i++) svg.append(mk('line', {x1: W * i / 5, y1: 0, x2: W * i / 5, y2: H, class: 'grid'}), mk('line', {x1: 0, y1: H * i / 5, x2: W, y2: H * i / 5, class: 'grid'}));
  svg.append(mk('text', {x: W / 2, y: -10, class: 'cap', 'text-anchor': 'middle'}, 'back wall'), mk('text', {x: W / 2, y: H + 22, class: 'cap', 'text-anchor': 'middle'}, 'audience side (camera side A)'));
  const P = opts.plan !== undefined ? opts.plan : plan();   // other labs (Lighting) pass their own plan and names, so this one editor serves them too
  const beat = opts.beat && P ? (P.blocking || []).find(b => b.beat_id === opts.beat) : null;
  const nm = opts.names || names();
  if (beat) {
    const cs = beat.characters;
    if (cs.length >= 2) svg.append(mk('line', {x1: cs[0].end.x * W, y1: cs[0].end.y * H, x2: cs[1].end.x * W, y2: cs[1].end.y * H, class: 'axisline'}));
    cs.forEach((c, i) => { const col = COLORS[i % COLORS.length];
      svg.append(mk('polyline', {points: (c.path || [c.start, c.end]).map(p => `${p.x * W},${p.y * H}`).join(' '), class: 'path', stroke: col}),
        mk('circle', {cx: c.end.x * W, cy: c.end.y * H, r: 11, fill: col, class: 'enddot', opacity: '0.85'}), mk('text', {x: c.end.x * W, y: c.end.y * H + 4, class: 'ini', 'text-anchor': 'middle'}, (nm[c.character_id] || '?')[0].toUpperCase())); });
  }
  if (opts.cams && P && beat) {
    for (const s of (P.shots || []).filter(x => x.beat_id === opts.beat && x.status !== 'rejected' && (!opts.shotIds || opts.shotIds.includes(x.shot_id)))) {
      const c = (s.previz || {}).camera_position; if (!c || c.x < -0.2 || c.x > 1.2 || c.y < -0.3 || c.y > 1.35) continue;
      const cx = Math.max(-20, Math.min(W + 20, c.x * W)), cy = Math.max(-28, Math.min(H + 28, c.y * H));
      svg.append(mk('path', {d: `M${cx - 6},${cy + 6} L${cx + 6},${cy + 6} L${cx},${cy - 7} Z`, class: 'cam', 'data-camera': s.shot_id}), mk('text', {x: cx, y: cy + 17, class: 'cap', 'text-anchor': 'middle'}, s.shot_id.split('-').pop()));
    }
  }
  const drag = opts.editable ? opts.onMove : null;
  for (const o of doc.layout.objects) {
    const sel_ = opts.selected === o.id;
    const g = mk('g', {class: 'piece' + (sel_ ? ' sel' : ''), 'data-obj': o.id, tabindex: opts.editable ? '0' : '-1', role: 'button', 'aria-label': `${o.name}, ${o.kind}, at ${o.x.toFixed(2)}, ${o.y.toFixed(2)}${opts.editable ? '. Press arrow keys to move.' : ''}`});
    g.append(mk('rect', {x: (o.x - o.w / 2) * W, y: (o.y - o.h / 2) * H, width: o.w * W, height: o.h * H, fill: KIND_FILL[o.kind] || '#444', class: 'obj' + (o.solid ? ' solid' : ''), rx: 3}),
      mk('text', {x: o.x * W, y: (o.y + o.h / 2) * H + 11, class: 'cap', 'text-anchor': 'middle'}, o.name.slice(0, 16)));
    svg.append(g);
  }
  for (const p of doc.props) {
    if (!p.position) continue;
    const sel_ = opts.selectedProp === p.id;
    const g = mk('g', {class: 'prop' + (sel_ ? ' sel' : ''), 'data-prop': p.id, tabindex: opts.editable ? '0' : '-1', role: 'button', 'aria-label': `Prop ${p.name}, at ${p.position.x.toFixed(2)}, ${p.position.y.toFixed(2)}${opts.editable ? '. Press arrow keys to move.' : ''}`});
    g.append(mk('circle', {cx: p.position.x * W, cy: p.position.y * H, r: 7, fill: p.kind === 'personal' ? '#e0a85a' : (p.kind === 'practical' ? '#f4e29a' : '#c9d2ea'), class: 'propdot'}), mk('text', {x: p.position.x * W + 10, y: p.position.y * H + 3, class: 'cap'}, p.name.slice(0, 14)));
    svg.append(g);
  }
  if (opts.overlay) opts.overlay(svg, mk, {W, H});
  if (drag) wire(svg, doc, opts);
  return svg;
}
function wire(svg, doc, opts) {
  const pt = ev => { const m = svg.getScreenCTM().inverse(); const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; const q = p.matrixTransform(m); return {x: Math.round(Math.max(0, Math.min(1, q.x / W)) * 100) / 100, y: Math.round(Math.max(0, Math.min(1, q.y / H)) * 100) / 100}; };
  let drag = null;
  const target = el_ => { const g = el_.closest('[data-obj],[data-prop]'); if (!g) return null; return g.dataset.obj ? {kind: 'obj', id: g.dataset.obj, node: g} : {kind: 'prop', id: g.dataset.prop, node: g}; };
  const item = t => (t.kind === 'obj' ? doc.layout.objects.find(o => o.id === t.id) : doc.props.find(p => p.id === t.id));
  const place = (t, x, y) => { const it = item(t); if (t.kind === 'obj') { it.x = x; it.y = y; } else it.position = {x, y}; };
  svg.addEventListener('pointerdown', ev => { const t = target(ev.target); if (!t) return; drag = t; svg.setPointerCapture(ev.pointerId); opts.onSelect(t.kind, t.id); ev.preventDefault(); });
  svg.addEventListener('pointermove', ev => {
    if (!drag) return; const p = pt(ev); place(drag, p.x, p.y);
    const it = item(drag);
    if (drag.kind === 'obj') { const r = drag.node.querySelector('rect'); r.setAttribute('x', (it.x - it.w / 2) * W); r.setAttribute('y', (it.y - it.h / 2) * H); const t = drag.node.querySelector('text'); t.setAttribute('x', it.x * W); t.setAttribute('y', (it.y + it.h / 2) * H + 11); }
    else { const c = drag.node.querySelector('circle'); c.setAttribute('cx', p.x * W); c.setAttribute('cy', p.y * H); const t = drag.node.querySelector('text'); t.setAttribute('x', p.x * W + 10); t.setAttribute('y', p.y * H + 3); }
  });
  const end = () => { if (drag) { drag = null; touch(); render(); } };
  svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
  svg.addEventListener('keydown', ev => {
    const t = target(ev.target); const d = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[ev.key];
    if (!t || !d) return; ev.preventDefault();
    const it = item(t), step = ev.shiftKey ? 0.05 : 0.01, cur = t.kind === 'obj' ? {x: it.x, y: it.y} : (it.position || {x: 0.5, y: 0.5});
    place(t, Math.round(Math.max(0, Math.min(1, cur.x + d[0] * step)) * 100) / 100, Math.round(Math.max(0, Math.min(1, cur.y + d[1] * step)) * 100) / 100);
    opts.onSelect(t.kind, t.id); touch(); render();
    const again = document.querySelector(`#view-art [data-${t.kind === 'obj' ? 'obj' : 'prop'}="${t.id}"]`); if (again) again.focus();
  });
}
function step3() {
  const doc = A.art, o = doc.layout.objects.find(x => x.id === A.sel.obj) || null;
  const beats = (scene() || {}).beats || [];
  const mats = [['', '— none —'], ...(doc.style.materials || []).map(m => [m.id, m.name])], texs = [['', '— none —'], ...(doc.style.textures || []).map(t => [t.id, t.name])];
  const svg = layoutSvg(doc, {editable: true, selected: A.sel.obj, selectedProp: A.sel.prop, beat: A.sel.beat, cams: A.showCams, onSelect: (k, id) => { if (k === 'obj') { A.sel.obj = id; A.sel.prop = null; } else { A.sel.prop = id; A.sel.obj = null; } persist(); },
    onMove: true, label: 'Set layout plan. Drag a piece, or select it and press the arrow keys to move it.', testid: 'layout-svg'});
  const inspector = o ? el('div', {class: 'subcard picked', 'data-testid': 'obj-inspector'}, el('h3', {}, `Selected: ${o.name}`),
    row('Name', bind(o, 'name', {'data-testid': 'obj-name'}, 'input')), row('Kind', sel(o, 'kind', [['architecture', 'Architecture'], ['furniture', 'Furniture'], ['decor', 'Decor']], {'data-testid': 'obj-kind'})),
    row('Position', el('div', {class: 'inline'}, bind(o, 'x', {type: 'number', min: '0', max: '1', step: '0.01', 'aria-label': 'Position x', 'data-testid': 'obj-x', oninput: () => render()}, 'input', Number), bind(o, 'y', {type: 'number', min: '0', max: '1', step: '0.01', 'aria-label': 'Position y', 'data-testid': 'obj-y', oninput: () => render()}, 'input', Number)), 'x runs left to right, y from the back wall to the audience.'),
    row('Size', el('div', {class: 'inline'}, bind(o, 'w', {type: 'number', min: '0.01', max: '1', step: '0.01', 'aria-label': 'Width', 'data-testid': 'obj-w'}, 'input', Number), bind(o, 'h', {type: 'number', min: '0.01', max: '1', step: '0.01', 'aria-label': 'Depth', 'data-testid': 'obj-h'}, 'input', Number))),
    row('Blocks movement', el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!o.solid, 'data-testid': 'obj-solid', onchange: ev => { o.solid = ev.target.checked; touch(); render(); }}), ' people cannot walk through it')),
    row('Material', sel(o, 'material_id', mats, {}, {nullable: true})), row('Texture', sel(o, 'texture_id', texs, {}, {nullable: true})), row('Notes', bind(o, 'notes', {rows: '2'}, 'textarea')),
    el('div', {class: 'buttons'}, btn('Duplicate this piece', () => { const c = JSON.parse(JSON.stringify(o)); c.id = nextId('D-', doc.layout.objects.map(x => x.id)); c.x = Math.min(1, o.x + 0.06); c.name = `${o.name} (copy)`; doc.layout.objects.push(c); A.sel.obj = c.id; touch(); render(); }, {'data-testid': 'obj-dup'}),
      guarded('Delete this piece', `rmobj-${o.id}`, () => { doc.layout.objects = doc.layout.objects.filter(x => x.id !== o.id); A.sel.obj = null; touch(); render(); }, {'data-testid': 'obj-del'}))) :
    el('p', {class: 'hint', 'data-empty': 'selection', 'data-testid': 'no-selection'}, 'Nothing is selected. Click a piece on the plan, or press “Add a piece”, to change its name, size and position.');
  const add = {name: '', kind: 'furniture'};
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'layout-form'}, el('h2', {}, `${doc.treatment.name}: the set layout`),
    row('Show the actors for the beat', sel(A.sel, 'beat', beats.map(b => [b.id, b.title]), {'data-testid': 'layout-beat'}, {render: true}), 'Circles are the actors from the director’s blocking; triangles are the cameras for that beat; the dashed line is the 180° line.'),
    el('div', {class: 'chips'}, el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: A.showCams, 'data-testid': 'show-cams', onchange: ev => { A.showCams = ev.target.checked; persist(); render(); }}), ' show camera positions')),
    el('div', {class: 'blockgrid'}, el('div', {}, svg, el('p', {class: 'hint'}, 'Drag to move. With a piece selected, the arrow keys move it by 0.01; hold Shift for 0.05.')),
      el('div', {}, inspector, el('div', {class: 'listcard'}, el('h3', {}, 'Add a piece'), row('Name', el('input', {placeholder: 'For example: Reading armchair', 'data-testid': 'add-name', oninput: ev => { add.name = ev.target.value; }})),
        row('Kind', sel(add, 'kind', [['furniture', 'Furniture'], ['architecture', 'Architecture'], ['decor', 'Decor']], {'data-testid': 'add-kind'})),
        el('div', {class: 'buttons'}, btn('Add a piece', () => { const n = (add.name || '').trim(); if (!n) return fail('layout', 'Type a name for the new piece first.'); const id = nextId('D-', doc.layout.objects.map(x => x.id));
          doc.layout.objects.push({id, name: n, kind: add.kind, x: 0.5, y: 0.5, w: 0.1, h: 0.08, solid: add.kind === 'furniture', material_id: null, texture_id: null, notes: ''}); A.sel.obj = id; touch(); render(); }, {'data-testid': 'add-piece'})), ...feedback('layout')))),
    el('div', {class: 'buttons'}, btn('Check the design', check, {'data-testid': 'a-check', disabled: busy() || !A.base, title: !A.base ? 'Draft or open a treatment first.' : 'Looks for problems without saving.'})), ...feedback('check'),
    findings('layout', 'entrance', 'location'), el('hr'), saveBlock(), glossary(TERMS[2]));
}

// ---- step 4: props -----------------------------------------------------------------------------------------------------------------------------------
function step4() {
  const doc = A.art, p = doc.props.find(x => x.id === A.sel.prop) || null, sc = scene() || {beats: []}, shots = (plan() || {}).shots || [];
  const where = [['beat', 'Beat'], ['shot', 'Shot']];
  const table = doc.props.length ? el('div', {class: 'tablewrap'}, el('table', {class: 'table', 'data-testid': 'prop-table'}, el('thead', {}, el('tr', {}, ...['Prop', 'From', 'Kind', 'Placed', 'Shots', 'Status'].map(h => el('th', {}, h)))),
    el('tbody', {}, ...doc.props.map(x => el('tr', {class: x.id === A.sel.prop ? 'selected' : '', 'data-prop-row': x.id}, el('td', {}, el('button', {type: 'button', class: 'linkbtn', 'data-testid': `pick-${x.id}`, onclick: () => { A.sel.prop = x.id; persist(); render(); }}, x.name)),
      el('td', {}, x.source === 'script' ? 'script' : 'added by hand'), el('td', {}, x.kind || 'prop'), el('td', {}, x.position ? 'yes' : 'no'), el('td', {}, String((x.shot_ids || []).length)), el('td', {}, badge(x.status))))))) :
    el('p', {class: 'hint', 'data-empty': 'props', 'data-testid': 'no-props'}, 'No props yet. Press “Add a prop”, or draft a treatment from a scene whose script mentions objects.');
  const insp = p ? el('div', {class: 'subcard picked', 'data-testid': 'prop-inspector'}, el('h3', {}, `Selected: ${p.name}`),
    row('Name', bind(p, 'name', {'data-testid': 'prop-name'})), row('Kind', sel(p, 'kind', [['prop', 'Prop'], ['personal', 'Personal object'], ['practical', 'Practical light']], {'data-testid': 'prop-kind'})),
    row('Description', bind(p, 'description', {rows: '2'}, 'textarea')),
    row('Position', p.position ? el('div', {class: 'inline'}, bind(p.position, 'x', {type: 'number', min: '0', max: '1', step: '0.01', 'aria-label': 'Prop x', 'data-testid': 'prop-x'}, 'input', Number), bind(p.position, 'y', {type: 'number', min: '0', max: '1', step: '0.01', 'aria-label': 'Prop y'}, 'input', Number),
      btn('Remove the position', () => { p.position = null; touch(); render(); }, {'data-testid': 'prop-unplace'})) : el('div', {class: 'inline'}, el('span', {class: 'hint'}, 'No position yet.'), btn('Place it in the middle of the set layout', () => { p.position = {x: 0.5, y: 0.5}; touch(); render(); }, {'data-testid': 'prop-place'}))),
    row('Status', sel(p, 'status', [['proposed', 'Proposed'], ['approved', 'Approved'], ['needs_review', 'Needs review']], {'data-testid': 'prop-status'})),
    row('Script lines that mention it', el('div', {class: 'chips'}, ...(p.mentions.length ? p.mentions.map(m => el('span', {class: 'chip'}, m.replace(`${doc.scene_id}-`, ''))) : [el('span', {class: 'hint'}, 'None.')]))),
    row('Shots that show it', el('div', {class: 'chips'}, ...((p.shot_ids || []).length ? p.shot_ids.map(m => el('span', {class: 'chip'}, m.replace(`${doc.scene_id}-`, ''))) : [el('span', {class: 'hint'}, 'None.')]))),
    row('Scenes', el('div', {class: 'chips'}, ...p.scene_ids.map(m => el('span', {class: 'chip'}, m)))),
    el('h4', {}, 'Where it is as the scene goes on (continuity)'),
    listEditor(p.states, () => ({at_kind: 'beat', at_id: (sc.beats[0] || {}).id || '', where: '', note: ''}), (s, i) => el('div', {}, row('At', el('div', {class: 'inline'}, sel(s, 'at_kind', where, {'aria-label': 'State applies to', 'data-testid': 'state-kind'}, {render: true}),
      sel(s, 'at_id', s.at_kind === 'beat' ? sc.beats.map(b => [b.id, b.title]) : shots.map(x => [x.shot_id, x.shot_id.split('-').pop()]), {'aria-label': 'State applies at', 'data-testid': 'state-at'}))),
      row('Where it is', bind(s, 'where', {'data-testid': 'state-where', placeholder: 'For example: on the counter, in Nila’s hand, gone'})), row('How it got there', bind(s, 'note', {'data-testid': 'state-note', placeholder: 'Who moved it, and when'}))),
      'Add a state', 'state', 'No states yet. Press “Add a state” to say where this prop is at a beat or in a shot.'),
    el('div', {class: 'buttons'}, guarded('Delete this prop', `rmprop-${p.id}`, () => { doc.props = doc.props.filter(x => x.id !== p.id); A.sel.prop = null; touch(); render(); }, {'data-testid': 'prop-del'}))) :
    el('p', {class: 'hint', 'data-empty': 'prop-selection', 'data-testid': 'no-prop-selection'}, 'No prop is selected. Click a prop in the table to edit it, or press “Add a prop”.');
  const add = {name: ''};
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'props-form'}, el('h2', {}, `${doc.treatment.name}: the prop inventory`), table,
    el('div', {class: 'formrow'}, el('label', {for: 'new-prop-name'}, 'New prop'), el('input', {id: 'new-prop-name', placeholder: 'For example: Reading glasses', 'data-testid': 'new-prop', oninput: ev => { add.name = ev.target.value; }}),
      btn('Add a prop', () => { const n = (add.name || '').trim(); if (!n) return fail('props', 'Type the prop’s name first.'); const id = nextId('PR-M', doc.props.map(x => x.id));
        doc.props.push({id, name: n, source: 'manual', kind: 'prop', description: '', position: null, mentions: [], scene_ids: [doc.scene_id], shot_ids: [], states: [], asset_ids: [], status: 'proposed', notes: ''}); A.sel.prop = id; touch(); render(); }, {'data-testid': 'add-prop'})),
    ...feedback('props'), insp, el('div', {class: 'buttons'}, btn('Check the design', check, {'data-testid': 'a-check', disabled: busy() || !A.base, title: !A.base ? 'Draft or open a treatment first.' : 'Looks for problems without saving.'})), ...feedback('check'),
    findings('props'), el('hr'), saveBlock(), glossary(TERMS[3]));
}

// ---- step 5: visual style ---------------------------------------------------------------------------------------------------------------------------------
function swatch(c) { return el('span', {class: 'swatch', style: `background:${c.hex}`, title: `${c.name} ${c.hex}`, role: 'img', 'aria-label': `${c.name} ${c.hex}`}); }
function subtabs(items) {
  return el('div', {class: 'subtabs', role: 'tablist'}, ...items.map(([id, label]) => el('button', {type: 'button', role: 'tab', class: 'subtab' + (A.sub.s5 === id ? ' active' : ''), 'aria-selected': String(A.sub.s5 === id), 'data-testid': `subtab-${id}`, onclick: () => { A.sub.s5 = id; persist(); render(); }}, label)));
}
function step5() {
  const doc = A.art, st = doc.style; st.palette = st.palette || []; st.textures = st.textures || []; st.materials = st.materials || []; st.period = st.period || {}; st.themes = st.themes || []; st.mood_words = st.mood_words || [];
  const tabs = subtabs([['palette', 'Colours'], ['materials', 'Textures and materials'], ['period', 'Period and themes'], ['variations', 'Shot variations'], ['assets', 'Assets']]);
  let body;
  if (A.sub.s5 === 'palette') {
    body = el('div', {}, st.profile_ref ? el('p', {class: 'hint'}, `Started from the project style “${st.profile_ref.name}”. You can still change anything here.`) : null,
      listEditor(st.palette, () => ({id: nextId('C', st.palette.map(c => c.id)), name: '', hex: '#888888', role: ''}), c => el('div', {}, row('Colour name', bind(c, 'name', {'data-testid': 'pal-name'})),
        row('Colour', el('div', {class: 'inline'}, el('input', {type: 'color', value: c.hex, 'aria-label': 'Pick the colour', 'data-testid': 'pal-picker', oninput: ev => { c.hex = ev.target.value; const t = ev.target.nextSibling; if (t) t.value = c.hex; touch(); }}),
          bind(c, 'hex', {'aria-label': 'Colour code', placeholder: '#8B5E3C', 'data-testid': 'pal-hex', maxlength: '7'}), swatch(c))), row('Role', bind(c, 'role', {placeholder: 'dominant, accent, light…'}))), 'Add a colour', 'colour', 'No colours yet. Press “Add a colour” to start the palette (three or more work best).'));
  } else if (A.sub.s5 === 'materials') {
    body = el('div', {}, el('h3', {}, 'Textures'), listEditor(st.textures, () => ({id: nextId('T', st.textures.map(t => t.id)), name: '', description: '', asset_id: null}), t => el('div', {}, row('Texture', bind(t, 'name', {'data-testid': 'tex-name'})), row('Description', bind(t, 'description')),
      row('Picture file', sel(t, 'asset_id', [['', '— none —'], ...((R.register || {}).assets || []).map(a => [a.id, a.name])], {'data-testid': 'tex-asset'}, {nullable: true}))), 'Add a texture', 'texture', 'No textures yet. Press “Add a texture” and describe the surface, for example “scratched wood grain”.'),
      el('h3', {}, 'Materials'), listEditor(st.materials, () => ({id: nextId('M', st.materials.map(m => m.id)), name: '', finish: '', notes: ''}), m => el('div', {}, row('Material', bind(m, 'name', {'data-testid': 'mat-name'})), row('Finish', bind(m, 'finish', {placeholder: 'matte, polished, worn…'}))),
        'Add a material', 'material', 'No materials yet. Press “Add a material”, for example “aged oak, waxed”.'));
  } else if (A.sub.s5 === 'period') {
    body = el('div', {}, row('Period or era', bind(st.period, 'era', {'data-testid': 'period-era', placeholder: 'For example: 1980s'})), row('Notes', bind(st.period, 'notes', {rows: '2'}, 'textarea')),
      row('Themes', bind({v: st.themes.join(', ')}, 'v', {'data-testid': 'themes', placeholder: 'memory, warmth, accumulation', oninput: ev => { st.themes = ev.target.value.split(',').map(s => s.trim()).filter(Boolean); touch(); }}), 'Separate with commas.'),
      row('Mood words', bind({v: st.mood_words.join(', ')}, 'v', {'data-testid': 'moods', placeholder: 'intimate, nostalgic', oninput: ev => { st.mood_words = ev.target.value.split(',').map(s => s.trim()).filter(Boolean); touch(); }}), 'Separate with commas.'));
    body.querySelector('[data-testid=themes]').value = st.themes.join(', '); body.querySelector('[data-testid=moods]').value = st.mood_words.join(', ');
  } else if (A.sub.s5 === 'variations') {
    doc.variations = doc.variations || [];
    const shots = (plan() || {}).shots || [];
    body = el('div', {}, el('p', {class: 'hint'}, 'A variation changes the look for one shot only. The treatment’s palette stays the base, so the scene keeps its overall look.'),
      listEditor(doc.variations, () => ({id: nextId('V', doc.variations.map(v => v.id)), shot_id: (shots[0] || {}).shot_id || '', summary: '', palette: [], hide_prop_ids: [], show_prop_ids: [], note: '', status: 'proposed'}), v => el('div', {},
        row('Shot', sel(v, 'shot_id', [['', '— choose a shot —'], ...shots.map(s => [s.shot_id, `${s.shot_id.split('-').pop()} · ${s.size} ${s.purpose.replace(/_/g, ' ')}`])], {'data-testid': 'var-shot'})),
        row('What changes', bind(v, 'summary', {'data-testid': 'var-summary', placeholder: 'For example: cooler light on the ticket reveal'})),
        row('Hide these props', el('div', {class: 'chips'}, ...doc.props.map(p => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: (v.hide_prop_ids || []).includes(p.id), onchange: ev => { v.hide_prop_ids = ev.target.checked ? [...(v.hide_prop_ids || []), p.id] : v.hide_prop_ids.filter(x => x !== p.id); touch(); }}), ` ${p.name}`)))),
        row('Replace colours', el('div', {}, ...(v.palette || []).map((c, i) => el('div', {class: 'inline'}, bind(c, 'name', {'aria-label': 'Variation colour name'}), bind(c, 'hex', {'aria-label': 'Variation colour code', maxlength: '7'}), swatch(c), btn('×', () => { v.palette.splice(i, 1); touch(); render(); }, {'aria-label': 'Remove this colour'}))),
          btn('Add a colour for this shot', () => { v.palette = v.palette || []; v.palette.push({id: nextId('VC', v.palette.map(c => c.id)), name: 'Shot colour', hex: (doc.style.palette[0] || {hex: '#888888'}).hex}); touch(); render(); }, {'data-testid': 'var-addcol'}))),
        row('Status', sel(v, 'status', [['proposed', 'Proposed'], ['approved', 'Approved'], ['needs_review', 'Needs review']]))), 'Add a shot variation', 'variation',
        shots.length ? 'No shot variations yet. Press “Add a shot variation” to change the look of one shot.' : 'No director’s plan is attached, so there are no shots to vary. Go back to step 1 and choose a plan.'));
  } else {
    const assets = (R.register || {}).assets || [];
    body = el('div', {}, assets.length ? el('div', {class: 'tablewrap'}, el('table', {class: 'table', 'data-testid': 'asset-table'}, el('thead', {}, el('tr', {}, ...['Use', 'Picture', 'Name', 'Kind', 'Rights', 'File'].map(h => el('th', {}, h)))), el('tbody', {}, ...assets.map(a => el('tr', {'data-asset': a.id},
      el('td', {}, el('input', {type: 'checkbox', 'aria-label': `Use ${a.name} in this treatment`, checked: (doc.asset_ids || []).includes(a.id), 'data-testid': `use-${a.id}`, onchange: ev => { doc.asset_ids = ev.target.checked ? [...(doc.asset_ids || []), a.id] : (doc.asset_ids || []).filter(x => x !== a.id); touch(); }})),
      el('td', {}, a.file_present ? el('img', {src: `/api/assets/${a.sha256}/file`, alt: a.name, class: 'thumb'}) : '—'), el('td', {}, a.name), el('td', {}, a.kind), el('td', {}, badge(a.rights.status)), el('td', {}, a.file_present ? 'stored' : 'missing')))))) :
      el('p', {class: 'hint', 'data-empty': 'assets', 'data-testid': 'no-assets'}, 'No assets are registered for this project yet. Open the Art Library tab, choose “Step 2 of 2”, and upload a picture file; then press “Refresh the list” here.'),
      el('div', {class: 'buttons'}, btn('Refresh the list', async () => { await loadOverview(); render(); }, {'data-testid': 'assets-refresh'}), btn('Open the Art Library', () => byId('tab-lib').click(), {'data-testid': 'open-library'})));
  }
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'style-form'}, el('h2', {}, `${doc.treatment.name}: the look`), tabs, body, findings('style', 'variation', 'assets'), el('hr'), saveBlock(), glossary(TERMS[4]));
}

// ---- step 6: comparison -----------------------------------------------------------------------------------------------------------------------------------
async function compare() {
  if (!A.cmp) return fail('cmp', 'Choose the treatment to compare with first.');
  await withBusy('cmp', 'Comparing the treatments', async () => { R.cmpResult = await call(`/api/art/compare?run_a=${A.base.runId}&run_b=${A.cmp}`); R.cmpDoc = null;
    const other = await call(`/api/runs/${A.cmp}`); R.cmpDoc = other.envelope.artifact; });
}
function step6() {
  const doc = A.art, same = ((R.overview && R.overview.treatments) || []).filter(t => t.scene_id === doc.scene_id && t.run_id && t.run_id !== (A.base || {}).runId);
  const saved = dirty() === 'saved', r = R.cmpResult;
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'compare-form'}, el('h2', {}, `Compare “${doc.treatment.name}” with another treatment`),
    saved ? null : el('p', {class: 'why', 'data-testid': 'compare-why'}, 'Save your changes first. Comparisons use saved versions, never unsaved edits.'),
    same.length ? el('div', {class: 'formrow'}, el('label', {for: 'cmp-pick'}, 'Compare with'), sel(A, 'cmp', [['', '— choose a treatment —'], ...same.map(t => [t.run_id, `${t.name}${t.treatment_name ? ' (' + t.treatment_name + ')' : ''}`])], {id: 'cmp-pick', 'data-testid': 'cmp-pick'}),
      el('span', {class: 'act'}, el('button', {type: 'button', class: 'primary', 'data-testid': 'cmp-go', onclick: compare, disabled: busy() || !saved, title: !saved ? 'Save your changes first.' : ''}, 'Compare the two treatments'))) :
      el('p', {class: 'hint', 'data-empty': 'compare', 'data-testid': 'no-compare'}, 'There is no other saved treatment of this scene yet. Go back to step 1, choose another starting point, and press “Draft the treatment”.'),
    ...feedback('cmp'), r ? compareView(r) : null), glossary(TERMS[5]));
}
function miniPalette(list) { return el('div', {class: 'swatches'}, ...list.map(swatch)); }
function compareView(r) {
  const side = (label, t, readings, pal, docx) => el('div', {class: 'cmpcol', 'data-testid': `cmp-${label}`}, el('h3', {}, t.name), el('p', {class: 'hint'}, t.intent || ''), miniPalette(pal), docx ? layoutSvg(docx, {editable: false, beat: A.sel.beat, label: `Layout of ${t.name}`, testid: `cmp-layout-${label}`}) : null,
    el('ul', {class: 'readings'}, ...readings.map(x => el('li', {}, x.text, el('span', {class: 'hint'}, ` (because: ${x.because})`)))));
  return el('div', {'data-testid': 'cmp-result'}, el('div', {class: 'twocol'}, side('a', r.a.treatment, r.readings.a, r.palettes.a, A.art), side('b', r.b.treatment, r.readings.b, r.palettes.b, R.cmpDoc)),
    el('h3', {}, 'Measures'), el('table', {class: 'table'}, el('thead', {}, el('tr', {}, el('th', {}, 'Measure'), el('th', {}, r.a.treatment.name), el('th', {}, r.b.treatment.name))),
      el('tbody', {}, ...r.metrics.map(m => el('tr', {class: m.differs ? 'diffrow' : ''}, el('td', {}, m.metric), el('td', {}, m.a == null ? '—' : String(m.a)), el('td', {}, m.b == null ? '—' : String(m.b)))))),
    el('h3', {}, 'What is different'), el('ul', {}, el('li', {}, `Only in ${r.a.treatment.name}: ${[...r.differences.objects_only_a, ...r.differences.props_only_a].join(', ') || 'nothing'}`), el('li', {}, `Only in ${r.b.treatment.name}: ${[...r.differences.objects_only_b, ...r.differences.props_only_b].join(', ') || 'nothing'}`),
      el('li', {}, `Moved: ${r.differences.moved.join(', ') || 'nothing'}`)),
    el('p', {class: 'hint'}, 'These statements come from fixed rules over the measures above. They describe what the design is likely to suggest; they do not judge which one is better.'));
}

// ---- step 7: review -----------------------------------------------------------------------------------------------------------------------------------------
async function decide(kind) {
  const reviewer = (A.reviewer || '').trim(), note = (A.rnote || '').trim();
  if (kind !== 'submit-review' && !reviewer) return fail('decide', 'Type your name in “Your name”, then press the button again. A decision needs a name.');
  if (kind === 'reject' && !note) return fail('decide', 'Write a short note saying why you are rejecting this treatment, then press Reject again.');
  await withBusy('decide', kind === 'submit-review' ? 'Submitting' : (kind === 'approve' ? 'Approving' : 'Rejecting'), async () => {
    await call(`/api/runs/${A.base.runId}/${kind}`, 'POST', {reviewer, note}); await loadRun(); await loadOverview();
    R.notice.decide = kind === 'submit-review' ? 'Submitted for review. Now approve or reject it.' : (kind === 'approve' ? 'Approved. You can export it in the next step.' : 'Rejected. Your note is recorded; change the design and save a new version.');
  });
}
function step7() {
  const doc = A.art, an = R.analysis || {issues: [], readiness: {attention: 0, notes: 0}}, imp = R.impact, saved = dirty() === 'saved', status = R.runInfo ? R.runInfo.approval_status : null;
  const att = an.issues.filter(i => i.severity === 'attention'), notes = an.issues.filter(i => i.severity === 'note');
  const pend = [...doc.props.filter(p => p.status !== 'approved').map(p => ({id: p.id, name: p.name, kind: 'prop', ref: p})), ...(doc.variations || []).filter(v => v.status !== 'approved').map(v => ({id: v.id, name: `Variation for ${v.shot_id}`, kind: 'variation', ref: v}))];
  const dec = (label, testid, kind, ok, why, cls = '') => el('span', {class: 'act'}, el('button', {type: 'button', class: cls, 'data-testid': testid, disabled: !ok || busy(), title: ok ? null : why, onclick: () => decide(kind)}, label), ok ? null : el('span', {class: 'why'}, why));
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'review-form'}, el('h2', {}, `Review “${doc.treatment.name}”`),
    el('div', {class: 'metrics'}, el('div', {class: 'metric'}, el('strong', {'data-testid': 'rv-attention'}, String(att.length)), el('span', {}, 'need attention (advice)')), el('div', {class: 'metric'}, el('strong', {}, String(notes.length)), el('span', {}, 'notes')),
      el('div', {class: 'metric'}, el('strong', {}, String(pend.length)), el('span', {}, 'items not yet approved')), el('div', {class: 'metric'}, el('strong', {}, String(doc.layout.objects.length)), el('span', {}, 'set pieces'))),
    imp && imp.stale ? el('div', {class: 'warnpanel panel', 'data-testid': 'impact'}, el('h3', {}, 'The script or the director’s plan changed after this design was made'), el('p', {}, imp.summary),
      imp.affected_props.length ? el('p', {class: 'hint'}, `Props to re-check: ${imp.affected_props.join(', ')}`) : null,
      el('p', {class: 'hint'}, 'To recover, rebase: it copies this design onto the newest script and plan, sends only the items listed here back for review, and keeps everything else as it was. This version stays as it is.'),
      el('div', {class: 'buttons'}, btn('Rebase onto the latest script and plan', rebase, {class: 'primary', 'data-testid': 'a-rebase', disabled: busy() || !saved, title: saved ? '' : 'Save your changes first.'}), !saved ? el('span', {class: 'why'}, 'Save your changes first.') : null)) : null,
    ...feedback('rebase'),
    el('h3', {}, 'What the checks found (advice only)'), (att.length || notes.length) ? findingsList([...att, ...notes]) : el('p', {class: 'notice ok', 'data-testid': 'no-findings'}, 'No problems found. The layout, props, style and assets all pass the checks.'),
    el('div', {class: 'buttons'}, btn('Check the design again', check, {'data-testid': 'a-check', disabled: busy()})), ...feedback('check'),
    el('h3', {}, 'Items waiting for your decision'),
    pend.length ? el('ul', {class: 'audit'}, ...pend.map(x => el('li', {class: 'advice', 'data-testid': `pend-${x.id}`}, el('span', {class: 'mark'}, '!'), el('span', {}, `${x.name} is ${x.ref.status.replace('_', ' ')}.`)))) : el('p', {class: 'hint', 'data-empty': 'pending'}, 'Every prop and shot variation is approved. Nothing is waiting; press Save if you change anything.'),
    el('div', {class: 'buttons'}, btn(`Approve all ${pend.length} item(s)`, () => { for (const x of pend) x.ref.status = 'approved'; touch(); render(); }, {'data-testid': 'approve-items', disabled: !pend.length, title: pend.length ? '' : 'There is nothing waiting for approval.'})),
    el('hr'), saveBlock()),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'decision-form'}, el('h2', {}, 'Approve or reject this treatment'),
      el('p', {}, el('span', {}, 'Status: '), status ? badge(status) : el('span', {class: 'hint'}, saved ? 'checking…' : 'not saved')),
      !saved ? el('p', {class: 'why', 'data-testid': 'decision-why'}, 'Save your changes first. Approval applies to a saved version, never to unsaved edits.') : null,
      att.length ? el('p', {class: 'hint'}, `${att.length} finding(s) still need attention. You can approve anyway. Exporting then asks you to confirm, and the choice is recorded.`) : null,
      row('Your name', bind(A, 'reviewer', {maxlength: '80', 'data-testid': 'a-reviewer', placeholder: 'Needed to approve or reject'})), row('Note', bind(A, 'rnote', {maxlength: '2000', 'data-testid': 'a-rnote', placeholder: 'Needed when rejecting'})),
      el('div', {class: 'buttons'}, dec('Submit for review', 'a-submit', 'submit-review', saved && ['draft', 'rejected'].includes(status), !saved ? 'Save your changes first.' : 'This version is already submitted or decided.'),
        dec('Approve this treatment', 'a-approve', 'approve', saved && status === 'review', 'Submit for review first.', 'primary'), dec('Reject this treatment', 'a-reject', 'reject', saved && status === 'review', 'Submit for review first.')),
      ...feedback('decide')), glossary(TERMS[6]));
}

// ---- step 8: export ---------------------------------------------------------------------------------------------------------------------------------------------------
const EXPORTS = [
  {kind: 'art-direction-json', label: 'Art direction (JSON)', desc: 'This treatment as saved, with its checks.'},
  {kind: 'prop-list-csv', label: 'Prop list (spreadsheet)', desc: 'Every prop with its position, shots and states, for Excel.'},
  {kind: 'storyboard-metadata', label: 'Storyboard and previz notes', desc: 'For each shot: palette, props in view, nearby set pieces and a suggested previz place. No pictures are made.'},
  {kind: 'art-direction-manifest', label: 'Art direction manifest', desc: 'The approved design in one file, with sections prepared for Lighting, Costume, Cinematography and Dreambox Scene Maker.', approved: true},
  {kind: 'asset-reference-manifest', label: 'Asset reference manifest', desc: 'The picture files this treatment uses, with source, rights and file fingerprints.', approved: true},
];
async function doExport(ex, overrides) {
  await withBusy(`x-${ex.kind}`, `Exporting ${ex.label}`, async () => {
    const q = overrides.map(o => `override=${o}`).join('&');
    const r = await fetch(`/api/runs/${A.base.runId}/exports/${ex.kind}${q ? '?' + q : ''}`, {method: 'POST'});
    if (!r.ok) { const d = await r.json().catch(() => ({})); const msg = typeof d.detail === 'string' ? d.detail : (d.detail && d.detail.message) || `HTTP ${r.status}`; R.needs[ex.kind] = msg; throw new Error(msg); }
    const name = (/filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || `${ex.kind}.json`;
    const url = URL.createObjectURL(new Blob([await r.text()], {type: r.headers.get('Content-Type') || 'application/json'}));
    const a = el('a', {href: url, download: name}); document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    delete R.needs[ex.kind];
    R.notice[`x-${ex.kind}`] = `Saved “${name}” to your Downloads folder.${r.headers.get('X-Craftbox-Existing') === 'true' ? ' This is the file made earlier; it is never made again.' : ''}${overrides.length ? ' Recorded in the file: you chose to export anyway (' + overrides.join(', ').replace(/_/g, ' ') + ').' : ''}`;
  });
}
const OVERRIDE_TEXT = {acknowledge_stale: 'The script or plan changed after this design was made.', allow_open_findings: 'Some checks still need attention.', allow_pending: 'Some items are waiting for review.'};
function step8() {
  const doc = A.art, status = R.runInfo ? R.runInfo.approval_status : null, approved = ['approved', 'exported'].includes(status), saved = dirty() === 'saved';
  const rows = EXPORTS.map(ex => {
    const need = ex.approved && !approved, msg = R.needs[ex.kind] || '', can = Object.keys(OVERRIDE_TEXT).filter(o => msg.includes(o));
    return el('div', {class: 'exrow', 'data-testid': `export-${ex.kind}`}, el('div', {}, el('strong', {}, ex.label), el('p', {class: 'hint'}, ex.desc)),
      el('div', {}, el('span', {class: 'act'}, el('button', {type: 'button', class: ex.approved ? 'primary' : '', 'data-testid': `dl-${ex.kind}`, disabled: need || busy() || !A.base, title: need ? 'Approve this treatment in the review step first.' : null, onclick: () => doExport(ex, [])}, 'Download'),
        need ? el('span', {class: 'why'}, 'Approve this treatment in the review step first.') : null),
        can.length ? el('div', {class: 'override'}, ...can.map(o => el('p', {class: 'hint'}, `${OVERRIDE_TEXT[o]} You can export anyway; your choice is written into the file.`)), btn('Export anyway (recorded)', () => doExport(ex, can), {'data-testid': `force-${ex.kind}`, disabled: busy()})) : null,
        ...feedback(`x-${ex.kind}`)));
  });
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'export-form'}, el('h2', {}, `Export “${doc.treatment.name}”`),
    el('p', {}, el('span', {}, 'Status: '), status ? badge(status) : el('span', {class: 'hint'}, 'unknown'), el('span', {class: 'hint'}, saved ? ' · exports use the saved version' : ' · unsaved changes are NOT included; save them first')),
    !approved ? el('p', {class: 'why', 'data-testid': 'not-approved'}, 'The two manifests need an approved treatment. The other files can be exported at any time.') : null, ...rows),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'finish-form'}, el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'}, btn('Start another treatment', () => { A.art = null; A.base = null; A.saved = null; A.step = 1; persist(); render(); }, {'data-testid': 'a-new'}), btn('Back to the review', () => go(7), {'data-testid': 'a-back-review'}),
        btn('Open History (all experiments)', () => byId('tab-history').click(), {'data-testid': 'a-open-history'}))), glossary(TERMS[7]));
}

// ---- shell -------------------------------------------------------------------------------------------------------------------------------------------------------------------
const reached = () => (!A.art ? 1 : (A.base ? 8 : 1));
function go(n) { if (n < 1 || n > 8 || n > reached()) return; A.step = n; R.errors = {}; R.notice = {}; R.armed = null; persist(); render(); window.scrollTo({top: 0}); onEnter(n); }
async function onEnter(n) {
  try { if (n >= 6 && A.base) { await loadImpact(); await loadRun(); await loadOverview(); } if (n === 7 && A.base && !R.analysis) { await check(); } } catch (e) { /* the page still works from the typed drafts */ }
  if (A.step === n) render();
}
function navSpec() {
  const n = A.step, before = STEPS.before(n), after = STEPS.after(n);
  const nextWhy = n === 1 ? 'Draft a new treatment, or open a saved one, first.' : '';
  return {n, total: 8, back: before ? {label: `Back: ${before.title}`, onclick: () => go(n - 1)} : null,
    next: after ? {label: `Next: ${after.title}`, disabled: n === 1 ? !A.art : false, why: nextWhy, onclick: () => go(n + 1)} : null};
}
function renderNav() { const h = byId('art-nav'); if (h) h.replaceChildren(ui.nav(navSpec())); }
const fns = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: step7, 8: step8};
function render() {
  ui.clearTimers();
  const mount = byId('art-mount');
  if (!mount) return;
  if (A.step > 1 && !A.art) A.step = 1;
  const n = A.step;
  mount.replaceChildren(el('div', {id: 'art-wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': 8, 'data-testid': 'art-wizard'},
    ui.stepper({defs: STEPS.list(), current: n, reached: reached(), onGo: go}), el('h1', {'data-testid': 'step-title'}, STEPS.title(n)), el('p', {class: 'intro', 'data-testid': 'step-intro'}, STEPS.intro(n)),
    n === 1 ? el('div', {}, fns[1](), glossary(TERMS[0])) : fns[n](), el('div', {id: 'art-nav'})));
  renderNav();
  fillGlossary(byId('art-wizard'));
}
async function show() {
  await loadProjects();
  if (!R.presets.length) { try { R.presets = await call('/api/art/presets'); } catch (e) { R.presets = []; } }
  if (!A.projectId && R.projects[0]) A.projectId = R.projects[0].project_id;
  await loadOverview();
  if (A.projectId && !A.screenplayExp && R.sps.length) A.screenplayExp = R.sps[R.sps.length - 1].experiment_id;
  if (A.screenplayExp && !R.spArt) { try { await loadScreenplay(A.screenplayExp); } catch (e) { /* ignore */ } }
  if (!A.sceneId && R.scenes[0]) A.sceneId = R.scenes[0].id;
  if (!A.planExp && A.sceneId) await defaultPlan();
  render();
}
async function init() {
  restore();
  try {
    await loadProjects(); R.presets = await call('/api/art/presets'); await loadOverview();
    if (A.screenplayExp) { try { await loadScreenplay(A.screenplayExp); } catch (e) { /* the revision may be gone */ } }
    if (A.art && A.base) {
      const run = await call(`/api/runs/${A.base.runId}`); R.analysis = run.envelope.artifact.analysis;
      const exp = await call(`/api/experiments/${A.base.experimentId}`); R.spArt = exp.input.screenplay; R.scenes = R.spArt.scenes; R.planArt = exp.input.direction_plan || null;
      await loadImpact(); await loadRun();
    }
  } catch (e) { A.base = null; }
  if (A.step > reached()) A.step = reached();
  render();
}
// Dependent selections: choosing a project loads its revisions; choosing a revision loads its scenes and plans.
document.addEventListener('change', async ev => {
  const t = ev.target && ev.target.getAttribute && ev.target.getAttribute('data-testid');
  if (!document.getElementById('view-art') || document.getElementById('view-art').hidden) return;
  if (t === 'a-project') { A.screenplayExp = ''; A.sceneId = ''; A.planExp = ''; R.spArt = null; R.scenes = []; await loadOverview(); if (R.sps.length) { A.screenplayExp = R.sps[R.sps.length - 1].experiment_id; await loadScreenplay(A.screenplayExp); A.sceneId = (R.scenes[0] || {}).id || ''; } await defaultPlan(); persist(); render(); }
  if (t === 'a-sp' && A.screenplayExp) { await loadScreenplay(A.screenplayExp); A.sceneId = (R.scenes[0] || {}).id || ''; await defaultPlan(); persist(); render(); }
  if (t === 'a-scene') { await defaultPlan(); persist(); render(); }
  if (t === 'a-plan') { await loadPlan(A.planExp); persist(); }
});
return {show, init, render, A, R, GLOSS, kit: {layoutSvg, findingsList, badge, swatch, miniPalette, W, H, COLORS}};
})();
