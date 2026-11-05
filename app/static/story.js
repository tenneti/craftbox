// Story Lab: the six-phase story development process (guidelines/story-process.md) as a 6-step wizard.
// It edits the `story` block of the same screenplay document the Scene Lab uses; Save creates a screenplay revision.
// Follows guidelines/ui-standard.md. Needs ui.js, lab.js.
const Story = (() => {
const {L, R, el, call, byId, bind, sel, row, btn, touch, persist, fail, withBusy, busy, feedback, guarded, spState, saveScreenplay, adoptScreenplay, replaceGuard, confirmBox} = Lab;
const STATE_TEXT = {unsaved: 'Not saved yet. Saving creates a new screenplay revision and keeps what you typed on screen.', saved: 'Saved. What you typed is still shown here.', changed: 'Changed, not saved yet. Saving creates a new revision; earlier ones stay exactly as they were.'};
L.storyStep = L.storyStep || 1;

const STEPS = ui.steps([
  {short: 'Concept', title: 'audit the concept', intro: 'Before writing, check that the idea is a real story and not just a situation. Name the five pillars (setting, characters, core conflict, plot and theme), prove that at least two events happen in order and are joined by a "but" or "so", and pick a classic plot shape to measure against. This prevents starting a story with no friction, stakes or purpose.'},
  {short: 'Hook', title: 'make it tellable', intro: 'A story grabs attention by breaking an expectation. Name the everyday norm your opening violates, write the hook that should land in the first 15 seconds, and decide how to show something familiar in an unfamiliar way. This avoids cliché openings and pulls the audience in from the first line.'},
  {short: 'Empathy', title: 'design the empathy', intro: 'Decide how the audience will feel with your people. Frame their struggle so it invites shared feeling rather than making viewers look away, choose how we reach their thoughts, say whom the story is meant to move, and list the hard choices the protagonist makes. This gives you characters the audience admires and invests in.'},
  {short: 'Conflict', title: 'escalate the conflict', intro: 'The middle of a story sags unless the pressure keeps rising. Explain why neither side can walk away, map the moments where a choice gets an unexpected answer, decide what the audience is not told yet, and place the feelings that go unspoken under the dialogue.'},
  {short: 'Structure', title: 'map the structure', intro: 'Check that the story carries a point. Fill in the six parts of a told story (summary, setting, rising conflict, why it matters, outcome, bridge to now) and the eight steps of the story circle, and link them to your dramatic beats so the order can be checked.'},
  {short: 'Revision', title: 'revise and test', intro: 'Write the whole first draft without stopping to edit, share it and record what readers say, polish it, then ask the last question: does the story work as a safe rehearsal of real human choices? This is where a blueprint becomes a finished story.'},
]);

// ---- helpers ---------------------------------------------------------------------------------------------------------
const need = () => { L.sp.story = L.sp.story || {}; return L.sp.story; };
const sub = (o, k) => (o[k] = o[k] || {});
const arr = (o, k) => (o[k] = o[k] || []);
const chars = () => (L.sp ? L.sp.characters : []);
const charOpts = (blank = '— choose —') => [['', blank], ...chars().map(c => [c.id, c.name || c.id])];
const beatOpts = () => [['', '— choose a beat —'], ...L.sp.scenes.flatMap(s => (s.beats || []).map((b, i) => [b.id, `${s.id} · ${i + 1}. ${b.title}`]))];
const timeOf = id => { const an = ((R.live || (R.spArt && R.spArt.analysis)) || {}).scenes || []; for (const a of an) { const e = a.elements.find(x => x.id === id); if (e) return e.start_seconds; } return null; };
const lineOpts = (onlyDialogue = false) => [['', '— choose a script line —'], ...L.sp.scenes.flatMap(s => s.elements.filter(e => !onlyDialogue || e.type === 'dialogue').map(e => {
  const t = timeOf(e.id); return [e.id, `${e.id.replace(s.id + '-', '')}${t != null ? ` (${Math.round(t)}s)` : ''} ${e.type === 'dialogue' ? (chars().find(c => c.id === e.character_id) || {}).name + ': ' : ''}${(e.text || '').slice(0, 46)}`]; }))];
const audit = () => ((R.live || (R.spArt && R.spArt.analysis)) || {}).story || null;
const text = (obj, key, props = {}, rows = '2') => bind(obj, key, {rows, ...props}, 'textarea');
function addCharacter(name) {
  name = (name || '').trim();
  if (!name) return null;
  const ids = new Set(chars().map(c => c.id)); let n = chars().length + 1, id = `C-${String(n).padStart(3, '0')}`;
  while (ids.has(id)) id = `C-${String(++n).padStart(3, '0')}`;
  L.sp.characters.push({id, name, role: '', description: '', motivation: '', want: '', need: '', flaw: '', relationships: [], emotional_arc: {start: '', end: ''}});
  for (const s of L.sp.scenes) s.characters.push(id);
  return id;
}

// ---- audit panel (advice only, beside the answers: U5, U9) -------------------------------------------------------------
let checks = 0;   // completed checks; shown as data-checks so a test can wait for a fresh result
async function check() { await Lab.recalc(); checks++; render(); }
function auditPanel(n) {
  const a = audit();
  const ph = a && a.phases.find(p => p.phase === n);
  const head = ph ? `Phase ${n} check: ${ph.ok} of ${ph.total} answered well` : 'Not checked yet';
  return el('div', {class: 'auditbox', 'data-testid': 'audit', 'data-checks': String(checks)}, el('h3', {}, head),
    ph ? el('p', {class: 'hint'}, ph.helps) : el('p', {class: 'hint'}, 'Press “Check my answers”. The check is advice only; it never blocks anything.'),
    ph ? el('ul', {class: 'audit'}, ...ph.items.map(i => el('li', {class: i.status, 'data-item': i.id, 'data-status': i.status}, el('span', {class: 'mark'}, i.status === 'ok' ? '✓' : (i.status === 'advice' ? '!' : '○')),
      el('span', {}, el('span', {class: 'label'}, i.label), el('br'), el('span', {class: 'msg'}, i.message))))) : null,
    el('div', {class: 'buttons'}, btn('Check my answers', check, {'data-testid': 'story-check', disabled: busy(), title: 'Checks what is on screen. Saves nothing.'})), ...feedback('recalc'),
    a && a.overall ? el('p', {class: 'hint', 'data-testid': 'story-overall'}, `Whole story: ${a.overall.ok} of ${a.overall.total} answered well (${a.overall.percent}%).`) : null);
}
function saveBlock() {
  const s = spState();
  return el('div', {class: 'saveblock'}, row('What changed (optional)', bind(L, 'revNote', {maxlength: '120', placeholder: 'e.g. Chose the plot shape and the hook', 'data-testid': 'story-rev-note'})),
    el('p', {class: `state s-${s}`, 'data-testid': 'sp-state', 'aria-live': 'polite'}, STATE_TEXT[s] || ''),
    el('div', {class: 'buttons'}, el('button', {type: 'button', class: 'primary', 'data-ui': 'save', 'data-testid': 'story-save', onclick: async () => { await saveScreenplay(); }, disabled: s === 'saved' || busy(), title: s === 'saved' ? 'Nothing has changed since the last save.' : ''}, 'Save story revision')),
    ...feedback('save'));
}
function listEditor(items, makeNew, render1, addLabel, testid) {
  return el('div', {}, ...items.map((it, i) => el('div', {class: 'listcard', 'data-testid': `${testid}-${i}`}, render1(it, i), el('div', {class: 'buttons'}, guarded('Remove', `rm-${testid}-${i}`, () => { items.splice(i, 1); touch(); render(); })))),
    el('div', {class: 'buttons'}, btn(addLabel, () => { items.push(makeNew()); touch(); render(); }, {'data-testid': `add-${testid}`})));
}

// ---- phase 1 ---------------------------------------------------------------------------------------------------------------
const start = {title: '', logline: '', theme: '', setting: '', protagonist: '', antagonist: ''};
async function createProject() {
  if (!start.title.trim()) return fail('start', 'Give the story a title first.');
  if (!start.protagonist.trim()) return fail('start', 'Name the protagonist first.');
  await withBusy('start', 'Creating the project', async () => {
    const characters = [{name: start.protagonist, role: 'Protagonist'}, ...(start.antagonist.trim() ? [{name: start.antagonist, role: 'Antagonist'}] : [])];
    const doc = await call('/api/lab/idea', 'POST', {title: start.title, logline: start.logline, theme: start.theme, location: start.setting, characters, story_idea: start.logline});
    adoptScreenplay(doc, null, null);
    L.sp.story.pillars.setting = start.setting;
    R.notice.start = `Created “${L.sp.project.title}”. Now answer the five pillars below.`;
  });
}
async function loadSample() {
  await withBusy('start', 'Loading the sample', async () => { adoptScreenplay(await call('/api/crafts/screenwriting/fixture?name=screenplay'), null, null); R.notice.start = 'Loaded “The Closing Hour”, a finished example with most answers filled in.'; });
}
function step1() {
  if (!L.sp) {
    return el('div', {}, confirmBox(), el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'start-form'}, el('h2', {}, 'Start a story'),
      el('p', {class: 'hint'}, 'Only the essentials now; the rest of Phase 1 follows. You can also open a saved project from the Scene Lab, or load the finished sample.'),
      row('Title', bind(start, 'title', {'data-testid': 'start-title', placeholder: 'e.g. The Closing Hour'})), row('One-line story', bind(start, 'logline', {'data-testid': 'start-logline', placeholder: 'What if…?'})),
      row('Theme', bind(start, 'theme', {placeholder: 'The underlying message'})), row('Setting', bind(start, 'setting', {placeholder: 'World and context'})),
      row('Protagonist', bind(start, 'protagonist', {'data-testid': 'start-protagonist', placeholder: 'Name'})), row('Antagonist', bind(start, 'antagonist', {'data-testid': 'start-antagonist', placeholder: 'Name (a person; a force can be added later)'})),
      el('div', {class: 'buttons'}, btn('Create the project', createProject, {class: 'primary', 'data-testid': 'start-create', disabled: busy()}), btn('Load the sample story', () => loadSample(), {'data-testid': 'start-sample', disabled: busy()})), ...feedback('start')));
  }
  const st = need(), p = sub(st, 'pillars'), mn = sub(st, 'minimal_narrative');
  p.supporting_ids = p.supporting_ids || [];
  const newName = {v: ''};
  return el('div', {}, confirmBox(), el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase1-form'}, el('h2', {}, `“${L.sp.project.title}”: the five pillars`), ...feedback('start'),
    row('Setting', text(p, 'setting', {'data-testid': 'p-setting', placeholder: 'The world and context'})),
    row('Protagonist', sel(p, 'protagonist_id', charOpts(), {'data-testid': 'p-protagonist'}, {nullable: true})),
    row('Antagonist', sel(p, 'antagonist_id', charOpts('— none (a force) —'), {'data-testid': 'p-antagonist'}, {nullable: true})),
    row('Antagonist note', bind(p, 'antagonist_note', {placeholder: 'Who or what stands in the way, if it is not simply one person'})),
    row('Supporting cast', el('div', {class: 'chips'}, ...chars().filter(c => c.id !== p.protagonist_id && c.id !== p.antagonist_id).map(c => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: p.supporting_ids.includes(c.id),
      onchange: ev => { p.supporting_ids = ev.target.checked ? [...p.supporting_ids, c.id] : p.supporting_ids.filter(x => x !== c.id); touch(); }}), ` ${c.name || c.id}`)),
      el('input', {placeholder: 'Add a character…', 'aria-label': 'New character name', 'data-testid': 'p-newchar', oninput: ev => { newName.v = ev.target.value; }, onkeydown: ev => { if (ev.key === 'Enter') { addCharacter(newName.v); touch(); render(); } }}),
      btn('Add', () => { if (addCharacter(newName.v)) { touch(); render(); } }, {'data-testid': 'p-addchar'}))),
    row('Core conflict', text(p, 'core_conflict', {'data-testid': 'p-conflict', placeholder: 'The primary risk or obstacle'})),
    row('Plot', text(p, 'plot', {'data-testid': 'p-plot', placeholder: 'Connected cause and effect: this happens, so that happens…'}, '3')),
    row('Theme', text(p, 'theme', {'data-testid': 'p-theme', placeholder: 'The underlying message'})),
    el('h3', {}, 'Minimal narrative test'), el('p', {class: 'hint'}, 'A story needs at least two events in time order, joined by a turn such as “but then” or “so”.'),
    row('First event', bind(mn, 'event_1', {'data-testid': 'mn-1', placeholder: 'Something happens'})), row('Joined by', bind(mn, 'juncture', {'data-testid': 'mn-j', placeholder: 'e.g. but when… / and so…'})),
    row('Next event', bind(mn, 'event_2', {'data-testid': 'mn-2', placeholder: 'Something happens as a result'})),
    el('h3', {}, 'Master plot arc'),
    row('Shape', sel(st, 'master_plot', [['', '— choose —'], ['overcoming_the_monster', 'Overcoming the Monster'], ['rags_to_riches', 'Rags to Riches'], ['the_quest', 'The Quest'], ['voyage_and_return', 'Voyage and Return'], ['rebirth', 'Rebirth'], ['comedy', 'Comedy'], ['tragedy', 'Tragedy'], ['man_in_a_hole', 'Man in a Hole']], {'data-testid': 'master-plot'})),
    auditPanel(1), el('hr'), saveBlock()));
}

