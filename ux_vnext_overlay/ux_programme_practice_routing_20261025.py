from pathlib import Path
import hashlib

HELPERS="\ndef practice_scope_placements(c, programme, guided=False):\n    \"\"\"Read the active destination view without rewriting canonical PH content.\"\"\"\n    aliases=sorted({str(v).strip().casefold() for v in _programme_aliases(programme) if str(v).strip()})\n    if not aliases:return []\n    slots=','.join('?' for _ in aliases)\n    live=guided_live_question_clause('q') if guided else live_question_clause('q')\n    rows=c.execute(f\"\"\"SELECT DISTINCT q.id,q.topic,\n      CASE WHEN q.ph_projection_owner='POWER_HOUSE' THEN replace(r.subject_id,'_',' ') ELSE q.subject END subject,\n      CASE WHEN q.ph_projection_owner='POWER_HOUSE' AND lower(scoremax_release_programme(r.programme_id,v.curriculum_json))='mdcat'\n        THEN r.chapter_id ELSE q.chapter END chapter\n      FROM questions q\n      LEFT JOIN integration_ph_question_version_store v ON v.local_question_db_id=q.id\n        AND v.question_id=q.ph_question_id AND v.question_version_id=q.ph_question_version_id\n        AND v.question_checksum_sha256=q.ph_question_checksum_sha256\n      LEFT JOIN integration_ph_release_question_membership m ON m.question_id=v.question_id AND m.question_version_id=v.question_version_id\n      LEFT JOIN integration_ph_content_releases r ON r.release_id=m.release_id AND r.release_version=m.release_version\n      WHERE {live} AND (\n        (COALESCE(q.ph_projection_owner,'')<>'POWER_HOUSE' AND\n          (lower(q.programme) IN ({slots}) OR lower(q.qualification) IN ({slots})))\n        OR (q.ph_projection_owner='POWER_HOUSE' AND r.local_status='ACTIVE'\n          AND lower(scoremax_release_programme(r.programme_id,v.curriculum_json)) IN ({slots})\n          AND EXISTS(SELECT 1 FROM integration_ph_product_activation_authorizations a\n            WHERE a.release_id=r.release_id AND a.release_version=r.release_version\n              AND a.package_checksum_sha256=r.package_checksum_sha256 AND a.activation_status IN ('AUTHORIZED','ACTIVATED'))\n          AND NOT EXISTS(SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e\n            WHERE e.release_id=m.release_id AND e.release_version=m.release_version\n              AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id)))\n      ORDER BY subject,q.id,chapter\"\"\",aliases+aliases+aliases).fetchall()\n    return [dict(row,subject=str(row['subject']).strip().title()) for row in rows]\n\n\ndef practice_setup_context(c, student_id, programme, guided=False):\n    rows=practice_scope_placements(c,programme,guided)\n    subjects=sorted({r['subject'] for r in rows if r['subject']})\n    cards=[{'subject':s,'access_state':commercial_access.subject_state(c,student_id,programme,s,\n      available=True,commercial_gates_enabled=COMMERCIAL_GATES_ENABLED)} for s in subjects]\n    included={card['subject'] for card in cards if card['access_state']=='INCLUDED'}\n    subjects=[s for s in subjects if s in included]\n    chapters=[]\n    seen=set()\n    for row in rows:\n        key=(row['subject'],row['chapter'])\n        if row['subject'] not in included or not row['chapter'] or key in seen:continue\n        seen.add(key)\n        identity=chapter_identity(c,programme,row['subject'],row['chapter'])\n        chapters.append(dict(identity,programme=programme,subject=row['subject'],chapter=row['chapter']))\n    return {'programmes':[programme] if subjects else [],'subjects':subjects,'subject_cards':cards,\n      'subject_programmes':[{'programme':programme,'subject':s} for s in subjects],\n      'chapters':chapters,'topics':[{'programme':programme,'subject':s,'topic':t}\n        for s,t in sorted({(r['subject'],r['topic']) for r in rows if r['subject'] in included and r['topic']})]}\n\n\ndef mdcat_subject_map(c,student_id):\n    programme='MDCAT'\n    scored=practice_scope_placements(c,programme)\n    guided=practice_scope_placements(c,programme,True)\n    evidence=learner_answer_evidence(c,student_id,programme)\n    data=[]\n    for subject in sorted({r['subject'] for r in scored+guided}):\n        rows=[r for r in scored+guided if r['subject']==subject]\n        count=len({r['id'] for r in rows})\n        stats=evidence_summary([r for r in evidence if r['subject'].casefold()==subject.casefold()])\n        state=commercial_access.subject_state(c,student_id,programme,subject,available=bool(count),\n          commercial_gates_enabled=COMMERCIAL_GATES_ENABLED)\n        chapters=[]\n        for chapter in dict.fromkeys(r['chapter'] for r in rows if r['chapter']):\n            cs=evidence_summary([r for r in evidence if r['subject'].casefold()==subject.casefold() and r['chapter']==chapter])\n            chapters.append(dict(chapter_identity(c,programme,subject,chapter),\n              answered=cs['answered'],accuracy=cs['accuracy'],status=health_status(cs['accuracy'],cs['answered'])))\n        data.append({'subject':subject,'answered':stats['answered'],'accuracy':stats['accuracy'],\n          'status':health_status(stats['accuracy'],stats['answered']) if state=='INCLUDED' else state,\n          'chapters':chapters,'availability':'LIVE' if state=='INCLUDED' else state,\n          'access_state':state,'available_questions':count})\n    return data\n"
COMMERCIAL="\ndef programme_subjects(c, programme):\n    from question_contract_engine import programme_aliases\n    aliases=sorted({str(v).strip().casefold() for v in programme_aliases(programme) if str(v).strip()})\n    if not aliases:return []\n    slots=','.join('?' for _ in aliases)\n    columns={r['name'] for r in c.execute('PRAGMA table_info(questions)')}\n    tables={r['name'] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}\n    native={'integration_ph_question_version_store','integration_ph_release_question_membership','integration_ph_content_releases'}\n    if 'ph_projection_owner' not in columns or not native.issubset(tables):\n        rows=c.execute(f\"SELECT DISTINCT subject FROM questions WHERE COALESCE(subject,'')<>'' AND (lower(COALESCE(programme,'')) IN ({slots}) OR lower(COALESCE(qualification,'')) IN ({slots}))\",aliases+aliases).fetchall()\n        return sorted({r['subject'] for r in rows})\n    legacy=c.execute(f\"\"\"SELECT DISTINCT subject FROM questions WHERE COALESCE(ph_projection_owner,'')<>'POWER_HOUSE'\n      AND COALESCE(subject,'')<>'' AND (lower(COALESCE(programme,'')) IN ({slots}) OR lower(COALESCE(qualification,'')) IN ({slots}))\"\"\",aliases+aliases).fetchall()\n    placed=c.execute(f\"\"\"SELECT DISTINCT replace(r.subject_id,'_',' ') subject\n      FROM questions q\n      JOIN integration_ph_question_version_store v ON v.local_question_db_id=q.id AND v.question_id=q.ph_question_id\n        AND v.question_version_id=q.ph_question_version_id AND v.question_checksum_sha256=q.ph_question_checksum_sha256\n      JOIN integration_ph_release_question_membership m ON m.question_id=v.question_id AND m.question_version_id=v.question_version_id\n      JOIN integration_ph_content_releases r ON r.release_id=m.release_id AND r.release_version=m.release_version\n      WHERE q.ph_projection_owner='POWER_HOUSE' AND r.local_status='ACTIVE'\n        AND lower(scoremax_release_programme(r.programme_id,v.curriculum_json)) IN ({slots})\n        AND EXISTS(SELECT 1 FROM integration_ph_product_activation_authorizations a\n          WHERE a.release_id=r.release_id AND a.release_version=r.release_version\n            AND a.package_checksum_sha256=r.package_checksum_sha256 AND a.activation_status IN ('AUTHORIZED','ACTIVATED'))\n        AND NOT EXISTS(SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e\n          WHERE e.release_id=m.release_id AND e.release_version=m.release_version\n            AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id)\"\"\",aliases).fetchall()\n    return sorted({str(r['subject']).strip().title() for r in list(legacy)+list(placed) if r['subject']})\n"

