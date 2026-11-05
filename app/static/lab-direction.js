// Scene Lab, Direction Lab steps (5-8): blocking, shot list, director review, approved export. Needs lab.js.
(() => {
const {L, R, el, call, byId, bind, sel, row, btn, move, num, nameOf, scene, short, when, badge, nextId, download, touch, persist, fail, withBusy, busy, feedback, guarded, stateLine,
  spState, planState, render, renderNav, go, refreshOverview, cmpTable, STEPS} = Lab;

const SIZES = ['ECU', 'CU', 'MCU', 'MS', 'MWS', 'WS', 'EWS'];
const ANGLES = ['eye', 'low', 'high', 'dutch', 'overhead'];
const MOVES = ['static', 'push_in', 'pull_out', 'pan', 'tilt', 'track', 'handheld', 'crane'];
const FRAMINGS = ['single', 'two_shot', 'over_shoulder', 'insert', 'wide', 'group'];
const SIDES = [['A', 'A — master side'], ['B', 'B — opposite side'], ['axis', 'On the axis (neutral)']];
const PURPOSES = [['establish', 'Establish the space'], ['reveal', 'Reveal something'], ['emphasize_emotion', 'Emphasize emotion'], ['reaction', 'Show a reaction'], ['connect', 'Connect the people'],
  ['follow_movement', 'Follow movement'], ['insert_detail', 'Detail / insert'], ['show_distance', 'Show distance'], ['transition', 'Transition / neutral'], ['closure', 'Close the scene']];
const TRANSITIONS = ['cut', 'dissolve', 'match_cut', 'fade', 'j_cut', 'l_cut', 'smash_cut'];
const STATUSES = [['proposed', 'Proposed'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['needs_review', 'Needs review']];
const label = s => (s || '').replace(/_/g, ' ');
const COLORS = ['#8e88ff', '#f2a65a', '#6fd3a8', '#e87aa7'];
R.approaches = R.approaches || [];
R.planSp = R.planSp || null;
R.planRun = R.planRun || null;
R.sel = R.sel || {shot: null, beat: null, char: null};

const planScene = () => (R.planSp && L.plan && R.planSp.scenes.find(s => s.id === L.plan.scene_id)) || scene();
const planNames = () => Object.fromEntries(((R.planSp || L.sp).characters || []).map(c => [c.id, c.name]));
const pName = id => planNames()[id] || id;

// ---- plan data: draft, open, save, rebase -------------------------------------------------------------------
function adoptPlan(r) {
  const run = r.run;
  if (run.run_status === 'failed') throw new Error(run.error.message);
  const art = run.envelope.artifact;
  L.planBase = {experimentId: r.experiment.id, runId: run.id};
  const p = JSON.parse(JSON.stringify(art)); delete p.analysis;
  L.plan = p; L.planSaved = JSON.stringify(p); R.planArt = art; R.planAnalysis = art.analysis; R.planSp = r.experiment.input.screenplay; R.planRun = null; R.impact = null;
  if (!planScene().beats.some(b => b.id === R.sel.beat)) R.sel.beat = (planScene().beats[0] || {}).id || null;
  R.sel.shot = null; R.sel.char = null; R.planCmp = null; persist();
}
const presetName = () => (R.approaches.find(a => a.id === L.approach.preset) || {}).name || L.approach.preset;
async function draftPlan() {
  await withBusy('draft', 'Drafting the plan', async () => {
    const approach = {preset: L.approach.preset};
    if (String(L.approach.avg).trim()) approach.avg_shot_seconds = Number(L.approach.avg);
    const r = await call('/api/lab/direction/draft', 'POST', {screenplay_experiment_id: L.spBase.experimentId, scene_id: scene().id,
      name: `${L.sp.project.title} ${scene().id} — ${presetName()}`, approach, parent_experiment_id: null, note: ''});
    adoptPlan(r); await refreshOverview(); await loadPlanRun();
    R.notice.draft = `Drafted ${L.plan.shots.length} shots over ${R.planAnalysis.total_seconds} s. Everything is a proposal. Review the blocking, then click “Next: plan the shots”.`;
  });
}
async function openPlan(experimentId) {
  await withBusy('draft', 'Opening the plan', async () => {
    const exp = await call(`/api/experiments/${experimentId}`);
    const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
    if (!run) throw new Error('That plan has no completed run.');
    adoptPlan({experiment: exp, run: await call(`/api/runs/${run.id}`)});
    R.notice.draft = `Opened “${exp.name}”.`;
    await loadImpact(); await loadPlanRun();
  });
}
async function savePlan() {
  const n = ((R.overview && R.overview.plans.filter(p => p.scene_id === L.plan.scene_id).length) || 0) + 1;
  await withBusy('psave', 'Saving this plan version', async () => {
    const r = await call('/api/lab/direction/save', 'POST', {base_experiment_id: L.planBase.experimentId, plan: L.plan, name: `${L.sp.project.title} ${L.plan.scene_id} — ${L.plan.approach.name} v${n}`, note: (L.planNote || '').trim()});
    adoptPlan(r); await refreshOverview(); await loadImpact(); await loadPlanRun();
    R.notice.psave = `Saved as a new plan version (${L.plan.shots.length} shots). The earlier version is unchanged.`;
  });
}
async function checkPlan() {
  await withBusy('check', 'Checking the plan', async () => {
    const out = await call('/api/lab/direction/analyze', 'POST', {base_experiment_id: L.planBase.experimentId, plan: L.plan});
    R.planAnalysis = out.analysis; R.notice.check = `Checked: ${out.analysis.readiness.errors} error(s), ${out.analysis.readiness.warnings} warning(s). Nothing was saved.`;
  });
}
async function loadImpact() {
  if (!L.planBase) return;
  try { R.impact = await call(`/api/lab/plans/${L.planBase.experimentId}/impact`); } catch (e) { R.impact = null; }
}
async function loadPlanRun() {
  if (!L.planBase) { R.planRun = null; return; }
  try { R.planRun = await call(`/api/runs/${L.planBase.runId}`); } catch (e) { R.planRun = null; }
}
async function rebase() {
  await withBusy('rebase', 'Rebasing the plan', async () => {
    const r = await call(`/api/lab/plans/${L.planBase.experimentId}/rebase`, 'POST', {});
    adoptPlan(r); await refreshOverview(); await loadImpact(); await loadPlanRun();
    R.notice.rebase = `Created a new plan version on the latest screenplay. ${r.impact.affected_shots.length} shot(s) that depend on changed lines are back in review; the rest keep their decisions. The old version is unchanged.`;
  });
}

// ---- shared pieces ----------------------------------------------------------------------------------------------
function noPlan() { return el('section', {class: 'panel'}, el('p', {class: 'hint', 'data-testid': 'no-plan'}, 'There is no plan yet. Go back to “Blocking” and draft one.')); }
function loading() { return el('p', {class: 'hint'}, 'Loading the plan…'); }
function issuesList(an, onPick) {
  const issues = an ? an.issues : [];
  if (!an) return el('p', {class: 'hint'}, 'Not checked yet.');
  if (!issues.length) return el('p', {class: 'notice ok', 'data-testid': 'no-issues'}, 'No problems found: coverage, continuity and variety all pass.');
  return el('ul', {class: 'issues', 'data-testid': 'issues'}, ...[...issues].sort((a, b) => (a.severity === 'error' ? 0 : 1) - (b.severity === 'error' ? 0 : 1)).map(i =>
    el('li', {class: `issue ${i.severity}`, 'data-rule': i.rule}, el('span', {class: `badge ${i.severity === 'error' ? 'b-failed' : 'b-review'}`}, i.severity), ` ${i.message} `,
      ...i.shot_ids.slice(0, 3).map(id => el('button', {type: 'button', class: 'linkbtn', onclick: () => onPick(id)}, id.replace(`${L.plan.scene_id}-`, ''))))));
}
function planSaveBlock() {
  const s = planState();
  const save = el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'plan-save', onclick: savePlan, disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''}, 'Save direction plan version');
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(L, 'planNote', {maxlength: '300', placeholder: 'e.g. Wider opening, rejected the insert', 'data-testid': 'plan-note'})), stateLine('plan'),
    el('div', {class: 'buttons'}, save), ...feedback('psave'));
}
function planVersions() {
  const plans = ((R.overview && R.overview.plans) || []).filter(p => p.scene_id === (L.plan ? L.plan.scene_id : scene().id));
  return el('details', {class: 'panel', 'data-testid': 'plan-versions', open: plans.length > 0}, el('summary', {}, `Plans for this scene (${plans.length})`),
    !plans.length ? el('p', {class: 'hint'}, 'No saved plans yet.') : el('table', {class: 'table'}, el('thead', {}, el('tr', {}, ...['Plan', 'Approach', 'Shots', 'Checks', 'Status', ''].map(h => el('th', {}, h)))),
      el('tbody', {}, ...[...plans].reverse().map(p => el('tr', {'data-testid': `plan-row-${p.experiment_id}`, class: p.experiment_id === (L.planBase || {}).experimentId ? 'selected' : ''},
        el('td', {}, p.name, p.parent_experiment_id ? el('span', {class: 'hint'}, ' (edit of an earlier plan)') : null), el('td', {}, p.approach || '—'), el('td', {}, String(p.shots ?? '—')),
        el('td', {}, p.errors != null ? `${p.errors} err / ${p.warnings} warn` : '—'),
        el('td', {}, p.approval_status ? badge(p.approval_status) : '—', p.stale ? el('span', {class: 'badge b-review', 'data-testid': 'stale-badge', title: p.impact_summary}, 'script changed') : null),
        el('td', {}, btn('Open', () => openPlan(p.experiment_id), {'data-testid': `open-plan-${p.experiment_id}`, disabled: busy() || p.experiment_id === (L.planBase || {}).experimentId}))))))
  );
}