// ---- phase 2 --------------------------------------------------------------------------------------------------------------------
function step2() {
  const st = need(), br = sub(st, 'breach'), hk = sub(st, 'hook'), df = sub(st, 'defamiliarization');
  const t = hk.element_id ? timeOf(hk.element_id) : null;
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase2-form'}, el('h2', {}, 'Break an expectation, early'),
    el('h3', {}, 'Canonical script breach'), row('The expected norm', text(br, 'norm', {'data-testid': 'b-norm', placeholder: 'The everyday routine or social expectation'})),
    row('How the story breaks it', text(br, 'violation', {'data-testid': 'b-viol', placeholder: 'What the inciting incident does instead'})),
    el('h3', {}, 'The 15-second hook'), row('The hook', text(hk, 'text', {'data-testid': 'h-text', placeholder: 'The opening moment that raises tension'})),
    row('Delivered by line', sel(hk, 'element_id', lineOpts(), {'data-testid': 'h-line'}, {nullable: true, render: true}), t != null ? `starts at ${Math.round(t)} s` : 'Pick the script line to check the timing.'),
    el('h3', {}, 'Defamiliarization lens'),
    row('Technique', sel(df, 'technique', [['', '— choose —'], ['unexpected_perspective', 'An unexpected perspective'], ['unconventional_sensory_detail', 'Unconventional sensory detail'], ['shifting_point_of_view', 'Shifting point of view'], ['other', 'Something else']], {'data-testid': 'd-tech'})),
    row('In practice', text(df, 'description', {'data-testid': 'd-desc', placeholder: 'How a familiar situation will be seen in an unexpected way'})),
    auditPanel(2), el('hr'), saveBlock());
}

