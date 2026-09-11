from __future__ import annotations

from pathlib import Path


def apply_student_account_patch(root: Path) -> None:
    base = root / 'templates' / 'base.html'
    if not base.is_file():
        raise SystemExit('UX_STUDENT_ACCOUNT_BASE_MISSING')
    text = base.read_text(encoding='utf-8')

    # Add a visible desktop logout immediately after the stable student Progress link.
    if 'ux-student-logout-link' not in text:
        progress_token = '>Progress</a>'
        first = text.find(progress_token)
        if first < 0:
            raise SystemExit('UX_STUDENT_ACCOUNT_PROGRESS_ANCHOR_MISSING')
        end = first + len(progress_token)
        logout = '<a class="ux-student-logout-link" href="{{url_for(\'logout\')}}">Logout</a>'
        text = text[:end] + logout + text[end:]

    # Mobile learner menu already contains Logout in the accepted baseline; keep it,
    # but make it visually explicit if present.
    if 'ux-student-mobile-logout' not in text:
        mobile_logout = '<a href="{{url_for(\'logout\')}}">Logout</a>'
        if mobile_logout in text:
            text = text.replace(mobile_logout, '<a class="ux-student-mobile-logout" href="{{url_for(\'logout\')}}">Logout</a>', 1)

    style = '''\n<style id="ux-student-logout-style">
.ux-student-logout-link{display:inline-flex;align-items:center;padding:7px 10px;border-radius:10px;border:1px solid #dce7e6;color:#556562;text-decoration:none;font-size:.72rem;font-weight:850;white-space:nowrap}.ux-student-logout-link:hover{background:#f6f9f8;border-color:#c9dad8;color:#244c4a}.ux-student-mobile-logout{font-weight:900;color:#8f3d3d!important}
@media(max-width:760px){.ux-student-logout-link{display:none}}
</style>\n'''
    if 'ux-student-logout-style' not in text:
        if '</head>' not in text:
            raise SystemExit('UX_STUDENT_ACCOUNT_HEAD_MISSING')
        text = text.replace('</head>', style + '</head>', 1)

    for token in ('ux-student-logout-link',"url_for('logout')"):
        if token not in text:
            raise SystemExit('UX_STUDENT_ACCOUNT_POSTCHECK_MISSING:'+token)
    base.write_text(text, encoding='utf-8')
    print('SCOREMAX_UX_STUDENT_LOGOUT_VISIBLE desktop=true mobile_existing=true existing_logout_route_reused=true', flush=True)
