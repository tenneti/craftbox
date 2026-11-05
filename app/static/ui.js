// Shared UI helpers implementing guidelines/ui-standard.md for Craftbox (window.ui).
// Pages call these instead of re-implementing requests, steppers, nav rows, errors or progress panels.
window.ui = (() => {
  function el(tag, props = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === 'class') node.className = v;
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else if (v === true) node.setAttribute(k, '');
      else if (v !== false && v != null) node.setAttribute(k, v);
    }
    node.append(...kids.filter(k => k != null && k !== false));
    return node;
  }

  const mm = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

  function formatError(detail) {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
    if (detail && detail.message) {
      const more = (detail.errors || []).map(e => `${e.path}: ${e.message}`).join('; ');
      return more ? `${detail.message} — ${more}` : detail.message;
    }
    return JSON.stringify(detail);
  }

  // U-none: one JSON request helper. Throws Error(message) with the server's explanation.
  async function call(path, method = 'GET', body) {
    const options = {method, headers: {}};
    if (body !== undefined) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
    const response = await fetch(path, options);
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { /* non-JSON body */ }
    if (!response.ok) {
      const err = new Error(data && data.detail ? formatError(data.detail) : `HTTP ${response.status}`);
      err.status = response.status;
      throw err;
    }
    return data;
  }

  // U3/U4: text fields whose typed text lives in `store`, so a redraw never empties them.
  function fields(store, onChange) {
    return (key, init = '', props = {}, tag = 'input') => {
      const {onedit, ...rest} = props;
      const node = el(tag, rest);
      if (store[key] === undefined) store[key] = init;
      node.value = store[key];
      node.addEventListener('input', () => { store[key] = node.value; if (onChange) onChange(); if (onedit) onedit(node.value); });
      return node;
    };
  }

  // U1: step list. defs = [{id, title, intro}]
  function steps(defs) {
    return {
      count: defs.length,
      list: () => defs,
      title: n => `Step ${n} of ${defs.length}: ${defs[n - 1].title}`,
      intro: n => defs[n - 1].intro,
      after: n => defs[n] || null,
      before: n => defs[n - 2] || null,
    };
  }

  function stepper({defs, current, reached, onGo}) {
    const list = el('ol', {class: 'steps'});
    defs.forEach((d, i) => {
      const n = i + 1;
      const state = n === current ? 'current' : (n < current ? 'done' : 'todo');
      const can = n <= reached && n !== current;
      list.append(el('li', {class: `step ${state}`},
        el('button', {type: 'button', class: 'stepbtn', 'data-step-target': n, disabled: !can, 'aria-current': n === current ? 'step' : null,
          title: can ? `Go to step ${n}` : (n === current ? 'You are here' : 'Finish the earlier steps first'),
          onclick: () => onGo(n)}, el('span', {class: 'num'}, state === 'done' ? '✓' : String(n)), el('span', {class: 'lbl'}, d.short || d.title))));
    });
    return el('nav', {'data-ui': 'stepper', 'aria-label': 'Steps'}, list);
  }

  // U1/U2/U5: Back / Next row. A disabled Next says why, beside the button.
  function nav({n, total, back, next}) {
    const row = el('div', {class: 'navrow'});
    if (n > 1 && back) row.append(el('button', {type: 'button', 'data-ui': 'back', 'data-testid': 'wizard-back', onclick: back.onclick}, back.label));
    if (n < total && next) {
      row.append(el('button', {type: 'button', class: 'primary', 'data-ui': 'next', 'data-testid': 'wizard-next', disabled: !!next.disabled, title: next.disabled ? next.why : null, onclick: next.onclick}, next.label));
      if (next.disabled && next.why) row.append(el('span', {class: 'why', 'data-testid': 'next-why'}, next.why));
    }
    return row;
  }

  // U5: an error inside the card of the action that failed.
  function errorBox(message, testid) {
    return el('div', {class: 'errbox', role: 'alert', 'data-testid': testid || 'error'}, message);
  }
  function reveal(testid) {
    const node = document.querySelector(`[data-testid="${testid}"]`);
    if (node && node.scrollIntoView) node.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }

  // U6: background-work panel with elapsed time. Timers are cleared by ui.clearTimers() on every redraw.
  const timers = new Set();
  function clearTimers() { for (const t of timers) clearInterval(t); timers.clear(); }
  function progress({what, startedAt = Date.now()}) {
    const time = el('span', {class: 'elapsed'}, '0:00');
    const node = el('div', {class: 'progress', 'data-ui': 'progress', 'data-testid': 'progress', role: 'status'},
      el('span', {class: 'spinner', 'aria-hidden': 'true'}), el('span', {}, `${what}… `), time);
    const tick = () => { time.textContent = mm((Date.now() - startedAt) / 1000); };
    timers.add(setInterval(tick, 500)); tick();
    return node;
  }

  return {el, mm, call, fields, steps, stepper, nav, errorBox, reveal, progress, clearTimers, formatError};
})();
