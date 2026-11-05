// Lighting Lab (CB2B): an 8-step wizard from choosing a scene to exporting an approved lighting plan.
// It draws on the Art Lab's own set-layout editor (Art.kit.layoutSvg) and adds lights, illumination zones and shadow directions as an overlay,
// so the set, the actors' blocking and the cameras are the same ones the other labs show. Follows guidelines/ui-standard.md.
// The zones and shadows drawn here are a quick approximate preview in the browser; every number in the checks comes from the server.
const Light = (() => {
const {el, call} = ui;
const K = Art.kit;
const byId = id => document.getElementById(id);
const KEY = 'craftbox.light.v1';
const L = {v: 1, step: 1, projectId: null, sceneId: null, screenplayExp: null, artExp: '', planExp: '', preset: 'warm_naturalistic', setupExp: '', planName: '', doc: null, base: null, saved: null, note: '',
  sel: {light: null, beat: null, shot: null}, show: {zones: true, shadows: true, cams: true}, reviewer: '', rnote: '', cmp: '', copyTo: [], newRole: 'fill', setupId: '', setupName: '', setupSummary: ''};
const R = {projects: [], overview: null, sps: [], scenes: [], plans: [], arts: [], presets: [], spArt: null, artDoc: null, planArt: null, analysis: null, impact: null, runInfo: null, cmpResult: null, errors: {}, notice: {}, busy: null, armed: null, needs: {}, uid: 0};

const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(L)); } catch (e) { /* storage unavailable: drafts live for this session only */ } };
const restore = () => { try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.v === 1) Object.assign(L, s, {sel: {...L.sel, ...s.sel}, show: {...L.show, ...s.show}}); } catch (e) { /* ignore */ } };

const GLOSS = {...Art.GLOSS,
  'lighting plan': 'one complete way of lighting a scene: the lights, their settings, and any changes for single shots. You can make several and compare them.',
  'scene setup': 'the lights that every shot of the scene shares.',
  'shot adjustment': 'a change to the scene setup for one shot only. The shared setup stays as it is.',
  'key light': 'the main light on the people.',
  'fill light': 'a softer light that lifts the shadows the key light leaves.',
  backlight: 'a light behind the people that traces their edges and separates them from the background.',
  practical: 'a light you can see in the room, such as a lamp.',
  motivated: 'light that seems to come from a visible source, such as a doorway or a window.',
  ambient: 'the general level of light in the room, with no single direction.',
  'colour temperature': 'how warm or cool a light looks, in Kelvin (K). About 2700 K is a warm lamp, 5600 K is daylight, and higher is bluer.',
  'beam angle': 'how wide the light spreads, in degrees.',
  softness: 'how gentle the edge of a shadow is. 0 is hard and sharp; 1 is soft.',
  falloff: 'how quickly a light fades as you move away from it.',
};
const STEPS = ui.steps([
  {short: 'Scene', title: 'choose a scene and start a lighting plan', intro: 'Pick the scene, the art design it is lit for, and a starting point, then start a lighting plan. The plan uses the art design’s set layout and the director’s actors and cameras, and never changes them. You can make several plans for one scene and compare them.'},
  {short: 'Conditions', title: 'describe the light of the scene', intro: 'Say what time of day and weather the scene is set in, the mood you want, and what the light is for in the story. The checks use this to tell you when a light does not belong, for example sunlight at night.'},
  {short: 'Lights', title: 'place and set the lights', intro: 'Place each light on the top-down plan. Drag a light to move it, drag the small circle at the end of its arrow to turn it, or select it and use the arrow keys. The coloured glow and the dark arrows are an approximate preview, not a simulation.'},
  {short: 'Shots', title: 'adjust the lights for single shots', intro: 'Pick a shot to see which lights are on for it and where its camera looks. Change a setting for this shot only, and the scene setup stays the same for every other shot. Say why, so the next person knows the change is on purpose.'},
  {short: 'Checks', title: 'check the lighting for problems', intro: 'Run the checks to compare related shots, the set, the actors’ movement and the time of day. The checks are advice: they say what looks wrong and how to fix it, and they never change your plan or stop you saving.'},
  {short: 'Comparison', title: 'compare two lighting plans', intro: 'Put two plans for this scene side by side. Each is compared on settings you can check, with a plain statement of how it is likely to feel and what that rests on.'},
  {short: 'Review', title: 'review the lighting and decide', intro: 'Read what the checks found, deal with anything that is out of date after a change to the script, the art design or the director’s plan, then approve or reject this plan with your name. Approval applies to one saved version and never changes other plans.'},
  {short: 'Export', title: 'approve and export', intro: 'An approved plan can be exported as files for later tools: the plan, a list of lights for each shot, and instructions for the camera and previz work. You can also keep these lights as a setup to reuse. Nothing is sent to Dreambox or any other program.'},
]);

// ---- element helpers --------------------------------------------------------------------------------------------------------------------------
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
function numBind(obj, key, props = {}, after) {
  const node = el('input', {type: 'number', ...props});
  node.value = obj[key] ?? '';
  node.addEventListener('input', () => { if (node.value !== '' && Number.isFinite(Number(node.value))) { obj[key] = Number(node.value); if (after) after(); touch(); } });
  return node;
}
function sel(obj, key, options, props = {}, opt = {}) {
  const node = el('select', props);
  for (const o of options) { const [v, label] = Array.isArray(o) ? o : [o, o]; node.append(el('option', {value: v}, label)); }
  node.value = obj[key] ?? '';
  node.addEventListener('change', () => { obj[key] = node.value; touch(); if (opt.render) render(); });
  return node;
}
const btn = (label, fn, props = {}) => el('button', {type: 'button', onclick: fn, ...props}, label);
function guarded(label, key, fn, props = {}) {
  const armed = R.armed === key;
  return el('button', {type: 'button', class: armed ? 'danger' : '', onclick: () => { if (armed) { R.armed = null; fn(); } else { R.armed = key; render(); } }, ...props}, armed ? 'Click again to confirm' : label);
}
const jsonOf = o => JSON.stringify(o);
const clone = o => JSON.parse(JSON.stringify(o));
const dirty = () => (!L.doc ? 'none' : (!L.saved ? 'unsaved' : (L.saved === jsonOf(L.doc) ? 'saved' : 'changed')));
const STATE = {unsaved: 'Not saved yet. Saving makes a new version and keeps what you typed on screen.', saved: 'Saved. What you typed is still shown here.', changed: 'Changed, not saved yet. Saving makes a new version; earlier versions stay exactly as they were.'};
const when = iso => (iso ? iso.replace('T', ' ').replace(/\.\d+Z$/, 'Z') : '');
const badge = K.badge;
const names = () => Object.fromEntries(((R.spArt && R.spArt.characters) || []).map(c => [c.id, c.name]));
const scene = () => R.spArt && R.spArt.scenes.find(s => s.id === L.sceneId);
const stage = () => ({w: (R.artDoc || {layout: {width_m: 6}}).layout.width_m, d: (R.artDoc || {layout: {depth_m: 5}}).layout.depth_m});
function nextId(prefix, existing) {
  const nums = existing.filter(x => x.startsWith(prefix)).map(x => parseInt(x.slice(prefix.length), 10)).filter(Number.isFinite);
  return prefix + String((nums.length ? Math.max(...nums) : 0) + 1);
}
function friendly(message) {
  const m = message.replace(/\$\./g, '').replace(/\[(\d+)\]/g, (_, n) => ` #${Number(n) + 1}`).replace(/\./g, ' › ');
  return `Cannot save yet: ${m}. Change the field it names, then press Save again. Nothing you typed was lost.`;
}
const shotName = id => id.split('-').pop();

// ---- feedback beside the control (U5) -----------------------------------------------------------------------------------------------------------
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
function fillGlossary(root) {   // built from the words actually on screen, so no term is used without its gloss
  if (!root) return;
  const body = [...root.querySelectorAll('h1, h2, h3, .intro, .hint, label, button, p')].filter(e => !e.closest('.glossary')).map(e => e.textContent).join(' | ').toLowerCase();
  const terms = Object.keys(GLOSS).filter(t => new RegExp('\\b' + t + 's?\\b').test(body));
  const old = root.querySelector('.glossary'); if (old) old.remove();
  if (terms.length) root.insertBefore(glossaryBlock(terms), root.querySelector('#light-nav'));
}

