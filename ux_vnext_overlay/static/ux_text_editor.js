(() => {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .ux-text-editor-toolbar{position:fixed;right:18px;bottom:18px;z-index:9999;width:min(340px,calc(100vw - 36px));background:rgba(15,23,42,.96);color:#fff;border:1px solid rgba(255,255,255,.12);border-radius:18px;box-shadow:0 18px 55px rgba(15,23,42,.28);padding:14px;backdrop-filter:blur(16px);font:500 14px/1.4 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .ux-text-editor-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.ux-text-editor-title strong{font-size:15px}.ux-text-editor-title span{font-size:11px;font-weight:800;letter-spacing:.08em;color:#93c5fd;text-transform:uppercase}
    .ux-text-editor-actions{display:flex;gap:8px;flex-wrap:wrap}.ux-text-editor-actions button{border:0;border-radius:999px;padding:9px 12px;background:#fff;color:#0f172a;font-weight:800;cursor:pointer}.ux-text-editor-actions button.secondary{background:#2563eb;color:#fff}.ux-text-editor-actions button.quiet{background:rgba(255,255,255,.1);color:#e2e8f0}
    .ux-text-editor-status{margin-top:9px;color:#cbd5e1;font-size:12px}
    body.ux-text-editing [data-ux-edit-key]{outline:2px dashed #f59e0b;outline-offset:4px;border-radius:4px;cursor:text;background-color:rgba(254,243,199,.35)}
    body.ux-text-editing [data-ux-edit-key]:focus{outline-style:solid;outline-color:#2563eb;background-color:rgba(219,234,254,.6)}
    @media(max-width:640px){.ux-text-editor-toolbar{left:10px;right:10px;bottom:10px;width:auto}.ux-text-editor-actions button{padding:8px 10px}}
  `;
  document.head.appendChild(style);

  const editables = Array.from(document.querySelectorAll('[data-ux-edit-key]'));
  if (!editables.length) return;

  const STORAGE_KEY = 'scoremax-ux-text-edits:v1:' + window.location.pathname;
  const originals = {};
  let editing = false;

  const readSaved = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch (_) { return {}; }
  };

  const writeSaved = (value) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)); }
    catch (_) {}
  };

  const cleanText = (node) => (node.textContent || '').replace(/\s+/g, ' ').trim();

  editables.forEach((node) => {
    const key = node.dataset.uxEditKey;
    originals[key] = cleanText(node);
  });

  const saved = readSaved();
  editables.forEach((node) => {
    const key = node.dataset.uxEditKey;
    if (typeof saved[key] === 'string') node.textContent = saved[key];
  });

  const toolbar = document.createElement('aside');
  toolbar.className = 'ux-text-editor-toolbar';
  toolbar.setAttribute('aria-label', 'Staging text editor');
  toolbar.innerHTML = `
    <div class="ux-text-editor-title"><strong>Text review</strong><span>Staging only</span></div>
    <div class="ux-text-editor-actions">
      <button type="button" data-action="toggle">Edit text</button>
      <button type="button" data-action="copy" class="secondary">Copy changes</button>
      <button type="button" data-action="reset" class="quiet">Reset</button>
    </div>
    <div class="ux-text-editor-status" role="status" aria-live="polite">No production changes</div>`;
  document.body.appendChild(toolbar);

  const status = toolbar.querySelector('.ux-text-editor-status');
  const toggleButton = toolbar.querySelector('[data-action="toggle"]');

  const getChanges = () => {
    const changes = [];
    editables.forEach((node) => {
      const key = node.dataset.uxEditKey;
      const current = cleanText(node);
      if (current !== originals[key]) changes.push({ key, from: originals[key], to: current });
    });
    return changes;
  };

  const persist = () => {
    const state = {};
    editables.forEach((node) => {
      const key = node.dataset.uxEditKey;
      const current = cleanText(node);
      if (current !== originals[key]) state[key] = current;
    });
    writeSaved(state);
    const count = Object.keys(state).length;
    status.textContent = count ? `${count} text change${count === 1 ? '' : 's'} saved in this browser` : 'No text changes yet';
  };

  const setEditing = (on) => {
    editing = on;
    document.body.classList.toggle('ux-text-editing', on);
    editables.forEach((node) => {
      if (on) {
        node.setAttribute('contenteditable', 'true');
        node.setAttribute('spellcheck', 'true');
        node.setAttribute('role', 'textbox');
        node.setAttribute('aria-label', `Edit text: ${node.dataset.uxEditKey}`);
      } else {
        node.removeAttribute('contenteditable');
        node.removeAttribute('spellcheck');
        node.removeAttribute('role');
        node.removeAttribute('aria-label');
      }
    });
    toggleButton.textContent = on ? 'Done editing' : 'Edit text';
    status.textContent = on ? 'Click highlighted text and type. Changes stay on this browser.' : `${getChanges().length} change${getChanges().length === 1 ? '' : 's'} saved in this browser`;
  };

  editables.forEach((node) => {
    node.addEventListener('input', persist);
    node.addEventListener('blur', persist);
    node.addEventListener('keydown', (event) => {
      if (!editing) return;
      if (event.key === 'Enter') { event.preventDefault(); node.blur(); }
      if (event.key === 'Escape') { event.preventDefault(); node.blur(); }
    });
    node.addEventListener('click', (event) => {
      if (editing && (node.closest('a') || node.tagName === 'A')) {
        event.preventDefault(); event.stopPropagation();
      }
    }, true);
  });

  const copyText = async (text) => {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (_) {
      const area = document.createElement('textarea');
      area.value = text; area.style.position = 'fixed'; area.style.opacity = '0';
      document.body.appendChild(area); area.focus(); area.select();
      const ok = document.execCommand('copy'); area.remove(); return ok;
    }
  };

  toolbar.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'toggle') { setEditing(!editing); return; }
    if (action === 'copy') {
      persist(); const changes = getChanges();
      if (!changes.length) { status.textContent = 'Nothing to copy yet'; return; }
      const lines = ['ScoreMax UX text changes', `Page: ${window.location.href}`, ''];
      changes.forEach((change, index) => {
        lines.push(`${index + 1}. ${change.key}`, `FROM: ${change.from}`, `TO: ${change.to}`, '');
      });
      const ok = await copyText(lines.join('\n'));
      status.textContent = ok ? `${changes.length} change${changes.length === 1 ? '' : 's'} copied — paste them into ChatGPT` : 'Copy failed — please select the text manually';
      return;
    }
    if (action === 'reset') {
      if (!window.confirm('Reset all text edits on this staging page?')) return;
      editables.forEach((node) => { node.textContent = originals[node.dataset.uxEditKey]; });
      try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
      status.textContent = 'Text edits reset';
    }
  });

  persist();
})();

(() => {
  'use strict';
  if (window.__scoremaxCalculatorDrawerReady) return;
  window.__scoremaxCalculatorDrawerReady = true;
  const panel = document.querySelector('.ux-inline-calculator');
  if (!panel) return;

  const style = document.createElement('style');
  style.id = 'ux-calculator-drawer-style';
  style.textContent = `
    .ux-inline-calculator{position:fixed!important;top:0!important;right:0!important;bottom:0!important;left:auto!important;z-index:10020!important;width:min(500px,calc(100vw - 28px))!important;max-width:none!important;height:100dvh!important;margin:0!important;padding:0!important;background:#fff!important;box-shadow:-24px 0 60px rgba(15,23,42,.2)!important;transform:translateX(104%)!important;transition:transform .24s ease!important;overflow:auto!important;visibility:hidden!important}
    .ux-inline-calculator.is-open{transform:translateX(0)!important;visibility:visible!important}
    .ux-inline-calculator .ux-inline-calculator-inner{min-height:100%!important;border:0!important;border-radius:0!important;padding:64px 24px 30px!important;box-shadow:none!important;background:#fff!important}
    .ux-calculator-side-tab{position:fixed;right:16px;top:46%;z-index:10010;transform:translateY(-50%);display:flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:11px 15px;background:linear-gradient(135deg,#3FA6A3,#2F7F7D);color:#fff;box-shadow:0 10px 28px rgba(47,127,125,.26);font:850 13px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:.01em;cursor:pointer;writing-mode:horizontal-tb;white-space:nowrap}
    .ux-calculator-side-tab:before{content:'⌗';display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:rgba(255,255,255,.16);font-size:13px}
    .ux-calculator-side-tab:hover,.ux-calculator-side-tab:focus-visible{background:linear-gradient(135deg,#378F8C,#236765);transform:translateY(-50%) translateX(-2px)}
    .ux-calculator-drawer-close{position:absolute;top:16px;right:16px;z-index:2;width:36px;height:36px;border:1px solid #dce7e6;border-radius:50%;background:#f7fbfa;color:#234847;font:800 20px/1 system-ui;cursor:pointer}
    .ux-calculator-drawer-backdrop{position:fixed;inset:0;z-index:10015;background:rgba(15,23,42,.28);opacity:0;pointer-events:none;transition:opacity .2s ease}.ux-calculator-drawer-backdrop.is-open{opacity:1;pointer-events:auto}body.ux-calculator-open{overflow:hidden}
    @media(max-width:700px){.ux-calculator-side-tab{top:auto;right:12px;bottom:14px;transform:none;border-radius:999px;padding:11px 14px}.ux-calculator-side-tab:hover,.ux-calculator-side-tab:focus-visible{transform:translateY(-1px)}.ux-inline-calculator{top:auto!important;bottom:0!important;width:100%!important;height:min(86dvh,760px)!important;transform:translateY(105%)!important;border-radius:22px 22px 0 0!important}.ux-inline-calculator.is-open{transform:translateY(0)!important}.ux-inline-calculator .ux-inline-calculator-inner{padding:58px 16px 24px!important}}
  `;
  document.head.appendChild(style);

  const toggle = document.createElement('button');
  toggle.type = 'button'; toggle.className = 'ux-calculator-side-tab'; toggle.textContent = 'Calculators';
  toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-controls', 'uxLandingCalculatorDrawer');
  panel.id = 'uxLandingCalculatorDrawer'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); panel.setAttribute('aria-label', 'Admission calculators');
  const close = document.createElement('button'); close.type = 'button'; close.className = 'ux-calculator-drawer-close'; close.setAttribute('aria-label', 'Close calculators'); close.textContent = '×'; panel.prepend(close);
  const backdrop = document.createElement('div'); backdrop.className = 'ux-calculator-drawer-backdrop'; backdrop.setAttribute('aria-hidden', 'true');
  document.body.appendChild(backdrop); document.body.appendChild(toggle); document.body.appendChild(panel);

  const setOpen = (open) => {
    panel.classList.toggle('is-open', open); backdrop.classList.toggle('is-open', open); document.body.classList.toggle('ux-calculator-open', open); toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) window.setTimeout(() => panel.querySelector('input')?.focus(), 80); else toggle.focus();
  };
  toggle.addEventListener('click', () => setOpen(true)); close.addEventListener('click', () => setOpen(false)); backdrop.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && panel.classList.contains('is-open')) setOpen(false); });
})();
