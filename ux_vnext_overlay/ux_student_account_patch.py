from __future__ import annotations

import re
from pathlib import Path


def apply_student_account_patch(root: Path) -> None:
    base = root / 'templates' / 'base.html'
    if not base.is_file():
        raise SystemExit('UX_STUDENT_ACCOUNT_BASE_MISSING')
    text = base.read_text(encoding='utf-8')

    # Make logout visible on desktop rather than burying it inside the avatar menu.
    student_block = re.compile(
        r"(\{% if learner_ui_global %\}.*?<details class=\"student-account-menu\">.*?</details>)",
        re.S,
    )
    match = student_block.search(text)
    if not match:
        raise SystemExit('UX_STUDENT_ACCOUNT_DESKTOP_BLOCK_MISSING')
    block = match.group(1)
    if 'ux-student-logout-link' not in block:
        replacement = block + '<a class="ux-student-logout-link" href="{{url_for(\'logout\')}}">Logout</a>'
        text = text[:match.start()] + replacement + text[match.end():]

    # Ensure mobile More menu has a clearly labelled logout entry too.
    mobile_anchor = "<a href=\"{{url_for('account_settings')}}\">Settings</a>"
    mobile_logout = "<a class=\"ux-student-mobile-logout\" href=\"{{url_for('logout')}}\">Logout</a>"
    mobile_section = re.search(r"\{% if session.get\('user_id'\) and learner_ui_global %\}(.*?)\{% elif session.get\('user_id'\) and session.get\('role'\)=='teacher' %\}", text, re.S)
    if not mobile_section:
        raise SystemExit('UX_STUDENT_ACCOUNT_MOBILE_BLOCK_MISSING')
    section = mobile_section.group(1)
    if 'ux-student-mobile-logout' not in section:
        if mobile_anchor not in section:
            raise SystemExit('UX_STUDENT_ACCOUNT_MOBILE_SETTINGS_ANCHOR_MISSING')
        section_new = section.replace(mobile_anchor, mobile_anchor + mobile_logout, 1)
        text = text[:mobile_section.start(1)] + section_new + text[mobile_section.end(1):]

    style = '''\n<style id="ux-student-logout-style">
.ux-student-logout-link{display:inline-flex;align-items:center;padding:7px 10px;border-radius:10px;border:1px solid #dce7e6;color:#556562;text-decoration:none;font-size:.72rem;font-weight:850;white-space:nowrap}.ux-student-logout-link:hover{background:#f6f9f8;border-color:#c9dad8;color:#244c4a}.ux-student-mobile-logout{font-weight:900;color:#8f3d3d!important}
@media(max-width:760px){.ux-student-logout-link{display:none}}
</style>\n'''
    if 'ux-student-logout-style' not in text:
        if '</head>' not in text:
            raise SystemExit('UX_STUDENT_ACCOUNT_HEAD_MISSING')
        text = text.replace('</head>', style + '</head>', 1)

    for token in ('ux-student-logout-link','ux-student-mobile-logout',"url_for('logout')"):
        if token not in text:
            raise SystemExit('UX_STUDENT_ACCOUNT_POSTCHECK_MISSING:'+token)
    base.write_text(text, encoding='utf-8')
    print('SCOREMAX_UX_STUDENT_LOGOUT_VISIBLE desktop=true mobile=true existing_logout_route_reused=true', flush=True)