// ---- data ---------------------------------------------------------------------------------------------------------------------------------------------
async function loadProjects() { try { R.projects = await call('/api/lab/projects'); } catch (e) { R.projects = []; } }
async function loadOverview() {
  if (!L.projectId) { R.overview = null; R.arts = []; return; }
  try {
    R.overview = await call(`/api/light/projects/${encodeURIComponent(L.projectId)}`);
    const lab = await call(`/api/lab/projects/${encodeURIComponent(L.projectId)}`);
    R.sps = lab.screenplay_versions.filter(v => v.run_id); R.plans = lab.plans;
    const art = await call(`/api/art/projects/${encodeURIComponent(L.projectId)}`);
    R.arts = art.treatments.filter(t => t.run_id);
  } catch (e) { R.overview = null; R.arts = []; }
}
async function loadScreenplay(experimentId) {
  const exp = await call(`/api/experiments/${experimentId}`);
  const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
  if (!run) throw new Error('That screenplay revision has no completed run. Open it in the Scene Lab and save it again.');
  R.spArt = (await call(`/api/runs/${run.id}`)).envelope.artifact;
  R.scenes = R.spArt.scenes;
}
const sceneArts = () => R.arts.filter(t => t.scene_id === L.sceneId);
function defaults() {
  const plans = R.plans.filter(p => p.scene_id === L.sceneId && p.run_id);
  L.planExp = plans.length ? plans[plans.length - 1].experiment_id : '';
  const arts = sceneArts();
  if (!arts.some(a => a.experiment_id === L.artExp)) L.artExp = arts.length ? arts[arts.length - 1].experiment_id : '';
}
async function adopt(r) {
  const run = r.run;
  if (run.run_status === 'failed') throw new Error(run.error.message);
  const a = run.envelope.artifact;
  L.base = {experimentId: r.experiment.id, runId: run.id};
  const doc = clone(a); delete doc.analysis;
  L.doc = doc; L.saved = jsonOf(doc); R.analysis = a.analysis; R.impact = null; R.runInfo = null; R.cmpResult = null;
  const exp = r.experiment.input ? r.experiment : await call(`/api/experiments/${r.experiment.id}`);
  R.artDoc = exp.input.art_direction; R.planArt = exp.input.direction_plan || null; R.spArt = exp.input.screenplay; R.scenes = R.spArt.scenes;
  L.sceneId = a.scene_id;
  if (!L.sel.beat) L.sel.beat = ((scene() || {}).beats || [{}])[0].id || null;
  if (!L.sel.light || !doc.lights.some(l => l.id === L.sel.light)) L.sel.light = (doc.lights[0] || {}).id || null;
  if (!L.sel.shot || !(R.planArt || {shots: []}).shots.some(s => s.shot_id === L.sel.shot)) L.sel.shot = ((R.planArt || {shots: []}).shots[0] || {}).shot_id || null;
  persist();
}
async function draft() {
  if (!L.screenplayExp || !L.sceneId) return fail('draft', 'Choose a screenplay revision and a scene first.');
  if (!L.artExp) return fail('draft', 'Choose the art design to light first. If the list is empty, draft one in the Art Lab.');
  if (!L.planName.trim()) return fail('draft', 'Give the lighting plan a name first, for example “Warm, naturalistic, intimate”.');
  await withBusy('draft', 'Drafting the lighting plan', async () => {
    const r = await call('/api/light/draft', 'POST', {screenplay_experiment_id: L.screenplayExp, art_experiment_id: L.artExp, name: L.planName.trim(), preset: L.setupExp ? 'setup' : L.preset, plan_experiment_id: L.planExp || null, setup_experiment_id: L.setupExp || null});
    await adopt(r); await loadOverview();
    R.notice.draft = `Drafted “${L.doc.plan.name}” with ${L.doc.lights.length} lights and ${L.doc.adjustments.length} shot adjustments. Click “Next: describe the light of the scene” to continue.`;
  });
}
async function openPlan(experimentId) {
  await withBusy('draft', 'Opening the lighting plan', async () => {
    const exp = await call(`/api/experiments/${experimentId}`);
    const run = [...exp.runs].reverse().find(r => r.run_status === 'completed');
    if (!run) throw new Error('That lighting plan has no completed run.');
    L.projectId = exp.input.screenplay.project.id; const ref = exp.input.source_ref || {};
    L.screenplayExp = ref.screenplay_experiment_id || L.screenplayExp; L.artExp = ref.art_experiment_id || L.artExp; L.planExp = ref.plan_experiment_id || '';
    await adopt({experiment: exp, run: await call(`/api/runs/${run.id}`)});
    await loadOverview(); await loadImpact();
    R.notice.draft = `Opened “${exp.name}”. Click “Next: describe the light of the scene” to continue.`;
  });
}
async function save() {
  const stamp = new Date().toISOString().slice(11, 16);
  const n = ((R.overview && R.overview.plans.filter(t => t.plan_id === L.doc.plan.id && t.art_treatment_id === L.doc.source.art.treatment_id).length) || 0) + 1;
  await withBusy('save', 'Saving this version', async () => {
    const r = await call('/api/light/save', 'POST', {base_experiment_id: L.base.experimentId, light: L.doc, name: `${L.doc.plan.name} v${n + 1}`, note: (L.note || '').trim() || `saved ${stamp}`});
    await adopt(r); await loadOverview(); await loadImpact(); await loadRun();
    R.notice.save = `Saved as a new version of “${L.doc.plan.name}”. The earlier version is unchanged.`;
  });
}
async function check() {
  await withBusy('check', 'Checking the lighting', async () => {
    const out = await call('/api/light/analyze', 'POST', {base_experiment_id: L.base.experimentId, light: L.doc});
    R.analysis = out.analysis; R.notice.check = `Checked: ${out.analysis.readiness.attention} item(s) need attention and ${out.analysis.readiness.notes} note(s). Nothing was saved.`;
  });
}
async function loadImpact() { if (!L.base) return; try { R.impact = await call(`/api/light/plans/${L.base.experimentId}/impact`); } catch (e) { R.impact = null; } }
async function loadRun() { if (!L.base) { R.runInfo = null; return; } try { R.runInfo = await call(`/api/runs/${L.base.runId}`); } catch (e) { R.runInfo = null; } }
async function rebase() {
  await withBusy('rebase', 'Rebasing the lighting plan', async () => {
    const r = await call(`/api/light/plans/${L.base.experimentId}/rebase`, 'POST', {});
    await adopt(r); await loadOverview(); await loadImpact(); await loadRun();
    R.notice.rebase = `Created a new version on the latest script, art design and director’s plan. ${r.impact.affected_lights.length + r.impact.affected_adjustments.length} item(s) that depend on changed material are back in review; everything else keeps its decision. The old version is unchanged.`;
  });
}

// ---- save block (U2, U3) ------------------------------------------------------------------------------------------------------------------------
function saveBlock() {
  const s = dirty();
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(L, 'note', {maxlength: '200', placeholder: 'For example: warmer key for the close-ups', 'data-testid': 'light-note'})),
    el('p', {class: `state s-${s}`, 'data-testid': 'light-state', 'aria-live': 'polite'}, STATE[s] || ''),
    el('div', {class: 'buttons'}, el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'light-save', onclick: save, disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''}, 'Save lighting plan version')),
    ...feedback('save'));
}
function afterEdit() {
  for (const n of document.querySelectorAll('#view-light [data-testid="light-state"]')) { const s = dirty(); n.textContent = STATE[s] || ''; n.className = `state s-${s}`; }
  for (const b of document.querySelectorAll('#view-light [data-testid="light-save"]')) { const same = dirty() === 'saved'; b.disabled = same || busy(); b.title = same ? 'Nothing has changed since the last save.' : ''; }
  renderNav();
}

// ---- approximate preview of the light (browser only; the checks use the server's numbers) -------------------------------------------------------------
const REF = 1.5;
const bearing = (a, b) => { const s = stage(); return (Math.atan2((b.x - a.x) * s.w, (b.y - a.y) * s.d) * 180 / Math.PI + 360) % 360; };
const angDiff = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; };
const smooth = t => { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); };
function levelAt(l, p) {
  if (!l.enabled) return 0;
  if (l.positional === false) return l.intensity;
  const s = stage(), dx = (l.x - p.x) * s.w, dy = (l.y - p.y) * s.d, d = Math.max(Math.hypot(dx, dy), 0.2);
  const off = angDiff(bearing(l, p), l.rotation_deg), half = l.beam_angle_deg / 2, inner = half * (1 - l.softness);
  const ang = off <= inner ? 1 : (off < half ? smooth(1 - (off - inner) / Math.max(half - inner, 1e-6)) : 0);
  const f = l.falloff || {mode: 'inverse_square', range_m: 8};
  const dist = f.mode === 'inverse_square' ? (d < f.range_m ? Math.min(1, (REF / d) ** 2) * Math.min(1, 1 + (f.range_m - d) / f.range_m) : 0) : (f.mode === 'linear' ? Math.max(0, 1 - d / f.range_m) : 1);
  return l.intensity * ang * dist;
}
function kelvinRgb(k) {   // a common approximation of the colour of a black-body light, for the preview only
  const t = Math.max(1000, Math.min(15000, k)) / 100;
  const r = t <= 66 ? 255 : 329.7 * Math.pow(t - 60, -0.1332), g = t <= 66 ? 99.47 * Math.log(t) - 161.12 : 288.12 * Math.pow(t - 60, -0.0755), b = t >= 66 ? 255 : (t <= 19 ? 0 : 138.52 * Math.log(t - 10) - 305.04);
  const c = v => Math.round(Math.max(0, Math.min(255, v)));
  return `rgb(${c(r)},${c(g)},${c(b)})`;
}
const ROLE_COLOUR = {key: '#ffffff', fill: '#9fd8ff', backlight: '#ffb86b', rim: '#ffb86b', practical: '#f4e29a', ambient: '#bbbbbb', motivated: '#8ef0b5'};
const ROLE_LABEL = {key: 'Key light', fill: 'Fill light', backlight: 'Backlight', rim: 'Rim light', practical: 'Practical (a lamp in the room)', ambient: 'Ambient (general level)', motivated: 'Motivated (from a visible source)'};
const reachM = l => { const f = l.falloff || {range_m: 8, mode: 'inverse_square'}; let last = 0.4; for (let d = 0.4; d <= Math.min(f.range_m, 12); d += 0.25) { if (levelAt({...l, positional: true}, {x: l.x + Math.sin(l.rotation_deg * Math.PI / 180) * d / stage().w, y: l.y + Math.cos(l.rotation_deg * Math.PI / 180) * d / stage().d}) >= 0.06) last = d; } return last; };

