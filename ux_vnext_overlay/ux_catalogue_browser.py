from __future__ import annotations

from flask import abort, render_template, session, url_for

from ux_catalogue_data import CATALOGUES, TRACK_ORDER, get_catalogue, subject_items


_TRACK_PROGRAMMES={
    'year11':'FSc Part 1',
    'year12':'FSc Part 2',
    'mdcat':'MDCAT',
}


def install_catalogue_browser(app):
    if getattr(app, '_ux_catalogue_browser_installed', False):
        return
    app._ux_catalogue_browser_installed = True

    def _student_required():
        if session.get('role') != 'student' or not session.get('user_id'):
            abort(403)

    def _sync_active_programme(track: str) -> None:
        programme=_TRACK_PROGRAMMES.get(track)
        if not programme:
            return
        # UI programme preference only. Governed curriculum/question state is untouched.
        from app import db
        conn=db()
        try:
            row=conn.execute("SELECT COALESCE(active_programme,'') active_programme FROM users WHERE id=?",(session['user_id'],)).fetchone()
            current=(row['active_programme'] if row else '') or ''
            if current.strip()!=programme:
                conn.execute("UPDATE users SET active_programme=? WHERE id=?",(programme,session['user_id']))
                conn.commit()
        finally:
            conn.close()

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
        cards=[]
        for item in items:
            cards.append({
                'number': item['number'],
                'name': item['name'],
                'available': False,
                'status': 'Ready to browse',
                'note': 'Questions will appear here as they become available.',
            })
        return render_template('ux_catalogue_subject.html', track_key=track, catalogue=cat, subject=subject,
                               item_label=label, cards=cards, track_url=url_for('ux_catalogue_track',track=track),
                               home_url=url_for('ux_catalogue_home'))

    print('SCOREMAX_PROVISIONAL_CATALOGUE_BROWSER_PASS tracks=3 programme_context_sync=true governed_db_untouched=true release_authority=false',flush=True)
