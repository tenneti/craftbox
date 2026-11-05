// Scene Lab (CB1): 8-step wizard from story idea to approved export. This file: shell, helpers and the
// Screenwriting Lab steps (1-4). lab-direction.js adds the Direction Lab steps (5-8). Follows guidelines/ui-standard.md.
const Lab = (window.Lab = window.Lab || {});
(() => {
const {el, call} = ui;
const byId = id => document.getElementById(id);
const KEY = 'craftbox.lab.v1';

// L = everything the user typed or chose (persisted, so a reload reopens where the work is). R = fetched/view state.
const L = {v: 1, step: 1, sceneId: null, sp: null, spBase: null, spSaved: null, plan: null, planBase: null, planSaved: null, selBeat: null, selChar: null,
  sub: {s2: 'script'}, revNote: '', planNote: '', reviewer: '', note: '', scriptText: '', jsonText: '', approach: {preset: 'intimate', avg: ''},
  idea: {title: '', logline: '', genre: '', theme: '', location: '', time: 'NIGHT', int_ext: 'INT.', arc_start: '', arc_end: '', chars: [{name: '', role: '', want: ''}, {name: '', role: '', want: ''}]}};
const R = {projects: [], overview: null, spArt: null, planArt: null, planAnalysis: null, live: null, impact: null, errors: {}, notice: {}, busy: null,
  confirm: null, armed: null, preview: '', cmp: null, planCmp: null, cmpPick: {a: '', b: ''}, exportsDone: [], override: {}};

const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(L)); } catch (e) { /* storage unavailable */ } };
const restore = () => {
  try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.v === 1) Object.assign(L, s, {idea: {...L.idea, ...s.idea}, sub: {...L.sub, ...s.sub}, approach: {...L.approach, ...s.approach}}); }
  catch (e) { /* corrupt store: start fresh */ }
};

const STEPS = ui.steps([
  {short: 'Story idea', title: 'start with a story idea', intro: 'Every scene starts as an idea. Tell Craftbox the idea and it builds an empty screenplay outline (three acts, a first scene and six dramatic beats) for you to fill in. Or open a project you saved earlier, or load the sample scene to see a finished example. Nothing here writes your story for you.'},
  {short: 'Screenplay', title: 'write the screenplay', intro: 'Write who is in the story and what happens, line by line: action, dialogue and pauses. Every line has a permanent ID, so later plans can point at exactly the line they use. Saving keeps this as a new revision; earlier revisions are never lost, and you can compare them.'},
  {short: 'Scene breakdown', title: 'break the scene down', intro: 'Say what the scene is for: what each person wants, what stands in the way, what changes, and how it ends. Arrange your scenes and sequences, and see how long the scene will run. The length is an estimate from word counts, not a measurement.'},
  {short: 'Dramatic beats', title: 'shape the dramatic beats', intro: 'Beats are the emotional steps of the scene, from calm to climax. Give each one an emotion and an intensity, and say which script lines belong to it. The director will use the beats to decide where the camera should move closer, hold back or cut faster.'},
  {short: 'Blocking', title: 'block the actors', intro: 'Start the Direction Lab. Pick a directing approach, then see a draft of where each person stands and moves in every beat, what they look at, and how the director reads the scene. Everything is a proposal you can change. Blocking is planned from your saved screenplay revision.'},
  {short: 'Shot list', title: 'plan the shots', intro: 'Every shot must say why it is there. Edit, add, reorder, approve or reject shots one at a time. Check the plan to catch repeated framing, missing coverage and continuity mistakes such as crossing the 180-degree line.'},
  {short: 'Director review', title: 'review as the director', intro: 'Look at the whole plan before you decide: coverage, variety, pacing against the dramatic beats, and any warnings. Compare it with your other approach, handle script changes that happened after the plan was made, then approve or reject the plan with your name.'},
  {short: 'Export', title: 'approve and export', intro: 'Approved plans can be exported as files: the screenplay, a readable script, blocking, a shot list, and the scene and shot manifests that a future Dreambox Scene Maker adapter will read. Exporting does not send anything to Dreambox.'},
]);

// ---- small DOM helpers bound to the working documents -----------------------------------------
const touch = () => { persist(); Lab.afterEdit && Lab.afterEdit(); };
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
  node.addEventListener('change', () => { obj[key] = node.value === '' && opt.nullable ? null : (opt.number ? Number(node.value) : node.value); touch(); if (opt.render) render(); });
  return node;
}
const row = (label, ctl, hint) => el('div', {class: 'formrow'}, el('label', {}, label), ctl, hint ? el('span', {class: 'hint'}, hint) : null);
const btn = (label, fn, props = {}) => el('button', {type: 'button', onclick: fn, ...props}, label);
const move = (arr, i, d) => { const j = i + d; if (j < 0 || j >= arr.length) return; [arr[i], arr[j]] = [arr[j], arr[i]]; touch(); render(); };
const nameOf = id => (L.sp?.characters.find(c => c.id === id)?.name) || id || '—';
const scene = () => L.sp && (L.sp.scenes.find(s => s.id === L.sceneId) || L.sp.scenes[0]);
const short = h => (h || '').slice(0, 8);
const when = iso => iso ? iso.replace('T', ' ').replace(/\.\d+Z$/, 'Z') : '';
const badge = t => el('span', {class: `badge b-${t}`}, t);
function nextId(prefix, existing, pad = 2) {   // next free numeric suffix after the highest one in use (IDs are never reused)
  const nums = existing.filter(x => x.startsWith(prefix)).map(x => parseInt(x.slice(prefix.length), 10)).filter(Number.isFinite);
  const n = (nums.length ? Math.max(...nums) : 0) + 1;
  return prefix + (pad ? String(n).padStart(pad, '0') : String(n));
}
const spJson = () => JSON.stringify(L.sp);
const planJson = () => JSON.stringify(L.plan);
function spState() { return !L.sp ? 'none' : (!L.spSaved ? 'unsaved' : (L.spSaved === spJson() ? 'saved' : 'changed')); }
function planState() { return !L.plan ? 'none' : (!L.planSaved ? 'unsaved' : (L.planSaved === planJson() ? 'saved' : 'changed')); }
const STATE_TEXT = {
  unsaved: 'Not saved yet. Saving creates a new revision and keeps everything you typed on screen.',
  saved: 'Saved. What you typed is still shown here.',
  changed: 'Changed, not saved yet. Saving creates a new revision; the earlier ones stay exactly as they were.',
};
function stateLine(kind) {
  const s = kind === 'plan' ? planState() : spState();
  return el('p', {class: `state s-${s}`, 'data-testid': kind === 'plan' ? 'plan-state' : 'sp-state', 'aria-live': 'polite'}, STATE_TEXT[s] || '');
}