// ---- the lighting overlay on the art layout editor (reuses Art.kit.layoutSvg) ------------------------------------------------------------------------------------
function overlayFor(lights, o) {
  return (svg, mk, {W, H}) => {
    const zl = mk('g', {class: 'zonelayer', 'pointer-events': 'none'}), ll = mk('g', {class: 'lightlayer'});
    svg.append(zl, ll);
    const st = stage();
    const bl = o.beat && R.planArt ? (R.planArt.blocking || []).find(b => b.beat_id === o.beat) : null;
    const keyLight = () => (lights.find(l => l.id === o.selected && ['key', 'motivated'].includes(l.role) && l.enabled) || lights.filter(l => l.role === 'key' && l.enabled).sort((a, b) => b.intensity - a.intensity)[0] || lights.find(l => l.role === 'motivated' && l.enabled));
    function draw() {
      zl.replaceChildren(); ll.replaceChildren();
      if (o.zones) {
        const nx = 26, ny = 20;
        for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
          const p = {x: (i + 0.5) / nx, y: (j + 0.5) / ny};
          let tot = 0, m = 0;
          for (const l of lights) { const v = levelAt(l, p); tot += v; m += v * 1e6 / l.color_temp_k; }
          if (tot < 0.03) continue;
          zl.append(mk('rect', {x: i * W / nx, y: j * H / ny, width: W / nx, height: H / ny, fill: kelvinRgb(1e6 / (m / tot)), opacity: Math.min(0.55, tot * 0.5).toFixed(2), class: 'glowcell'}));
        }
      }
      if (o.camera) {
        const c = o.camera.camera_position, t = o.camera.target;
        if (c && t) {
          const ax = bearing(c, t), half = (o.camera.fov_deg || 40) / 2, r = Math.hypot((t.x - c.x) * st.w, (t.y - c.y) * st.d) + 1.5, pts = [`${c.x * W},${c.y * H}`];
          for (let a = -half; a <= half + 0.01; a += half / 4) { const b = (ax + a) * Math.PI / 180; pts.push(`${(c.x + Math.sin(b) * r / st.w) * W},${(c.y + Math.cos(b) * r / st.d) * H}`); }
          zl.append(mk('polygon', {points: pts.join(' '), class: 'camwedge'}));
        }
      }
      for (const l of lights) {
        if (!l.enabled || l.positional === false) continue;
        const half = l.beam_angle_deg / 2, r = reachM(l), pts = [`${l.x * W},${l.y * H}`];
        for (let a = -half; a <= half + 0.01; a += Math.max(half / 6, 1)) { const b = (l.rotation_deg + a) * Math.PI / 180; pts.push(`${(l.x + Math.sin(b) * r / st.w) * W},${(l.y + Math.cos(b) * r / st.d) * H}`); }
        zl.append(mk('polygon', {points: pts.join(' '), class: 'cone' + (l.id === o.selected ? ' sel' : ''), stroke: kelvinRgb(l.color_temp_k)}));
      }
      if (o.shadows && bl) {
        const k = keyLight();
        if (k && k.positional !== false) for (const c of bl.characters) {
          const b = bearing(k, c.end) * Math.PI / 180, x0 = c.end.x * W, y0 = c.end.y * H, x1 = x0 + Math.sin(b) * 38, y1 = y0 + Math.cos(b) * 38;
          zl.append(mk('line', {x1: x0, y1: y0, x2: x1, y2: y1, class: 'shadowarrow'}), mk('circle', {cx: x1, cy: y1, r: 3.5, class: 'shadowtip'}));
        }
      }
      for (const l of lights) {
        const cx = l.x * W, cy = l.y * H, rot = l.rotation_deg * Math.PI / 180, on = l.enabled, selected = l.id === o.selected;
        const g = mk('g', {class: 'lamp' + (selected ? ' sel' : '') + (on ? '' : ' off'), 'data-light': l.id, tabindex: o.editable ? '0' : '-1', role: 'button',
          'aria-label': `Light ${l.id}, ${ROLE_LABEL[l.role] || l.role}, ${on ? 'on' : 'off'}, at ${l.x.toFixed(2)}, ${l.y.toFixed(2)}, pointing ${Math.round(l.rotation_deg)} degrees.${o.editable ? ' Press the arrow keys to move it, and [ or ] to turn it.' : ''}`});
        if (l.positional !== false) g.append(mk('line', {x1: cx, y1: cy, x2: cx + Math.sin(rot) * 30, y2: cy + Math.cos(rot) * 30, class: 'dirline', stroke: ROLE_COLOUR[l.role] || '#fff'}));
        g.append(mk('circle', {cx, cy, r: 9, fill: kelvinRgb(l.color_temp_k), stroke: ROLE_COLOUR[l.role] || '#fff', class: 'lampdot'}), mk('text', {x: cx, y: cy - 13, class: 'cap lampcap', 'text-anchor': 'middle'}, l.id.replace(/^L-/, '')));
        if (o.editable && selected && l.positional !== false) g.append(mk('circle', {cx: cx + Math.sin(rot) * 30, cy: cy + Math.cos(rot) * 30, r: 5, class: 'handle', 'data-handle': l.id}));
        ll.append(g);
      }
    }
    draw();
    if (!o.editable) return;
    const pt = ev => { const m = svg.getScreenCTM().inverse(), p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; const q = p.matrixTransform(m); return {x: Math.max(0, Math.min(1, q.x / W)), y: Math.max(0, Math.min(1, q.y / H))}; };
    const r2 = v => Math.round(v * 100) / 100;
    let drag = null;
    svg.addEventListener('pointerdown', ev => {
      const h = ev.target.closest && ev.target.closest('[data-handle]'), g = ev.target.closest && ev.target.closest('[data-light]');
      if (!h && !g) return;
      const id = (h || g).dataset.handle || (h || g).dataset.light;
      drag = {id, mode: h ? 'rotate' : 'move'}; svg.setPointerCapture(ev.pointerId); o.onSelect(id); ev.preventDefault();
    });
    svg.addEventListener('pointermove', ev => {
      if (!drag) return;
      const l = lights.find(x => x.id === drag.id), p = pt(ev);
      if (drag.mode === 'move') { l.x = r2(p.x); l.y = r2(p.y); } else { l.rotation_deg = Math.round(bearing(l, p)) % 360; }
      draw();
    });
    const end = () => { if (drag) { drag = null; touch(); render(); } };
    svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
    svg.addEventListener('keydown', ev => {
      const g = ev.target.closest && ev.target.closest('[data-light]'); if (!g) return;
      const l = lights.find(x => x.id === g.dataset.light), step = ev.shiftKey ? 0.05 : 0.01, d = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[ev.key];
      if (d) { ev.preventDefault(); l.x = r2(Math.max(0, Math.min(1, l.x + d[0] * step))); l.y = r2(Math.max(0, Math.min(1, l.y + d[1] * step))); }
      else if (ev.key === '[' || ev.key === ']') { ev.preventDefault(); l.rotation_deg = (Math.round(l.rotation_deg) + (ev.key === ']' ? 1 : -1) * (ev.shiftKey ? 5 : 1) + 360) % 360; }
      else return;
      o.onSelect(l.id); touch(); render();
      const again = document.querySelector(`#view-light [data-light="${l.id}"]`); if (again) again.focus();
    });
  };
}
function planSvg(lights, o = {}) {
  return K.layoutSvg(R.artDoc, {editable: false, plan: R.planArt, names: names(), beat: o.beat, cams: o.cams, shotIds: o.shotIds, label: o.label || 'Lighting plan on the set layout', testid: o.testid || 'light-svg',
    overlay: overlayFor(lights, o)});
}

// ---- findings -----------------------------------------------------------------------------------------------------------------------------------------
function findings(rules, shotId) {
  const list = ((R.analysis || {}).issues || []).filter(i => (!rules || rules.includes(i.rule)) && (!shotId || i.shot_id === shotId));
  if (!list.length) return null;
  return el('div', {class: 'auditbox', 'data-testid': 'findings'}, el('h3', {}, 'What the checks found (advice only)'), K.findingsList(list));
}
function listEditor(items, makeNew, render1, addLabel, testid, emptyText) {
  return el('div', {}, !items.length ? el('p', {class: 'hint', 'data-empty': testid}, emptyText) : null,
    ...items.map((it, i) => el('div', {class: 'listcard', 'data-testid': `${testid}-${i}`}, render1(it, i), el('div', {class: 'buttons'}, guarded('Remove', `rm-${testid}-${i}`, () => { items.splice(i, 1); touch(); render(); }, {'aria-label': `Remove ${testid} ${i + 1}`})))),
    el('div', {class: 'buttons'}, btn(addLabel, () => { items.push(makeNew()); touch(); render(); }, {'data-testid': `add-${testid}`})));
}

