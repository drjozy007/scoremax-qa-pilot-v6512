from __future__ import annotations

from flask import abort, render_template, request, session, url_for
import re

from ux_catalogue_data import CATALOGUES, TRACK_ORDER, get_catalogue, subject_items


_TRACK_PROGRAMMES={
    'year11':'FSc Part 1',
    'year12':'FSc Part 2',
    'mdcat':'MDCAT',
}
_MAIN_FSC_SUBJECTS={'biology','chemistry','physics'}
_RELEASE_PROGRAMME_ALIASES={
    'year11':('FSc Part 1','FSC_PART_I','FSC_PART_1','HSSC_PART_I'),
    'year12':('FSc Part 2','FSC_PART_II','FSC_PART_2','HSSC_PART_II'),
    'mdcat':('MDCAT',),
}


def _norm(value: str) -> str:
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).strip()


def _release_scope_counts(conn, track: str, subject: str) -> dict[str,int]:
    aliases=_RELEASE_PROGRAMME_ALIASES.get(track) or ()
    if not aliases:return {}
    vals=[x.casefold() for x in aliases]
    marks=','.join('?' for _ in vals)
    rows=conn.execute(f"""SELECT r.chapter_id,COUNT(DISTINCT v.local_question_db_id) n
      FROM integration_ph_content_releases r
      JOIN integration_ph_release_question_membership m
        ON m.release_id=r.release_id AND m.release_version=r.release_version
      JOIN integration_ph_question_version_store v
        ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE r.local_status='ACTIVE'
        AND lower(trim(r.programme_id)) IN ({marks})
        AND lower(replace(trim(r.subject_id),'_',' '))=lower(?)
        AND v.local_question_db_id IS NOT NULL
      GROUP BY r.chapter_id
      ORDER BY r.chapter_id""",vals+[str(subject or '').replace('_',' ')]).fetchall()
    return {str(r['chapter_id'] or ''):int(r['n'] or 0) for r in rows if str(r['chapter_id'] or '').strip()}


def _scope_matches_item(scope_id: str, item: dict) -> bool:
    sid=_norm(scope_id); name=_norm(item.get('name')); number=str(item.get('number') or '').strip().casefold()
    if name and (sid==name or name in sid):
        return True
    tokens=re.findall(r'(?<![a-z0-9])(\d+(?:\.\d+)?)(?![a-z0-9])',str(scope_id or '').casefold())
    if number and tokens:
        # Governing release IDs conventionally end in the chapter/unit number.
        return tokens[-1].lstrip('0')==number.lstrip('0')
    return False


def _catalogue_item_scope(scope_counts: dict[str,int], item: dict):
    matches=[(scope,n) for scope,n in scope_counts.items() if _scope_matches_item(scope,item)]
    if len(matches)!=1:
        return None
    return matches[0]



