"""Donor functions extending existing assessment sessions; no scoring or new store."""

def guided_live_question_clause(alias='q'):
    # Keep the complete existing approval/activation/access population fence.
    base = _self_marking_original_live_question_clause_v2(alias)
    return ('('+base+") AND COALESCE("+alias+".ph_is_auto_markable,0)=0 AND "
            "json_extract(CASE WHEN json_valid("+alias+".marking_config) THEN "+alias+
            ".marking_config ELSE '{}' END,'$.rubric.guided_self_assessment.mode')='GUIDED_SELF_ASSESSMENT'")


def guided_chapters(c, programme, subject):
    """Use the existing active programme memberships, not canonical FSc placement."""
    aliases=sorted({v.strip().casefold() for v in _programme_aliases(programme) if v.strip()})
    if not aliases: return []
    slots=','.join('?' for _ in aliases)
    scope, params = _programme_scope_sql(aliases, 'q')
    rows=c.execute(f'''SELECT chapter,MIN(id) first_id FROM (
        SELECT q.id,CASE WHEN q.ph_projection_owner='POWER_HOUSE' THEN pr.chapter_id ELSE q.chapter END chapter
        FROM questions q
        LEFT JOIN integration_ph_question_version_store pv ON pv.local_question_db_id=q.id
        LEFT JOIN integration_ph_release_question_membership pm ON pm.question_id=pv.question_id AND pm.question_version_id=pv.question_version_id
        LEFT JOIN integration_ph_content_releases pr ON pr.release_id=pm.release_id AND pr.release_version=pm.release_version
          AND pr.local_status='ACTIVE' AND lower(trim(pr.programme_id)) IN ({slots})
        WHERE {guided_live_question_clause("q")} AND {scope} AND lower(q.subject)=lower(?)
        ) WHERE COALESCE(chapter,'')<>'' GROUP BY chapter ORDER BY first_id,chapter''',aliases+params+[subject]).fetchall()
    return [row['chapter'] for row in rows]


def guided_session_questions(c, a):
    from guided_self_assessment import from_question
    meta = safe_json(a['meta_json'], {})
    if meta.get('response_mode') != 'GUIDED_SELF_ASSESSMENT': return None
    if a['mode'] != 'practice' or meta.get('blueprint_snapshot') or meta.get('assessment_blueprint_id'):
        raise question_contracts.QuestionContractError('GUIDED_PRACTICE_ONLY')
    ids = parse_ids(a['question_ids'])
    rows = c.execute('SELECT * FROM questions WHERE id IN ('+','.join('?' for _ in ids)+')', ids).fetchall()
    byid = {r['id']: r for r in rows}
    result = []
    for qid in ids:
        q = integration_v1.pinned_question(a, qid, byid.get(qid))
        if not from_question(q): raise question_contracts.QuestionContractError('GUIDED_CONTRACT_REQUIRED')
        result.append(q)
    if not result: raise question_contracts.QuestionContractError('EMPTY_GUIDED_SESSION')
    return result


def guided_submit_session(c, a):
    """The caller holds BEGIN IMMEDIATE. Freeze before any guidance is returned."""
    from guided_self_assessment import digest
    rows = guided_session_questions(c, a)
    if rows is None: return None
    if a['status'] == 'guided_submitted':
        c.rollback(); c.close()
        return redirect(url_for('guided_session_review', assessment_id=a['id']))
    if a['status'] != 'in_progress': raise question_contracts.QuestionContractError('GUIDED_SESSION_CLOSED')
    answers = load_answers(a)
    for q in rows:
        answer = answers.get(str(q['id']))
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 10000:
            raise question_contracts.QuestionContractError('GUIDED_WRITTEN_ATTEMPT_REQUIRED')
    meta = safe_json(a['meta_json'], {})
    meta['guided_submission'] = {'response_sha256': digest(answers),
        'submitted_at': datetime.now().isoformat(timespec='seconds'), 'guidance_revealed_at': None,
        'self_review': {}, 'scored': False}
    c.execute("UPDATE assessment_sessions SET status='guided_submitted',meta_json=? WHERE id=? AND status='in_progress'",
              (integration_v1.canonical_json(meta), a['id']))
    c.commit(); c.close()
    return redirect(url_for('guided_session_review', assessment_id=a['id']))


