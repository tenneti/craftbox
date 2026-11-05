// Art Library (CB2A): project style profiles and the asset register, as a 2-step wizard. Follows guidelines/ui-standard.md.
const Library = (() => {
const {el, call} = ui;
const byId = id => document.getElementById(id);
const KEY = 'craftbox.artlib.v1';
const B = {v: 1, step: 1, projectId: '', prof: null, profBase: null, profSaved: null, profNote: '', reg: null, regBase: null, regSaved: null, regNote: '', sel: '', path: ''};
const R = {projects: [], styles: [], view: null, errors: {}, notice: {}, busy: null, armed: null, uid: 0};
const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(B)); } catch (e) { /* storage unavailable */ } };
const restore = () => { try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.v === 1) Object.assign(B, s); } catch (e) { /* ignore */ } };
const GLOSS = Art.GLOSS;   // one set of plain-words definitions for every Art screen
const STEPS = ui.steps([
  {short: 'Style profiles', title: 'keep project style profiles', intro: 'A style profile is a reusable look for the whole project: colours, textures, materials, period and your own rules, such as a word to avoid. Treatments can start from one. Saving makes a new version and keeps the earlier ones.'},
  {short: 'Assets', title: 'register picture files', intro: 'Register the picture files you use for design: upload them, say who made them and what you may do with them. The files stay on this computer and are stored once. A treatment can only be exported with assets whose rights are cleared, unless you choose otherwise.'},
]);
const TERMS = [['palette', 'treatment'], ['asset', 'manifest', 'treatment']];
const uid = p => `${p}-${++R.uid}`;
function row(label, ctl, hint) {
  const lab = el('label', {}, label);
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(ctl.tagName)) { ctl.id = ctl.id || uid('g'); lab.setAttribute('for', ctl.id); } else { lab.id = uid('gl'); ctl.setAttribute('role', 'group'); ctl.setAttribute('aria-labelledby', lab.id); }
  return el('div', {class: 'formrow'}, lab, ctl, hint ? el('span', {class: 'hint'}, hint) : null);
}
const touch = () => { persist(); afterEdit(); };
function bind(o, k, props = {}, tag = 'input', conv) { const n = el(tag, props); n.value = o[k] ?? ''; n.addEventListener('input', () => { o[k] = conv ? conv(n.value) : n.value; touch(); }); return n; }
function sel(o, k, opts, props = {}, render_) { const n = el('select', props); for (const [v, l] of opts) n.append(el('option', {value: v}, l)); n.value = o[k] ?? ''; n.addEventListener('change', () => { o[k] = n.value; touch(); if (render_) render(); }); return n; }
const btn = (label, fn, props = {}) => el('button', {type: 'button', onclick: fn, ...props}, label);
function guarded(label, key, fn, props = {}) { const armed = R.armed === key; return el('button', {type: 'button', class: armed ? 'danger' : '', onclick: () => { if (armed) { R.armed = null; fn(); } else { R.armed = key; render(); } }, ...props}, armed ? 'Click again to confirm' : label); }
const j = o => JSON.stringify(o);
const dirtyOf = (doc, saved) => (!doc ? 'none' : (!saved ? 'unsaved' : (saved === j(doc) ? 'saved' : 'changed')));
const STATE = {unsaved: 'Not saved yet. Saving makes a new version and keeps what you typed on screen.', saved: 'Saved. What you typed is still shown here.', changed: 'Changed, not saved yet. Saving makes a new version; earlier versions stay exactly as they were.'};
const swatch = c => el('span', {class: 'swatch', style: `background:${c.hex}`, role: 'img', 'aria-label': `${c.name} ${c.hex}`, title: c.hex});
const next = (prefix, ids) => { const n = ids.filter(x => x.startsWith(prefix)).map(x => parseInt(x.slice(prefix.length), 10)).filter(Number.isFinite); return prefix + String((n.length ? Math.max(...n) : 0) + 1); };
const friendly = m => `Cannot save yet: ${m.replace(/\$\./g, '').replace(/\[(\d+)\]/g, (_, n) => ` #${Number(n) + 1}`).replace(/\./g, ' › ')}. Change the field it names, then press Save again. Nothing you typed was lost.`;
const glossaryBlock = terms => el('section', {class: 'glossary', 'data-testid': 'glossary'}, el('h3', {}, 'Words used on this screen'), el('dl', {}, ...terms.flatMap(t => [el('dt', {'data-gloss': t}, t), el('dd', {}, GLOSS[t])])));
const glossary = () => null;   // glossaries are built from the words actually on screen: see fillGlossary
function fillGlossary(root) {
  if (!root) return;
  const body = [...root.querySelectorAll('h1, h2, h3, .intro, .hint, label, button, p')].filter(e => !e.closest('.glossary')).map(e => e.textContent).join(' | ').toLowerCase();
  const terms = Object.keys(GLOSS).filter(t => new RegExp('\\b' + t + 's?\\b').test(body));
  const old = root.querySelector('.glossary'); if (old) old.remove();
  if (terms.length) root.insertBefore(glossaryBlock(terms), root.querySelector('#lib-nav'));
}
function fail(key, m) { R.errors[key] = m; render(); ui.reveal(`error-${key}`); }
async function withBusy(key, what, fn) {
  delete R.errors[key]; delete R.notice[key]; R.busy = {key, what, startedAt: Date.now()}; render();
  try { await fn(); } catch (e) { R.errors[key] = key.startsWith('save') ? friendly(e.message) : e.message; } finally { R.busy = null; render(); if (R.errors[key]) ui.reveal(`error-${key}`); }
}
const busy = () => !!R.busy;
const feedback = key => [R.busy && R.busy.key === key ? ui.progress({what: R.busy.what, startedAt: R.busy.startedAt}) : null, R.errors[key] ? ui.errorBox(R.errors[key], `error-${key}`) : null,
  R.notice[key] ? el('div', {class: 'notice ok', 'data-testid': `notice-${key}`, role: 'status'}, R.notice[key]) : null];