// ---- feedback and background work (U5, U6) ---------------------------------------------------------
function fail(key, message) { R.errors[key] = message; render(); ui.reveal(`error-${key}`); }
async function withBusy(key, what, fn) {
  delete R.errors[key]; delete R.notice[key];
  R.busy = {key, what, startedAt: Date.now()};
  render();
  try { await fn(); } catch (e) { R.errors[key] = e.message; }
  finally { R.busy = null; render(); if (R.errors[key]) ui.reveal(`error-${key}`); }
}
const busy = () => !!R.busy;
const feedback = key => [
  R.busy && R.busy.key === key ? ui.progress({what: R.busy.what, startedAt: R.busy.startedAt}) : null,
  R.errors[key] ? ui.errorBox(R.errors[key], `error-${key}`) : null,
  R.notice[key] ? el('div', {class: 'notice ok', 'data-testid': `notice-${key}`, role: 'status'}, R.notice[key]) : null,
];
// Two-click guard so nothing is removed or replaced by accident.
function guarded(label, key, fn, props = {}) {
  const armed = R.armed === key;
  return el('button', {type: 'button', class: armed ? 'danger' : '', onclick: () => { if (armed) { R.armed = null; fn(); } else { R.armed = key; render(); } }, ...props}, armed ? 'Click again to confirm' : label);
}
function replaceGuard(fn, why) {   // never lose unsaved work silently (U4)
  if (L.sp && spState() !== 'saved') { R.confirm = {fn, why}; render(); return; }
  fn();
}
function confirmBox() {
  if (!R.confirm) return null;
  return el('div', {class: 'errbox', role: 'alert', 'data-testid': 'confirm-replace'},
    el('p', {}, `You have a screenplay with unsaved changes. ${R.confirm.why} will replace it on screen. Your earlier saved revisions are not affected.`),
    el('div', {class: 'buttons'}, btn('Replace what is on screen', () => { const f = R.confirm.fn; R.confirm = null; f(); }, {'data-testid': 'confirm-yes'}),
      btn('Keep working', () => { R.confirm = null; render(); })));
}

// ---- data: overview, saving, loading ------------------------------------------------------------------
async function refreshProjects() { try { R.projects = await call('/api/lab/projects'); } catch (e) { R.projects = []; } }
async function refreshOverview() {
  if (!L.sp) { R.overview = null; return; }
  try { R.overview = await call(`/api/lab/projects/${encodeURIComponent(L.sp.project.id)}`); } catch (e) { R.overview = null; }
}
function adoptScreenplay(doc, base, artifact) {
  L.sp = JSON.parse(JSON.stringify(doc));
  L.spBase = base || null; L.spSaved = base ? spJson() : null; R.spArt = artifact || null; R.live = null;
  L.sceneId = L.sp.scenes[0]?.id || null; L.revNote = '';
  if (L.plan && L.plan.project_id !== L.sp.project.id) { L.plan = null; L.planBase = null; L.planSaved = null; R.planArt = null; R.planAnalysis = null; }
  persist();
}
async function openExperiment(experimentId) {
  const exp = await call(`/api/experiments/${experimentId}`);
  const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
  const art = run ? (await call(`/api/runs/${run.id}`)).envelope.artifact : null;
  adoptScreenplay(exp.input, {experimentId: exp.id, runId: run ? run.id : null, revision: (exp.input.revision || {}).number || 1}, art);
}
async function openProject(pid) {
  await withBusy('open', 'Opening the project', async () => {
    const ov = await call(`/api/lab/projects/${encodeURIComponent(pid)}`);
    await openExperiment(ov.latest_screenplay ? ov.latest_screenplay.experiment_id : ov.screenplay_versions[ov.screenplay_versions.length - 1].experiment_id);
    await refreshOverview();
    R.notice.open = `Opened “${L.sp.project.title}”, revision ${L.spBase.revision}. Click “Next: write the screenplay”.`;
  });
}
async function saveScreenplay() {
  const prev = L.spBase ? L.spBase.revision : 0;
  L.sp.revision = {number: prev + 1, note: (L.revNote || '').trim()};
  const name = `${L.sp.project.title} — revision ${L.sp.revision.number}${L.sp.revision.note ? ': ' + L.sp.revision.note.slice(0, 40) : ''}`;
  await withBusy('save', 'Saving this revision', async () => {
    let exp;
    try { exp = await call('/api/experiments', 'POST', {craft_id: 'screenwriting', name, input: L.sp, notes: L.sp.revision.note, run_now: true, parent_experiment_id: L.spBase ? L.spBase.experimentId : null}); }
    catch (e) { L.sp.revision.number = prev || 1; throw e; }
    const run = exp.latest_run;
    L.spBase = {experimentId: exp.id, runId: run.id, revision: L.sp.revision.number};
    if (run.run_status === 'failed') { L.spSaved = null; persist(); throw new Error(`Saved, but the screenplay has a problem to fix first: ${run.error.message}`); }
    L.spSaved = spJson(); R.spArt = run.envelope.artifact; R.live = null; persist();
    await refreshOverview();
    R.notice.save = `Saved as revision ${L.sp.revision.number}. ${run.warnings.length ? run.warnings.length + ' suggestion(s) are listed below.' : ''}`;
  });
}
async function recalc() {
  await withBusy('recalc', 'Recalculating', async () => { R.live = (await call('/api/lab/analyze/screenplay', 'POST', {screenplay: L.sp})).artifact.analysis; });
}
function download(name, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = el('a', {href: url, download: name}); document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

// ---- steps --------------------------------------------------------------------------------------------------
function step1() {
  const field = ui.fields(L.idea, persist), I = L.idea;
  const chars = I.chars.map((c, i) => el('div', {class: 'formrow'}, el('label', {}, `Character ${i + 1}`),
    bind(c, 'name', {placeholder: 'Name', 'data-testid': `idea-char-name-${i}`}), bind(c, 'role', {placeholder: 'Role (e.g. protagonist)'}), bind(c, 'want', {placeholder: 'What they want'}),
    i > 1 ? btn('×', () => { I.chars.splice(i, 1); touch(); render(); }, {'aria-label': 'Remove character'}) : null));
  const sa = (R.live || (R.spArt && R.spArt.analysis) || {}).story;
  return el('div', {},
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'story-first'}, el('h2', {}, 'Develop the story first (recommended)'),
      el('p', {class: 'hint'}, 'The Story Lab walks six phases (concept, hook, empathy, conflict, structure, revision) before and during writing, and tells you what is still missing. Everything you answer is saved in this same project.'),
      L.sp && sa ? el('p', {class: 'notice ok', 'data-testid': 'story-health'}, `Story audit for “${L.sp.project.title}”: ${sa.overall.ok} of ${sa.overall.total} answered well${sa.overall.advice ? `, ${sa.overall.advice} with advice` : ''}${sa.overall.missing ? `, ${sa.overall.missing} not answered` : ''}. Advice only.`) : null,
      el('div', {class: 'buttons'}, btn('Open the Story Lab', () => document.getElementById('tab-story').click(), {'data-testid': 'open-story-lab'}))),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'open-form'}, el('h2', {}, 'Open a project you saved before'),
      R.projects.length ? el('table', {class: 'table'}, el('tbody', {}, ...R.projects.map(p => el('tr', {}, el('td', {}, p.title || p.project_id), el('td', {class: 'hint'}, `${p.versions} revision(s)`), el('td', {class: 'hint'}, when(p.updated_at)),
        el('td', {}, btn('Open', () => replaceGuard(() => openProject(p.project_id), `“${p.title}”`), {'data-testid': `open-${p.project_id}`, disabled: busy()})))))) : el('p', {class: 'hint', 'data-testid': 'no-projects'}, 'Nothing saved yet. Start from an idea below, or load the sample scene.'),
      ...feedback('open')),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'idea-form'}, el('h2', {}, 'Start from a story idea'),
      row('Title', field('title', '', {maxlength: '200', 'data-testid': 'idea-title', placeholder: 'e.g. The Closing Hour'})),
      row('One-line story', field('logline', '', {'data-testid': 'idea-logline', placeholder: 'Who wants what, and what stands in the way?'})),
      row('Genre', field('genre', '', {placeholder: 'e.g. Romantic drama'})), row('Theme', field('theme', '', {placeholder: 'What is it really about?'})),
      row('Where', el('div', {class: 'inline'}, sel(I, 'int_ext', ['INT.', 'EXT.', 'INT/EXT.', 'EXT/INT.']), field('location', '', {placeholder: 'Location, e.g. Page & Candle Bookshop', 'data-testid': 'idea-location'}), field('time', 'NIGHT', {placeholder: 'Time of day'}))),
      row('Feeling', el('div', {class: 'inline'}, field('arc_start', '', {placeholder: 'Starts feeling…'}), field('arc_end', '', {placeholder: 'Ends feeling…'}))),
      el('h3', {}, 'Characters'), ...chars,
      el('div', {class: 'buttons'}, btn('Add a character', () => { I.chars.push({name: '', role: '', want: ''}); touch(); render(); }),
        btn('Create the screenplay outline', () => replaceGuard(createIdea, 'The new outline'), {class: 'primary', 'data-testid': 'idea-create', disabled: busy()})),
      ...feedback('idea')),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'sample-form'}, el('h2', {}, 'Or load the finished sample'),
      el('p', {class: 'hint'}, '“The Closing Hour”: an original 84-second romantic-drama scene with two characters in one bookshop. Use it to explore every step.'),
      el('div', {class: 'buttons'}, btn('Load the sample scene', () => replaceGuard(loadSample, 'The sample scene'), {'data-testid': 'load-sample', disabled: busy()})),
      ...feedback('sample')),
    L.sp ? el('p', {class: 'notice ok', 'data-testid': 'current-project'}, `On screen now: “${L.sp.project.title}” (${spState() === 'saved' ? 'saved' : 'not saved yet'}). Click “Next: write the screenplay” to continue.`) : null);
}
async function createIdea() {
  await withBusy('idea', 'Creating the outline', async () => {
    const I = L.idea;
    const body = {title: I.title, logline: I.logline, genre: I.genre, theme: I.theme, int_ext: I.int_ext, location: I.location, time: I.time, story_idea: I.logline,
      characters: I.chars.filter(c => c.name.trim()), emotional_arc: {start: I.arc_start, end: I.arc_end}};
    adoptScreenplay(await call('/api/lab/idea', 'POST', body), null, null);
    R.notice.idea = `Created an outline for “${L.sp.project.title}”. It is not saved yet. Click “Next: write the screenplay”.`;
  });
}
async function loadSample() {
  await withBusy('sample', 'Loading the sample', async () => {
    adoptScreenplay(await call('/api/crafts/screenwriting/fixture?name=screenplay'), null, null);
    R.notice.sample = 'Loaded “The Closing Hour”. It is not saved yet. Click “Next: write the screenplay”.';
  });
}