def replace_once(text,old,new):
    assert text.count(old)==1,('ROUTING_ANCHOR_MISMATCH',old[:100],text.count(old))
    return text.replace(old,new,1)

def apply(root):
    root=Path(root)
    path=root/'app.py';source=path.read_text(encoding='utf8')
    assert 'def practice_scope_placements(' not in source
    # Derive the subject predicate from the existing strict membership predicate.
    start=source.index('def _programme_chapter_scope_sql(')
    end=source.index('\n\ndef eligible_attempts(',start)
    helper=source[start:end].replace('_programme_chapter_scope_sql','_programme_subject_scope_sql').replace('chapter','subject')
    helper=helper.replace('cr.subject_id','replace(cr.subject_id,\'_\',\' \')')
    old='subject_clause=f"(lower(COALESCE({table_alias}.subject,\'\'))=lower(?) OR {ph_subject})"'
    new='subject_clause=f"((COALESCE({table_alias}.ph_projection_owner,\'\')<>\'POWER_HOUSE\' AND lower(COALESCE({table_alias}.subject,\'\'))=lower(?)) OR {ph_subject})"'
    helper=replace_once(helper,old,new)
    source+='\n\n'+helper+'\n'+HELPERS
    # PH MDCAT units cannot match canonical FSc chapters.
    old='    chapter_clause=f"(lower(COALESCE({table_alias}.chapter,\'\'))=lower(?) OR {ph_chapter})"'
    new="""    legacy_chapter=f"lower(COALESCE({table_alias}.chapter,''))=lower(?)"
    if canonical_programme(programme)=='MDCAT':
        legacy_chapter=f"(COALESCE({table_alias}.ph_projection_owner,'')<>'POWER_HOUSE' AND {legacy_chapter})"
    chapter_clause=f"({legacy_chapter} OR {ph_chapter})" """
    source=replace_once(source,old,new.rstrip())
    # Setup follows the current normal programme selector and the destination metadata.
    start=source.index('    programmes=[',source.index('def test_setup():'))
    end=source.index('    c.close()',start)
    setup="""    programme=canonical_programme(student_programme(c,session['user_id']))
    context=practice_setup_context(c,session['user_id'],programme,request.args.get('response_mode')=='GUIDED_SELF_ASSESSMENT')
    programmes=context['programmes'];subjects=context['subjects']
    subject_programmes=context['subject_programmes'];chapters=context['chapters']
    topics=context['topics'];subject_cards=context['subject_cards']
    access=get_access_profile(c,session['user_id'])
"""
    source=source[:start]+setup+source[end:]
    needle="    return render_template('test_setup.html',programmes=programmes,"
    source=replace_once(source,needle,"    prefill['programme']=programme\n"+needle)
    # Existing commercial rules stay authoritative, using destination subject.
    old="""    row=c.execute(f"SELECT COUNT(*) n FROM questions q WHERE {live_question_clause('q')} AND {scope_clause} AND lower(q.subject)=lower(?)",scope_params+[subject]).fetchone()"""
    new="""    subject_sql,subject_params=_programme_subject_scope_sql(programme,subject,'q')
    row=c.execute(f"SELECT COUNT(*) n FROM questions q WHERE {live_question_clause('q')} AND {subject_sql}",subject_params).fetchone()"""
    source=replace_once(source,old,new)
    # Patch only the native builder's selection, preserving native marker and persistence.
    start=source.index('def test_start():');end=source.index("\n@app.route('/test/session/",start)
    block=source[start:end]
    block=replace_once(block,"    if guided_mode:\n        guided_scope,","    subject_scope,subject_params=_programme_subject_scope_sql(programme,subject,'q')\n    if guided_mode:\n        guided_scope,")
    block=replace_once(block,'AND {guided_scope} AND lower(q.subject)=lower(?) LIMIT 1\',guided_params+[subject])','AND {subject_scope} LIMIT 1\',subject_params)')
    block=replace_once(block,"clauses=[guided_live_question_clause('q') if guided_mode else live_question_clause('q'),'q.subject=?']\n    params=[subject]","clauses=[guided_live_question_clause('q') if guided_mode else live_question_clause('q'),subject_scope]\n    params=list(subject_params)")
    halfstart=block.index('        if guided_mode:\n            all_chapters=')
    halfend=block.index('        ctmp.close()',halfstart)
    block=block[:halfstart]+"""        all_chapters=list(dict.fromkeys(r['chapter'] for r in practice_scope_placements(ctmp,programme,guided_mode)
          if r['subject'].casefold()==subject.casefold() and r['chapter']))
"""+block[halfend:]
    source=source[:start]+block+source[end:]
    # Quick practice uses the same destination subject fence.
    start=source.index('def scoremax_test_me():');end=source.index("\n@app.route('/student/blueprint-practice",start)
    block=source[start:end].replace("scope_sql,scope_args=_programme_scope_sql(_programme_aliases(programme),'q')","scope_sql,scope_args=_programme_subject_scope_sql(programme,subject,'q')")
    block=replace_once(block,"AND q.subject=?\n        AND {scope_sql}","AND {scope_sql}")
    block=replace_once(block,"+weak_keys+weak_keys+[subject]+scope_args","+weak_keys+weak_keys+scope_args")
    source=source[:start]+block+source[end:]
    # Current MDCAT subject counts/entitlements do not inherit canonical Physics placement.
    start=source.index('def _subject_map(')
    insert=source.index('    # Declared subjects',start)
    source=source[:insert]+"""    if canonical_programme(programme)=='MDCAT':return mdcat_subject_map(c,student_id)
"""+source[insert:]
    compile(source,str(path),'exec');path.write_text(source,encoding='utf8',newline='\n')
    commercial=root/'commercial_access_engine.py';text=commercial.read_text(encoding='utf8')
    start=text.index('def programme_subjects(');end=text.index('\n\ndef effective_coverage(',start)
    text=text[:start]+COMMERCIAL.strip()+text[end:]
    compile(text,str(commercial),'exec');commercial.write_text(text,encoding='utf8',newline='\n')
    template=root/'templates/test_setup.html';text=template.read_text(encoding='utf8')
    old="countChapters();}function countChapters"
    new="const wantedChapter="+ "{{prefill.chapter|tojson}}" +",wantedTopic="+ "{{prefill.topic|tojson}}" +";if(cs.some(x=>x.chapter===wantedChapter))document.getElementById('chapterSelect').value=wantedChapter;if(ts.some(x=>x.topic===wantedTopic))document.getElementById('topicSelect').value=wantedTopic;countChapters();}function countChapters"
    text=replace_once(text,old,new);template.write_text(text,encoding='utf8',newline='\n')
    return {'files_changed':['app.py','commercial_access_engine.py','templates/test_setup.html'],'canonical_question_mutations':0}