// ---- step 1: scene ------------------------------------------------------------------------------------------------------------------------------------------
function step1() {
  const items = (R.overview && R.overview.plans) || [], setups = (R.overview && R.overview.setups) || [];
  const arts = sceneArts();
  const started = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'start-form'}, el('h2', {}, 'Start a new lighting plan'),
    !R.projects.length ? el('p', {class: 'hint', 'data-empty': 'projects', 'data-testid': 'no-projects'}, 'There are no saved screenplays yet. Open the Scene Lab, load the sample scene and save it, then come back and press “Refresh the list”.') : null,
    row('Project', sel(L, 'projectId', [['', '— choose a project —'], ...R.projects.map(p => [p.project_id, p.title || p.project_id])], {'data-testid': 'l-project'}), 'Projects come from the Scene Lab.'),
    row('Screenplay revision', sel(L, 'screenplayExp', [['', '— choose a revision —'], ...R.sps.map(v => [v.experiment_id, `Revision ${v.revision}${v.note ? ' — ' + v.note : ''}`])], {'data-testid': 'l-sp'})),
    row('Scene', sel(L, 'sceneId', [['', '— choose a scene —'], ...R.scenes.map(s => [s.id, `${s.id} — ${s.slugline}`])], {'data-testid': 'l-scene'})),
    row('Art design to light', sel(L, 'artExp', [['', '— choose an art design —'], ...arts.map(a => [a.experiment_id, `${a.name}${a.approval_status ? ' (' + a.approval_status + ')' : ''}`])], {'data-testid': 'l-art'}),
      arts.length ? 'The lights are placed on this design’s set layout. The lighting plan never changes it.' : null),
    !arts.length && L.sceneId ? el('p', {class: 'hint', 'data-empty': 'arts', 'data-testid': 'no-arts'}, 'This scene has no art design yet. Open the Art Lab, press “Draft the treatment”, then come back and press “Refresh the list”.') : null,
    row('Director’s plan', sel(L, 'planExp', [['', '— none (no shots or cameras) —'], ...R.plans.filter(p => p.scene_id === L.sceneId && p.run_id).map(p => [p.experiment_id, `${p.name} (${p.approach || 'plan'})`])], {'data-testid': 'l-plan'}), 'The plan supplies the actors’ blocking, the shots and the cameras.'),
    row('Starting point', el('div', {class: 'cards'}, ...R.presets.map(p => el('label', {class: 'craftcard' + (!L.setupExp && L.preset === p.id ? ' selected' : ''), 'data-testid': `preset-${p.id}`},
      el('input', {type: 'radio', name: 'lpreset', value: p.id, checked: !L.setupExp && L.preset === p.id, 'aria-label': p.name, onchange: () => { L.preset = p.id; L.setupExp = ''; if (!L.planName.trim() || R.presets.some(q => q.name === L.planName)) L.planName = p.id === 'blank' ? '' : p.name; persist(); render(); }}),
      el('span', {class: 'cname'}, p.name), el('span', {class: 'cdesc'}, p.summary))),
      ...setups.map(s => el('label', {class: 'craftcard' + (L.setupExp === s.experiment_id ? ' selected' : ''), 'data-testid': `setup-${s.setup_id}`},
        el('input', {type: 'radio', name: 'lpreset', value: s.experiment_id, checked: L.setupExp === s.experiment_id, 'aria-label': `Saved setup ${s.name}`, onchange: () => { L.setupExp = s.experiment_id; if (!L.planName.trim()) L.planName = s.name; persist(); render(); }}),
        el('span', {class: 'cname'}, `Saved setup: ${s.name}`), el('span', {class: 'cdesc'}, `${s.lights} lights from scene ${s.from_scene_id || 'earlier work'}. ${s.summary || ''}`)))),
      setups.length ? 'Saved setups come from earlier plans. Lights tied to a set piece this art design does not have are unlinked and noted.' : null),
    row('Lighting plan name', bind(L, 'planName', {maxlength: '120', placeholder: 'For example: Warm, naturalistic, intimate', 'data-testid': 'l-name'})),
    el('div', {class: 'buttons'}, btn('Draft the lighting plan', draft, {class: 'primary', 'data-testid': 'l-draft', disabled: busy()}), btn('Refresh the list', async () => { await loadProjects(); await loadOverview(); defaults(); render(); }, {'data-testid': 'l-refresh'})),
    ...feedback('draft'));
  const existing = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'open-form'}, el('h2', {}, 'Or open a saved lighting plan'),
    items.length ? el('table', {class: 'table'}, el('thead', {}, el('tr', {}, ...['Lighting plan', 'Lit for', 'Status', 'Checks', ''].map(h => el('th', {}, h)))),
      el('tbody', {}, ...[...items].reverse().map(t => el('tr', {'data-testid': `tr-${t.experiment_id}`}, el('td', {}, t.name), el('td', {}, t.art_treatment_name || '—'), el('td', {}, t.approval_status ? badge(t.approval_status) : '—', t.stale ? badge('out of date') : null),
        el('td', {}, t.attention != null ? `${t.attention} need attention, ${t.notes} notes` : '—'), el('td', {}, btn('Open', () => openPlan(t.experiment_id), {'data-testid': `open-${t.experiment_id}`, disabled: busy()})))))) :
      el('p', {class: 'hint', 'data-empty': 'plans', 'data-testid': 'no-plans'}, 'No lighting plans saved for this project yet. Choose a starting point above and press “Draft the lighting plan”.'));
  return el('div', {}, started, existing);
}

// ---- step 2: conditions -------------------------------------------------------------------------------------------------------------------------------------------
const TIMES = [['dawn', 'Dawn'], ['day', 'Day'], ['golden_hour', 'Golden hour'], ['dusk', 'Dusk'], ['night', 'Night']];
const WEATHER = [['unspecified', 'Not stated'], ['clear', 'Clear'], ['overcast', 'Overcast'], ['rain', 'Rain'], ['fog', 'Fog'], ['snow', 'Snow']];
function step2() {
  const d = L.doc, c = d.conditions, env = (R.artDoc.location || {}).environment || {};
  const mood = el('input', {value: (c.mood_words || []).join(', '), 'data-testid': 'c-mood', placeholder: 'For example: intimate, sheltered', oninput: ev => { c.mood_words = ev.target.value.split(',').map(x => x.trim()).filter(Boolean); touch(); }});
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'conditions-form'}, el('h2', {}, `${d.plan.name}: the light of the scene`),
    scene() ? el('p', {class: 'hint'}, `The script heading reads: ${scene().slugline}`) : null,
    el('p', {class: 'hint'}, `The art design “${d.source.art.treatment_name}” says: time of day “${env.time_of_day || 'not stated'}”, weather “${env.weather || 'not stated'}”.`),
    row('Plan name', bind(d.plan, 'name', {maxlength: '120', 'data-testid': 'c-name'})),
    row('Time of day', sel(c, 'time_of_day', TIMES, {'data-testid': 'c-time'}, {render: true})),
    row('Weather', sel(c, 'weather', WEATHER, {'data-testid': 'c-weather'})),
    row('Mood', mood, 'Separate with commas.'),
    row('What the light is for in the story', bind(c, 'narrative_purpose', {rows: '3', 'data-testid': 'c-purpose', placeholder: 'For example: warmth that comes from the room, so the argument is the only discomfort'}, 'textarea')),
    row('Intent of this plan', bind(d.plan, 'intent', {rows: '2', 'data-testid': 'c-intent'}, 'textarea')),
    findings(['time_of_day_mismatch', 'sun_at_night', 'natural_colour']),
    el('div', {class: 'buttons'}, btn('Check the lighting', check, {'data-testid': 'l-check', disabled: busy() || !L.base, title: !L.base ? 'Draft or open a lighting plan first.' : 'Looks for problems without saving.'})), ...feedback('check'),
    el('hr'), saveBlock());
}