// -- step 2: characters / script / import-export
function characterCard(c, i) {
  c.emotional_arc = c.emotional_arc || {}; c.relationships = c.relationships || [];
  const others = L.sp.characters.filter(x => x.id !== c.id).map(x => [x.id, x.name || x.id]);
  return el('div', {class: 'subcard', 'data-testid': `char-${c.id}`},
    el('div', {class: 'cardhead'}, el('strong', {}, c.name || '(unnamed)'), el('span', {class: 'hint'}, `ID ${c.id} (permanent)`), guarded('Remove', `rmchar-${c.id}`, () => removeCharacter(i))),
    row('Name', bind(c, 'name', {maxlength: '80', 'data-testid': `char-name-${c.id}`})), row('Role', bind(c, 'role', {placeholder: 'e.g. Protagonist'})),
    row('Age range', bind(c, 'age_range', {placeholder: 'e.g. early 30s'})), row('Description', bind(c, 'description', {rows: '2'}, 'textarea')),
    row('Motivation', bind(c, 'motivation', {rows: '2', placeholder: 'Why they act'}, 'textarea')), row('Wants', bind(c, 'want', {placeholder: 'What they say they want'})),
    row('Needs', bind(c, 'need', {placeholder: 'What they actually need'})), row('Flaw', bind(c, 'flaw')),
    row('Feeling: starts', bind(c.emotional_arc, 'start', {placeholder: 'Emotional state at the start'})), row('Feeling: ends', bind(c.emotional_arc, 'end', {placeholder: 'Emotional state at the end'})),
    el('h4', {}, 'Relationships'),
    ...c.relationships.map((r, k) => el('div', {class: 'formrow'}, sel(r, 'character_id', others), bind(r, 'relation', {placeholder: 'Relationship'}), bind(r, 'tension', {placeholder: 'Tension'}), btn('×', () => { c.relationships.splice(k, 1); touch(); render(); }, {'aria-label': 'Remove relationship'}))),
    others.length ? btn('Add a relationship', () => { c.relationships.push({character_id: others[0][0], relation: '', tension: ''}); touch(); render(); }) : null);
}
function removeCharacter(i) {
  const c = L.sp.characters[i];
  const used = L.sp.scenes.some(s => s.elements.some(e => e.character_id === c.id));
  if (used) return fail('chars', `${c.name || c.id} speaks in the script. Remove or reassign their lines first.`);
  L.sp.characters.splice(i, 1);
  for (const x of L.sp.characters) x.relationships = (x.relationships || []).filter(r => r.character_id !== c.id);
  for (const s of L.sp.scenes) s.characters = s.characters.filter(id => id !== c.id);
  touch(); render();
}
function addCharacter() {
  const id = `C-${String(L.sp.characters.length + 1).padStart(3, '0')}`;
  const ids = new Set(L.sp.characters.map(c => c.id)); let n = L.sp.characters.length + 1, cid = id;
  while (ids.has(cid)) cid = `C-${String(++n).padStart(3, '0')}`;
  L.sp.characters.push({id: cid, name: '', role: '', description: '', motivation: '', want: '', need: '', flaw: '', relationships: [], emotional_arc: {start: '', end: ''}});
  touch(); render();
}
function addElement(sc, type) {
  const speakers = sc.elements.filter(e => e.type === 'dialogue').map(e => e.character_id);
  const last = speakers[speakers.length - 1];
  const other = sc.characters.find(c => c !== last) || sc.characters[0] || null;
  sc.elements.push({id: nextId(`${sc.id}-E`, sc.elements.map(e => e.id)), type, character_id: ['dialogue', 'parenthetical'].includes(type) ? other : null, text: ''});
  touch(); render();
}
function removeElement(sc, i) {
  const id = sc.elements[i].id;
  sc.elements.splice(i, 1);
  for (const b of sc.beats) b.element_ids = b.element_ids.filter(x => x !== id);
  touch(); render();
}
function elementRow(sc, e, i) {
  const speaker = ['dialogue', 'parenthetical'].includes(e.type);
  return el('div', {class: `elrow t-${e.type}`, 'data-el': e.id},
    el('span', {class: 'hint elid'}, e.id.replace(`${sc.id}-`, '')),
    sel(e, 'type', ['action', 'dialogue', 'parenthetical', 'transition'], {'aria-label': 'Line type', 'data-testid': `el-type-${e.id}`}, {render: true}),
    speaker ? sel(e, 'character_id', [['', '— who —'], ...sc.characters.map(id => [id, nameOf(id)])], {'aria-label': 'Speaker', 'data-testid': `el-char-${e.id}`}, {nullable: true}) : el('span', {class: 'spacer'}),
    bind(e, 'text', {rows: '2', 'aria-label': 'Text', 'data-testid': `el-text-${e.id}`}, 'textarea'),
    bind(e, 'pause_seconds', {type: 'number', step: '0.5', min: '0', max: '60', placeholder: 'pause s', 'aria-label': 'Extra pause in seconds'}, 'input', num),
    el('span', {class: 'rowbtns'}, btn('↑', () => move(sc.elements, i, -1), {'aria-label': 'Move up'}), btn('↓', () => move(sc.elements, i, 1), {'aria-label': 'Move down'}),
      btn('×', () => removeElement(sc, i), {'aria-label': 'Delete line', 'data-testid': `el-del-${e.id}`})));
}
function scenePicker() {
  if (L.sp.scenes.length < 2) return null;
  return row('Scene', sel(L, 'sceneId', L.sp.scenes.map(s => [s.id, `${s.id} — ${s.heading.location}`]), {'data-testid': 'scene-picker'}, {render: true}));
}
function scriptPane() {
  const sc = scene();
  if (!sc) return el('p', {class: 'hint'}, 'This screenplay has no scenes yet. Add one in the next step (Scene breakdown).');
  return el('div', {}, scenePicker(),
    el('div', {class: 'formrow'}, el('label', {}, 'Heading'), sel(sc.heading, 'int_ext', ['INT.', 'EXT.', 'INT/EXT.', 'EXT/INT.'], {'data-testid': 'head-intext'}),
      bind(sc.heading, 'location', {placeholder: 'Location', 'data-testid': 'head-location'}), bind(sc.heading, 'time', {placeholder: 'Time of day'})),
    el('p', {class: 'hint'}, `Heading reads: ${sc.heading.int_ext} ${(sc.heading.location || '').toUpperCase()}${sc.heading.time ? ' - ' + sc.heading.time.toUpperCase() : ''}`),
    row('In this scene', el('div', {class: 'chips'}, ...L.sp.characters.map(c => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: sc.characters.includes(c.id),
      onchange: ev => { sc.characters = ev.target.checked ? [...sc.characters, c.id] : sc.characters.filter(x => x !== c.id); touch(); render(); }}), ` ${c.name || c.id}`)))),
    el('div', {class: 'elements', 'data-testid': 'elements'}, ...sc.elements.map((e, i) => elementRow(sc, e, i)),
      !sc.elements.length ? el('p', {class: 'hint'}, 'No lines yet. Add the first action or dialogue line below.') : null),
    el('div', {class: 'buttons'}, btn('Add action', () => addElement(sc, 'action'), {'data-testid': 'add-action'}), btn('Add dialogue', () => addElement(sc, 'dialogue'), {'data-testid': 'add-dialogue'}),
      btn('Add parenthetical', () => addElement(sc, 'parenthetical')), btn('Add transition', () => addElement(sc, 'transition'))));
}
async function importScript() {
  if (!L.scriptText.trim()) return fail('import', 'Paste a script into the box first.');
  await withBusy('import', 'Reading the script', async () => {
    const r = await call('/api/lab/import/fountain', 'POST', {text: L.scriptText, project_id: L.sp ? L.sp.project.id : null, title: L.sp ? L.sp.project.title : null});
    const keep = L.sp ? {...L.sp.project} : null;
    adoptScreenplay(r.screenplay, null, null);
    if (keep) L.sp.project = {...L.sp.project, ...keep};
    L.spBase = null; L.spSaved = null; L.scriptText = '';
    R.notice.import = `Imported ${L.sp.scenes.length} scene(s) and ${L.sp.characters.length} character(s)${keep ? `; the project “${L.sp.project.title}” and its revision history are kept` : ''}. ${r.check.ok ? 'Nothing is saved until you save a revision.' : 'Problem to fix: ' + r.check.error}`;
  });
}
async function importJson() {
  if (!L.jsonText.trim()) return fail('import', 'Paste screenplay JSON into the box first.');
  await withBusy('import', 'Checking the JSON', async () => {
    let doc; try { doc = JSON.parse(L.jsonText); } catch (e) { throw new Error(`That is not valid JSON: ${e.message}`); }
    const doc2 = doc.screenplay && doc.screenplay.schema ? doc.screenplay : doc;
    await call('/api/lab/analyze/screenplay', 'POST', {screenplay: doc2});
    adoptScreenplay(doc2, null, null); L.jsonText = '';
    R.notice.import = `Imported “${L.sp.project.title}” from JSON (${L.sp.scenes.length} scene(s)).`;
  });
}
async function showScript() {
  await withBusy('export', 'Building the readable script', async () => {
    const r = await fetch('/api/lab/export/fountain', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({screenplay: L.sp})});
    if (!r.ok) throw new Error((await r.json()).detail.message || 'The screenplay cannot be exported yet');
    R.preview = await r.text();
  });
}
function ioPane() {
  return el('div', {},
    el('h3', {}, 'Import'),
    el('p', {class: 'hint'}, 'Paste a readable script (Fountain-style: scene headings like “INT. KITCHEN - NIGHT”, character names in capitals, dialogue underneath) to replace the screenplay on screen. Scene and character IDs in an exported script are kept.'),
    el('textarea', {id: 'script-text', rows: '6', 'data-testid': 'script-text', placeholder: 'INT. KITCHEN - NIGHT\n\nSteam rises.\n\nMAYA\nHe is late.', value: L.scriptText, oninput: ev => { L.scriptText = ev.target.value; persist(); }}),
    el('div', {class: 'buttons'}, btn('Import this script', () => replaceGuard(importScript, 'The imported script'), {'data-testid': 'import-script', disabled: busy()})),
    el('p', {class: 'hint'}, 'Or paste screenplay JSON (as exported from Craftbox):'),
    el('textarea', {id: 'json-text', rows: '4', 'data-testid': 'json-text', value: L.jsonText, oninput: ev => { L.jsonText = ev.target.value; persist(); }}),
    el('div', {class: 'buttons'}, btn('Import this JSON', () => replaceGuard(importJson, 'The imported JSON'), {'data-testid': 'import-json', disabled: busy()})),
    ...feedback('import'),
    el('h3', {}, 'Export what is on screen'),
    el('div', {class: 'buttons'}, btn('Download JSON', () => download(`${L.sp.project.id}.screenplay.json`, JSON.stringify(L.sp, null, 2)), {'data-testid': 'dl-json'}),
      btn('Show / refresh readable script', showScript, {'data-testid': 'show-script', disabled: busy()}),
      btn('Download readable script', () => R.preview ? download(`${L.sp.project.id}.fountain`, R.preview, 'text/plain') : showScript().then(() => R.preview && download(`${L.sp.project.id}.fountain`, R.preview, 'text/plain')), {'data-testid': 'dl-script'})),
    ...feedback('export'), R.preview ? el('pre', {'data-testid': 'script-preview'}, R.preview) : null);
}
function subtabs(key, items) {
  return el('div', {class: 'subtabs', role: 'tablist'}, ...items.map(([id, label]) => el('button', {type: 'button', role: 'tab', class: 'subtab' + (L.sub[key] === id ? ' active' : ''), 'aria-selected': String(L.sub[key] === id),
    'data-testid': `subtab-${id}`, onclick: () => { L.sub[key] = id; persist(); render(); }}, label)));
}
function saveBlock() {
  const s = spState();
  const save = el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'screenplay-save', onclick: saveScreenplay, disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''}, 'Save screenplay revision');
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(L, 'revNote', {maxlength: '120', placeholder: 'e.g. Sharper ending line', 'data-testid': 'rev-note'})),
    stateLine('sp'), el('div', {class: 'buttons'}, save), ...feedback('save'));
}
function versionsPanel() {
  const ov = R.overview;
  const vs = ov ? ov.screenplay_versions : [];
  const opts = vs.filter(v => v.run_id).map(v => [v.run_id, `Revision ${v.revision}${v.note ? ' — ' + v.note : ''}`]);
  return el('details', {class: 'panel', 'data-testid': 'versions', open: vs.length > 1}, el('summary', {}, `Revision history (${vs.length})`),
    !vs.length ? el('p', {class: 'hint'}, 'No saved revisions yet. The first save creates revision 1.') : el('table', {class: 'table'}, el('thead', {}, el('tr', {}, el('th', {}, 'Revision'), el('th', {}, 'Saved'), el('th', {}, 'Length'), el('th', {}, 'Status'), el('th', {}, ''))),
      el('tbody', {}, ...[...vs].reverse().map(v => el('tr', {'data-testid': `version-${v.revision}`}, el('td', {}, `${v.revision}${v.note ? ' — ' + v.note : ''}`), el('td', {class: 'hint'}, when(v.created_at)),
        el('td', {}, v.estimated_seconds ? `${v.estimated_seconds}s` : '—'), el('td', {}, v.approval_status ? badge(v.approval_status) : badge(v.run_status || 'failed')),
        el('td', {}, btn('Open this revision', () => replaceGuard(() => withBusy('open', 'Opening', async () => { await openExperiment(v.experiment_id); await refreshOverview(); R.notice.open = `Opened revision ${v.revision}. Saving continues from this revision as a new one; no revision is replaced.`; }), `Revision ${v.revision}`), {'data-testid': `open-rev-${v.revision}`, disabled: busy()})))))),
    opts.length >= 2 ? el('div', {class: 'formrow'}, el('label', {}, 'Compare'), sel(R.cmpPick, 'a', [['', 'older…'], ...opts], {'data-testid': 'cmp-a'}), sel(R.cmpPick, 'b', [['', 'newer…'], ...opts], {'data-testid': 'cmp-b'}),
      btn('Show differences', compareVersions, {'data-testid': 'cmp-go', disabled: busy()})) : null,
    ...feedback('open'), ...feedback('cmp'), R.cmp ? cmpTable(R.cmp) : null);
}
async function compareVersions() {
  if (!R.cmpPick.a || !R.cmpPick.b) return fail('cmp', 'Pick two revisions to compare.');
  await withBusy('cmp', 'Comparing', async () => { R.cmp = await call(`/api/compare?run_a=${R.cmpPick.a}&run_b=${R.cmpPick.b}`); });
}
function friendly(path) {
  return path.replace(/^artifact\./, '').replace(/scenes\[([^\]]+)\]/g, 'scene $1').replace(/elements\[([^\]]+)\]/g, 'line $1').replace(/beats\[([^\]]+)\]/g, 'beat $1').replace(/shots\[([^\]]+)\]/g, 'shot $1').replace(/\./g, ' › ');
}
function cmpTable(d) {
  const ch = d.artifact_changes.filter(c => !/analysis|\.hash|slugline/.test(c.path));
  const fmt = v => v === undefined ? '' : (typeof v === 'string' ? v : JSON.stringify(v)).slice(0, 140);
  return el('div', {'data-testid': 'cmp-result'}, el('p', {class: 'hint'}, ch.length ? `${ch.length} difference(s) in the content (timings and fingerprints are left out):` : 'No content differences.'),
    ch.length ? el('table', {class: 'table diff'}, el('thead', {}, el('tr', {}, el('th', {}, 'Where'), el('th', {}, 'Change'), el('th', {}, 'Before'), el('th', {}, 'After'))),
      el('tbody', {}, ...ch.slice(0, 60).map(c => el('tr', {}, el('td', {}, friendly(c.path)), el('td', {}, c.change), el('td', {}, fmt(c.a)), el('td', {}, fmt(c.b)))))) : null);
}
function step2() {
  const tabs = subtabs('s2', [['script', 'Script'], ['characters', 'Characters'], ['io', 'Import / export']]);
  const body = L.sub.s2 === 'characters' ? el('div', {}, ...L.sp.characters.map(characterCard), el('div', {class: 'buttons'}, btn('Add a character', addCharacter, {'data-testid': 'add-character'})), ...feedback('chars'))
    : (L.sub.s2 === 'io' ? ioPane() : scriptPane());
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'screenplay-form'}, el('h2', {}, `“${L.sp.project.title}”`),
    el('div', {class: 'formrow'}, el('label', {}, 'Title'), bind(L.sp.project, 'title', {maxlength: '200', 'data-testid': 'proj-title'}),
      el('span', {class: 'hint'}, `Project ID ${L.sp.project.id} (permanent)`)), tabs, body, el('hr'), saveBlock()), versionsPanel());
}

