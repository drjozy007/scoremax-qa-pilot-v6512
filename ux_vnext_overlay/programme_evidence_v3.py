"""Donor functions installed into the existing application, not an alternate reader API."""

def canonical_programme(value):
    return question_contracts.canonical_programme(value)


def _programme_aliases(value):
    return question_contracts.programme_aliases(value)


def _programme_scope_sql(alias_values,table_alias='q'):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',table_alias):
        raise ValueError('Invalid SQL scope alias')
    vals=sorted({str(x).strip().casefold() for x in alias_values or [] if str(x).strip()})
    if not vals:return '0=1',[]
    marks=','.join('?' for _ in vals)
    # A populated programme is authoritative. Qualification is only legacy fallback,
    # never a second route by which an explicitly different programme can match.
    expression=f"lower(COALESCE(NULLIF(trim({table_alias}.programme),''),trim({table_alias}.qualification),''))"
    return f'{expression} IN ({marks})',vals


def student_programme(c,user_id):
    row=c.execute("SELECT academic_level,active_programme FROM users WHERE id=?",(user_id,)).fetchone()
    return canonical_programme((row['active_programme'] or '').strip() or row['academic_level']) if row else ''


def eligible_attempts(c,student_id,programme=None):
    programme=canonical_programme(student_programme(c,student_id) if programme is None else programme)
    aliases=_programme_aliases(programme)
    if not aliases:return []
    marks=','.join('?' for _ in aliases)
    return c.execute(f"""SELECT * FROM attempts WHERE student_id=?
      AND lower(trim(COALESCE(programme,''))) IN ({marks})
      AND marking_status='FINAL' AND mastery_evidence_eligible=1 AND score IS NOT NULL
      AND COALESCE(guided_mode,0)=0
      AND COALESCE(assessment_kind,'') NOT IN ('demo_progress','science_genius')
      ORDER BY created_at DESC,id DESC""",[student_id]+[x.casefold() for x in aliases]).fetchall()


