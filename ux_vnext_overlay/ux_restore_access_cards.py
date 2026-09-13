from __future__ import annotations

from pathlib import Path

_MARKER='SCOREMAX_SERVER_RENDERED_ACCESS_CARDS_V1'

_ACCESS_SECTION='''
  <!-- SCOREMAX_SERVER_RENDERED_ACCESS_CARDS_V1 -->
  <section class="ux-home-plans" aria-labelledby="ux-home-plans-title">
    <div class="ux-home-plans-head">
      <div><p class="eyebrow">YOUR SCOREMAX ACCESS</p><h2 id="ux-home-plans-title">Silver, Gold and Platinum.</h2></div>
      <a href="{{url_for('access_account')}}">Compare access →</a>
    </div>
    <div class="ux-home-plan-grid">
      <a class="ux-home-plan silver" href="{{url_for('access_account')}}"><strong>Silver</strong><span>Build strong foundations and structured progress.</span><b>Explore Silver →</b></a>
      <a class="ux-home-plan gold" href="{{url_for('access_account')}}"><strong>Gold</strong><span>Go deeper with broader mastery and exam preparation.</span><b>Explore Gold →</b></a>
      <a class="ux-home-plan platinum" href="{{url_for('access_account')}}"><strong>Platinum</strong><span>Use the fullest ScoreMax learning and mastery journey.</span><b>Explore Platinum →</b></a>
    </div>
  </section>

'''


def apply_restore_access_cards(root: Path) -> None:
    path=Path(root)/'templates'/'student.html'
    if not path.is_file():
        raise SystemExit('SCOREMAX_ACCESS_CARDS_STUDENT_TEMPLATE_MISSING')
    text=path.read_text(encoding='utf-8')
    if _MARKER in text:
        return
    anchor='  <section class="home-two-column">\n'
    if text.count(anchor)!=1:
        raise SystemExit(f'SCOREMAX_ACCESS_CARDS_ANCHOR_MISMATCH:matches={text.count(anchor)}')
    text=text.replace(anchor,_ACCESS_SECTION+anchor,1)
    required=(
        _MARKER,
        '<strong>Silver</strong>',
        '<strong>Gold</strong>',
        '<strong>Platinum</strong>',
        "url_for('access_account')",
        'Build strong foundations and structured progress.',
        'Go deeper with broader mastery and exam preparation.',
        'Use the fullest ScoreMax learning and mastery journey.',
    )
    missing=[token for token in required if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_ACCESS_CARDS_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    path.write_text(text,encoding='utf-8')
    print('SCOREMAX_ACCESS_CARDS_RESTORED server_rendered=true silver=true gold=true platinum=true destination=packages_access prices_unchanged=true',flush=True)