// -- step 3: scene breakdown
function addScene() {
  const prev = scene();
  const ids = L.sp.scenes.map(s => s.id); let n = ids.length + 1, id = `SC-${String(n).padStart(3, '0')}`;
  while (ids.includes(id)) id = `SC-${String(++n).padStart(3, '0')}`;
  const seq = L.sp.sequences[0] || null;
  L.sp.scenes.push({id, sequence_id: seq ? seq.id : null, heading: {int_ext: prev ? prev.heading.int_ext : 'INT.', location: 'NEW LOCATION', time: prev ? prev.heading.time : 'DAY'}, synopsis: '', objective: '', conflict: '',
    turning_point: '', outcome: '', characters: L.sp.characters.map(c => c.id), props: [], elements: [], beats: []});
  if (seq) seq.scene_ids.push(id);
  L.sceneId = id; touch(); render();
}
function removeScene(i) {
  const s = L.sp.scenes[i];
  L.sp.scenes.splice(i, 1);
  for (const q of L.sp.sequences) q.scene_ids = q.scene_ids.filter(x => x !== s.id);
  L.sceneId = L.sp.scenes[0] ? L.sp.scenes[0].id : null; touch(); render();
}
function syncSequenceOrder() {
  const order = L.sp.scenes.map(s => s.id);
  for (const q of L.sp.sequences) q.scene_ids.sort((a, b) => order.indexOf(a) - order.indexOf(b));
}
function assignSequence(sc, seqId) {
  for (const q of L.sp.sequences) q.scene_ids = q.scene_ids.filter(x => x !== sc.id);
  sc.sequence_id = seqId || null;
  const q = L.sp.sequences.find(x => x.id === seqId);
  if (q) { q.scene_ids.push(sc.id); syncSequenceOrder(); }
  touch(); render();
}
function addSequence() {
  const id = nextId('SEQ-', L.sp.sequences.map(s => s.id), 0);
  L.sp.sequences.push({id, title: 'New sequence', act: 1, summary: '', scene_ids: []}); touch(); render();
}
function analysisPanel() {
  const an = R.live || (R.spArt && R.spArt.analysis);
  if (!an) return el('p', {class: 'hint', 'data-testid': 'no-analysis'}, 'Estimates appear after you save a revision or press “Recalculate”.');
  const sa = an.scenes.find(s => s.scene_id === L.sceneId) || an.scenes[0];
  if (!sa) return null;
  return el('div', {class: 'metrics', 'data-testid': 'analysis'},
    el('div', {class: 'metric'}, el('strong', {'data-testid': 'est-seconds'}, `${sa.estimated_seconds} s`), el('span', {}, 'estimated length')),
    el('div', {class: 'metric'}, el('strong', {}, `${sa.duration_frames}`), el('span', {}, `frames at ${sa.fps} fps`)),
    el('div', {class: 'metric'}, el('strong', {'data-testid': 'pacing'}, sa.pacing.label), el('span', {}, `pacing (${sa.pacing.dialogue_words_per_minute} spoken words/min)`)),
    el('div', {class: 'metric'}, el('strong', {}, `${Math.round(sa.pacing.dialogue_share * 100)}% / ${Math.round(sa.pacing.action_share * 100)}%`), el('span', {}, 'dialogue / action time')),
    el('div', {class: 'wide'}, el('p', {class: 'hint'}, 'Three-act balance inside this scene (from the beats): ' + sa.micro_structure.map(m => `act ${m.act}: ${Math.round(m.share * 100)}% (guide ${Math.round(m.expected_share * 100)}%)`).join(' · ')),
      ...(an.warnings.length ? [el('ul', {class: 'warn', 'data-testid': 'analysis-warnings'}, ...an.warnings.map(w => el('li', {}, w)))] : []),
      el('p', {class: 'hint'}, an.model.note)));
}
function step3() {
  const sc = scene();
  const seqOpts = [['', '— none —'], ...L.sp.sequences.map(q => [q.id, q.title])];
  const list = el('table', {class: 'table', 'data-testid': 'scene-list'}, el('thead', {}, el('tr', {}, el('th', {}, 'Order'), el('th', {}, 'Scene'), el('th', {}, 'Sequence'), el('th', {}, ''))),
    el('tbody', {}, ...L.sp.scenes.map((s, i) => el('tr', {class: s.id === L.sceneId ? 'selected' : '', 'data-scene': s.id},
      el('td', {}, String(i + 1)), el('td', {}, el('button', {type: 'button', class: 'linkbtn', onclick: () => { L.sceneId = s.id; persist(); render(); }}, `${s.id} — ${s.heading.int_ext} ${s.heading.location}`)),
      el('td', {}, sel(s, 'sequence_id', seqOpts, {'aria-label': `Sequence of ${s.id}`}, {nullable: true, render: true})),
      el('td', {class: 'rowbtns'}, btn('↑', () => { move(L.sp.scenes, i, -1); syncSequenceOrder(); }, {'aria-label': 'Move scene up'}), btn('↓', () => { move(L.sp.scenes, i, 1); syncSequenceOrder(); }, {'aria-label': 'Move scene down'}),
        guarded('Remove', `rmscene-${s.id}`, () => removeScene(i)))))));
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'breakdown-form'},
    el('h2', {}, 'Scenes and sequences'), list, el('div', {class: 'buttons'}, btn('Add a scene', addScene, {'data-testid': 'add-scene'}), btn('Add a sequence', addSequence, {'data-testid': 'add-sequence'})),
    ...L.sp.sequences.map(q => el('div', {class: 'formrow'}, el('label', {}, q.id), bind(q, 'title', {placeholder: 'Sequence title'}), sel(q, 'act', [[1, 'Act 1'], [2, 'Act 2'], [3, 'Act 3']], {'aria-label': 'Act'}, {number: true}))),
    el('h3', {}, 'Three-act structure'), ...(L.sp.structure.acts || []).map(a => el('div', {class: 'formrow'}, el('label', {}, `Act ${a.act}`), bind(a, 'label', {placeholder: 'Label'}), bind(a, 'purpose', {placeholder: 'What this act does'}))),
    sc ? el('div', {}, el('h2', {}, `Scene ${sc.id}: what it is for`), scenePicker(),
      row('Summary', bind(sc, 'synopsis', {rows: '2', 'data-testid': 'scene-synopsis'}, 'textarea')), row('Objective', bind(sc, 'objective', {rows: '2', 'data-testid': 'scene-objective', placeholder: 'What does each person want in this scene?'}, 'textarea')),
      row('Conflict', bind(sc, 'conflict', {rows: '2', placeholder: 'What stands in the way?'}, 'textarea')), row('Turning point', bind(sc, 'turning_point', {rows: '2', placeholder: 'What changes?'}, 'textarea')),
      row('Outcome', bind(sc, 'outcome', {rows: '2', placeholder: 'How does it end?'}, 'textarea')),
      row('Fix the length', bind(sc, 'estimated_seconds_override', {type: 'number', min: '1', max: '7200', placeholder: 'seconds (optional)', 'data-testid': 'scene-override'}, 'input', num), 'Leave empty to use the estimate.'),
      el('div', {class: 'buttons'}, btn('Recalculate estimates', recalc, {'data-testid': 'recalc', disabled: busy()})), ...feedback('recalc'), analysisPanel()) : el('p', {class: 'hint'}, 'Add a scene to continue.'),
    el('hr'), saveBlock()), versionsPanel());
}