// ---- step 3: lights -----------------------------------------------------------------------------------------------------------------------------------------------
const NEW_LIGHT = {
  key: {name: 'New key light', source: 'artificial', kind: 'fresnel', intensity: 0.7, color_temp_k: 3200, beam_angle_deg: 60, softness: 0.5},
  fill: {name: 'New fill light', source: 'artificial', kind: 'bounce', intensity: 0.25, color_temp_k: 3200, beam_angle_deg: 110, softness: 1},
  backlight: {name: 'New backlight', source: 'artificial', kind: 'fresnel', intensity: 0.35, color_temp_k: 3200, beam_angle_deg: 45, softness: 0.4},
  rim: {name: 'New rim light', source: 'artificial', kind: 'fresnel', intensity: 0.3, color_temp_k: 5600, beam_angle_deg: 35, softness: 0.3},
  practical: {name: 'New practical light', source: 'artificial', kind: 'practical_lamp', intensity: 0.4, color_temp_k: 2700, beam_angle_deg: 110, softness: 0.9},
  ambient: {name: 'New ambient level', source: 'artificial', kind: 'ambient', intensity: 0.1, color_temp_k: 4000, beam_angle_deg: 180, softness: 1},
  motivated: {name: 'New motivated light', source: 'natural', kind: 'street', intensity: 0.4, color_temp_k: 4500, beam_angle_deg: 60, softness: 0.5},
};
function newLight(role) {
  const t = NEW_LIGHT[role], ids = L.doc.lights.map(l => l.id), positional = role !== 'ambient';
  return {id: nextId(`L-${role.toUpperCase()}-`, ids), role, ...t, x: 0.5, y: 0.9, height_m: 2.0, rotation_deg: 180, tilt_deg: -20, falloff: {mode: positional ? 'inverse_square' : 'none', range_m: 8}, enabled: true, positional,
    motivated_by: '', practical_object_id: '', narrative_purpose: '', notes: '', status: 'proposed'};
}
function inspector(l) {
  const objs = [['', '— none —'], ...R.artDoc.layout.objects.map(o => [o.id, o.name])];
  const n = (k, label, p = {}, hint) => row(label, numBind(l, k, {'data-testid': `lf-${p.id || k}`, ...p.props}, p.after), hint);
  const pos = l.positional !== false;
  return el('div', {class: 'inspector', 'data-testid': 'light-inspector'}, el('h3', {}, `${l.name} (${l.id})`),
    row('Name', bind(l, 'name', {maxlength: '120', 'data-testid': 'lf-name'})),
    row('Role', sel(l, 'role', Object.entries(ROLE_LABEL), {'data-testid': 'lf-role'}, {render: true})),
    row('Source', sel(l, 'source', [['artificial', 'Artificial (a lamp or lighting unit)'], ['natural', 'Natural (sun, moon, street, sky)']], {'data-testid': 'lf-source'})),
    row('Kind', bind(l, 'kind', {maxlength: '40', placeholder: 'For example: softbox, street, practical_lamp', 'data-testid': 'lf-kind'})),
    row('Switched on', el('input', {type: 'checkbox', checked: l.enabled, 'data-testid': 'lf-enabled', onchange: ev => { l.enabled = ev.target.checked; touch(); render(); }})),
    pos ? el('div', {}, n('x', 'Across the stage (0 left, 1 right)', {props: {step: '0.01', min: '-0.5', max: '1.5'}}), n('y', 'Back to front (0 back wall, 1 audience)', {props: {step: '0.01', min: '-0.5', max: '1.5'}}),
      n('height_m', 'Height in metres', {id: 'height', props: {step: '0.1', min: '0', max: '12'}}), n('rotation_deg', 'Points toward (0 audience, 90 right, 180 back wall, 270 left)', {id: 'rot', props: {step: '1', min: '0', max: '360'}}),
      n('tilt_deg', 'Tilt in degrees (negative aims down)', {id: 'tilt', props: {step: '1', min: '-90', max: '90'}})) : null,
    n('intensity', 'Intensity (0 off, 1 full)', {props: {step: '0.05', min: '0', max: '1'}}),
    n('color_temp_k', 'Colour temperature in Kelvin', {id: 'kelvin', props: {step: '50', min: '1000', max: '20000'}}),
    pos ? el('div', {}, n('beam_angle_deg', 'Beam angle in degrees', {id: 'beam', props: {step: '1', min: '5', max: '360'}}), n('softness', 'Softness of shadow edges (0 hard, 1 soft)', {id: 'soft', props: {step: '0.05', min: '0', max: '1'}}),
      row('Falloff', sel(l.falloff, 'mode', [['inverse_square', 'Fades like real light (inverse square)'], ['linear', 'Fades evenly to zero at its range'], ['none', 'Does not fade']], {'data-testid': 'lf-fall-mode'}, {render: true})),
      l.falloff.mode !== 'none' ? row('Falloff range in metres', numBind(l.falloff, 'range_m', {'data-testid': 'lf-fall-range', step: '0.5', min: '0.5', max: '60'})) : null,
      row('Seems to come from', sel(l, 'motivated_by', objs, {'data-testid': 'lf-motiv'}), 'A door, window or lamp in the art design. The checks warn if it moves away or is removed.'),
      row('Sits on the set piece', sel(l, 'practical_object_id', objs, {'data-testid': 'lf-pract'}), 'For a lamp you can see in the room.')) : null,
    row('What this light is for', bind(l, 'narrative_purpose', {maxlength: '300', 'data-testid': 'lf-purpose'})),
    row('Status', sel(l, 'status', [['proposed', 'Proposed'], ['approved', 'Approved'], ['needs_review', 'Needs review']], {'data-testid': 'lf-status'})),
    el('div', {class: 'buttons'}, guarded('Remove this light', 'rm-light', () => { L.doc.lights = L.doc.lights.filter(x => x !== l); L.doc.adjustments.forEach(a => { a.changes = a.changes.filter(c => c.light_id !== l.id); }); L.sel.light = (L.doc.lights[0] || {}).id || null; touch(); render(); }, {'data-testid': 'rm-light'})));
}
function step3() {
  const d = L.doc, beats = (scene() || {}).beats || [], cur = d.lights.find(l => l.id === L.sel.light) || null, shots = ((R.planArt || {}).shots || []);
  const svg = planSvg(d.lights, {editable: true, selected: L.sel.light, beat: L.sel.beat, cams: L.show.cams, zones: L.show.zones, shadows: L.show.shadows, onSelect: id => { L.sel.light = id; persist(); },
    label: 'Lighting plan on the set layout. Drag a light to move it, drag the small circle at the end of its arrow to turn it, or select it and press the arrow keys.', testid: 'light-svg'});
  const chk = (key, label, tid) => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: L.show[key], 'data-testid': tid, onchange: ev => { L.show[key] = ev.target.checked; persist(); render(); }}), ` ${label}`);
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'lights-form'}, el('h2', {}, `${d.plan.name}: the lights`),
    R.planArt ? row('Show the actors for the beat', sel(L.sel, 'beat', beats.map(b => [b.id, b.title]), {'data-testid': 'l-beat'}, {render: true}), 'Circles are the actors from the director’s blocking; triangles are the cameras for that beat; the dashed line is the 180° line.') :
      el('p', {class: 'hint'}, 'This plan has no director’s plan, so no actors or cameras are shown. Start a new plan with a director’s plan chosen to see them.'),
    el('div', {class: 'chips'}, chk('zones', 'show the glow (approximate lit area)', 'show-zones'), chk('shadows', 'show shadow directions', 'show-shadows'), chk('cams', 'show camera positions', 'show-cams')),
    el('div', {class: 'twocol'}, el('div', {}, svg, el('p', {class: 'hint'}, 'The glow and the dark arrows are a quick preview from the light’s direction, beam, softness and falloff. They are not a simulation of real light; the checks give the numbers.')),
      el('div', {}, el('div', {class: 'chips', 'data-testid': 'light-chips'}, ...d.lights.map(l => el('button', {type: 'button', class: 'chip lightchip' + (l.id === L.sel.light ? ' sel' : ''), 'data-testid': `lt-${l.id}`, 'aria-pressed': String(l.id === L.sel.light), onclick: () => { L.sel.light = l.id; persist(); render(); }}, `${l.id}${l.enabled ? '' : ' (off)'}`))),
        !d.lights.length ? el('p', {class: 'hint', 'data-empty': 'lights', 'data-testid': 'no-lights'}, 'No lights yet. Choose a role below and press “Add a light”.') : null,
        row('New light', sel(L, 'newRole', Object.entries(ROLE_LABEL), {'data-testid': 'new-light-role'}), 'A new light starts at the front of the stage, pointing at the back wall.'),
        el('div', {class: 'buttons'}, btn('Add a light', () => { const l = newLight(L.newRole); d.lights.push(l); L.sel.light = l.id; touch(); render(); }, {'data-testid': 'add-light'})),
        cur ? inspector(cur) : null)),
    findings(['light_inside_set', 'practical_moved', 'unknown_object', 'motivation_far', 'light_lights_nothing', 'no_lights', 'no_main_light']),
    el('div', {class: 'buttons'}, btn('Check the lighting', check, {'data-testid': 'l-check', disabled: busy() || !L.base})), ...feedback('check'), el('hr'), saveBlock());
}

// ---- step 4: shots -------------------------------------------------------------------------------------------------------------------------------------------------------
const CHANGE_FIELDS = [['intensity', 'Intensity', {step: '0.05', min: '0', max: '1'}], ['color_temp_k', 'Kelvin', {step: '50', min: '1000', max: '20000'}], ['softness', 'Softness', {step: '0.05', min: '0', max: '1'}], ['height_m', 'Height (m)', {step: '0.1', min: '0', max: '12'}],
  ['x', 'Across', {step: '0.01'}], ['y', 'Back to front', {step: '0.01'}], ['rotation_deg', 'Turn (degrees)', {step: '1', min: '0', max: '360'}]];