// ---- step 5: blocking -----------------------------------------------------------------------------------------------
function facingPoint(c, beat) {
  const f = c.facing || '', e = c.end;
  if (f.startsWith('toward:')) { const o = beat.characters.find(x => x.character_id === f.slice(7)); return o ? o.end : null; }
  if (f.startsWith('object:')) { const o = L.plan.stage.objects.find(x => x.id === f.slice(7)); return o ? {x: o.x, y: o.y} : null; }
  if (f === 'screen_left') return {x: e.x - 0.15, y: e.y};
  if (f === 'screen_right') return {x: e.x + 0.15, y: e.y};
  if (f === 'away') return {x: e.x, y: e.y - 0.15};
  return null;
}
function stageSvg(beat) {
  const W = 420, H = 300, ns = 'http://www.w3.org/2000/svg';
  const mk = (t, a, txt) => { const n = document.createElementNS(ns, t); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); if (txt) n.textContent = txt; return n; };
  const X = v => v * W, Y = v => v * H;
  const svg = mk('svg', {viewBox: `0 0 ${W} ${H}`, class: 'stage', role: 'img', 'aria-label': 'Stage plan: positions, paths and eyelines for the selected beat', 'data-testid': 'stage'});
  svg.append(mk('rect', {x: 0, y: 0, width: W, height: H, class: 'floor'}));
  for (let i = 1; i < 4; i++) { svg.append(mk('line', {x1: W * i / 4, y1: 0, x2: W * i / 4, y2: H, class: 'grid'}), mk('line', {x1: 0, y1: H * i / 4, x2: W, y2: H * i / 4, class: 'grid'})); }
  svg.append(mk('text', {x: W / 2, y: 12, class: 'cap', 'text-anchor': 'middle'}, 'back wall'), mk('text', {x: W / 2, y: H - 4, class: 'cap', 'text-anchor': 'middle'}, 'audience / master camera side (A)'));
  for (const o of L.plan.stage.objects) { svg.append(mk('rect', {x: X(o.x) - 11, y: Y(o.y) - 8, width: 22, height: 16, class: 'obj', rx: 3}), mk('text', {x: X(o.x), y: Y(o.y) + 22, class: 'cap', 'text-anchor': 'middle'}, o.name.slice(0, 18))); }
  const ids = planScene().characters;
  if (L.plan.stage.axis && L.plan.stage.axis.between && L.plan.stage.axis.between.length === 2) {
    const [a, b] = L.plan.stage.axis.between.map(id => beat.characters.find(c => c.character_id === id));
    if (a && b) svg.append(mk('line', {x1: X(a.end.x), y1: Y(a.end.y), x2: X(b.end.x), y2: Y(b.end.y), class: 'axisline'}));
  }
  beat.characters.forEach(c => {
    const col = COLORS[ids.indexOf(c.character_id) % COLORS.length] || COLORS[0];
    const pts = (c.path && c.path.length ? c.path : [c.start, c.end]).map(p => `${X(p.x)},${Y(p.y)}`).join(' ');
    svg.append(mk('polyline', {points: pts, class: 'path', stroke: col}), mk('circle', {cx: X(c.start.x), cy: Y(c.start.y), r: 6, class: 'startdot', stroke: col}));
    const fp = facingPoint(c, beat);
    if (fp) svg.append(mk('line', {x1: X(c.end.x), y1: Y(c.end.y), x2: X(c.end.x) + (X(fp.x) - X(c.end.x)) * 0.5, y2: Y(c.end.y) + (Y(fp.y) - Y(c.end.y)) * 0.5, class: 'eye', stroke: col}));
    svg.append(mk('circle', {cx: X(c.end.x), cy: Y(c.end.y), r: 11, fill: col, class: 'enddot' + (R.sel.char === c.character_id ? ' sel' : '')}), mk('text', {x: X(c.end.x), y: Y(c.end.y) + 4, class: 'ini', 'text-anchor': 'middle'}, (pName(c.character_id) || '?')[0].toUpperCase()));
  });
  svg.addEventListener('click', ev => {
    const c = beat.characters.find(x => x.character_id === R.sel.char);
    if (!c) return;
    const r = svg.getBoundingClientRect();
    c.end = {x: Math.round(Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)) * 100) / 100, y: Math.round(Math.max(0, Math.min(1, (ev.clientY - r.top) / r.height)) * 100) / 100};
    syncPath(c); touch(); render();
  });
  return svg;
}
function syncPath(c) {
  if (!c.path || c.path.length < 2) { c.path = [{...c.start}, {...c.end}]; return; }
  c.path[0] = {...c.start}; c.path[c.path.length - 1] = {...c.end};
}
const pathText = c => (c.path || []).map(p => `${p.x},${p.y}`).join('; ');
function parsePath(text, c) {
  const pts = text.split(';').map(s => s.trim()).filter(Boolean).map(s => s.split(',').map(Number));
  if (pts.length < 2 || pts.some(p => p.length !== 2 || p.some(v => !Number.isFinite(v) || v < 0 || v > 1))) return false;
  c.path = pts.map(([x, y]) => ({x, y})); c.start = {...c.path[0]}; c.end = {...c.path[c.path.length - 1]}; return true;
}
function charBlocking(beat, c, scn) {
  const others = scn.characters.filter(id => id !== c.character_id);
  const facingOpts = [...others.map(id => [`toward:${id}`, `toward ${pName(id)}`]), ...L.plan.stage.objects.map(o => [`object:${o.id}`, `at ${o.name}`]), ['screen_left', 'screen left'], ['screen_right', 'screen right'], ['away', 'away from camera']];
  const redraw = () => { syncPath(c); const h = byId('stage-host'); if (h) h.replaceChildren(stageSvg(beat)); };
  const xy = (obj, key, extra = {}) => bind(obj, key, {type: 'number', min: '0', max: '1', step: '0.01', ...extra, oninput: redraw}, 'input', Number);
  const door = L.plan.stage.objects.find(o => /door/i.test(o.name)) || L.plan.stage.objects[0];
  return el('div', {class: 'subcard' + (R.sel.char === c.character_id ? ' picked' : ''), 'data-testid': `block-${c.character_id}`},
    el('div', {class: 'cardhead'}, el('strong', {style: `color:${COLORS[scn.characters.indexOf(c.character_id) % COLORS.length]}`}, pName(c.character_id)),
      btn(R.sel.char === c.character_id ? 'Click the stage to move them' : 'Move by clicking the stage', () => { R.sel.char = R.sel.char === c.character_id ? null : c.character_id; render(); }, {'data-testid': `pick-${c.character_id}`})),
    row('Starts at', el('div', {class: 'inline'}, xy(c.start, 'x', {'aria-label': 'Start x', 'data-testid': `sx-${c.character_id}`}), xy(c.start, 'y', {'aria-label': 'Start y'}))),
    row('Ends at', el('div', {class: 'inline'}, xy(c.end, 'x', {'aria-label': 'End x', 'data-testid': `ex-${c.character_id}`}), xy(c.end, 'y', {'aria-label': 'End y'}))),
    row('Path', el('input', {value: pathText(c), 'aria-label': 'Path points', 'data-testid': `path-${c.character_id}`, onchange: ev => { if (parsePath(ev.target.value, c)) { touch(); render(); } else { ev.target.value = pathText(c); } }}), 'x,y points separated by ;'),
    row('Looks', sel(c, 'facing', facingOpts, {'data-testid': `facing-${c.character_id}`}, {render: true})),
    row('Eyeline', bind(c.eyeline || (c.eyeline = {target: '', note: ''}), 'note', {placeholder: 'What the eyes do (e.g. avoids him, then meets his eyes)'}), c.eyeline.target ? `looking at ${pName(c.eyeline.target)}` : ''),
    row('Does', bind(c, 'action', {placeholder: 'e.g. sets the book down'})), row('Posture', bind(c, 'posture')),
    row('Enters / exits', el('div', {class: 'chips'}, el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!c.entrance, 'data-testid': `entrance-${c.character_id}`, onchange: ev => { c.entrance = ev.target.checked ? {from: door.id} : null; touch(); render(); }}), ' enters in this beat'),
      el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!c.exit, 'data-testid': `exit-${c.character_id}`, onchange: ev => { c.exit = ev.target.checked ? {to: door.id} : null; touch(); render(); }}), ' exits in this beat'))));
}
function step5() {
  if (!L.sp) return noPlan();
  const plansHere = ((R.overview && R.overview.plans) || []).filter(p => p.scene_id === (scene() || {}).id);
  const chooser = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'approach-form'}, el('h2', {}, L.plan ? 'Start another plan (a new version of the approach)' : 'Choose a directing approach'),
    el('p', {class: 'hint'}, `Scene ${(scene() || {}).id}, from screenplay revision ${L.spBase ? L.spBase.revision : '?'}. Try both approaches on the same script to compare them in the review step.`),
    el('div', {class: 'cards'}, ...R.approaches.map(a => el('label', {class: 'craftcard' + (L.approach.preset === a.id ? ' selected' : ''), 'data-testid': `approach-${a.id}`},
      el('input', {type: 'radio', name: 'approach', value: a.id, checked: L.approach.preset === a.id, onchange: () => { L.approach.preset = a.id; persist(); render(); }, 'aria-label': a.name}),
      el('span', {class: 'cname'}, a.name), el('span', {class: 'cdesc'}, a.summary), el('span', {class: 'hint'}, `Average shot about ${a.avg_shot_seconds} s · ${a.tone}`)))),
    row('Average shot (s)', bind(L.approach, 'avg', {type: 'number', min: '0.5', max: '60', step: '0.5', placeholder: 'optional override', 'data-testid': 'approach-avg'}), 'Leave empty to use the approach default.'),
    el('div', {class: 'buttons'}, btn(L.plan ? 'Draft another plan' : 'Draft the plan', draftPlan, {class: 'primary', 'data-testid': 'draft-plan', disabled: busy() || !R.approaches.length})), ...feedback('draft'),
    plansHere.length ? el('p', {class: 'hint'}, 'Plans already saved for this scene are listed at the bottom of this step; open one to continue it.') : null);
  if (!L.plan) return el('div', {}, chooser, planVersions());
  if (!R.planSp) return loading();
  const scn = planScene(), beat = L.plan.blocking.find(b => b.beat_id === R.sel.beat) || L.plan.blocking[0];
  const it = L.plan.interpretation;
  const motifs = el('textarea', {rows: '3', 'data-testid': 'motifs', 'aria-label': 'Visual motifs, one per line', oninput: ev => { it.visual_motifs = ev.target.value.split('\n').map(s => s.trim()).filter(Boolean); touch(); }}); motifs.value = (it.visual_motifs || []).join('\n');
  const stale = R.impact && R.impact.stale;
  const beatTitle = id => (scn.beats.find(b => b.id === id) || {}).title || id;
  return el('div', {},
    chooser,
    stale ? el('section', {class: 'panel warnpanel', 'data-testid': 'stale-warning'}, el('h3', {}, 'The script changed after this plan was made'), el('p', {}, R.impact.summary), el('p', {class: 'hint'}, 'Go to “Director review” to rebase the plan onto the latest screenplay. Approved shots that do not depend on the changed lines keep their decisions.')) : null,
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'blocking-form'}, el('h2', {}, `${L.plan.approach.name}`),
      el('h3', {}, 'How the director reads the scene'),
      row('Summary', bind(it, 'summary', {rows: '3', 'data-testid': 'interp-summary'}, 'textarea')), row('Intent', bind(it, 'directorial_intent', {rows: '3', 'data-testid': 'interp-intent'}, 'textarea')),
      row('Tone', bind(it, 'tone')), row('Visual motifs', motifs, 'one per line'),
      el('h3', {}, 'Blocking: where everyone stands and looks'),
      row('Beat', sel(R.sel, 'beat', L.plan.blocking.map(b => [b.beat_id, beatTitle(b.beat_id)]), {'data-testid': 'beat-picker'}, {render: true})),
      beat ? el('div', {class: 'blockgrid'}, el('div', {}, el('div', {id: 'stage-host'}, stageSvg(beat)), el('p', {class: 'hint'}, 'Hollow circle = start, filled = end, line = path, short line = where they look. The dashed line is the 180° axis between the two main characters.'),
        row('Beat notes', bind(beat, 'notes', {rows: '2'}, 'textarea'))), el('div', {}, ...beat.characters.map(c => charBlocking(beat, c, scn)))) : el('p', {class: 'hint'}, 'This plan has no blocking.'),
      el('hr'), planSaveBlock()), planVersions());
}