// -- step 4: dramatic beats
function addBeat(sc) {
  sc.beats.push({id: nextId(`${sc.id}-B`, sc.beats.map(b => b.id), 0), title: 'New beat', description: '', emotion: '', role: 'rising', act: 2, intensity: 5, element_ids: [], character_states: {}});
  touch(); render();
}
function assignElement(sc, beat, eid, on) {
  for (const b of sc.beats) b.element_ids = b.element_ids.filter(x => x !== eid);
  if (on) { beat.element_ids.push(eid); const order = sc.elements.map(e => e.id); beat.element_ids.sort((a, b) => order.indexOf(a) - order.indexOf(b)); }
  touch(); render();
}
function assignEvenly(sc) {
  if (!sc.beats.length) return fail('beats', 'Add at least one beat first.');
  const n = sc.elements.length, k = sc.beats.length;
  sc.beats.forEach((b, i) => { b.element_ids = sc.elements.slice(Math.floor(i * n / k), Math.floor((i + 1) * n / k)).map(e => e.id); });
  touch(); render();
}
function curve(sc) {
  const w = 640, h = 130, pad = 24, bs = sc.beats;
  if (!bs.length) return null;
  const x = i => pad + (bs.length === 1 ? (w - 2 * pad) / 2 : i * (w - 2 * pad) / (bs.length - 1)), y = v => h - pad - (v / 10) * (h - 2 * pad);
  const ns = 'http://www.w3.org/2000/svg', mk = (t, a, txt) => { const n = document.createElementNS(ns, t); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); if (txt) n.textContent = txt; return n; };
  const svg = mk('svg', {viewBox: `0 0 ${w} ${h}`, class: 'curve', role: 'img', 'aria-label': 'Emotional intensity across the beats', 'data-testid': 'intensity-curve'});
  svg.append(mk('line', {x1: pad, y1: y(0), x2: w - pad, y2: y(0), class: 'axis'}), mk('line', {x1: pad, y1: y(10), x2: w - pad, y2: y(10), class: 'axis'}));
  svg.append(mk('polyline', {points: bs.map((b, i) => `${x(i)},${y(b.intensity ?? 0)}`).join(' '), class: 'line'}));
  bs.forEach((b, i) => { svg.append(mk('circle', {cx: x(i), cy: y(b.intensity ?? 0), r: 5, class: 'dot'}), mk('text', {x: x(i), y: h - 6, 'text-anchor': 'middle', class: 'lbl'}, String(i + 1)), mk('text', {x: x(i), y: y(b.intensity ?? 0) - 9, 'text-anchor': 'middle', class: 'val'}, String(b.intensity ?? 0))); });
  return svg;
}
function beatCard(sc, b, i) {
  b.character_states = b.character_states || {};
  const elems = sc.elements.map(e => {
    const owner = sc.beats.find(x => x.element_ids.includes(e.id));
    const label = `${e.id.replace(sc.id + '-', '')} ${e.type === 'dialogue' ? nameOf(e.character_id) + ': ' : ''}${(e.text || '').slice(0, 44)}`;
    return el('label', {class: 'chip wideChip' + (owner && owner !== b ? ' taken' : '')}, el('input', {type: 'checkbox', checked: b.element_ids.includes(e.id), 'data-testid': `beat-el-${b.id}-${e.id}`, onchange: ev => assignElement(sc, b, e.id, ev.target.checked)}),
      ` ${label}`, owner && owner !== b ? el('span', {class: 'hint'}, ` (in “${owner.title}”)`) : null);
  });
  return el('div', {class: 'subcard', 'data-testid': `beat-${b.id}`},
    el('div', {class: 'cardhead'}, el('strong', {}, `${i + 1}. ${b.title || '(untitled)'}`), el('span', {class: 'rowbtns'}, btn('↑', () => move(sc.beats, i, -1), {'aria-label': 'Move beat up'}), btn('↓', () => move(sc.beats, i, 1), {'aria-label': 'Move beat down'}),
      guarded('Remove', `rmbeat-${b.id}`, () => { sc.beats.splice(i, 1); touch(); render(); }))),
    row('Title', bind(b, 'title', {'data-testid': `beat-title-${b.id}`})),
    row('Role', sel(b, 'role', [['setup', 'Setup'], ['inciting', 'Inciting moment'], ['rising', 'Rising tension'], ['turning_point', 'Turning point'], ['climax', 'Climax'], ['resolution', 'Resolution']], {}, {nullable: true})),
    row('Act of the scene', sel(b, 'act', [[1, 'Act 1 (setup)'], [2, 'Act 2 (confrontation)'], [3, 'Act 3 (resolution)']], {}, {number: true})),
    row('Intensity', el('div', {class: 'inline'}, bind(b, 'intensity', {type: 'range', min: '0', max: '10', step: '1', 'aria-label': 'Intensity 0 to 10', 'data-testid': `beat-intensity-${b.id}`, oninput: ev => { ev.target.nextSibling.textContent = ev.target.value; }}, 'input', Number), el('output', {}, String(b.intensity ?? 0)))),
    row('Emotion', bind(b, 'emotion', {placeholder: 'e.g. Stiff politeness'})), row('What happens', bind(b, 'description', {rows: '2'}, 'textarea')),
    ...sc.characters.map(cid => row(`${nameOf(cid)} feels`, el('input', {value: b.character_states[cid] || '', placeholder: 'Emotional state in this beat', oninput: ev => { b.character_states[cid] = ev.target.value; touch(); }}))),
    el('details', {open: !b.element_ids.length}, el('summary', {}, `Script lines in this beat (${b.element_ids.length})`), el('div', {class: 'chips col'}, ...elems)));
}
function step4() {
  const sc = scene();
  if (!sc) return el('section', {class: 'panel'}, el('p', {class: 'hint'}, 'No scene yet. Go back and add one.'));
  const an = (R.live || (R.spArt && R.spArt.analysis));
  const sa = an && an.scenes.find(s => s.scene_id === sc.id);
  const loose = sc.elements.filter(e => !sc.beats.some(b => b.element_ids.includes(e.id)));
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'beats-form'}, scenePicker(), el('h2', {}, 'Emotional shape of the scene'), curve(sc) || el('p', {class: 'hint'}, 'Add a beat to see the curve.'),
    sc.beats.length ? el('p', {class: 'hint'}, `Numbers are intensity (0 calm, 10 peak). ${sa ? 'Length ' + sa.estimated_seconds + ' s.' : ''}`) : null,
    loose.length && sc.beats.length ? el('p', {class: 'why', 'data-testid': 'loose-lines'}, `${loose.length} script line(s) are not in any beat yet.`) : null,
    ...sc.beats.map((b, i) => beatCard(sc, b, i)),
    el('div', {class: 'buttons'}, btn('Add a beat', () => addBeat(sc), {'data-testid': 'add-beat'}), btn('Spread the script lines across the beats in order', () => assignEvenly(sc), {'data-testid': 'assign-evenly'})),
    ...feedback('beats'), el('hr'), saveBlock()), versionsPanel());
}

