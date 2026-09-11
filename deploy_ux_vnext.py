from __future__ import annotations

import shutil
from pathlib import Path

import deploy_ux_vnext_teacher_base as base
from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace
from ux_vnext_overlay.ux_student_account_patch import apply_student_account_patch

ICON_NAME = 'scoremax-icon-student-summit-v3.png'


def _install_agreed_scoremax_icon(root: Path) -> None:
    source = Path('ux_vnext_overlay') / 'static' / ICON_NAME
    target = root / 'static' / ICON_NAME
    manifest_source = Path('ux_vnext_overlay') / 'static' / 'scoremax.webmanifest'
    manifest_target = root / 'static' / 'scoremax.webmanifest'
    if not source.is_file():
        raise SystemExit('SCOREMAX_V3_AGREED_ICON_SOURCE_MISSING')
    if not manifest_source.is_file():
        raise SystemExit('SCOREMAX_V3_MANIFEST_SOURCE_MISSING')

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    shutil.copy2(manifest_source, manifest_target)

    base_path = root / 'templates' / 'base.html'
    text = base_path.read_text(encoding='utf-8')
    new_ref = "{{url_for('static',filename='scoremax-icon-student-summit-v3.png')}}?v=3"
    for old in (
        "{{url_for('static',filename='scoremax-icon-32.png')}}",
        "{{url_for('static',filename='scoremax-icon-180.png')}}",
        "{{url_for('static',filename='scoremax-icon-summit-v2.png')}}?v=2",
    ):
        text = text.replace(old, new_ref)

    old_mark = '<span class="scoremax-install-mark" aria-hidden="true"><i></i><i></i><i></i></span>'
    new_mark = '<img class="scoremax-install-art" src="'+new_ref+'" alt="">'
    if old_mark in text:
        text = text.replace(old_mark, new_mark)
    if 'scoremax-install-art' not in text:
        raise SystemExit('SCOREMAX_V3_VISIBLE_INSTALL_ART_MISSING')

    style = '''\n<style id="scoremax-agreed-icon-v3-style">
.scoremax-install-art{width:46px;height:46px;flex:0 0 46px;object-fit:cover;border-radius:12px;display:block;box-shadow:0 3px 10px rgba(15,23,42,.14)}
.scoremax-install-help-card .scoremax-install-art{width:68px;height:68px;flex-basis:68px;border-radius:16px;margin:0 auto 8px}
</style>\n'''
    if 'scoremax-agreed-icon-v3-style' not in text:
        if '</head>' not in text:
            raise SystemExit('SCOREMAX_V3_HEAD_MARKER_MISSING')
        text = text.replace('</head>', style + '</head>', 1)

    manifest = manifest_target.read_text(encoding='utf-8')
    if 'scoremax-icon-student-summit-v3.png?v=3' not in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_REFERENCE_MISSING')
    if 'scoremax-icon-summit-v2.png' in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_OLD_ICON_STILL_AUTHORITATIVE')
    if 'scoremax-icon-student-summit-v3.png' not in text:
        raise SystemExit('SCOREMAX_V3_BASE_REFERENCE_MISSING')

    base_path.write_text(text, encoding='utf-8')
    print(
        'SCOREMAX_INSTALL_AGREED_ICON_V3_ACTIVE '
        'filename=scoremax-icon-student-summit-v3.png cache_bust=v3 '
        'artwork=student_climbing_mountain_steps_gold_star '
        'served_image_visual_acceptance_required=true',
        flush=True,
    )


def main() -> None:
    base.main()
    apply_teacher_workspace(base.OUT)
    apply_student_account_patch(base.OUT)
    _install_agreed_scoremax_icon(base.OUT)

    rendered_base = (base.OUT / 'templates' / 'base.html').read_text(encoding='utf-8')
    for required in ('ux-student-logout-link','ux-student-mobile-logout','scoremax-icon-student-summit-v3.png','scoremax-install-art'):
        if required not in rendered_base:
            raise SystemExit('SCOREMAX_POSTBUILD_ACCOUNT_ICON_CONTROL_MISSING:'+required)
    print(
        'SCOREMAX_UX_ACCOUNT_ICON_RECTIFICATION_V3_PASS '
        'student_logout_visible=true landing_install_art=true '
        'teacher_workspace_preserved=true',
        flush=True,
    )


if __name__ == '__main__':
    main()