function adjOf(shotId, create) {
  let a = L.doc.adjustments.find(x => x.shot_id === shotId);
  if (!a && create) { a = {id: `ADJ-${shotName(shotId)}`, shot_id: shotId, reason: '', changes: [], added_lights: [], status: 'proposed', accepted_findings: []}; L.doc.adjustments.push(a); }
  return a;
}
function tidyAdj(a) { if (a && !a.changes.length && !a.added_lights.length && !(a.accepted_findings || []).length) L.doc.adjustments = L.doc.adjustments.filter(x => x !== a); }
function setChange(shotId, lightId, field, value, base) {
  const a = adjOf(shotId, true); let ch = a.changes.find(c => c.light_id === lightId);
  if (!ch) { ch = {light_id: lightId}; a.changes.push(ch); }
  if (value === base) delete ch[field]; else ch[field] = value;
  if (Object.keys(ch).length === 1) a.changes = a.changes.filter(c => c !== ch);
  tidyAdj(a); touch();
}
function step4() {
  const d = L.doc, shots = ((R.planArt || {}).shots || []).filter(s => s.status !== 'rejected');
  if (!shots.length) return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'shots-form'}, el('h2', {}, 'Shot adjustments'),
    el('p', {class: 'hint', 'data-empty': 'shots', 'data-testid': 'no-shots'}, 'This plan has no director’s plan, so there are no shots to adjust. Go back to step 1, choose a director’s plan, and press “Draft the lighting plan”.'), saveBlock());
  const shot = shots.find(s => s.shot_id === L.sel.shot) || shots[0]; L.sel.shot = shot.shot_id;
  const {lights, adj} = resolveShot(d, shot.shot_id), pv = shot.previz || {}, adjusted = d.adjustments.map(a => a.shot_id);
  const svg = planSvg(lights, {editable: false, selected: null, beat: shot.beat_id, cams: true, shotIds: [shot.shot_id], zones: true, shadows: true, camera: pv, label: `Lighting for shot ${shot.shot_id}`, testid: 'shot-svg'});
  const rows = [...d.lights.map(l => ({l, extra: false})), ...(adj ? adj.added_lights.map(l => ({l, extra: true})) : [])].map(({l, extra}) => {
    const eff = lights.find(x => x.id === l.id) || l, ch = adj && adj.changes.find(c => c.light_id === l.id);
    return el('tr', {'data-testid': `shrow-${l.id}`, class: ch || extra ? 'diffrow' : ''}, el('td', {}, el('strong', {}, l.id), el('div', {class: 'hint'}, extra ? 'only this shot' : (ch ? 'changed here' : 'scene setup'))),
      el('td', {}, el('input', {type: 'checkbox', checked: eff.enabled, 'aria-label': `${l.id} is on for this shot`, 'data-testid': `sh-${l.id}-enabled`, onchange: ev => { if (extra) l.enabled = ev.target.checked; else setChange(shot.shot_id, l.id, 'enabled', ev.target.checked, l.enabled); touch(); render(); }})),
      ...CHANGE_FIELDS.map(([f, label, props]) => el('td', {}, el('input', {type: 'number', value: eff[f], 'aria-label': `${l.id} ${label} for this shot`, 'data-testid': `sh-${l.id}-${f}`, ...props,
        oninput: ev => {
          if (ev.target.value === '' || !Number.isFinite(Number(ev.target.value))) return;
          const v = Number(ev.target.value);
          if (extra) { l[f] = v; touch(); return; }
          const state = () => `${!!adjOf(shot.shot_id)}|${!!(adjOf(shot.shot_id) || {changes: []}).changes.find(c => c.light_id === l.id)}`, before = state();
          setChange(shot.shot_id, l.id, f, v, l[f]);
          if (state() !== before) renderKeepFocus(`sh-${l.id}-${f}`);   // the reset button and the reason field depend on this, so show them now
        }}))),
      el('td', {}, extra ? guarded('Remove', `rm-extra-${l.id}`, () => { adj.added_lights = adj.added_lights.filter(x => x !== l); tidyAdj(adj); touch(); render(); }, {'aria-label': `Remove ${l.id} from this shot`}) :
        (ch ? btn('Use the scene setup', () => { adj.changes = adj.changes.filter(c => c !== ch); tidyAdj(adj); touch(); render(); }, {'data-testid': `sh-reset-${l.id}`, 'aria-label': `Use the scene setup for ${l.id} in this shot`}) : null)));
  });
  const otherShots = shots.filter(s => s.shot_id !== shot.shot_id);
  const mine = findings(null, shot.shot_id), accept = ((R.analysis || {}).issues || []).filter(i => i.shot_id === shot.shot_id && i.severity === 'attention' && !i.accepted);
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'shots-form'}, el('h2', {}, `${d.plan.name}: lights for one shot`),
    row('Shot', sel(L.sel, 'shot', shots.map(s => [s.shot_id, `${shotName(s.shot_id)} — ${s.size}, ${s.framing || ''}, beat ${shotName(s.beat_id)}${adjusted.includes(s.shot_id) ? ' (adjusted)' : ''}`]), {'data-testid': 'shot-select'}, {render: true})),
    el('p', {class: 'hint', 'data-testid': 'shot-camera'}, `Camera: ${shot.lens_mm} mm, ${shot.angle || 'eye'} angle, camera side ${shot.camera_side}${pv.camera_position ? `, at ${pv.camera_position.x.toFixed(2)}, ${pv.camera_position.y.toFixed(2)}, ${pv.camera_position.height_m} m high` : ''}. The shaded wedge is what the lens sees.`),
    svg,
    el('h3', {}, 'Lights for this shot'),
    el('p', {class: 'hint'}, 'Each row starts from the scene setup. Change a number to make it different for this shot only; a number that matches the scene setup is not stored as a change.'),
    el('div', {class: 'tablewrap'}, el('table', {class: 'table shottable', 'data-testid': 'shot-table'}, el('thead', {}, el('tr', {}, el('th', {}, 'Light'), el('th', {}, 'On'), ...CHANGE_FIELDS.map(c => el('th', {}, c[1])), el('th', {}, ''))), el('tbody', {}, ...rows))),
    el('div', {class: 'buttons'}, btn('Add a light for this shot only', () => { const a = adjOf(shot.shot_id, true); const l = newLight('fill'); l.id = nextId(`L-S${shotName(shot.shot_id)}-`, [...d.lights.map(x => x.id), ...a.added_lights.map(x => x.id)]); a.added_lights.push(l); touch(); render(); }, {'data-testid': 'add-shot-light'})),
    row('Why this shot is different', bind(adj || {reason: ''}, 'reason', {maxlength: '300', placeholder: 'For example: the key goes softer for the close-up', 'data-testid': 'sh-reason', disabled: !adj}), adj ? 'A stated reason turns a continuity warning into a note.' : 'Change a setting above first; then you can say why.'),
    accept.length ? el('div', {class: 'override'}, el('h3', {}, 'Warnings you can accept for this shot'), el('p', {class: 'hint'}, 'Accepting is your choice, recorded in the plan. The warning stays visible as a note.'),
      ...accept.map(i => btn(`Accept “${i.rule.replace(/_/g, ' ')}” for this shot`, () => { const a = adjOf(shot.shot_id, true); a.accepted_findings = [...new Set([...(a.accepted_findings || []), i.rule])]; touch(); render(); }, {'data-testid': `accept-${i.rule}`}))) : null,
    otherShots.length ? el('div', {}, el('h3', {}, 'Use these changes in other shots'), adj && (adj.changes.length || adj.added_lights.length) ? null : el('p', {class: 'hint', 'data-empty': 'copy'}, 'Change a setting above first, then you can copy the changes to other shots.'),
      el('div', {class: 'chips'}, ...otherShots.map(s => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: L.copyTo.includes(s.shot_id), 'data-testid': `copy-${shotName(s.shot_id)}`, 'aria-label': `Copy to shot ${shotName(s.shot_id)}`, onchange: ev => { L.copyTo = ev.target.checked ? [...L.copyTo, s.shot_id] : L.copyTo.filter(x => x !== s.shot_id); persist(); renderKeepFocus(`copy-${shotName(s.shot_id)}`); }}), ` ${shotName(s.shot_id)}`))),
      el('div', {class: 'buttons'}, btn('Copy the changes to the chosen shots', () => {
        for (const sid of L.copyTo) { const t = adjOf(sid, true); t.changes = clone(adj.changes); t.added_lights = clone(adj.added_lights).map(x => ({...x, id: x.id.replace(`L-S${shotName(shot.shot_id)}-`, `L-S${shotName(sid)}-`)})); t.reason = adj.reason; }
        const n = L.copyTo.length; L.copyTo = []; touch(); R.notice.copy = `Copied this shot’s changes to ${n} shot(s). Their earlier changes were replaced; save to keep it.`; render();
      }, {'data-testid': 'copy-go', disabled: !(adj && (adj.changes.length || adj.added_lights.length)) || !L.copyTo.length, title: !(adj && (adj.changes.length || adj.added_lights.length)) ? 'Change a setting for this shot first.' : (!L.copyTo.length ? 'Choose at least one shot to copy to.' : '')}), ...feedback('copy'))) : null,
    mine, el('div', {class: 'buttons'}, btn('Check the lighting', check, {'data-testid': 'l-check', disabled: busy() || !L.base})), ...feedback('check'), el('hr'), saveBlock());
}
function resolveShot(doc, shotId) {
  const lights = clone(doc.lights), adj = (doc.adjustments || []).find(a => a.shot_id === shotId);
  if (adj) {
    const extra = clone(adj.added_lights || []), by = Object.fromEntries([...lights, ...extra].map(l => [l.id, l]));
    for (const ch of adj.changes) for (const [k, v] of Object.entries(ch)) if (k !== 'light_id' && by[ch.light_id]) by[ch.light_id][k] = v;
    lights.push(...extra);
  }
  return {lights, adj};
}

// ---- step 5: checks -------------------------------------------------------------------------------------------------------------------------------------------------------
function step5() {
  const an = R.analysis || {issues: [], shots: [], readiness: {attention: 0, notes: 0}, metrics: {}}, att = an.issues.filter(i => i.severity === 'attention'), notes = an.issues.filter(i => i.severity === 'note');
  const m = an.metrics || {}, nm = names();
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'checks-form'}, el('h2', {}, `${L.doc.plan.name}: what the checks say`),
    el('div', {class: 'metrics'}, el('div', {class: 'metric'}, el('strong', {'data-testid': 'ck-attention'}, String(att.length)), el('span', {}, 'need attention (advice)')), el('div', {class: 'metric'}, el('strong', {}, String(notes.length)), el('span', {}, 'notes')),
      el('div', {class: 'metric'}, el('strong', {}, m.mean_kelvin ? `${m.mean_kelvin} K` : '—'), el('span', {}, 'average colour')), el('div', {class: 'metric'}, el('strong', {}, m.key_fill_ratio ? `${m.key_fill_ratio}:1` : '—'), el('span', {}, 'key to fill ratio'))),
    (att.length || notes.length) ? K.findingsList([...att, ...notes]) : el('p', {class: 'notice ok', 'data-testid': 'no-findings'}, 'No problems found. The lights, the set, the shots and the actors’ movement all pass the checks.'),
    el('div', {class: 'buttons'}, btn('Check the lighting again', check, {'data-testid': 'l-check', disabled: busy() || !L.base})), ...feedback('check'),
    el('p', {class: 'hint'}, an.model_note || 'Levels are relative planning estimates, not measured light.'),
    el('h3', {}, 'Shot by shot'),
    an.shots && an.shots.length ? el('div', {class: 'tablewrap'}, el('table', {class: 'table', 'data-testid': 'shot-summary'}, el('thead', {}, el('tr', {}, ...['Shot', 'Key light', 'Key colour', 'Key on camera', 'Level on the people (start → end)', 'Key to fill'].map(h => el('th', {}, h)))),
      el('tbody', {}, ...an.shots.map(r => el('tr', {'data-testid': `ss-${shotName(r.shot_id)}`, class: r.adjusted ? 'diffrow' : ''}, el('td', {}, `${shotName(r.shot_id)} (${r.size})${r.adjusted ? ' · adjusted' : ''}`), el('td', {}, r.key_id || '—'), el('td', {}, r.key_kelvin ? `${r.key_kelvin} K` : '—'), el('td', {}, r.key_side || '—'),
        el('td', {}, r.subjects.map(s => `${nm[s.character_id] || s.character_id} ${s.level_start} → ${s.level_end}`).join('; ') || '—'), el('td', {}, r.subjects.map(s => s.key_fill_ratio ? `${s.key_fill_ratio}:1` : '—').join(', ') || '—')))))) :
      el('p', {class: 'hint', 'data-empty': 'shotsum'}, 'There are no shots to summarise. Start a new plan with a director’s plan chosen, then press “Draft the lighting plan”.'),
    el('p', {class: 'hint'}, 'The level is the approximate light on each person’s face (0 dark, 1 full). A big drop between start and end means they walk out of the light.')));
}