def guided_session_review(assessment_id):
    if not require('student'): return redirect(url_for('login'))
    from guided_self_assessment import digest, guidance, REVIEWS
    c = db()
    try:
        c.execute('BEGIN IMMEDIATE')
        a = get_assessment_session(c, assessment_id, session['user_id'])
        if not a or a['status'] != 'guided_submitted': abort(404)
        rows = guided_session_questions(c, a)
        if rows is None: abort(404)
        meta = safe_json(a['meta_json'], {})
        frozen = meta.get('guided_submission', {})
        answers = load_answers(a)
        if frozen.get('response_sha256') != digest(answers):
            raise question_contracts.QuestionContractError('GUIDED_RESPONSE_CHANGED')
        previous = bool(frozen.get('guidance_revealed_at'))
        views = [dict(guidance(q), answer=answers[str(q['id'])]) for q in rows]
        if request.method == 'POST':
            if not previous: abort(409)
            allowed = {f'review_{i}_{j}' for i, v in enumerate(views) for j in range(len(v['points']))}
            submitted = {k: v for k, v in request.form.items() if k != '_csrf_token'}
            if set(submitted) != allowed or any(v not in REVIEWS for v in submitted.values()): abort(400)
            if any(len(request.form.getlist(k)) != 1 for k in allowed): abort(400)
            frozen['self_review'] = submitted
            frozen['self_reviewed_at'] = datetime.now().isoformat(timespec='seconds')
        if not previous: frozen['guidance_revealed_at'] = datetime.now().isoformat(timespec='seconds')
        meta['guided_submission'] = frozen
        c.execute('UPDATE assessment_sessions SET meta_json=? WHERE id=?', (integration_v1.canonical_json(meta), assessment_id))
        c.commit()
        response = make_response(render_template('guided_self_review.html', views=views,
            assessment_id=assessment_id, reviews=frozen['self_review'],
            after_guidance=bool(meta.get('guided_parent_session_id')),
            parent_session_id=meta.get('guided_parent_session_id')))
        response.headers['Cache-Control'] = 'no-store, private'
        return response
    except (ValueError, TypeError, KeyError):
        c.rollback(); abort(409, description='Your saved answer could not be verified.')
    finally:
        c.close()


def guided_retry_session(assessment_id):
    if not require('student'): return redirect(url_for('login'))
    c = db()
    try:
        c.execute('BEGIN IMMEDIATE')
        a = get_assessment_session(c, assessment_id, session['user_id'])
        if not a or a['status'] != 'guided_submitted': abort(404)
        rows = guided_session_questions(c, a)
        meta = safe_json(a['meta_json'], {})
        if rows is None or not meta.get('guided_submission', {}).get('guidance_revealed_at'): abort(409)
        prior = meta.get('guided_retry_session_id')
        if prior:
            c.rollback()
            return redirect(url_for('take_test_v4', assessment_id=prior))
        child_meta = {k: v for k, v in meta.items() if not k.startswith('guided_')}
        child_meta['guided_parent_session_id'] = assessment_id
        child = create_assessment_session(c, session['user_id'], 'practice', None,
            [q['id'] for q in rows], child_meta, commit=False)
        # Retry the same pinned immutable versions, never silently substitute an update.
        c.execute('UPDATE assessment_sessions SET ph_release_pins_json=?,ph_question_pins_json=? WHERE id=?',
                  (a['ph_release_pins_json'], a['ph_question_pins_json'], child))
        meta['guided_retry_session_id'] = child
        c.execute('UPDATE assessment_sessions SET meta_json=? WHERE id=?', (integration_v1.canonical_json(meta), assessment_id))
        c.commit()
        return redirect(url_for('take_test_v4', assessment_id=child))
    except (ValueError, TypeError, KeyError):
        c.rollback(); abort(409, description='This practice cannot be retried right now.')
    finally:
        c.close()