// ---- step 6: shot list ------------------------------------------------------------------------------------------------
function shotIssue(id) {
  const is = (R.planAnalysis ? R.planAnalysis.issues : []).filter(i => i.shot_ids.includes(id));
  return is.some(i => i.severity === 'error') ? 'error' : (is.length ? 'warning' : '');
}
function newShot() {
  const scn = planScene(), ids = L.plan.shots.map(s => s.shot_id);
  const beat = R.sel.beat || scn.beats[0].id;
  return {shot_id: nextId(`${L.plan.scene_id}-S`, ids), beat_id: beat, covers: [], purpose: 'connect', purpose_note: '', size: 'MS', angle: 'eye', movement: 'static', framing: 'single', camera_side: 'A',
    lens_mm: 50, subject: [], duration_seconds: 3, transition_in: 'cut', intensity: (scn.beats.find(b => b.id === beat) || {}).intensity ?? 5, status: 'proposed', review_note: '',
    previz: {notes: ''}, storyboard: {description: '', frame_ref: null}};
}
function shotEditor(s) {
  const scn = planScene();
  const beatEls = scn.elements;
  const subjects = el('div', {class: 'chips'}, ...scn.characters.map(id => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: s.subject.includes(id), 'data-testid': `subj-${id}`,
    onchange: ev => { s.subject = ev.target.checked ? [...s.subject, id] : s.subject.filter(x => x !== id); touch(); }}), ` ${pName(id)}`)));
  const covers = el('div', {class: 'chips col'}, ...beatEls.map(e => el('label', {class: 'chip wideChip'}, el('input', {type: 'checkbox', checked: s.covers.includes(e.id), 'data-testid': `cover-${e.id}`,
    onchange: ev => { s.covers = ev.target.checked ? [...s.covers, e.id] : s.covers.filter(x => x !== e.id); touch(); }}), ` ${e.id.replace(scn.id + '-', '')} ${e.type === 'dialogue' ? pName(e.character_id) + ': ' : ''}${(e.text || '').slice(0, 50)}`)));
  s.previz = s.previz || {}; s.storyboard = s.storyboard || {description: '', frame_ref: null};
  return el('section', {class: 'panel picked', 'data-testid': 'shot-editor'}, el('h3', {}, `Editing ${s.shot_id}`),
    row('Why this shot', sel(s, 'purpose', PURPOSES, {'data-testid': 'shot-purpose'}, {render: true})),
    row('In your words', bind(s, 'purpose_note', {rows: '2', placeholder: 'Every shot must say what it is for (at least 8 characters)', 'data-testid': 'shot-purpose-note', maxlength: '400'}, 'textarea'), 'Required'),
    row('Beat', sel(s, 'beat_id', scn.beats.map(b => [b.id, b.title]), {'data-testid': 'shot-beat'}, {render: true})),
    row('Size', sel(s, 'size', SIZES, {'data-testid': 'shot-size'})), row('Angle', sel(s, 'angle', ANGLES)), row('Movement', sel(s, 'movement', MOVES.map(m => [m, label(m)]))),
    row('Framing', sel(s, 'framing', FRAMINGS.map(m => [m, label(m)]))), row('Camera side', sel(s, 'camera_side', SIDES, {'data-testid': 'shot-side'}),
      'A and B are the two sides of the line between the characters. Crossing it needs a neutral “on the axis” shot, or a move you mark as motivated below.'),
    row('Lens (mm)', bind(s, 'lens_mm', {type: 'number', min: '8', max: '400', step: '1'}, 'input', num)),
    row('Duration (s)', bind(s, 'duration_seconds', {type: 'number', min: '0.5', max: '120', step: '0.5', 'data-testid': 'shot-duration'}, 'input', Number)),
    row('Cut in with', sel(s, 'transition_in', TRANSITIONS.map(t => [t, label(t)]))), row('Who is in frame', subjects), row('Script lines it covers', el('details', {}, el('summary', {}, `${s.covers.length} line(s)`), covers)),
    row('Axis move', el('div', {class: 'inline'}, el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!s.axis_cross, 'data-testid': 'axis-motivated', onchange: ev => { s.axis_cross = ev.target.checked ? {motivated: true, reason: (s.axis_cross && s.axis_cross.reason) || ''} : null; touch(); render(); }}), ' motivated crossing of the line'),
      s.axis_cross ? el('input', {placeholder: 'Why (e.g. a character walks across)', value: s.axis_cross.reason || '', oninput: ev => { s.axis_cross.reason = ev.target.value; touch(); }}) : null)),
    row('Decision', sel(s, 'status', STATUSES, {'data-testid': 'shot-status'}, {render: true})), row('Decision note', bind(s, 'review_note', {placeholder: 'Why approved, rejected or needs review'})),
    row('Storyboard', bind(s.storyboard, 'description', {rows: '2', placeholder: 'What the frame looks like'}, 'textarea')), row('Previz note', bind(s.previz, 'notes', {placeholder: 'Notes for the previz / Scene Maker'})),
    s.previz.camera_position ? el('p', {class: 'hint'}, `Previz camera: x ${s.previz.camera_position.x}, y ${s.previz.camera_position.y}, ${s.previz.camera_position.height_m} m high, field of view ${s.previz.fov_deg}° (recalculated when you save).`) : null);
}
function step6() {
  if (!L.plan) return noPlan();
  if (!R.planSp) return loading();
  const scn = planScene(), shots = L.plan.shots;
  const cur = shots.find(s => s.shot_id === R.sel.shot) || null;
  const tl = Object.fromEntries(((R.planAnalysis || {}).timeline || []).map(t => [t.shot_id, t]));
  const rows = shots.map((s, i) => {
    const iss = shotIssue(s.shot_id);
    return el('tr', {class: `${s.shot_id === R.sel.shot ? 'selected ' : ''}${s.status === 'rejected' ? 'rejected ' : ''}${iss}`, 'data-shot': s.shot_id, 'data-testid': `shot-row-${s.shot_id}`},
      el('td', {}, String(i + 1)), el('td', {}, el('button', {type: 'button', class: 'linkbtn', 'data-testid': `edit-${s.shot_id}`, onclick: () => { R.sel.shot = s.shot_id; persist(); render(); }}, s.shot_id.replace(`${L.plan.scene_id}-`, ''))),
      el('td', {class: 'hint'}, ((scn.beats.find(b => b.id === s.beat_id) || {}).title || s.beat_id)), el('td', {}, `${s.size} · ${label(s.framing)}`), el('td', {}, `${s.angle} · ${label(s.movement)}`),
      el('td', {}, s.camera_side), el('td', {}, `${s.duration_seconds}s`), el('td', {}, label(s.purpose)), el('td', {}, badge(s.status)), el('td', {}, iss ? el('span', {class: `badge ${iss === 'error' ? 'b-failed' : 'b-review'}`}, iss) : ''),
      el('td', {class: 'rowbtns'}, btn('↑', () => move(shots, i, -1), {'aria-label': 'Move shot up', 'data-testid': `up-${s.shot_id}`}), btn('↓', () => move(shots, i, 1), {'aria-label': 'Move shot down', 'data-testid': `down-${s.shot_id}`}),
        btn('Approve', () => { s.status = 'approved'; touch(); render(); }, {'data-testid': `approve-${s.shot_id}`, disabled: s.status === 'approved'}), btn('Reject', () => { s.status = 'rejected'; touch(); render(); }, {'data-testid': `reject-${s.shot_id}`, disabled: s.status === 'rejected'}),
        btn('Copy', () => { const c = JSON.parse(JSON.stringify(s)); c.shot_id = nextId(`${L.plan.scene_id}-S`, shots.map(x => x.shot_id)); c.status = 'proposed'; shots.splice(i + 1, 0, c); R.sel.shot = c.shot_id; touch(); render(); }),
        guarded('Delete', `rmshot-${s.shot_id}`, () => { shots.splice(i, 1); if (R.sel.shot === s.shot_id) R.sel.shot = null; touch(); render(); })));
  });
  const tot = (R.planAnalysis || {}).total_seconds;
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'shots-form'}, el('h2', {}, `Shots for ${L.plan.scene_id} (${shots.length})`),
    el('p', {class: 'hint'}, `${L.plan.approach.name}. ${tot ? `Shots add up to ${tot} s against a script estimate of ${R.planAnalysis.script_seconds} s.` : ''} Click a shot number to edit it. Rejected shots drop out of the timing; every shot keeps its permanent ID.`),
    el('div', {class: 'tablewrap'}, el('table', {class: 'table shots', 'data-testid': 'shot-table'}, el('thead', {}, el('tr', {}, ...['#', 'Shot', 'Beat', 'Size · framing', 'Angle · move', 'Side', 'Length', 'Purpose', 'Decision', 'Checks', ''].map(h => el('th', {}, h)))), el('tbody', {}, ...rows))),
    el('div', {class: 'buttons'}, btn('Add a shot', () => { const s = newShot(); shots.push(s); R.sel.shot = s.shot_id; touch(); render(); }, {'data-testid': 'add-shot'}),
      btn('Check this plan', checkPlan, {'data-testid': 'check-plan', disabled: busy() || !L.planBase, title: 'Looks for repeated framing, missing coverage and continuity mistakes. Saves nothing.'})), ...feedback('check'),
    el('h3', {}, 'What the check found'), issuesList(R.planAnalysis, id => { R.sel.shot = id; persist(); render(); }),
    cur ? shotEditor(cur) : el('p', {class: 'hint'}, 'Select a shot above to edit its framing, purpose, coverage and decision.'),
    el('hr'), planSaveBlock()), planVersions());
}