// ---- wizard shell ---------------------------------------------------------------------------------------------
const sp5 = () => !!(L.sp && L.spBase && R.spArt);
function reached() {
  if (!L.sp) return 1;
  if (!sp5()) return 4;
  if (!L.plan) return 5;
  return L.planBase ? 8 : 7;
}
function go(n) {
  if (n < 1 || n > STEPS.count || n > reached()) return;
  L.step = n; R.errors = {}; R.notice = {}; R.armed = null; R.confirm = null; persist(); render(); Lab.onEnter && Lab.onEnter(n);
  window.scrollTo({top: 0});
}
const stepFns = {1: step1, 2: step2, 3: step3, 4: step4};
function navSpec() {
  const n = L.step, before = STEPS.before(n);
  const back = before ? {label: `Back: ${before.short.toLowerCase()}`, onclick: () => go(n - 1)} : null;
  const nexts = {
    1: {label: 'Next: write the screenplay', disabled: !L.sp, why: 'Create an outline, open a project or load the sample first.'},
    2: {label: 'Next: break the scene down', disabled: false},
    3: {label: 'Next: shape the dramatic beats', disabled: false},
    4: {label: 'Next: block the actors', disabled: !sp5() || spState() !== 'saved', why: !sp5() ? 'Save a screenplay revision first. The plan is built from a saved revision.' : 'You changed the screenplay. Save it first so the plan matches what you see.'},
    5: Lab.nextFor ? Lab.nextFor(5) : null, 6: Lab.nextFor ? Lab.nextFor(6) : null, 7: Lab.nextFor ? Lab.nextFor(7) : null,
  }[n] || null;
  if (nexts) nexts.onclick = () => go(n + 1);
  return {n, total: STEPS.count, back, next: nexts};
}
function renderNav() { const h = byId('lab-nav'); if (h) h.replaceChildren(ui.nav(navSpec())); }
function render() {
  ui.clearTimers();
  const mount = byId('lab-mount');
  if (!mount) return;
  const n = L.step;
  const fn = stepFns[n];
  const body = fn ? (n > 1 && !L.sp ? el('p', {class: 'hint'}, 'Go back to step 1 and start a project.') : fn()) : el('p', {}, 'Loading…');
  (Lab.renderHooks || []).forEach(f => f());
  mount.replaceChildren(el('div', {id: 'lab-wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': STEPS.count, 'data-testid': 'lab-wizard'},
    ui.stepper({defs: STEPS.list(), current: n, reached: reached(), onGo: go}), el('h1', {'data-testid': 'step-title'}, STEPS.title(n)),
    el('p', {class: 'intro', 'data-testid': 'step-intro'}, STEPS.intro(n)), confirmBox(), body, el('div', {id: 'lab-nav'})));
  renderNav();
}
Lab.afterEdit = () => {   // keep state lines and Save/Next buttons current while typing, without a redraw
  for (const [id, kind] of [['sp-state', 'sp'], ['plan-state', 'plan']]) {
    for (const n of document.querySelectorAll(`[data-testid="${id}"]`)) { const s = kind === 'plan' ? planState() : spState(); n.textContent = STATE_TEXT[s] || ''; n.className = `state s-${s}`; }
  }
  for (const sv of document.querySelectorAll('[data-testid="screenplay-save"],[data-testid="story-save"]')) { const same = spState() === 'saved'; sv.disabled = same || busy(); sv.title = same ? 'Nothing has changed since the last save.' : ''; }
  for (const ps of document.querySelectorAll('[data-testid="plan-save"]')) { const same = planState() === 'saved'; ps.disabled = same || busy(); ps.title = same ? 'Nothing has changed since the last save.' : ''; }
  renderNav();
  (Lab.editHooks || []).forEach(f => f());
};

