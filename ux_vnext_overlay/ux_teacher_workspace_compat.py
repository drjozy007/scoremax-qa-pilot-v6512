from __future__ import annotations

import re
from pathlib import Path

from ux_vnext_overlay import ux_teacher_workspace as core


def _replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    rx=re.compile(pattern,re.S)
    matches=list(rx.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'UX_TEACHER_{label}_BLOCK_MISMATCH:{len(matches)}')
    m=matches[0]
    return text[:m.start()]+m.group(1)+replacement+m.group(3)+text[m.end():]


def _refine_teacher_navigation(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    desktop_new='''<a href="{{url_for('teacher_dashboard')}}">Home</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('knowledge_home')}}">Resources</a><details class="ux-teacher-nav-menu"><summary>More</summary><div><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a></div></details>'''
    text=_replace_one(
        text,
        r"(\{% elif session\.get\('role'\)=='teacher' %\}\s*)(.*?)(\s*\{% elif session\.get\('role'\)=='parent' %\})",
        desktop_new,
        'DESKTOP_NAV',
    )
    mobile_new='''<a href="{{url_for('teacher_dashboard')}}">Teacher Home</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('knowledge_home')}}">Resources</a><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    text=_replace_one(
        text,
        r"(\{% elif session\.get\('user_id'\) and session\.get\('role'\)=='teacher' %\}\s*)(.*?)(\s*\{% elif session\.get\('user_id'\) and session\.get\('role'\)=='parent' %\})",
        mobile_new,
        'MOBILE_NAV',
    )
    if text.count('ux-teacher-nav-menu')!=1 or text.count('>Teacher Corner</a>')<2:
        raise SystemExit('UX_TEACHER_NAV_POSTCHECK_FAILED')
    path.write_text(text,encoding='utf-8')


def apply_teacher_workspace(root: Path) -> None:
    core._refine_teacher_navigation=_refine_teacher_navigation
    core.apply_teacher_workspace(root)
