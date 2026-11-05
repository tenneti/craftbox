"""UI contract check from guidelines/ui-standard.md ("Markup contract").

``assert_ui_contract(page)`` inspects the rendered wizard step: a wizard root with a stepper, at most
one primary Save per form and per screen, a Back unless it is the first step, a Next unless it is the
last, and "Back:"/"Next:" labels that say where they lead. Browser tests call it on every step.
(Placed in tests/ rather than tests/ui/ so ``unittest discover -s tests`` can import it directly.)
"""

_JS = """
(root) => {
  const bad = [];
  const w = document.querySelector(root || '[data-ui=wizard]');
  if (!w || w.dataset.ui !== 'wizard') return ['no [data-ui=wizard] found at ' + (root || 'the page')];
  const step = Number(w.dataset.step), total = Number(w.dataset.steps);
  const count = sel => w.querySelectorAll(sel).length;
  if (count('[data-ui=stepper]') !== 1) bad.push('a wizard needs exactly one stepper');
  const saves = count('[data-ui=save]');
  if (saves > 1) bad.push(`more than one primary Save on the screen (${saves})`);
  w.querySelectorAll('[data-ui=form]').forEach((f, i) => {
    const n = f.querySelectorAll('[data-ui=save]').length;
    if (n > 1) bad.push(`form ${i} has ${n} Save buttons`);
  });
  if (!w.querySelector('[data-ui=form]')) bad.push('step has no [data-ui=form] section');
  const backs = w.querySelectorAll('[data-ui=back]'), nexts = w.querySelectorAll('[data-ui=next]');
  if (step > 1 && backs.length !== 1) bad.push(`step ${step} needs exactly one Back (found ${backs.length})`);
  if (step === 1 && backs.length) bad.push('first step must not have Back');
  if (step < total && nexts.length !== 1) bad.push(`step ${step} needs exactly one Next (found ${nexts.length})`);
  if (step === total && nexts.length) bad.push('last step must not have Next');
  backs.forEach(b => { if (!/^Back: /.test(b.textContent)) bad.push(`Back label should say where it goes: "${b.textContent}"`); });
  nexts.forEach(b => { if (!/^Next: /.test(b.textContent)) bad.push(`Next label should say what comes next: "${b.textContent}"`); });
  if (!/^Step \\d+ of \\d+: /.test((w.querySelector('h1') || {}).textContent || '')) bad.push('title must read "Step N of M: ..."');
  if (!(w.querySelector('.intro') || {}).textContent) bad.push('step needs a plain-words intro line');
  return bad;
}
"""


def assert_ui_contract(page, root=None):
    """``root`` selects one wizard when a page has several (e.g. '#wizard' or '#lab-wizard')."""
    violations = page.evaluate(_JS, root)
    assert not violations, "UI contract violations: " + "; ".join(violations)


# ---------------------------------------------------------------------------------------------------------------------------------
# Text checks (CB2A). Each check maps to a rule that exists in guidelines/ui-standard.md; see docs/cb2a-ui-text-checklist.md.
# They test what can be tested objectively. Whether the words are good plain language still needs a human ("read it cold").
# ---------------------------------------------------------------------------------------------------------------------------------
JARGON = ["treatment", "set layout", "blocking", "continuity", "palette", "previz", "manifest", "rebase", "storyboard", "beat", "asset"]
JARGON_LIGHT = JARGON + ["lighting plan", "scene setup", "shot adjustment", "key light", "fill light", "backlight", "practical", "motivated", "ambient", "colour temperature", "beam angle", "softness", "falloff"]
ACTION_WORDS = r"\b(add|choose|pick|press|click|create|draft|open|start|register|upload|select|go|write|save|make)\b"

_TEXT_JS = r"""
([root, jargon, actionWords]) => {
  const bad = [];
  const w = document.querySelector(root);
  if (!w) return ['no wizard found at ' + root];
  const words = s => (s || '').trim().split(/\s+/).filter(Boolean);
  const title = (w.querySelector('h1') || {}).textContent || '';
  const m = /^Step \d+ of \d+: (.+)$/.exec(title.trim());
  if (!m) bad.push('U1: title must read "Step N of M: <what you do here>": ' + title);
  else if (words(m[1]).length < 2) bad.push('U1: the part after the colon should say what you do here: ' + title);
  const intro = (w.querySelector('.intro') || {}).textContent || '';
  const n = words(intro).length;
  if (n < 6 || n > 90) bad.push('U8: the step intro should be a short plain-words explanation (6-90 words), found ' + n);
  w.querySelectorAll('[data-ui=back], [data-ui=next]').forEach(b => { if (words(b.textContent.replace(/^(Back|Next): /, '')).length < 1 || !/^(Back|Next): .+/.test(b.textContent.trim())) bad.push('U1: label should read "Back: ..." / "Next: ..." and name the step: ' + b.textContent); });
  const last = Number(w.dataset.step) === Number(w.dataset.steps);
  if (last && w.querySelectorAll('[data-ui=form] button:not([disabled])').length < 2) bad.push('U1: the last step must end with explicit buttons for where to go');
  w.querySelectorAll('button:disabled').forEach(b => {
    const reason = (b.getAttribute('title') || '').trim() || ((b.closest('.act, .navrow, .buttons, .saveblock') || {}).querySelector && (b.closest('.act, .navrow, .buttons, .saveblock').querySelector('.why') || {}).textContent) || '';
    if (!reason.trim()) bad.push('U5: a disabled button must say why: "' + b.textContent.trim() + '"');
  });
  w.querySelectorAll('button').forEach(b => { if (!(b.textContent.trim() || b.getAttribute('aria-label'))) bad.push('a11y: button has no name'); });
  w.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(c => {
    const named = c.getAttribute('aria-label') || c.getAttribute('aria-labelledby') || (c.id && w.querySelector('label[for="' + c.id + '"]')) || c.closest('label') || (c.closest('[role=group][aria-labelledby]'));
    if (!named) bad.push('a11y: field has no label: ' + (c.getAttribute('data-testid') || c.name || c.tagName));
  });
  if (w.querySelector('[data-ui=save]')) {
    const st = w.querySelector('.state');
    if (!st || !/saved/i.test(st.textContent)) bad.push('U3: a Save screen must show its state ("saved" / "changed, not saved yet")');
  }
  w.querySelectorAll('.errbox').forEach(e => { if (!e.closest('[data-ui=form]')) bad.push('U5: an error must sit inside the card of the action, not on its own'); });
  w.querySelectorAll('[data-empty]').forEach(e => { if (!new RegExp(actionWords, 'i').test(e.textContent)) bad.push('U8: an empty state must say what to do: ' + e.textContent.slice(0, 60)); });
  const body = Array.from(w.querySelectorAll('h1, h2, h3, .intro, .hint, label, button, p')).filter(e => !e.closest('.glossary')).map(e => e.textContent).join(' \n ').toLowerCase();
  jargon.forEach(t => {
    if (new RegExp('\\b' + t + 's?\\b').test(body) && !w.querySelector('.glossary [data-gloss="' + t + '"]')) bad.push('U8: "' + t + '" is used on this screen with no gloss');
  });
  return bad;
}
"""


def assert_ui_text(page, root, jargon=None):
    """Objective subset of the standard's text rules for one rendered wizard step (U1 titles and labels, U3 state, U5, U8)."""
    violations = page.evaluate(_TEXT_JS, [root, JARGON if jargon is None else jargon, ACTION_WORDS])
    assert not violations, "UI text violations: " + "; ".join(violations)