// ---- phase 3 ---------------------------------------------------------------------------------------------------------------------
function step3() {
  const st = need(), em = sub(st, 'empathy'), ag = sub(st, 'agency'), ch = arr(ag, 'choices');
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase3-form'}, el('h2', {}, 'Empathy, not distress'),
    row('How the struggle is framed', text(em, 'vulnerability', {'data-testid': 'e-vuln', placeholder: 'What makes the audience feel with them rather than turn away?'})),
    row('Risk of overwhelming distress', sel(em, 'distress_risk', [['', '— rate it —'], ['low', 'Low'], ['medium', 'Medium'], ['high', 'High']], {'data-testid': 'e-risk'})),
    row('How we reach their thoughts', sel(em, 'consciousness', [['', '— choose —'], ['free_indirect_discourse', 'Free indirect discourse (narrated monologue)'], ['interior_monologue', 'Interior monologue (e.g. voice-over)'], ['psycho_narration', 'Psycho-narration'], ['behavioural_only', 'Behaviour and objects only']], {'data-testid': 'e-mode'})),
    row('Whom the story is for', sel(em, 'target', [['', '— choose —'], ['bounded', 'Bounded (an in-group)'], ['ambassadorial', 'Ambassadorial (an out-group or cause)'], ['broadcast', 'Broadcast (universal vulnerabilities)']], {'data-testid': 'e-target'})),
    el('h3', {}, 'Agency and effort'), el('p', {class: 'hint'}, 'Hard choices made under pressure, each with a cost. Not luck, and not being rescued.'),
    listEditor(ch, () => ({text: '', cost: ''}), c => el('div', {}, row('Choice', text(c, 'text', {'data-testid': 'ag-text', placeholder: 'What the protagonist chooses'})), row('What it costs', bind(c, 'cost', {'data-testid': 'ag-cost', placeholder: 'What they risk or lose'}))), 'Add a choice', 'choice'),
    row('Any luck or rescue?', bind(ag, 'luck_note', {placeholder: 'Be honest about anything unearned'})),
    auditPanel(3), el('hr'), saveBlock());
}

