from pathlib import Path

from deploy_ux_vnext_recovery import main as recovery_main


def _install_post_init_teacher_preview() -> None:
    path=Path('scoremax_runtime_v669b')/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    old='scoremax.init()\napplication=scoremax.app'
    new="scoremax.init()\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()\napplication=scoremax.app"
    if 'ensure_teacher_preview()' not in text:
        if old not in text:
            raise SystemExit('SCOREMAX_TEACHER_PREVIEW_POST_INIT_ANCHOR_MISSING')
        text=text.replace(old,new,1)
    path.write_text(text,encoding='utf-8')
    if 'scoremax.init()\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()' not in text:
        raise SystemExit('SCOREMAX_TEACHER_PREVIEW_POST_INIT_CONTROL_MISSING')
    print('SCOREMAX_UX_TEACHER_PREVIEW_STARTUP_ORDER_PASS after_database_init=true',flush=True)


def main() -> None:
    recovery_main()
    _install_post_init_teacher_preview()


if __name__ == '__main__':
    main()
