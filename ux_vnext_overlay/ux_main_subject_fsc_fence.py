from __future__ import annotations

from pathlib import Path

_MARKER='SCOREMAX_MAIN_SCIENCE_RENDER_FSC_FENCE_V1'

_OLD="""        if endpoint=='subject_detail':
            subject=(request.view_args or {}).get('subject','').strip(); conn=_connect()
            try: chapters=_chapter_snapshots(conn,session['user_id'],subject); snap=_subject_snapshot(conn,session['user_id'],subject)
            finally: conn.close()
            return render_template('ux_subject_chapters.html',subject=subject,chapters=chapters,chapter_count=snap['chapter_count'],started_chapters=snap['started_chapters'],answered=snap['answered'],avg_accuracy=snap['avg_accuracy'],learn_url=url_for('ux_student_learn'))
"""

_NEW="""        if endpoint=='subject_detail':
            # SCOREMAX_MAIN_SCIENCE_RENDER_FSC_FENCE_V1
            # The permanent Biology/Chemistry/Physics tabs are FSc surfaces. MDCAT
            # owns a separate catalogue route and must never leak into these pages.
            subject=(request.view_args or {}).get('subject','').strip(); conn=_connect()
            try:
                if subject.casefold() in {'biology','chemistry','physics'}:
                    row=conn.execute("SELECT COALESCE(academic_level,'') academic_level,COALESCE(active_programme,'') active_programme FROM users WHERE id=?",(session['user_id'],)).fetchone()
                    level=((row['academic_level'] if row else '') or '').strip().casefold()
                    if 'fsc' in level:
                        target_programme='FSc Part 2' if ('part 2' in level or 'year 2' in level or level in {'fsc 2','fsc2'}) else 'FSc Part 1'
                        if ((row['active_programme'] if row else '') or '').strip()!=target_programme:
                            conn.execute("UPDATE users SET active_programme=? WHERE id=?",(target_programme,session['user_id']))
                            conn.commit()
                chapters=_chapter_snapshots(conn,session['user_id'],subject)
                snap=_subject_snapshot(conn,session['user_id'],subject)
            finally: conn.close()
            return render_template('ux_subject_chapters.html',subject=subject,chapters=chapters,chapter_count=snap['chapter_count'],started_chapters=snap['started_chapters'],answered=snap['answered'],avg_accuracy=snap['avg_accuracy'],learn_url=url_for('ux_student_learn'))
"""


def apply_main_subject_fsc_fence(root: Path) -> None:
    path=Path(root)/'ux_student_batch.py'
    if not path.is_file():
        raise SystemExit('SCOREMAX_MAIN_SCIENCE_RUNTIME_MISSING')
    text=path.read_text(encoding='utf-8')
    if _MARKER in text:
        return
    matches=text.count(_OLD)
    if matches!=1:
        raise SystemExit(f'SCOREMAX_MAIN_SCIENCE_RENDER_ANCHOR_MISMATCH:matches={matches}')
    text=text.replace(_OLD,_NEW,1)
    required=(
        _MARKER,
        "subject.casefold() in {'biology','chemistry','physics'}",
        "target_programme='FSc Part 2'",
        "else 'FSc Part 1'",
        "UPDATE users SET active_programme=? WHERE id=?",
        "chapters=_chapter_snapshots(conn,session['user_id'],subject)",
    )
    missing=[token for token in required if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_MAIN_SCIENCE_RENDER_CONTROL_MISSING:'+','.join(missing))
    compile(text,str(path),'exec')
    path.write_text(text,encoding='utf-8')
    print(
        'SCOREMAX_MAIN_SCIENCE_RENDER_FSC_FENCE_PASS '
        'biology=true chemistry=true physics=true mdcat_separate=true '
        'fsc_year_from_academic_level=true before_request_order_bypassed=true',
        flush=True,
    )