// ---- step 7: director review ------------------------------------------------------------------------------------------
async function decide(kind) {
  const reviewer = (L.reviewer || '').trim(), note = (L.note || '').trim();
  if (kind !== 'submit-review' && !reviewer) return fail('decide', 'Enter your name as reviewer first.');
  if (kind === 'reject' && !note) return fail('decide', 'Add a note explaining why you are rejecting the plan.');
  await withBusy('decide', kind === 'submit-review' ? 'Submitting' : (kind === 'approve' ? 'Approving' : 'Rejecting'), async () => {
    await call(`/api/runs/${L.planBase.runId}/${kind}`, 'POST', {reviewer, note}); await loadPlanRun(); await refreshOverview();
    R.notice.decide = kind === 'submit-review' ? 'Submitted for review.' : (kind === 'approve' ? 'Plan approved. You can export it in the next step.' : 'Plan rejected. The note is recorded.');
  });
}
async function compareWith(runId) {
  if (!runId) return fail('pcmp', 'Choose the plan to compare with.');
  await withBusy('pcmp', 'Comparing the plans', async () => { R.planCmp = await call(`/api/lab/compare-plans?run_a=${L.planBase.runId}&run_b=${runId}`); });
}
function metricsPanel(an) {
  const r = an.readiness, v = an.variety;
  return el('div', {class: 'metrics', 'data-testid': 'plan-metrics'},
    ...[[`${an.status_summary.approved + an.status_summary.proposed + an.status_summary.needs_review}`, 'shots in the timeline'], [`${an.total_seconds} s`, `vs script ${an.script_seconds} s (${an.duration_delta >= 0 ? '+' : ''}${Math.round(an.duration_delta * 100)}%)`],
      [`${an.avg_shot_seconds} s`, 'average shot'], [`${v.variety_score}`, `variety (${v.distinct_setups} setups)`], [`${r.errors} / ${r.warnings}`, 'errors / warnings'],
      [`${an.status_summary.approved} / ${an.status_summary.rejected} / ${an.status_summary.proposed + an.status_summary.needs_review}`, 'approved / rejected / undecided']]
      .map(([a, b]) => el('div', {class: 'metric'}, el('strong', {}, a), el('span', {}, b))));
}
function pacingTable(an, scn) {
  return el('table', {class: 'table', 'data-testid': 'pacing-table'}, el('thead', {}, el('tr', {}, ...['Beat', 'Intensity', 'Shots', 'Average shot', 'Expected', 'Covered'].map(h => el('th', {}, h)))),
    el('tbody', {}, ...an.pacing.map((p, i) => el('tr', {}, el('td', {}, (scn.beats.find(b => b.id === p.beat_id) || {}).title || p.beat_id), el('td', {}, el('span', {class: 'bar'}, el('i', {style: `width:${p.intensity * 10}%`})), ` ${p.intensity}`),
      el('td', {}, String(p.shots)), el('td', {}, p.avg_shot_seconds != null ? `${p.avg_shot_seconds} s` : '—'), el('td', {class: 'hint'}, `${p.expected_shot_seconds} s`), el('td', {}, an.coverage.beats[i] && an.coverage.beats[i].covered ? '✓' : badge('failed'))))));
}
function step7() {
  if (!L.plan) return noPlan();
  if (!R.planSp) return loading();
  const an = R.planAnalysis, scn = planScene();
  const others = ((R.overview && R.overview.plans) || []).filter(p => p.scene_id === L.plan.scene_id && p.run_id && p.experiment_id !== (L.planBase || {}).experimentId);
  const status = R.planRun ? R.planRun.approval_status : null, saved = planState() === 'saved';
  const shotsDecide = L.plan.shots.map(s => el('tr', {class: s.status === 'rejected' ? 'rejected' : '', 'data-testid': `review-row-${s.shot_id}`}, el('td', {}, s.shot_id.replace(`${L.plan.scene_id}-`, '')), el('td', {}, `${s.size} ${label(s.framing)}`),
    el('td', {class: 'hint'}, s.purpose_note), el('td', {}, badge(s.status)), el('td', {class: 'rowbtns'}, btn('Approve', () => { s.status = 'approved'; touch(); render(); }, {'data-testid': `rv-approve-${s.shot_id}`, disabled: s.status === 'approved'}),
      btn('Reject', () => { s.status = 'rejected'; touch(); render(); }, {'data-testid': `rv-reject-${s.shot_id}`, disabled: s.status === 'rejected'}))));
  const undecided = L.plan.shots.filter(s => ['proposed', 'needs_review'].includes(s.status)).length;
  const imp = R.impact;
  const dec = (label_, testid, kind, ok, why, cls = '') => el('span', {class: 'act'}, el('button', {type: 'button', class: cls, 'data-testid': testid, disabled: !ok || busy(), title: ok ? null : why, onclick: () => decide(kind)}, label_), ok ? null : el('span', {class: 'why'}, why));
  return el('div', {},
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'review-form'}, el('h2', {}, `Review: ${L.plan.approach.name}`),
      an ? metricsPanel(an) : null, el('h3', {}, 'Does the plan follow the dramatic beats?'), an ? pacingTable(an, scn) : null,
      el('p', {class: 'hint'}, 'Tighter cutting is expected where intensity is higher. “Expected” is the approach’s rule of thumb, shown as advice only.'),
      el('h3', {}, 'Problems and warnings'), issuesList(an, id => { R.sel.shot = id; persist(); go(6); }),
      imp && imp.stale ? el('div', {class: 'warnpanel panel', 'data-testid': 'impact'}, el('h3', {}, 'The script changed after this plan was made'), el('p', {}, imp.summary),
        imp.affected_shots.length ? el('ul', {class: 'issues'}, ...imp.affected_shots.map(id => el('li', {}, `${id.replace(L.plan.scene_id + '-', '')}: ${imp.reasons[id].join('; ')}`))) : null,
        imp.unplanned_elements.length ? el('p', {class: 'why'}, `New dialogue with no shot yet: ${imp.unplanned_elements.join(', ')}.`) : null,
        el('p', {class: 'hint'}, 'Rebasing creates a new plan version on the latest screenplay. Only the shots listed above go back to review; everything else keeps its decision. This version stays as it is.'),
        el('div', {class: 'buttons'}, btn('Rebase onto the latest screenplay', rebase, {class: 'primary', 'data-testid': 'rebase', disabled: busy() || !saved, title: saved ? '' : 'Save your edits first.'}))) : null,
      ...feedback('rebase'),
      el('h3', {}, 'Decide each shot'), el('div', {class: 'tablewrap'}, el('table', {class: 'table'}, el('tbody', {}, ...shotsDecide))),
      el('div', {class: 'buttons'}, btn(`Approve all ${undecided} undecided shot(s)`, () => { for (const s of L.plan.shots) if (['proposed', 'needs_review'].includes(s.status)) s.status = 'approved'; touch(); render(); }, {'data-testid': 'approve-all', disabled: !undecided}),
        undecided ? el('span', {class: 'hint'}, 'Only do this after you have looked at them; it is recorded when you save.') : null),
      el('hr'), planSaveBlock()),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'compare-form'}, el('h2', {}, 'Compare with another approach'),
      others.length && saved ? el('div', {class: 'formrow'}, sel(R.cmpPick, 'p', [['', 'choose a plan…'], ...others.map(p => [p.run_id, `${p.name} (${p.approach})`])], {'data-testid': 'cmp-plan'}), btn('Compare the two plans', () => compareWith(R.cmpPick.p), {'data-testid': 'compare-plans', disabled: busy()}))
        : el('p', {class: 'hint'}, saved ? 'Draft a second approach in “Blocking” (use “Draft another plan”) to compare them here.' : 'Save this plan first; comparisons use saved versions.'),
      ...feedback('pcmp'), R.planCmp ? planCmpTable(R.planCmp) : null),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'approval-form'}, el('h2', {}, 'Approve or reject this plan'),
      el('p', {}, el('span', {}, 'Plan status: '), status ? badge(status) : el('span', {class: 'hint'}, saved ? 'checking…' : 'not saved')),
      !saved ? el('p', {class: 'why', 'data-testid': 'approval-why'}, 'Save your edits above first: approval applies to a saved version, never to unsaved changes.') : null,
      undecided ? el('p', {class: 'hint'}, `${undecided} shot(s) are still undecided. You can approve the plan anyway; the manifest will then need an explicit, recorded override.`) : null,
      row('Your name', bind(L, 'reviewer', {maxlength: '80', placeholder: 'Needed to approve or reject', 'data-testid': 'plan-reviewer'})), row('Note', bind(L, 'note', {maxlength: '2000', placeholder: 'Required when rejecting', 'data-testid': 'plan-note-review'})),
      el('div', {class: 'buttons'}, dec('Submit for review', 'plan-submit', 'submit-review', saved && ['draft', 'rejected'].includes(status), !saved ? 'Save first.' : 'Already submitted or decided.'),
        dec('Approve the plan', 'plan-approve', 'approve', saved && status === 'review', 'Submit for review first.', 'primary'), dec('Reject the plan', 'plan-reject', 'reject', saved && status === 'review', 'Submit for review first.')),
      ...feedback('decide')));
}
function planCmpTable(d) {
  return el('div', {'data-testid': 'plan-cmp'}, el('table', {class: 'table'}, el('thead', {}, el('tr', {}, el('th', {}, 'Measure'), el('th', {}, 'This plan'), el('th', {}, 'Other plan'))),
    el('tbody', {}, ...d.metrics.map(m => el('tr', {class: m.differs ? 'diffrow' : ''}, el('td', {}, m.metric), el('td', {}, String(m.a)), el('td', {}, String(m.b)))))),
    el('h3', {}, 'Directorial intent'), el('div', {class: 'twocol'}, el('div', {}, el('strong', {}, 'This plan'), el('p', {}, d.interpretation.a)), el('div', {}, el('strong', {}, 'Other plan'), el('p', {}, d.interpretation.b))));
}