// ---- phase 4 ---------------------------------------------------------------------------------------------------------------------
function step4() {
  const st = need(), cf = sub(st, 'conflict'), eg = arr(cf, 'expectation_gaps'), ig = arr(cf, 'information_gaps'), sb = arr(cf, 'subtext');
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase4-form'}, el('h2', {}, 'Keep the middle tight'),
    row('Unity of opposites', text(cf, 'unity_of_opposites', {'data-testid': 'c-unity', placeholder: 'Why neither side can simply walk away'})),
    el('h3', {}, 'Expectation gaps'), el('p', {class: 'hint'}, 'A decision point where the world answers a character’s action in an unexpected way, raising the stakes.'),
    listEditor(eg, () => ({beat_id: '', action: '', reaction: '', stakes: ''}), g => el('div', {}, row('At beat', sel(g, 'beat_id', beatOpts(), {'data-testid': 'eg-beat'})), row('Character acts', bind(g, 'action', {'data-testid': 'eg-action'})),
      row('Reality answers', bind(g, 'reaction', {'data-testid': 'eg-reaction'})), row('Stakes now', bind(g, 'stakes', {'data-testid': 'eg-stakes'}))), 'Add an expectation gap', 'eg'),
    el('h3', {}, 'Information gaps'), el('p', {class: 'hint'}, 'What the audience is deliberately not told yet, and the beat where they find out.'),
    listEditor(ig, () => ({withheld: '', reveal_beat_id: ''}), g => el('div', {}, row('Withheld', bind(g, 'withheld', {'data-testid': 'ig-withheld'})), row('Revealed at beat', sel(g, 'reveal_beat_id', beatOpts(), {'data-testid': 'ig-beat'}))), 'Add an information gap', 'ig'),
    el('h3', {}, 'Subtext (the iceberg)'), el('p', {class: 'hint'}, 'What is felt but not said, and the line that carries it.'),
    listEditor(sb, () => ({element_id: '', surface: '', unspoken: ''}), s => el('div', {}, row('Script line', sel(s, 'element_id', lineOpts(), {'data-testid': 'sb-line'}, {nullable: true})), row('What is said', bind(s, 'surface', {'data-testid': 'sb-surface'})), row('What is not said', bind(s, 'unspoken', {'data-testid': 'sb-unspoken'}))), 'Add a layer of subtext', 'sb'),
    auditPanel(4), el('hr'), saveBlock());
}

