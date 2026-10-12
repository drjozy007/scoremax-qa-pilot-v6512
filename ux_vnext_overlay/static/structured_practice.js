/* Blank learner-created response fields. No marking evidence is sent to this code. */
(() => {
  for (const root of document.querySelectorAll('[data-structured-practice]')) {
    if (root.dataset.initialized) continue;
    root.dataset.initialized = 'true';
    const value = root.querySelector('[data-structured-value]');
    const statements = root.querySelector('[data-statements]');
    const equations = root.querySelector('[data-equations]');
    const quantities = root.querySelector('[data-values]');
    const status = root.querySelector('[data-structured-status]');
    function serialize() {
      const assertions = [...statements.children].map(row => Object.fromEntries(
        [...row.querySelectorAll('input')].map(input => [input.dataset.field, input.value.trim()])
      )).filter(row => Object.values(row).some(Boolean));
      const working = [...equations.querySelectorAll('input')].map(x => x.value.trim()).filter(Boolean);
      const values = [...quantities.children].map(row => Object.fromEntries([...row.querySelectorAll('input')].map(input => [input.dataset.field,input.value.trim()]))).filter(row => Object.values(row).some(Boolean));
      value.value = JSON.stringify({version:'PH-STRUCTURED-PRACTICE-1', assertions, equations:working, values});
      status.textContent = '';
      return assertions.every(row => Object.values(row).every(Boolean));
    }
    function add(container, fields, saved={}) {
      if (container.children.length >= 50) return;
      const row = document.createElement('fieldset');
      for (const field of fields) {
        const label = document.createElement('label');
        label.textContent = field[0].toUpperCase() + field.slice(1);
        const input = document.createElement('input');
        input.type = 'text'; input.maxLength = 1000; input.autocomplete = 'off';
        input.dataset.field = field; input.value = saved[field] || '';
        input.addEventListener('input', serialize); label.append(input); row.append(label);
      }
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove';
      remove.addEventListener('click', () => {row.remove();serialize();});
      row.append(remove); container.append(row);
    }
    let saved;
    try {saved = JSON.parse(value.value);} catch (_) {saved = null;}
    if (saved && saved.version === 'PH-STRUCTURED-PRACTICE-1') {
      for (const row of saved.assertions || []) add(statements, ['subject','relation','object'], row);
      for (const row of saved.values || []) add(quantities, ['value','unit','working'], row);
      for (const row of saved.equations || []) add(equations, ['equation'], {equation:row});
    } else if (value.value.trim()) {
      status.textContent = 'The saved response uses a different format. It has not been replaced.';
      root.querySelectorAll('button').forEach(button => button.disabled = true);
      root.closest('form').addEventListener('submit', event => event.preventDefault());
      continue;
    } else add(statements, ['subject','relation','object']);
    root.querySelector('[data-add-statement]').addEventListener('click', () => add(statements, ['subject','relation','object']));
    root.querySelector('[data-add-equation]').addEventListener('click', () => add(equations, ['equation']));
    root.querySelector('[data-add-value]').addEventListener('click', () => add(quantities, ['value','unit','working']));
    root.closest('form').addEventListener('submit', event => {
      if (!serialize()) {event.preventDefault();status.textContent='Complete all three fields of each statement or remove that statement.';}
    });
  }
})();