function saveBlock(kind) {
  const doc = kind === 'prof' ? B.prof : B.reg, s = dirtyOf(doc, kind === 'prof' ? B.profSaved : B.regSaved);
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(B, kind === 'prof' ? 'profNote' : 'regNote', {maxlength: '200', 'data-testid': `${kind}-note`, placeholder: 'For example: added the amber accent'})),
    el('p', {class: `state s-${s}`, 'data-testid': `${kind}-state`, 'aria-live': 'polite'}, STATE[s] || ''),
    el('div', {class: 'buttons'}, el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': kind === 'prof' ? 'style-save' : 'assets-save', onclick: () => save(kind), disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''},
      kind === 'prof' ? 'Save style profile version' : 'Save asset register version')), ...feedback(`save-${kind}`));
}
function afterEdit() {
  for (const kind of ['prof', 'reg']) for (const n of document.querySelectorAll(`#view-lib [data-testid="${kind}-state"]`)) { const s = dirtyOf(kind === 'prof' ? B.prof : B.reg, kind === 'prof' ? B.profSaved : B.regSaved); n.textContent = STATE[s] || ''; n.className = `state s-${s}`;
    const b = document.querySelector(`#view-lib [data-testid="${kind === 'prof' ? 'style-save' : 'assets-save'}"]`); if (b) { b.disabled = s === 'saved' || busy(); b.title = s === 'saved' ? 'Nothing has changed since the last save.' : ''; } }
  renderNav();
}
async function save(kind) {
  const doc = kind === 'prof' ? B.prof : B.reg, base = kind === 'prof' ? B.profBase : B.regBase, note = (kind === 'prof' ? B.profNote : B.regNote).trim();
  const name = kind === 'prof' ? `${doc.profile.name || 'Style profile'} (${doc.profile.id})` : `Asset register (${doc.assets.length} assets)`;
  await withBusy(`save-${kind}`, 'Saving this version', async () => {
    const exp = await call('/api/experiments', 'POST', {craft_id: 'art_direction', name, input: doc, notes: note, run_now: true, parent_experiment_id: base ? base.experimentId : null});
    const run = exp.latest_run;
    if (run.run_status === 'failed') throw new Error(run.error.message);
    const b = {experimentId: exp.id, runId: run.id};
    if (kind === 'prof') { B.profBase = b; B.profSaved = j(doc); } else { B.regBase = b; B.regSaved = j(doc); }
    persist(); await refresh();
    R.notice[`save-${kind}`] = `Saved as a new version${run.warnings.length ? `. ${run.warnings.length} suggestion(s) are listed below the list` : ''}. The earlier version is unchanged.`;
  });
}
async function refresh() {
  if (!B.projectId) { R.styles = []; R.view = null; return; }
  try { R.styles = await call(`/api/art/styles?project_id=${encodeURIComponent(B.projectId)}`); R.view = await call(`/api/art/assets?project_id=${encodeURIComponent(B.projectId)}`); } catch (e) { R.styles = []; R.view = null; }
}
function newProfile() {
  const n = next('STYLE-', R.styles.map(s => s.profile_id));
  B.prof = {schema: 'filmcraft.style_profile.v1', project_id: B.projectId, profile: {id: n, name: '', summary: '', palette: [], textures: [], materials: [], period: {era: '', notes: ''}, themes: [], mood_words: [], constraints: []}};
  B.profBase = null; B.profSaved = null; persist(); render();
}
function openProfile(s) {
  B.prof = {schema: 'filmcraft.style_profile.v1', project_id: B.projectId, profile: JSON.parse(JSON.stringify(s.profile))}; B.profBase = {experimentId: s.experiment_id, runId: s.run_id}; B.profSaved = j(B.prof); persist(); render();
}
function listEditor(items, makeNew, render1, addLabel, testid, empty) {
  return el('div', {}, !items.length ? el('p', {class: 'hint', 'data-empty': testid}, empty) : null,
    ...items.map((it, i) => el('div', {class: 'listcard', 'data-testid': `${testid}-${i}`}, render1(it, i), el('div', {class: 'buttons'}, guarded('Remove', `rm-${testid}-${i}`, () => { items.splice(i, 1); touch(); render(); }, {'aria-label': `Remove ${testid} ${i + 1}`})))),
    el('div', {class: 'buttons'}, btn(addLabel, () => { items.push(makeNew()); touch(); render(); }, {'data-testid': `add-${testid}`})));
}
function projectPicker() {
  return row('Project', sel(B, 'projectId', [['', '— choose a project —'], ...R.projects.map(p => [p.project_id, p.title || p.project_id])], {'data-testid': 'lib-project'}), 'Projects come from the Scene Lab.');
}
function step1() {
  const p = B.prof && B.prof.profile;
  const list = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'profiles-form'}, el('h2', {}, 'Project style profiles'), projectPicker(),
    !B.projectId ? el('p', {class: 'hint', 'data-empty': 'noproject', 'data-testid': 'lib-noproject'}, 'Choose a project first. If the list is empty, save a screenplay in the Scene Lab, then press “Refresh the list”.') :
      (R.styles.length ? el('table', {class: 'table'}, el('thead', {}, el('tr', {}, ...['Profile', 'Colours', 'Rules', ''].map(h => el('th', {}, h)))), el('tbody', {}, ...R.styles.map(s => el('tr', {'data-testid': `prof-${s.profile_id}`}, el('td', {}, s.name), el('td', {}, String(s.colours)), el('td', {}, String(s.constraints)),
        el('td', {}, btn('Open', () => openProfile(s), {'data-testid': `open-${s.profile_id}`})))))) : el('p', {class: 'hint', 'data-empty': 'noprofiles', 'data-testid': 'lib-noprofiles'}, 'No style profiles yet for this project. Press “Create a style profile”.')),
    el('div', {class: 'buttons'}, btn('Create a style profile', newProfile, {class: 'primary', 'data-testid': 'new-profile', disabled: !B.projectId, title: B.projectId ? '' : 'Choose a project first.'}), btn('Refresh the list', async () => { await loadProjects(); await refresh(); render(); }, {'data-testid': 'lib-refresh'}),
      !B.projectId ? el('span', {class: 'why'}, 'Choose a project first.') : null));
  if (!p) return el('div', {}, list, glossary(TERMS[0]));
  p.palette = p.palette || []; p.textures = p.textures || []; p.materials = p.materials || []; p.constraints = p.constraints || []; p.period = p.period || {}; p.themes = p.themes || []; p.mood_words = p.mood_words || [];
  const themes = el('input', {'data-testid': 'prof-themes', oninput: ev => { p.themes = ev.target.value.split(',').map(s => s.trim()).filter(Boolean); touch(); }}); themes.value = p.themes.join(', ');
  const editor = el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'profile-editor'}, el('h2', {}, `Edit “${p.name || p.id}”`),
    row('Profile name', bind(p, 'name', {maxlength: '120', 'data-testid': 'prof-name', placeholder: 'For example: House style'})), row('Summary', bind(p, 'summary', {rows: '2'}, 'textarea')),
    el('h3', {}, 'Colours'), listEditor(p.palette, () => ({id: next('C', p.palette.map(c => c.id)), name: '', hex: '#888888', role: ''}), c => el('div', {}, row('Colour name', bind(c, 'name', {'data-testid': 'pc-name'})),
      row('Colour', el('div', {class: 'inline'}, el('input', {type: 'color', value: c.hex, 'aria-label': 'Pick the colour', oninput: ev => { c.hex = ev.target.value; const t = ev.target.nextSibling; if (t) t.value = c.hex; touch(); }}), bind(c, 'hex', {'aria-label': 'Colour code', maxlength: '7', 'data-testid': 'pc-hex'}), swatch(c)))), 'Add a colour', 'colour', 'No colours yet. Press “Add a colour”; three or more work best.'),
    el('h3', {}, 'Textures and materials'), listEditor(p.textures, () => ({id: next('T', p.textures.map(t => t.id)), name: '', description: ''}), t => row('Texture', bind(t, 'name', {'data-testid': 'pt-name'})), 'Add a texture', 'texture', 'No textures yet. Press “Add a texture”.'),
    listEditor(p.materials, () => ({id: next('M', p.materials.map(m => m.id)), name: '', finish: ''}), m => row('Material', bind(m, 'name', {'data-testid': 'pm-name'})), 'Add a material', 'material', 'No materials yet. Press “Add a material”.'),
    el('h3', {}, 'Period and themes'), row('Period or era', bind(p.period, 'era', {'data-testid': 'prof-era'})), row('Themes', themes, 'Separate with commas.'),
    el('h3', {}, 'Project rules'), el('p', {class: 'hint'}, 'Rules apply to this project only. A treatment that uses a word you avoid, or leaves out a word you require, is flagged as advice.'),
    listEditor(p.constraints, () => ({id: next('K', p.constraints.map(c => c.id)), kind: 'avoid', term: '', note: ''}), c => el('div', {}, row('Rule', sel(c, 'kind', [['avoid', 'Avoid this word'], ['require', 'Include this word']], {'data-testid': 'rule-kind'})), row('Word', bind(c, 'term', {'data-testid': 'rule-term', placeholder: 'For example: neon'})), row('Why', bind(c, 'note'))), 'Add a rule', 'rule', 'No rules yet. Press “Add a rule” to avoid or require a word in treatments.'),
    el('hr'), saveBlock('prof'));
  return el('div', {}, list, editor, glossary(TERMS[0]));
}