// ---- phase 5 ---------------------------------------------------------------------------------------------------------------------
const LABOV = [['abstract', 'Abstract: the summary hook'], ['orientation', 'Orientation: context and setting'], ['complicating_action', 'Complicating action: rising conflict'], ['evaluation', 'Evaluation: why the story matters'], ['resolution', 'Result: the outcome'], ['coda', 'Coda: the bridge to now']];
const CIRCLE = [['you', '1. You'], ['need', '2. Need'], ['go', '3. Go'], ['search', '4. Search'], ['find', '5. Find'], ['take', '6. Take (the price paid)'], ['return', '7. Return'], ['change', '8. Change']];
function step5() {
  const st = need(), lb = sub(st, 'labov'), cr = sub(st, 'circle');
  const rowFor = (obj, key, label, tag) => { const o = sub(obj, key); return el('div', {class: 'listcard', 'data-testid': `${tag}-${key}`}, row(label, text(o, 'text', {'data-testid': `${tag}-text-${key}`})), row('Beat', sel(o, 'beat_id', beatOpts(), {'data-testid': `${tag}-beat-${key}`}, {nullable: true}))); };
  return el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase5-form'}, el('h2', {}, 'Does it answer “so what?”'),
    el('h3', {}, 'The six parts of a told story'), ...LABOV.map(([k, l]) => rowFor(lb, k, l, 'lb')),
    el('h3', {}, 'The story circle'), el('p', {class: 'hint'}, 'Link each step to a beat. The check confirms the journey moves forward through the script.'), ...CIRCLE.map(([k, l]) => rowFor(cr, k, l, 'cr')),
    auditPanel(5), el('hr'), saveBlock());
}