// ---- step 6: comparison -------------------------------------------------------------------------------------------------------------------------------------------------------
async function compare() {
  if (!L.cmp) return fail('cmp', 'Choose a second lighting plan to compare with, then press Compare.');
  await withBusy('cmp', 'Comparing the lighting plans', async () => {
    R.cmpResult = await call(`/api/light/compare?run_a=${L.base.runId}&run_b=${L.cmp}`);
  });
}
function step6() {
  const cur = `${L.doc.plan.id}|${L.doc.source.art.treatment_id}`;
  const latest = new Map();
  for (const t of ((R.overview && R.overview.plans) || [])) if (t.scene_id === L.doc.scene_id && t.run_id && `${t.plan_id}|${t.art_treatment_id}` !== cur) latest.set(`${t.plan_id}|${t.art_treatment_id}`, t);
  const uniq = [...latest.values()];
  const r = R.cmpResult;
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'compare-form'}, el('h2', {}, `Compare “${L.doc.plan.name}” with another plan`),
    !uniq.length ? el('p', {class: 'hint', 'data-empty': 'compare', 'data-testid': 'no-compare'}, 'There is no other saved lighting plan for this scene yet. Go back to step 1, choose another starting point, and press “Draft the lighting plan”.') : null,
    uniq.length ? row('Compare with', sel(L, 'cmp', [['', '— choose a lighting plan —'], ...uniq.map(t => [t.run_id, `${t.name} (lit for ${t.art_treatment_name})`])], {'data-testid': 'l-cmp-pick'})) : null,
    el('div', {class: 'buttons'}, btn('Compare', compare, {class: 'primary', 'data-testid': 'l-cmp-go', disabled: !uniq.length || busy(), title: !uniq.length ? 'Draft a second lighting plan first.' : ''})),
    ...feedback('cmp'), r ? compareView(r) : null));
}
function compareView(r) {
  const side = (label, p, key, readings, docx) => el('div', {class: 'cmpcol', 'data-testid': `cmp-${label}`}, el('h3', {}, p.plan.name), el('p', {class: 'hint'}, `Lit for the art design “${p.art_treatment}”.`), el('p', {class: 'hint'}, p.plan.intent || ''),
    docx ? K.layoutSvg(docx.art, {editable: false, plan: R.planArt, names: names(), beat: L.sel.beat, cams: false, label: `Lights of ${p.plan.name}`, testid: `cmp-layout-${label}`, overlay: (svg, mk, d) => overlayFor(docx.lights, {zones: true, shadows: false, beat: null})(svg, mk, d)}) : null,
    p.key ? el('p', {class: 'hint'}, `Key light: ${p.key.name}, ${p.key.color_temp_k} K, intensity ${p.key.intensity}, beam ${p.key.beam_angle_deg}°, softness ${p.key.softness}.`) : null,
    el('ul', {class: 'readings'}, ...readings.map(x => el('li', {}, x.text, el('span', {class: 'hint'}, ` (because: ${x.because})`)))));
  return el('div', {'data-testid': 'cmp-result'}, el('div', {class: 'twocol'}, side('a', r.a, 'a', r.readings.a, {art: r.docs.a.art, lights: r.docs.a.lights}), side('b', r.b, 'b', r.readings.b, {art: r.docs.b.art, lights: r.docs.b.lights})),
    el('h3', {}, 'Settings and measures'), el('table', {class: 'table'}, el('thead', {}, el('tr', {}, el('th', {}, 'Measure'), el('th', {}, r.a.plan.name), el('th', {}, r.b.plan.name))),
      el('tbody', {}, ...r.metrics.map(m => el('tr', {class: m.differs ? 'diffrow' : ''}, el('td', {}, m.metric), el('td', {}, m.a == null ? '—' : String(m.a)), el('td', {}, m.b == null ? '—' : String(m.b)))))),
    el('h3', {}, 'What is different'), el('ul', {}, el('li', {}, `Only in ${r.a.plan.name}: ${r.differences.lights_only_a.join(', ') || 'nothing'}`), el('li', {}, `Only in ${r.b.plan.name}: ${r.differences.lights_only_b.join(', ') || 'nothing'}`), el('li', {}, `Moved: ${r.differences.moved.join(', ') || 'nothing'}`)),
    el('p', {class: 'hint'}, 'These statements come from fixed rules over the measures above. They describe what the lighting is likely to suggest; they do not judge which one is better. ' + (r.model_note || '')));
}

// ---- step 7: review -------------------------------------------------------------------------------------------------------------------------------------------------------------
async function decide(kind) {
  const reviewer = (L.reviewer || '').trim(), note = (L.rnote || '').trim();
  if (kind !== 'submit-review' && !reviewer) return fail('decide', 'Type your name in “Your name”, then press the button again. A decision needs a name.');
  if (kind === 'reject' && !note) return fail('decide', 'Write a short note saying why you are rejecting this plan, then press Reject again.');
  await withBusy('decide', kind === 'submit-review' ? 'Submitting' : (kind === 'approve' ? 'Approving' : 'Rejecting'), async () => {
    await call(`/api/runs/${L.base.runId}/${kind}`, 'POST', {reviewer, note}); await loadRun(); await loadOverview();
    R.notice.decide = kind === 'submit-review' ? 'Submitted for review. Now approve or reject it.' : (kind === 'approve' ? 'Approved. You can export it in the next step.' : 'Rejected. Your note is recorded; change the plan and save a new version.');
  });
}
function step7() {
  const d = L.doc, an = R.analysis || {issues: [], readiness: {attention: 0, notes: 0}}, imp = R.impact, saved = dirty() === 'saved', status = R.runInfo ? R.runInfo.approval_status : null;
  const att = an.issues.filter(i => i.severity === 'attention'), notes = an.issues.filter(i => i.severity === 'note');
  const pend = [...d.lights.filter(l => l.status !== 'approved').map(l => ({id: l.id, name: `${l.name} (${l.id})`, ref: l})), ...d.adjustments.filter(a => a.status !== 'approved').map(a => ({id: a.id, name: `Adjustment for shot ${shotName(a.shot_id)}`, ref: a}))];
  const dec = (label, testid, kind, ok, why, cls = '') => el('span', {class: 'act'}, el('button', {type: 'button', class: cls, 'data-testid': testid, disabled: !ok || busy(), title: ok ? null : why, onclick: () => decide(kind)}, label), ok ? null : el('span', {class: 'why'}, why));
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'review-form'}, el('h2', {}, `Review “${d.plan.name}”`),
    el('div', {class: 'metrics'}, el('div', {class: 'metric'}, el('strong', {'data-testid': 'rv-attention'}, String(att.length)), el('span', {}, 'need attention (advice)')), el('div', {class: 'metric'}, el('strong', {}, String(notes.length)), el('span', {}, 'notes')),
      el('div', {class: 'metric'}, el('strong', {}, String(pend.length)), el('span', {}, 'items not yet approved')), el('div', {class: 'metric'}, el('strong', {}, String(d.lights.length)), el('span', {}, 'lights'))),
    imp && imp.stale ? el('div', {class: 'warnpanel panel', 'data-testid': 'impact'}, el('h3', {}, 'The script, the art design or the director’s plan changed after this lighting plan was made'), el('p', {}, imp.summary),
      imp.affected_lights.length ? el('p', {class: 'hint'}, `Lights to re-check: ${imp.affected_lights.join(', ')}`) : null, imp.affected_adjustments.length ? el('p', {class: 'hint'}, `Shot adjustments to re-check: ${imp.affected_adjustments.join(', ')}`) : null,
      el('p', {class: 'hint'}, 'To recover, rebase: it copies this plan onto the newest script, art design and director’s plan, sends only the items listed here back for review, and keeps everything else as it was. This version stays as it is.'),
      el('div', {class: 'buttons'}, btn('Rebase onto the latest script, art design and plan', rebase, {class: 'primary', 'data-testid': 'l-rebase', disabled: busy() || !saved, title: saved ? '' : 'Save your changes first.'}), !saved ? el('span', {class: 'why'}, 'Save your changes first.') : null)) : null,
    ...feedback('rebase'),
    el('h3', {}, 'What the checks found (advice only)'), (att.length || notes.length) ? K.findingsList([...att, ...notes]) : el('p', {class: 'notice ok', 'data-testid': 'no-findings'}, 'No problems found. The lights, the set, the shots and the actors’ movement all pass the checks.'),
    el('div', {class: 'buttons'}, btn('Check the lighting again', check, {'data-testid': 'l-check', disabled: busy()})), ...feedback('check'),
    el('h3', {}, 'Items waiting for your decision'),
    pend.length ? el('ul', {class: 'audit'}, ...pend.map(x => el('li', {class: 'advice', 'data-testid': `pend-${x.id}`}, el('span', {class: 'mark'}, '!'), el('span', {}, `${x.name} is ${x.ref.status.replace('_', ' ')}.`)))) : el('p', {class: 'hint', 'data-empty': 'pending'}, 'Every light and shot adjustment is approved. Nothing is waiting; press Save if you changed anything.'),
    el('div', {class: 'buttons'}, btn(`Approve all ${pend.length} item(s)`, () => { for (const x of pend) x.ref.status = 'approved'; touch(); render(); }, {'data-testid': 'approve-items', disabled: !pend.length, title: pend.length ? '' : 'There is nothing waiting for approval.'})),
    el('hr'), saveBlock()),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'decision-form'}, el('h2', {}, 'Approve or reject this lighting plan'),
      el('p', {}, el('span', {}, 'Status: '), status ? badge(status) : el('span', {class: 'hint'}, saved ? 'checking…' : 'not saved')),
      !saved ? el('p', {class: 'why', 'data-testid': 'decision-why'}, 'Save your changes first. Approval applies to a saved version, never to unsaved edits.') : null,
      att.length ? el('p', {class: 'hint'}, `${att.length} finding(s) still need attention. You can approve anyway. Exporting then asks you to confirm, and the choice is recorded.`) : null,
      row('Your name', bind(L, 'reviewer', {maxlength: '80', 'data-testid': 'l-reviewer', placeholder: 'Needed to approve or reject'})), row('Note', bind(L, 'rnote', {maxlength: '2000', 'data-testid': 'l-rnote', placeholder: 'Needed when rejecting'})),
      el('div', {class: 'buttons'}, dec('Submit for review', 'l-submit', 'submit-review', saved && ['draft', 'rejected'].includes(status), !saved ? 'Save your changes first.' : 'This version is already submitted or decided.'),
        dec('Approve this lighting plan', 'l-approve', 'approve', saved && status === 'review', 'Submit for review first.', 'primary'), dec('Reject this lighting plan', 'l-reject', 'reject', saved && status === 'review', 'Submit for review first.')),
      ...feedback('decide')));
}

