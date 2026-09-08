(() => {
  const blockedTerms = ['coming next','mdcat','ecat','fsc','matric','grade 9','grade 10'];
  const form = document.querySelector('.ux-login-clean form');
  if (!form) return;

  const candidates = [...document.querySelectorAll('aside, section, article, .card, .panel, .programme, .programmes')];
  for (const el of candidates) {
    if (el.closest('.ux-login-clean')) continue;
    const text = (el.textContent || '').toLowerCase();
    if (!text.includes('coming next')) continue;
    if (!blockedTerms.some(term => text.includes(term))) continue;
    el.remove();
  }
})();
