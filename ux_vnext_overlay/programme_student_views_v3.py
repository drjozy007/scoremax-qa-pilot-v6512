"""Donor functions for the existing programme-aware learner surfaces."""

def _active_programme_for_student(conn,student_id):
    import app as runtime
    return runtime.student_programme(conn,student_id)


def _subject_snapshot(conn,student_id,subject):
    import app as runtime
    chapters=_catalogue_for_student(conn,student_id,subject)
    rows=runtime.learner_answer_evidence(conn,student_id,subject=subject)
    stats=runtime.evidence_summary(rows)
    started=min(len({r['chapter'] for r in rows if r['chapter']}),len(chapters))
    return {'chapter_count':len(chapters),'started_chapters':started,'answered':stats['answered'],
            'avg_accuracy':round(stats['accuracy']),'progress_pct':round(100*started/len(chapters)) if chapters else 0}


def _progress_context(conn,student_id):
    import app as runtime
    attempts=runtime.eligible_attempts(conn,student_id)
    programme=runtime.student_programme(conn,student_id)
    records=[r for r in runtime.current_mastery_records(conn,student_id) if runtime.canonical_programme(r['programme'])==programme]
    subjects,_=_learn_context(conn,student_id)
    actions=[{'title':'Open your subjects','copy':'Choose a chapter and continue from your current evidence.','url':url_for('ux_student_learn')},
      {'title':'Review weak areas','copy':'See where marks are being lost.','url':url_for('weak_areas_page')},
      {'title':'Open your exam plan','copy':'Follow your plan for the selected programme.','url':url_for('study_plan_page')}]
    n=len(attempts);avg=round(sum(float(a['score']) for a in attempts)/n) if n else 0
    return {'avg_score':avg,'tests_completed':n,'mastery_count':len(records),
            'health':min(100,round(avg*.7+min(n,10)*3)) if n else 0,'subjects':subjects,'actions':actions}


def _ensure_fixed_test_student():
    password=os.environ.get('SCOREMAX_STAGING_TEST_STUDENT_PASSWORD','').strip()
    if not password:return
    from ux_teacher_preview import resolve_preview_identity
    conn=_connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=resolve_preview_identity(conn,TEST_STUDENT_EMAIL,TEST_STUDENT_USERNAME,TEST_STUDENT_ID,'student')
        if not row:
            conn.execute('''INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,province,board,academic_level,subjects,account_status,active_programme,login_provider)
              VALUES(?,'student',?,?,?,?,?,?,?,'Biology,Chemistry,Physics','active','FSc Part 1','password')''',
              (TEST_STUDENT_ID,'ScoreMax UX Pre-Medical Student',TEST_STUDENT_EMAIL,TEST_STUDENT_USERNAME,
               generate_password_hash(password),'Punjab','Punjab Board','FSc Part 1'))
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