// ---- step 8: export -----------------------------------------------------------------------------------------------------
const EXPORTS = [
  {kind: 'screenplay-json', label: 'Screenplay (JSON)', desc: 'The full screenplay with timings and fingerprints (filmcraft.screenplay.v1).', src: 'sp'},
  {kind: 'script', label: 'Readable script', desc: 'A Fountain-style script you can open in any text editor.', src: 'sp'},
  {kind: 'blocking', label: 'Blocking (JSON)', desc: 'Stage layout, positions, paths and eyelines per beat.', src: 'plan'},
  {kind: 'shot-list', label: 'Shot list (JSON)', desc: 'Every shot in order with purpose, camera and timing.', src: 'plan'},
  {kind: 'shot-list-csv', label: 'Shot list (spreadsheet)', desc: 'The same list as CSV for Excel.', src: 'plan'},
  {kind: 'shot-plan', label: 'Shot plan for Cinematography / Editing', desc: 'Feeds the existing Cinematography and Editing crafts (filmcraft.shot_plan.v1).', src: 'plan'},
  {kind: 'scene-manifest', label: 'Scene manifest', desc: 'Screenplay scene, beats and blocking, prepared for a future Dreambox Scene Maker adapter.', src: 'plan', approved: true},
  {kind: 'shot-manifest', label: 'Shot manifest', desc: 'Approved shots with camera, previz and storyboard metadata, prepared for Scene Maker.', src: 'plan', approved: true},
];
async function doExport(ex, overrides) {
  const runId = ex.src === 'sp' ? L.spBase.runId : L.planBase.runId;
  await withBusy(`x-${ex.kind}`, `Exporting ${ex.label}`, async () => {
    const q = overrides.map(o => `override=${o}`).join('&');
    const r = await fetch(`/api/runs/${runId}/exports/${ex.kind}${q ? '?' + q : ''}`, {method: 'POST'});
    if (!r.ok) { const d = await r.json().catch(() => ({})); const msg = typeof d.detail === 'string' ? d.detail : (d.detail && d.detail.message) || `HTTP ${r.status}`; R.needs = {...(R.needs || {}), [ex.kind]: msg}; throw new Error(msg); }
    const name = (/filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || `${ex.kind}.json`;
    download(name, await r.text(), r.headers.get('Content-Type') || 'application/json');
    delete (R.needs || {})[ex.kind];
    R.notice[`x-${ex.kind}`] = `Saved “${name}” to your Downloads folder.${r.headers.get('X-Craftbox-Existing') === 'true' ? ' (This is the manifest created earlier; it is never regenerated.)' : ''}${overrides.length ? ' Override recorded: ' + overrides.join(', ') + '.' : ''}`;
    R.exportsDone.push(ex.kind);
  });
}
function step8() {
  if (!L.plan || !L.planBase) return noPlan();
  const status = R.planRun ? R.planRun.approval_status : null, approved = ['approved', 'exported'].includes(status), saved = planState() === 'saved';
  const rows = EXPORTS.map(ex => {
    const needsApproval = ex.approved && !approved, blocked = (ex.src === 'plan' && !L.planBase) || needsApproval;
    const msg = (R.needs || {})[ex.kind] || '';
    const can = ['acknowledge_stale', 'allow_pending'].filter(o => msg.includes(o));
    return el('div', {class: 'exrow', 'data-testid': `export-${ex.kind}`}, el('div', {}, el('strong', {}, ex.label), el('p', {class: 'hint'}, ex.desc)),
      el('div', {}, el('span', {class: 'act'}, el('button', {type: 'button', class: ex.approved ? 'primary' : '', 'data-testid': `dl-${ex.kind}`, disabled: blocked || busy(), title: needsApproval ? 'Approve the plan first.' : null, onclick: () => doExport(ex, [])}, 'Download'),
        needsApproval ? el('span', {class: 'why'}, 'Approve the plan in Director review first.') : null),
        can.length ? el('div', {class: 'override'}, ...can.map(o => el('p', {class: 'hint'}, o === 'acknowledge_stale' ? 'The script changed after this plan was made. You can export anyway; this is recorded in the file.' : 'Some shots are undecided. You can export anyway; the undecided shots are listed as excluded and the choice is recorded.')),
          btn('Export anyway (recorded)', () => doExport(ex, can), {'data-testid': `force-${ex.kind}`, disabled: busy()})) : null,
        ...feedback(`x-${ex.kind}`)));
  });
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'export-form'}, el('h2', {}, 'Export'),
    el('p', {}, el('span', {}, 'Plan status: '), status ? badge(status) : el('span', {class: 'hint'}, 'unknown'), el('span', {class: 'hint'}, ` · exports use the saved version${saved ? '' : ' (you have unsaved changes that are NOT included; save them in the previous step)'}`)),
    !approved ? el('p', {class: 'why', 'data-testid': 'not-approved'}, 'The two manifests need an approved plan. The other files can be exported any time.') : null, ...rows),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'finish-form'}, el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'}, btn('Start a new scene', () => { Lab.reset(); }, {'data-testid': 'lab-new'}), btn('Back to the review', () => go(7), {'data-testid': 'lab-back-review'}), btn('Open History (all experiments)', () => document.getElementById('tab-history').click(), {'data-testid': 'lab-open-history'}))));
}