Lab.renderHooks = Lab.renderHooks || []; Lab.editHooks = Lab.editHooks || [];
Object.assign(Lab, {saveScreenplay, recalc, adoptScreenplay, replaceGuard, confirmBox, refreshProjects, L, R, STEPS, el, call, byId, bind, sel, row, btn, move, num, nameOf, scene, short, when, badge, nextId, download, touch, persist, fail, withBusy, busy, feedback, guarded, stateLine,
  spState, planState, planJson, spJson, sp5, render, renderNav, go, refreshOverview, versionsPanelSp: versionsPanel, cmpTable, friendly, stepFns, subtabs, openExperiment, curve});

Lab.show = async () => { await refreshProjects(); await refreshOverview(); render(); };
Lab.init = async () => {
  restore();
  try {
    if (L.sp && L.spBase && L.spBase.runId) R.spArt = (await call(`/api/runs/${L.spBase.runId}`)).envelope.artifact;
    if (L.planBase && L.planBase.runId) { R.planArt = (await call(`/api/runs/${L.planBase.runId}`)).envelope.artifact; R.planAnalysis = R.planArt.analysis; }
  } catch (e) { /* the saved run is gone or unreadable: fall back to the typed drafts */ L.spBase = L.spBase; R.spArt = R.spArt || null; }
  if (L.step > reached()) L.step = reached();
  if (L.sp && !L.sceneId) L.sceneId = L.sp.scenes[0] && L.sp.scenes[0].id;
  await refreshProjects(); await refreshOverview();
  render();
  Lab.onEnter && Lab.onEnter(L.step);
};
})();