// ---- step 2: assets ---------------------------------------------------------------------------------------------------------------------
function ensureReg() {
  if (B.reg && B.reg.project_id === B.projectId) return;
  const v = R.view || {assets: []};
  B.reg = {schema: 'filmcraft.asset_register.v1', project_id: B.projectId, assets: (v.assets || []).map(({file_present, ...a}) => a)};
  B.regBase = v.experiment_id ? {experimentId: v.experiment_id, runId: v.run_id} : null; B.regSaved = j(B.reg);
}
function addAsset(meta, kind = 'texture') {
  const ids = B.reg.assets.map(a => a.id), id = next('A-', ids).replace(/^A-(\d)$/, 'A-00$1').replace(/^A-(\d\d)$/, 'A-0$1');
  B.reg.assets.push({id, name: (meta.filename || id).replace(/\.[a-z]+$/i, ''), kind, sha256: meta.sha256, filename: meta.filename, size_bytes: meta.size_bytes, mime: meta.mime, origin_path: meta.origin_path || '',
    tags: [], source: {type: 'unknown', creator: '', url: '', note: ''}, rights: {status: 'unknown', owner: '', licence: '', expires: '', note: ''}, usage: {allowed: [], note: ''}});
}
async function upload(files) {
  for (const f of files) {
    await withBusy('upload', `Uploading ${f.name}`, async () => {
      const r = await fetch(`/api/assets/upload?filename=${encodeURIComponent(f.name)}`, {method: 'POST', body: f});
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `The upload failed (HTTP ${r.status}). Try a smaller file.`);
      if (B.reg.assets.some(a => a.sha256 === d.sha256)) { R.notice.upload = `“${f.name}” is already registered; nothing was added.`; return; }
      addAsset(d); touch();
      R.notice.upload = `Added “${f.name}” to the list${d.already_stored ? ' (the file was already stored)' : ''}. Fill in where it came from and what you may do with it, then press Save.`;
    });
  }
}
async function fromPath() {
  if (!(B.path || '').trim()) return fail('upload', 'Type the full path of a picture file first, for example C:\\Pictures\\oak.png.');
  await withBusy('upload', 'Reading the file', async () => {
    const d = await call('/api/assets/from-path', 'POST', {path: B.path.trim()});
    if (B.reg.assets.some(a => a.sha256 === d.sha256)) { R.notice.upload = 'That picture is already registered; nothing was added.'; return; }
    addAsset(d); touch(); B.path = '';
    R.notice.upload = `Added “${d.filename}”. A copy is stored here; the original file is untouched.`;
  });
}
function step2() {
  ensureReg();
  const a = B.reg.assets;
  return el('div', {}, el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'assets-form'}, el('h2', {}, 'Asset register'), projectPicker(),
    !B.projectId ? el('p', {class: 'hint', 'data-empty': 'noproject', 'data-testid': 'lib-noproject2'}, 'Choose a project first, then upload your picture files.') : el('div', {},
      el('div', {class: 'formrow'}, el('label', {for: 'lib-file'}, 'Upload pictures'), el('input', {type: 'file', id: 'lib-file', accept: 'image/png,image/jpeg,image/gif,image/webp', multiple: true, 'data-testid': 'lib-file', onchange: ev => { upload([...ev.target.files]); ev.target.value = ''; }}),
        el('span', {class: 'hint'}, 'PNG, JPEG, GIF or WebP, up to 8 MB each.')),
      el('div', {class: 'formrow'}, el('label', {for: 'lib-path'}, 'Or a file on this computer'), el('input', {id: 'lib-path', placeholder: 'C:\\Pictures\\oak.png', 'data-testid': 'lib-path', value: B.path, oninput: ev => { B.path = ev.target.value; persist(); }}),
        btn('Add this file', fromPath, {'data-testid': 'lib-addpath', disabled: busy()})), ...feedback('upload'),
      !a.length ? el('p', {class: 'hint', 'data-empty': 'assets', 'data-testid': 'lib-noassets'}, 'No assets registered yet. Upload a picture above, or type the path of a file and press “Add this file”.') :
        el('div', {}, ...a.map((x, i) => el('div', {class: 'listcard', 'data-testid': `asset-${x.id}`}, el('div', {class: 'cardhead'}, el('strong', {}, x.id), el('img', {src: `/api/assets/${x.sha256}/file`, alt: `Preview of ${x.name}`, class: 'thumb big'})),
          row('Name', bind(x, 'name', {'data-testid': 'as-name'})), row('Kind', sel(x, 'kind', [['texture', 'Texture'], ['background', 'Background'], ['image', 'Image'], ['design', 'Design'], ['reference', 'Reference']], {'data-testid': 'as-kind'})),
          row('Who made it', sel(x.source, 'type', [['unknown', 'Not known yet'], ['own', 'I made it'], ['licensed', 'Licensed from someone'], ['public_domain', 'Public domain'], ['commissioned', 'Made for this project']], {'data-testid': 'as-source'}, true)),
          row('Creator or link', bind(x.source, 'creator', {placeholder: 'Name, or web address'})),
          row('Rights', sel(x.rights, 'status', [['unknown', 'Not known yet'], ['pending', 'Waiting for clearance'], ['cleared', 'Cleared for this project'], ['restricted', 'Restricted']], {'data-testid': 'as-rights'}, true)),
          row('Owner', bind(x.rights, 'owner', {'data-testid': 'as-owner'})), row('Licence', bind(x.rights, 'licence', {'data-testid': 'as-licence', placeholder: 'Licence name or reference'})),
          row('May be used for', bind({v: (x.usage.allowed || []).join(', ')}, 'v', {placeholder: 'film, trailer, poster', oninput: ev => { x.usage.allowed = ev.target.value.split(',').map(s => s.trim()).filter(Boolean); touch(); }}), 'Separate with commas.'),
          row('Tags', bind({v: (x.tags || []).join(', ')}, 'v', {placeholder: 'wood, warm', oninput: ev => { x.tags = ev.target.value.split(',').map(s => s.trim()).filter(Boolean); touch(); }}), 'Separate with commas.'),
          el('div', {class: 'buttons'}, guarded('Remove from the list', `rm-asset-${x.id}`, () => { B.reg.assets.splice(i, 1); touch(); render(); }, {'data-testid': 'as-del'}))))),
      el('hr'), saveBlock('reg'))), el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'lib-finish'}, el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'}, btn('Open the Art Lab', () => byId('tab-art').click(), {'data-testid': 'lib-open-art', class: 'primary'}), btn('Back to the style profiles', () => go(1), {'data-testid': 'lib-back-profiles'}))), glossary(TERMS[1]));
}