// ---- phase 6 ---------------------------------------------------------------------------------------------------------------------
function step6() {
  const st = need(), rv = sub(st, 'revision'), fb = arr(rv, 'feedback'), pol = sub(rv, 'polish'), sim = sub(rv, 'simulator');
  const lines = L.sp.scenes.reduce((n, s) => n + s.elements.length, 0);
  const chk = (obj, key, label) => el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!obj[key], 'data-testid': `pol-${key}`, onchange: ev => { obj[key] = ev.target.checked; touch(); }}), ` ${label}`);
  return el('div', {}, confirmBox(), el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'phase6-form'}, el('h2', {}, 'From blueprint to finished story'),
    el('h3', {}, '1. First draft sprint'), el('p', {class: 'hint', 'data-testid': 'draft-status'}, `${lines} script line(s) written so far. Write the whole draft in the Scene Lab without stopping to edit; polish comes after.`),
    el('div', {class: 'buttons'}, btn('Open the Scene Lab to write', () => goScene(2), {'data-testid': 'go-write'})),
    el('h3', {}, '2. Outside feedback'), el('p', {class: 'hint'}, 'Share the draft with readers or a writing group, and record what they find: plot holes, weak pacing, mischaracterization.'),
    listEditor(fb, () => ({from: '', note: '', status: 'open'}), f => el('div', {}, row('From', bind(f, 'from', {'data-testid': 'fb-from', placeholder: 'Who said it'})), row('Their note', text(f, 'note', {'data-testid': 'fb-note'})),
      row('Status', sel(f, 'status', [['open', 'Open'], ['addressed', 'Addressed']], {'data-testid': 'fb-status'}))), 'Add a note from a reader', 'fb'),
    el('h3', {}, '3. Polishing and proofreading'), el('div', {class: 'chips'}, chk(pol, 'prose', 'Prose'), chk(pol, 'tone', 'Tone'), chk(pol, 'word_choice', 'Word choice'), chk(pol, 'consistency', 'Structural consistency')),
    el('h3', {}, '4. Flight simulator verification'), el('p', {class: 'hint'}, 'Can the audience safely explore a complex human dynamic or moral choice through this story?'),
    row('What they rehearse', text(sim, 'question', {'data-testid': 'sim-q', placeholder: 'What situation could a viewer try on?'})), row('The moral choice', text(sim, 'moral_choice', {'data-testid': 'sim-m', placeholder: 'The hard choice the story lets them weigh'})),
    row('Verified', el('label', {class: 'chip'}, el('input', {type: 'checkbox', checked: !!sim.verified, 'data-testid': 'sim-ok', onchange: ev => { sim.verified = ev.target.checked; touch(); }}), ' A reader confirmed it works this way')),
    auditPanel(6), el('hr'), saveBlock()),
    el('section', {class: 'panel', 'data-ui': 'form', 'data-testid': 'story-finish'}, el('h2', {}, 'What would you like to do next?'),
      el('div', {class: 'buttons'}, btn('Continue to the Scene Lab (write the screenplay)', () => goScene(2), {class: 'primary', 'data-testid': 'continue-scene-lab'}),
        btn('Review phase 1 again', () => go(1), {'data-testid': 'story-review-1'}))));
}
function goScene(step) {   // the working screenplay lives in shared state, so nothing is lost by switching tabs
  document.getElementById('tab-lab').click();
  if (L.sp) Lab.go(step);
}

// ---- shell ----------------------------------------------------------------------------------------------------------------------------
const fns = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6};
const reached = () => (L.sp ? 6 : 1);
function go(n) { if (n < 1 || n > 6 || n > reached()) return; L.storyStep = n; R.errors = {}; R.notice = {}; R.armed = null; persist(); render(); window.scrollTo({top: 0}); if (L.sp) check().catch(() => {}); }
function navSpec() {
  const n = L.storyStep, before = STEPS.before(n);
  return {n, total: 6, back: before ? {label: `Back: ${before.short.toLowerCase()}`, onclick: () => go(n - 1)} : null,
    next: n < 6 ? {label: `Next: ${STEPS.list()[n].title}`, disabled: !L.sp, why: 'Create the project (or load the sample) first.', onclick: () => go(n + 1)} : null};
}
function renderNav() { const h = byId('story-nav'); if (h) h.replaceChildren(ui.nav(navSpec())); }
function render() {
  const mount = byId('story-mount');
  if (!mount || byId('view-story').hidden) return;
  const n = Math.min(L.storyStep, reached());
  L.storyStep = n;
  mount.replaceChildren(el('div', {id: 'story-wizard', 'data-ui': 'wizard', 'data-step': n, 'data-steps': 6, 'data-testid': 'story-wizard'},
    ui.stepper({defs: STEPS.list(), current: n, reached: reached(), onGo: go}), el('h1', {'data-testid': 'step-title'}, STEPS.title(n)), el('p', {class: 'intro', 'data-testid': 'step-intro'}, STEPS.intro(n)),
    fns[n](), el('div', {id: 'story-nav'})));
  renderNav();
}
Lab.renderHooks.push(render);
Lab.editHooks.push(renderNav);
async function show() { await Lab.refreshProjects(); render(); if (L.sp && !audit()) check().catch(() => {}); }
return {show, render};
})();