// ---- step 8: export ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
const EXPORTS = [
  {kind: 'lighting-plan-json', label: 'Lighting plan (JSON)', desc: 'This plan as saved, with its checks.'},
  {kind: 'light-schedule-csv', label: 'Light schedule (spreadsheet)', desc: 'Every light for every shot, with its position, direction, intensity and colour, for Excel.'},
  {kind: 'lighting-instructions', label: 'Lighting instructions', desc: 'For each shot: the camera, the lights that are on with positions in stage coordinates and metres, and which side the key light comes from. For camera and previz work.'},
  {kind: 'lighting-manifest', label: 'Lighting manifest', desc: 'The approved plan in one file, with sections prepared for Cinematography, previz and Dreambox Scene Maker. The art design is referenced, not copied.', approved: true},
];
const OVERRIDE_TEXT = {acknowledge_stale: 'The script, art design or plan changed after this lighting plan was made.', allow_open_findings: 'Some checks still need attention.', allow_pending: 'Some items are waiting for review.', allow_unapproved_art: 'The art design this plan is lit for is not approved yet.'};
async function doExport(ex, overrides) {
  await withBusy(`x-${ex.kind}`, `Exporting ${ex.label}`, async () => {
    const q = overrides.map(o => `override=${o}`).join('&');
    const r = await fetch(`/api/runs/${L.base.runId}/exports/${ex.kind}${q ? '?' + q : ''}`, {method: 'POST'});
    if (!r.ok) { const dd = await r.json().catch(() => ({})); const msg = typeof dd.detail === 'string' ? dd.detail : (dd.detail && dd.detail.message) || `HTTP ${r.status}`; R.needs[ex.kind] = msg; throw new Error(msg); }
    const name = (/filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || `${ex.kind}.json`;
    const url = URL.createObjectURL(new Blob([await r.text()], {type: r.headers.get('Content-Type') || 'application/json'}));
    const a = el('a', {href: url, download: name}); document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    delete R.needs[ex.kind];
    R.notice[`x-${ex.kind}`] = `Saved “${name}” to your Downloads folder.${r.headers.get('X-Craftbox-Existing') === 'true' ? ' This is the file made earlier; it is never made again.' : ''}${overrides.length ? ' Recorded in the file: you chose to export anyway (' + overrides.join(', ').replace(/_/g, ' ') + ').' : ''}`;
  });
}
async function saveSetup() {
  if (!(L.setupId || '').trim() || !(L.setupName || '').trim()) return fail('setup', 'Give the setup a short id (letters, numbers and dashes) and a name, then press the button again.');
  await withBusy('setup', 'Saving the setup', async () => {
    await call('/api/light/setups', 'POST', {plan_experiment_id: L.base.experimentId, setup_id: L.setupId.trim(), name: L.setupName.trim(), summary: (L.setupSummary || '').trim()});
    await loadOverview(); R.notice.setup = `Saved the setup “${L.setupName.trim()}” with ${L.doc.lights.length} lights. Start a plan from it in step 1, even in another scene.`;
  });
}
function step8() {
  const d = L.doc, status = R.runInfo ? R.runInfo.approval_status : null, approved = ['approved', 'exported'].includes(status), saved = dirty() === 'saved';
  const rows = EXPORTS.map(ex => {
    const need = ex.approved && !approved, msg = R.needs[ex.kind] || '', can = Object.keys(OVERRIDE_TEXT).filter(o => msg.includes(o));
    return el('div', {class: 'exrow', 'data-testid': `export-${ex.kind}`}, el('div', {}, el('strong', {}, ex.label), el('p', {class: 'hint'}, ex.desc)),
      el('div', {}, el('span', {class: 'act'}, el('button', {type: 'button', class: ex.approved ? 'primary' : '', 'data-testid': `dl-${ex.kind}`, disabled: need || busy() || !L.base, title: need ? 'Approve this lighting plan in the review step first.' : null, onclick: () => doExport(ex, [])}, 'Download'),
        need ? el('span', {class: 'why'}, 'Approve this lighting plan in the review step first.') : null),
        can.length ? el('div', {class: 'override'}, ...can.map(o => el('p', {class: 'hint'}, `${OVERRIDE_TEXT[o]} You can export anyway; your choice is written into the file.`)), btn('Export anyway (recorded)', () => doExport(ex, can), {'data-testid': `force-${ex.kind}`, disabled: busy()})) : null,
        ...feedback(`x-${ex.kind}`)));
  });
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'export-form'}, el('h2', {}, `Export “${d.plan.name}”`),
    el('p', {}, el('span', {}, 'Status: '), status ? badge(status) : el('span', {class: 'hint'}, 'unknown'), el('span', {class: 'hint'}, saved ? ' · exports use the saved version' : ' · unsaved changes are NOT included; save them first')),
    !approved ? el('p', {class: 'why', 'data-testid': 'not-approved'}, 'The manifest needs an approved lighting plan. The other files can be exported at any time.') : null, ...rows),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'setup-form'}, el('h2', {}, 'Keep these lights as a setup to reuse'),
      el('p', {class: 'hint'}, 'A saved setup is a copy of this plan’s lights. Use it as a starting point for another scene or another art design; it never changes this plan.'),
      row('Setup id', bind(L, 'setupId', {maxlength: '40', placeholder: 'For example: WARM-ROOM', 'data-testid': 'setup-id'})), row('Setup name', bind(L, 'setupName', {maxlength: '120', placeholder: 'For example: Warm room', 'data-testid': 'setup-name'})),
      row('Short description', bind(L, 'setupSummary', {maxlength: '200', 'data-testid': 'setup-summary'})),
      el('div', {class: 'buttons'}, btn('Add these lights to the setup library', saveSetup, {'data-testid': 'setup-save', disabled: busy() || !saved, title: saved ? '' : 'Save your changes first.'}), !saved ? el('span', {class: 'why'}, 'Save your changes first.') : null), ...feedback('setup')),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'finish-form'}, el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'}, btn('Start another lighting plan', () => { L.doc = null; L.base = null; L.saved = null; L.step = 1; persist(); render(); }, {'data-testid': 'l-new'}), btn('Back to the review', () => go(7), {'data-testid': 'l-back-review'}),
        btn('Open History (all experiments)', () => byId('tab-history').click(), {'data-testid': 'l-open-history'}))));
}

// ---- shell ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
const reached = () => (!L.doc ? 1 : (L.base ? 8 : 1));
function go(n) { if (n < 1 || n > 8 || n > reached()) return; L.step = n; R.errors = {}; R.notice = {}; R.armed = null; persist(); render(); window.scrollTo({top: 0}); onEnter(n); }
async function onEnter(n) {
  try { if (n >= 5 && L.base) { await loadImpact(); await loadRun(); await loadOverview(); } if (n >= 4 && L.base && !R.analysis) { await check(); } } catch (e) { /* the page still works from the typed drafts */ }
  if (L.step === n) render();
}
function navSpec() {
  const n = L.step, before = STEPS.before(n), after = STEPS.after(n);
  return {n, total: 8, back: before ? {label: `Back: ${before.title}`, onclick: () => go(n - 1)} : null,
    next: after ? {label: `Next: ${after.title}`, disabled: n === 1 ? !L.doc : false, why: n === 1 ? 'Draft a new lighting plan, or open a saved one, first.' : '', onclick: () => go(n + 1)} : null};
}
function renderKeepFocus(testid) {
  render();
  const n = document.querySelector(`#view-light [data-testid="${testid}"]`);
  if (!n) return;
  n.focus();
  try { n.setSelectionRange(n.value.length, n.value.length); } catch (e) { /* number inputs have no caret */ }
}
function renderNav() { const h = byId('light-nav'); if (h) h.replaceChildren(ui.nav(navSpec())); }
const fns = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: step7, 8: step8};
function render() {
  ui.clearTimers();
  const mount = byId('light-mount');
  if (!mount) return;
  if (L.step > 1 && !L.doc) L.step = 1;
  const n = L.step;
  mount.replaceChildren(el('div', {id: 'light-wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': 8, 'data-testid': 'light-wizard'},
    ui.stepper({defs: STEPS.list(), current: n, reached: reached(), onGo: go}), el('h1', {'data-testid': 'step-title'}, STEPS.title(n)), el('p', {class: 'intro', 'data-testid': 'step-intro'}, STEPS.intro(n)),
    fns[n](), el('div', {id: 'light-nav'})));
  renderNav();
  fillGlossary(byId('light-wizard'));
}
async function show() {
  await loadProjects();
  if (!R.presets.length) { try { R.presets = await call('/api/light/presets'); } catch (e) { R.presets = []; } }
  if (!L.projectId && R.projects[0]) L.projectId = R.projects[0].project_id;
  await loadOverview();
  if (L.projectId && !L.screenplayExp && R.sps.length) L.screenplayExp = R.sps[R.sps.length - 1].experiment_id;
  if (L.screenplayExp && !R.spArt) { try { await loadScreenplay(L.screenplayExp); } catch (e) { /* ignore */ } }
  if (!L.sceneId && R.scenes[0]) L.sceneId = R.scenes[0].id;
  defaults();
  if (!L.planName.trim()) { const p = R.presets.find(x => x.id === L.preset); if (p) L.planName = p.name; }
  render();
}
async function init() {
  restore();
  try {
    await loadProjects(); R.presets = await call('/api/light/presets'); await loadOverview();
    if (L.screenplayExp) { try { await loadScreenplay(L.screenplayExp); } catch (e) { /* the revision may be gone */ } }
    if (L.doc && L.base) {
      const run = await call(`/api/runs/${L.base.runId}`); R.analysis = run.envelope.artifact.analysis;
      const exp = await call(`/api/experiments/${L.base.experimentId}`); R.spArt = exp.input.screenplay; R.scenes = R.spArt.scenes; R.planArt = exp.input.direction_plan || null; R.artDoc = exp.input.art_direction;
      await loadImpact(); await loadRun();
    }
  } catch (e) { L.base = null; }
  if (L.step > reached()) L.step = reached();
  render();
}
// Dependent selections: choosing a project loads its revisions; choosing a revision loads its scenes, plans and art designs.
document.addEventListener('change', async ev => {
  const t = ev.target && ev.target.getAttribute && ev.target.getAttribute('data-testid');
  const v = document.getElementById('view-light');
  if (!v || v.hidden) return;
  if (t === 'l-project') { L.screenplayExp = ''; L.sceneId = ''; L.planExp = ''; L.artExp = ''; R.spArt = null; R.scenes = []; await loadOverview(); if (R.sps.length) { L.screenplayExp = R.sps[R.sps.length - 1].experiment_id; await loadScreenplay(L.screenplayExp); L.sceneId = (R.scenes[0] || {}).id || ''; } defaults(); persist(); render(); }
  if (t === 'l-sp' && L.screenplayExp) { await loadScreenplay(L.screenplayExp); L.sceneId = (R.scenes[0] || {}).id || ''; defaults(); persist(); render(); }
  if (t === 'l-scene') { defaults(); persist(); render(); }
});
return {show, init, render, L, R, GLOSS};
})();
