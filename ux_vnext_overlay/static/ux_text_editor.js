(() => {
  'use strict';

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
      if (event.key === 'Enter') {
        event.preventDefault();
        node.blur();
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        node.blur();
      }
    });
    node.addEventListener('click', (event) => {
      if (editing && (node.closest('a') || node.tagName === 'A')) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);
  });

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const area = document.createElement('textarea');
      area.value = text;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.focus(); area.select();
      const ok = document.execCommand('copy');
      area.remove();
      return ok;
    }
  };

  toolbar.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;

    if (action === 'toggle') {
      setEditing(!editing);
      return;
    }

    if (action === 'copy') {
      persist();
      const changes = getChanges();
      if (!changes.length) {
        status.textContent = 'Nothing to copy yet';
        return;
      }
      const lines = ['ScoreMax UX text changes', `Page: ${window.location.href}`, ''];
      changes.forEach((change, index) => {
        lines.push(`${index + 1}. ${change.key}`);
        lines.push(`FROM: ${change.from}`);
        lines.push(`TO: ${change.to}`);
        lines.push('');
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
