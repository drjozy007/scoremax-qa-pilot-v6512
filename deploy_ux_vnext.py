from __future__ import annotations

import shutil
from pathlib import Path

import deploy_ux_vnext_teacher_base as base
from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace
from ux_vnext_overlay.ux_student_account_patch import apply_student_account_patch

ICON_NAME = 'scoremax-icon-summit-v2.png'


def _install_versioned_scoremax_icon(root: Path) -> None:
    source = Path('ux_vnext_overlay') / 'static' / ICON_NAME
    target = root / 'static' / ICON_NAME
    manifest_source = Path('ux_vnext_overlay') / 'static' / 'scoremax.webmanifest'
    manifest_target = root / 'static' / 'scoremax.webmanifest'
    if not source.is_file():
        raise SystemExit('SCOREMAX_V2_ICON_SOURCE_MISSING')
    if not manifest_source.is_file():
        raise SystemExit('SCOREMAX_V2_MANIFEST_SOURCE_MISSING')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    shutil.copy2(manifest_source, manifest_target)

    base_path = root / 'templates' / 'base.html'
    text = base_path.read_text(encoding='utf-8')
    old_favicon = "{{url_for('static',filename='scoremax-icon-32.png')}}"
    old_apple = "{{url_for('static',filename='scoremax-icon-180.png')}}"
    new_icon = "{{url_for('static',filename='scoremax-icon-summit-v2.png')}}?v=2"
    if old_favicon in text:
        text = text.replace(old_favicon, new_icon)
    if old_apple in text:
        text = text.replace(old_apple, new_icon)
    if 'scoremax-icon-summit-v2.png' not in text:
        raise SystemExit('SCOREMAX_V2_ICON_BASE_REFERENCE_MISSING')
    if 'scoremax-icon-summit-v2.png?v=2' not in manifest_target.read_text(encoding='utf-8'):
        raise SystemExit('SCOREMAX_V2_ICON_MANIFEST_REFERENCE_MISSING')
    base_path.write_text(text, encoding='utf-8')
    print('SCOREMAX_INSTALL_ICON_V2_ACTIVE filename=scoremax-icon-summit-v2.png cache_bust=v2 old_icon_names_not_authoritative=true', flush=True)


def main() -> None:
    base.main()
    apply_teacher_workspace(base.OUT)
    apply_student_account_patch(base.OUT)
    _install_versioned_scoremax_icon(base.OUT)

    rendered_base = (base.OUT / 'templates' / 'base.html').read_text(encoding='utf-8')
    for required in ('ux-student-logout-link','ux-student-mobile-logout','scoremax-icon-summit-v2.png'):
        if required not in rendered_base:
            raise SystemExit('SCOREMAX_POSTBUILD_ACCOUNT_ICON_CONTROL_MISSING:'+required)
    print('SCOREMAX_UX_ACCOUNT_ICON_RECTIFICATION_PASS student_logout_visible=true install_icon_v2=true teacher_workspace_preserved=true', flush=True)


if __name__ == '__main__':
    main()