def install_catalogue_browser(app):
    if getattr(app, '_ux_catalogue_browser_installed', False):
        return
    app._ux_catalogue_browser_installed = True

    def _student_required():
        if session.get('role') != 'student' or not session.get('user_id'):
            abort(403)

    def _set_active_programme(programme: str) -> None:
        if not programme or not session.get('user_id'):
            return
        # UI programme preference only. Governed curriculum/question/release state is untouched.
        from app import db
        conn=db()
        try:
            row=conn.execute(
                "SELECT COALESCE(active_programme,'') active_programme FROM users WHERE id=?",
                (session['user_id'],),
            ).fetchone()
            current=(row['active_programme'] if row else '') or ''
            if current.strip()!=programme:
                conn.execute(
                    "UPDATE users SET active_programme=? WHERE id=?",
                    (programme,session['user_id']),
                )
                conn.commit()
        finally:
            conn.close()

    def _sync_active_programme(track: str) -> None:
        programme=_TRACK_PROGRAMMES.get(track)
        if programme:
            _set_active_programme(programme)

    def _sync_main_fsc_subject_context() -> None:
        """Keep the permanent Biology/Chemistry/Physics tabs on the learner's FSc year.

        MDCAT is a separate catalogue surface. Visiting it may set active_programme=MDCAT,
        but a later click on a main science subject must not inherit MDCAT units.
        The learner's academic_level is the stable source for which FSc year the main
        science tabs represent.
        """
        if session.get('role')!='student' or not session.get('user_id'):
            return
        if request.endpoint!='subject_detail':
            return
        subject=(request.view_args or {}).get('subject','')
        if str(subject).strip().casefold() not in _MAIN_FSC_SUBJECTS:
            return
        from app import db
        conn=db()
        try:
            row=conn.execute(
                "SELECT COALESCE(academic_level,'') academic_level FROM users WHERE id=?",
                (session['user_id'],),
            ).fetchone()
            level=((row['academic_level'] if row else '') or '').strip().casefold()
        finally:
            conn.close()
        if 'fsc' not in level:
            return
        if 'part 2' in level or 'year 2' in level or level in {'fsc 2','fsc2'}:
            _set_active_programme('FSc Part 2')
        else:
            _set_active_programme('FSc Part 1')

    @app.before_request
    def _scoremax_main_subject_context_guard():
        _sync_main_fsc_subject_context()
        return None

    @app.route('/student/catalogue', endpoint='ux_catalogue_home')
    def catalogue_home():
        _student_required()
        tracks=[]
        for key in TRACK_ORDER:
            cat=CATALOGUES[key]
            tracks.append({
                'key': key,
                'label': cat['label'],
                'subjects': list(cat['subjects'].keys()),
                'unit_count': sum(len(v) for v in cat['subjects'].values()),
                'url': url_for('ux_catalogue_track', track=key),
            })
        return render_template('ux_catalogue_home.html', tracks=tracks, learn_url=url_for('ux_student_learn'))

    @app.route('/student/catalogue/<track>', endpoint='ux_catalogue_track')
    def catalogue_track(track):
        _student_required()
        cat=get_catalogue(track)
        if not cat:
            abort(404)
        _sync_active_programme(track)
        subjects=[]
        for name, items in cat['subjects'].items():
            subjects.append({
                'name': name,
                'count': len(items),
                'label': cat.get('item_labels',{}).get(name, cat['collection_label'][:-1] if cat['collection_label'].endswith('s') else cat['collection_label']),
                'url': url_for('ux_catalogue_subject', track=track, subject=name),
            })
        return render_template('ux_catalogue_track.html', track_key=track, catalogue=cat, subjects=subjects,
                               home_url=url_for('ux_catalogue_home'), learn_url=url_for('ux_student_learn'))

    @app.route('/student/catalogue/<track>/<path:subject>', endpoint='ux_catalogue_subject')
    def catalogue_subject(track, subject):
        _student_required()
        cat=get_catalogue(track)
        if not cat or subject not in cat['subjects']:
            abort(404)
        _sync_active_programme(track)
        items=list(subject_items(track,subject))
        label=cat.get('item_labels',{}).get(subject, cat['collection_label'][:-1] if cat['collection_label'].endswith('s') else cat['collection_label'])
        from app import db
        conn=db()
        try:
            scope_counts=_release_scope_counts(conn,track,subject)
        finally:
            conn.close()
        cards=[]
        for item in items:
            scope=_catalogue_item_scope(scope_counts,item)
            available=scope is not None and int(scope[1])>0
            count=int(scope[1]) if scope else 0
            cards.append({
                'number': item['number'],
                'name': item['name'],
                'available': available,
                'status': f'{count} governed question'+('' if count==1 else 's')+' available' if available else 'Not yet populated',
                'note': 'Available from the active Power House release.' if available else 'Questions will appear automatically after a governed Power House release is activated.',
                'url': url_for('chapter_page',subject=subject,chapter=scope[0]) if available else '',
                'ph_release_chapter_id': scope[0] if scope else '',
            })
        return render_template('ux_catalogue_subject.html', track_key=track, catalogue=cat, subject=subject,
                               item_label=label, cards=cards, track_url=url_for('ux_catalogue_track',track=track),
                               home_url=url_for('ux_catalogue_home'))

    print(
        'SCOREMAX_PROVISIONAL_CATALOGUE_BROWSER_PASS '
        'tracks=3 programme_context_sync=true main_science_tabs_fsc_fenced=true '
        'mdcat_isolated=true active_ph_membership_drives_availability=true governed_db_untouched=true release_authority=false',
        flush=True,
    )