Lab.reset = () => {
  Object.assign(L, {step: 1, sceneId: null, sp: null, spBase: null, spSaved: null, plan: null, planBase: null, planSaved: null, selBeat: null, selChar: null, revNote: '', planNote: '', note: ''});
  Object.assign(R, {overview: null, spArt: null, planArt: null, planAnalysis: null, live: null, impact: null, planSp: null, planRun: null, planCmp: null, cmp: null, errors: {}, notice: {}, needs: {}, exportsDone: []});
  persist(); Lab.show();
};
Object.assign(Lab.stepFns, {5: step5, 6: step6, 7: step7, 8: step8});
Lab.nextFor = n => ({
  5: {label: 'Next: plan the shots', disabled: !L.plan, why: 'Draft a plan or open a saved one first.'},
  6: {label: 'Next: review as the director', disabled: !L.plan, why: 'There is no plan yet.'},
  7: {label: 'Next: approve and export', disabled: !L.planBase || planState() !== 'saved', why: 'Save the plan version first. Exports are made from saved versions.'},
}[n]);
Lab.onEnter = async n => {
  try {
    if (!R.approaches.length) R.approaches = await call('/api/lab/approaches');
    if (n >= 5 && L.planBase && !R.planSp) { R.planSp = (await call(`/api/experiments/${L.planBase.experimentId}`)).input.screenplay; if (!R.sel.beat && L.plan) R.sel.beat = (planScene().beats[0] || {}).id; }
    if (n >= 5) await refreshOverview();
    if (n === 6 || n === 7) { if (L.planBase && planState() === 'saved' && !R.planAnalysis && R.planArt) R.planAnalysis = R.planArt.analysis; }
    if (n === 7 || n === 8) { await loadImpact(); await loadPlanRun(); }
  } catch (e) { /* the page still works from the typed drafts */ }
  if (Lab.L.step === n) render();
};
})();
