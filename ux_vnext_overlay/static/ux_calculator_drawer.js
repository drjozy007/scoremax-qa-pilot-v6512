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