const go = n => { B.step = n; R.errors = {}; R.notice = {}; R.armed = null; persist(); render(); window.scrollTo({top: 0}); };
function navSpec() {
  const n = B.step, before = STEPS.before(n), after = STEPS.after(n);
  return {n, total: 2, back: before ? {label: `Back: ${before.title}`, onclick: () => go(n - 1)} : null, next: after ? {label: `Next: ${after.title}`, onclick: () => go(n + 1)} : null};
}
function renderNav() { const h = byId('lib-nav'); if (h) h.replaceChildren(ui.nav(navSpec())); }
function render() {
  ui.clearTimers();
  const mount = byId('lib-mount');
  if (!mount) return;
  const n = B.step;
  mount.replaceChildren(el('div', {id: 'lib-wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': 2, 'data-testid': 'lib-wizard'},
    ui.stepper({defs: STEPS.list(), current: n, reached: 2, onGo: go}), el('h1', {'data-testid': 'step-title'}, STEPS.title(n)), el('p', {class: 'intro', 'data-testid': 'step-intro'}, STEPS.intro(n)), (n === 1 ? step1 : step2)(), el('div', {id: 'lib-nav'})));
  renderNav();
  fillGlossary(byId('lib-wizard'));
}
async function loadProjects() { try { R.projects = await call('/api/lab/projects'); } catch (e) { R.projects = []; } }
async function show() { await loadProjects(); if (!B.projectId && R.projects[0]) B.projectId = R.projects[0].project_id; await refresh(); B.reg = B.reg && B.reg.project_id === B.projectId ? B.reg : null; render(); }
async function init() { restore(); await loadProjects(); await refresh(); render(); }
document.addEventListener('change', async ev => {
  if (ev.target && ev.target.getAttribute && ev.target.getAttribute('data-testid') === 'lib-project') { B.prof = null; B.reg = null; await refresh(); persist(); render(); }
});
return {show, init, render, B, R};
})();