def evidence_context(question,programme,question_db_id):
    import hashlib
    q=dict(question)
    fields=('subject','chapter','topic','subtopic','learning_outcome','level','difficulty','command_word','cognitive_skill','family_id','question_version')
    context={key:q.get(key) for key in fields}
    context.update(schema='SM-EVIDENCE-CONTEXT-1',programme=canonical_programme(programme),question_db_id=int(question_db_id),
                   question_id=q.get('question_id',''),ph_question_id=q.get('ph_question_id',''),
                   ph_question_version_id=q.get('ph_question_version_id',''))
    raw=integration_v1.canonical_json(context)
    context['checksum_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    return context


def learner_answer_evidence(c,student_id,programme=None,subject='',chapter='',attempt_id=None):
    """Single scoped eligible reader. Historical source and attempts are never rewritten.

    New evidence context is frozen on submit. Prior PH answers use their immutable
    projection; ambiguous legacy/missing/corrupt context is excluded, not guessed.
    A final raw attempt may remain visible in history without becoming mastery evidence.
    """
    import hashlib
    programme=canonical_programme(student_programme(c,student_id) if programme is None else programme)
    aliases=_programme_aliases(programme)
    if not aliases:return []
    marks=','.join('?' for _ in aliases)
    sql=f"""SELECT aa.*,a.programme attempt_programme,a.student_id,a.created_at,
      q.subject legacy_subject,q.chapter legacy_chapter,q.topic legacy_topic,q.subtopic legacy_subtopic,
      q.learning_outcome legacy_learning_outcome,q.level legacy_level,q.difficulty legacy_difficulty,
      q.family_id legacy_family_id,q.question_version legacy_question_version,q.command_word legacy_command_word,
      q.cognitive_skill legacy_cognitive_skill,q.programme legacy_programme,q.qualification legacy_qualification,
      COALESCE(q.is_demo,0) legacy_demo
      FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id
      LEFT JOIN questions q ON q.id=aa.question_db_id
      WHERE a.student_id=? AND lower(trim(COALESCE(a.programme,''))) IN ({marks})
      AND a.marking_status='FINAL' AND a.mastery_evidence_eligible=1 AND a.score IS NOT NULL
      AND aa.marking_status='FINAL' AND aa.mastery_evidence_eligible=1
      AND aa.marks_awarded IS NOT NULL AND COALESCE(a.guided_mode,0)=0
      AND COALESCE(a.assessment_kind,'') NOT IN ('demo_progress','science_genius')
      ORDER BY a.created_at DESC,aa.id DESC"""
    params=[student_id]+[x.casefold() for x in aliases]
    if attempt_id is not None:
        sql=sql.replace('      ORDER BY a.created_at', '      AND a.id=? ORDER BY a.created_at')
        params.append(int(attempt_id))
    rows=c.execute(sql,params).fetchall()
    out=[]
    for row in rows:
        r=dict(row);context={};authority=''
        raw=r.get('evidence_context_json')
        if raw and raw!='{}':
            try:
                context=json.loads(raw)
                if not isinstance(context,dict):continue
                digest=context.pop('checksum_sha256',None)
                if digest!=hashlib.sha256(integration_v1.canonical_json(context).encode()).hexdigest():continue
                if context.get('schema')!='SM-EVIDENCE-CONTEXT-1' or context.get('question_db_id')!=r['question_db_id']:continue
                if canonical_programme(context.get('programme'))!=programme:continue
                authority='FROZEN_CONTEXT'
            except (ValueError,TypeError):continue
        elif r.get('ph_question_id'):
            try:
                context=json.loads(r.get('ph_question_snapshot_json') or '{}')
                if not isinstance(context,dict):continue
                if str(context.get('ph_question_id') or '')!=str(r['ph_question_id']):continue
                if str(context.get('ph_question_version_id') or '')!=str(r['ph_question_version_id']):continue
                authority='FROZEN_PH_PROJECTION'
            except (ValueError,TypeError):continue
        else:
            # Conservative compatibility for older local attempts: retain original
            # attempt programme, and reject changed question-version/demonstration rows.
            if r.get('legacy_demo') or r.get('question_version')!=r.get('legacy_question_version'):continue
            if canonical_programme(r.get('legacy_programme') or r.get('legacy_qualification'))!=programme:continue
            context={key[len('legacy_'):]:v for key,v in r.items() if key.startswith('legacy_')}
            authority='LEGACY_VERSION_MATCH'
        if subject and str(context.get('subject') or '').casefold()!=subject.strip().casefold():continue
        if chapter and str(context.get('chapter') or '').casefold()!=chapter.strip().casefold():continue
        for key in ('subject','chapter','topic','subtopic','learning_outcome','level','difficulty','family_id','command_word','cognitive_skill'):
            r[key]=context.get(key) or ''
        r['programme']=programme;r['context_authority']=authority
        out.append(r)
    return out


def evidence_summary(rows):
    n=len(rows);correct=sum(int(r.get('is_correct')==1) for r in rows)
    return {'answered':n,'correct':correct,'accuracy':round(100*correct/n,1) if n else 0.0}


def evidence_groups(rows,field):
    groups={}
    for row in rows:
        key=(row.get('subject') or '',row.get(field) or row.get('topic') or 'Unmapped')
        groups.setdefault(key,[]).append(row)
    out=[]
    for (subject,name),items in groups.items():
        out.append({'subject':subject,'area':name,'name':name,field:name,**evidence_summary(items)})
    return sorted(out,key=lambda r:(r['accuracy'],-r['answered'],r['subject'],r['name']))


def _student_accuracy(c,student_id):
    stats=evidence_summary(learner_answer_evidence(c,student_id))
    return stats['answered'],stats['accuracy']


def _tested_chapters(c,student_id,target_exam=''):
    return {(r['subject'],r['chapter']) for r in learner_answer_evidence(c,student_id,programme=target_exam or None) if r['chapter']}


def student_analytics(c,student_id):
    attempts=eligible_attempts(c,student_id)
    n=len(attempts);average=round(sum(float(a['score']) for a in attempts)/n,1) if n else 0
    recent=[float(a['score']) for a in attempts[:5]]
    evidence=learner_answer_evidence(c,student_id)
    by_subtopic=evidence_groups(evidence,'subtopic');by_level=evidence_groups(evidence,'level')
    by_level.sort(key=lambda r:mastery_rank(r['level']))
    weakest=by_subtopic[0] if by_subtopic else None
    strongest=max(by_subtopic,key=lambda r:r['accuracy']) if by_subtopic else None
    recommendations=[]
    if weakest:recommendations.append(f"Prioritise {weakest['area']} in {weakest['subject']} — current accuracy is {weakest['accuracy']}%.")
    if n<3:recommendations.append('Complete more independent assessments to build a reliable progress profile.')
    elif average>=80:recommendations.append('Practice performance is strong. Verified mastery also requires sufficient breadth and independent evidence.')
    else:recommendations.append('Focus your next practice on weaker areas.')
    return dict(attempts=attempts,tests_completed=n,avg_score=average,health=calculate_health_score(average,n,recent),by_subtopic=by_subtopic,by_level=by_level,weakest=weakest,strongest=strongest,recommendations=recommendations)


def progress_chart_data(c,student_id,limit=12):
    rows=list(reversed(eligible_attempts(c,student_id)[:max(0,int(limit))]))
    trend=[]
    for r in rows:
        dt=str(r['created_at'] or '')[:10]
        try:label=datetime.strptime(dt,'%Y-%m-%d').strftime('%d %b')
        except ValueError:label=dt or 'Test'
        trend.append({'label':label,'score':round(float(r['score']),1),'subject':r['subject'] or ''})
    groups={}
    for row in learner_answer_evidence(c,student_id):groups.setdefault(row['subject'],[]).append(row)
    subject_data=[{'subject':name,**evidence_summary(rows)} for name,rows in groups.items() if name]
    subject_data.sort(key=lambda r:-r['accuracy'])
    plan=get_active_study_plan(c,student_id);weekly=[]
    if plan:
        for item in list(plan.get('weekly',[]))[:10]:
            total=item.get('total',0);done=item.get('done',0)
            weekly.append({'week':f"W{item.get('week',0)}",'completion':item.get('pct',round(100*done/total) if total else 0),'done':done,'total':total})
    return {'trend':trend,'subjects':subject_data,'plan_weeks':weekly}


def student_weak_areas(c,student_id,limit=12):
    programme=student_programme(c,student_id)
    states=c.execute("""SELECT subject,programme,area_name area,source_area_key concept_key,evidence_count answered,
      accuracy,'' capsule_id,status FROM student_learning_states
      WHERE student_id=? AND programme=? AND status IN ('Weak Area','Recovery') AND evidence_count>=3
      ORDER BY accuracy,evidence_count DESC LIMIT ?""",(student_id,programme,limit)).fetchall()
    if states:return states
    rows=learner_answer_evidence(c,student_id)
    groups=evidence_groups(rows,'learning_outcome')
    return [{'subject':r['subject'],'programme':programme,'area':r['name'],'concept_key':r['name'],
      'answered':r['answered'],'accuracy':r['accuracy'],'capsule_id':'','status':'Weak Area'}
      for r in groups if r['answered']>=3 and r['accuracy']<75][:limit]


def due_recall_items(c,student_id,limit=6):
    rows=c.execute("""SELECT * FROM recall_items WHERE student_id=? AND programme=? AND status='scheduled'
      AND next_due_date<>'' AND date(next_due_date)<=date('now') ORDER BY date(next_due_date),last_score LIMIT ?""",
      (student_id,student_programme(c,student_id),limit)).fetchall()
    return [dict(r,concept_key=r['source_area_key']) for r in rows]


def confirmed_misconceptions(c,student_id,limit=8):
    return c.execute("""SELECT * FROM student_misconceptions WHERE student_id=? AND programme=? AND status='Confirmed'
      ORDER BY confident_wrong_count DESC,evidence_count DESC,last_seen_at DESC LIMIT ?""",(student_id,student_programme(c,student_id),limit)).fetchall()


def subject_community_snapshot(c,programme,subject,student_id=None):
    # Verified mastery distribution, not the separate provisional accuracy-to-level model.
    programme=canonical_programme(programme)
    rows=c.execute("""SELECT student_id,mastery_level,status FROM mastery_records
      WHERE programme=? AND subject=? AND scope_type='subject' AND status IN ('Verified','Elite Candidate')""",(programme,subject)).fetchall()
    distribution={level:0 for level in SCOREMAX_LEVELS};current=None
    for row in rows:
        if row['mastery_level'] not in distribution:continue
        distribution[row['mastery_level']]+=1
        if row['student_id']==student_id:current=row['mastery_level']
    total=sum(distribution.values())
    return {'total':total,'distribution':distribution,'percentages':{k:round(100*v/total,1) if total else 0 for k,v in distribution.items()},'current_level':current}


def focus_accuracy(c,attempt_id,focus_type,focus_name):
    if not attempt_id or not focus_name:return None
    attempt=c.execute('SELECT student_id,programme FROM attempts WHERE id=?',(attempt_id,)).fetchone()
    if not attempt:return None
    rows=[r for r in learner_answer_evidence(c,attempt['student_id'],attempt['programme'],attempt_id=attempt_id)]
    rows=[r for r in rows if (r['learning_outcome']==focus_name if focus_type=='learning_outcome' else focus_name in (r['subtopic'],r['topic']))]
    return evidence_summary(rows)['accuracy'] if rows else None


def student_dashboard_intelligence(c,student_id):
    """Main dashboard uses the same scoped evidence and formal mastery authority."""
    programme=student_programme(c,student_id)
    rows=learner_answer_evidence(c,student_id,programme)
    subject_groups={};chapter_groups={};history_groups={}
    for row in rows:
        subject_groups.setdefault(row['subject'],[]).append(row)
        chapter_groups.setdefault((row['subject'],row['chapter']),[]).append(row)
        area=row['learning_outcome'] or row['subtopic'] or row['topic']
        history_groups.setdefault((row['subject'],area,row['attempt_id'],str(row['created_at'])),[]).append(row)
    subjects=[]
    for subject,items in sorted(subject_groups.items()):
        stats=evidence_summary(items);n=stats['answered']
        formal=c.execute("SELECT * FROM mastery_records WHERE student_id=? AND programme=? AND subject=? AND scope_type='subject' ORDER BY id DESC LIMIT 1",(student_id,programme,subject)).fetchone()
        earned=formal['mastery_level'] if formal else 'Not verified'
        subjects.append({'programme':programme,'subject':subject,**stats,
          'evidence':'Insufficient evidence' if n<4 else 'Emerging evidence' if n<8 else 'Moderate evidence' if n<15 else 'Strong evidence',
          'mastery':earned,'mastery_status':effective_mastery_status(formal) if formal else 'Not verified',
          'mastery_index':level_index(earned) if formal else 0,'next_level':next_level_name(earned) if formal else 'Foundation',
          'level_progress':0,'community':subject_community_snapshot(c,programme,subject,student_id)})
    chapters=[]
    for (subject,chapter),items in sorted(chapter_groups.items()):
        stats=evidence_summary(items)
        chapters.append({'subject':subject,'chapter':chapter,**stats,'status':'Strong' if stats['accuracy']>=80 else 'Developing' if stats['accuracy']>=60 else 'Needs attention'})
    since=(datetime.now()-timedelta(days=7)).isoformat(timespec='seconds')
    weekly=[r for r in rows if str(r['created_at']).replace(' ','T')>=since]
    weekly_data={'assessments':len({r['attempt_id'] for r in weekly}),'minutes':round(sum(float(r['response_time_seconds'] or 0) for r in weekly)/60),
      'answered':len(weekly),'correct':sum(r['is_correct']==1 for r in weekly),'goal':3}
    histories={}
    for (subject,area,aid,stamp),items in sorted(history_groups.items(),key=lambda x:(x[0][3],x[0][2])):
        if area:histories.setdefault((subject,area),[]).append(evidence_summary(items)['accuracy'])
    improvements=[]
    for (subject,area),scores in histories.items():
        if len(scores)>1 and scores[-1]>scores[0]:improvements.append({'subject':subject,'area':area,'first':scores[0],'latest':scores[-1],'change':round(scores[-1]-scores[0],1)})
    improvements.sort(key=lambda x:-x['change'])
    # Assignment inbox is an explicitly cross-class administrative list, not evidence.
    assignments=c.execute("""SELECT asg.*,u.full_name teacher_name,ast.status student_status
      FROM assignment_students ast JOIN assignments asg ON asg.id=ast.assignment_id JOIN users u ON u.id=asg.teacher_id
      WHERE ast.student_id=? AND asg.status='active' AND COALESCE(ast.status,'assigned')<>'completed'
      ORDER BY CASE WHEN COALESCE(asg.due_at,'')='' THEN 1 ELSE 0 END,asg.due_at LIMIT 5""",(student_id,)).fetchall()
    active=next((r for r in c.execute("SELECT * FROM assessment_sessions WHERE student_id=? AND status='in_progress' ORDER BY started_at DESC,id DESC",(student_id,)).fetchall()
      if canonical_programme(safe_json(r['meta_json'],{}).get('programme'))==programme),None)
    return {'subjects':subjects,'chapters':chapters,'weekly':weekly_data,'improvements':improvements[:3],
      'assignments':assignments,'active_assessment':active}


def admin_mastery_rules():
    # Preserve the old bookmarked endpoint; one visible editor and one mutation path.
    if not require('admin'):return redirect(url_for('login'))
    if request.method=='POST':return app.view_functions['admin_mastery_rigor_level']()
    return redirect(url_for('admin_mastery_rigor'))


def seen_question_families(c,student_id):
    """Exposure is not the same as eligible evidence: guided/failed practice was seen too.

    Use stable original family identity when present, with conservative local fallback.
    This can reduce future novelty but can never award a mark or mastery by itself.
    """
    seen=set()
    for row in c.execute("""SELECT aa.question_db_id,aa.evidence_context_json,aa.ph_question_snapshot_json,
      aa.question_version,q.question_version current_version,q.family_id current_family
      FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id
      LEFT JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=?""",(student_id,)):
        context=safe_json(row['evidence_context_json'],{})
        if not isinstance(context,dict) or not context:context=safe_json(row['ph_question_snapshot_json'],{})
        family=context.get('family_id') if isinstance(context,dict) else None
        if not family and row['question_version']==row['current_version']:family=row['current_family']
        if family:seen.add(str(family))
        seen.add(f"Q-{row['question_db_id']}")
    return seen
