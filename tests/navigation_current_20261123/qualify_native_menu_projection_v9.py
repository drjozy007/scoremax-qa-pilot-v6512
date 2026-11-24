"""Native SQLite/HMAC count parity. Software authorities confer no real approval."""
from __future__ import annotations
import argparse,ast,hashlib,json,sys
from unittest.mock import patch
from pathlib import Path


def original_function(path,name,namespace):
    text=path.read_text(encoding='utf-8')
    nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name]
    for node in nodes:node.decorator_list=[]
    assert len(nodes)==1
    scope=dict(namespace)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path), 'exec'),scope)
    return scope[name]


def run(runtime,reference,state):
    continuation=Path(__file__).resolve().parents[2]
    if not state.resolve().is_relative_to(continuation):
        raise RuntimeError('OWNED_DISPOSABLE_DIRECTORY_REQUIRED')
    sys.path.insert(0,str(continuation/'tests/biology_receiver_20261027'))
    from native_delivery_fixture import NativeDeliveryFixture
    fixture=NativeDeliveryFixture(runtime,state)
    sm=fixture.native
    import ux_student_batch as cards
    old_options=original_function(reference/'app.py','student_programme_options',sm.__dict__)
    old_cards=original_function(reference/'ux_student_batch.py','_chapter_snapshots',cards.__dict__)
    old_map=original_function(reference/'app.py','_subject_map',sm.__dict__)
    old_mastery=original_function(reference/'app.py','chapter_mastery_opportunity',sm.__dict__)
    old_inject=original_function(reference/'app.py','inject_ui_preferences',{**sm.__dict__,'_subject_map':old_map})
    c=sm.db()
    uid=c.execute("INSERT INTO users(role,system_user_id,username,full_name,academic_level,active_programme,subjects,account_status,email_verified) VALUES('student','SOFTWARE-COUNTS','software-counts','Software count fixture','FSc Part 1','FSc Part 1','Biology,FÍSICA,Física','active',1)").lastrowid
    columns={r[1] for r in c.execute('PRAGMA table_info(questions)')}
    shapes=[('Biology','opaque::chapter/α','FSc Part 1','MDCAT'),
            ('BIOLOGY','opaque::chapter/α ','FSc Part 1','FSc Part 1'),
            ('Biology','2 — Biological Molecules','FSc Part 1',''),
            ('FÍSICA','opaque::unicode','FSc Part 1',''),
            ('Física','opaque::unicode','MDCAT','FSc Part 1'),
            ('İSTANBUL','',None,'FSc Part 1'),
            ('Biology',None,'FSc Part 2','FSc Part 1')]
    for index,(subject,chapter,programme,qualification) in enumerate(shapes):
        row=dict(question_id='SOFTWARE-LEGACY-'+str(index),family_id='SOFTWARE-FAMILY-'+str(index),
            country='Pakistan',qualification=qualification,programme=programme,subject=subject,
            chapter=chapter,topic='Software fixture',qtype='single_choice',level='Foundation',
            question='Disposable count control',option_a='A',option_b='B',option_c='C',option_d='D',
            answer='A',status='Approved',review_status='Approved',active=1,is_demo=0,
            source_type='SOFTWARE_AUTHORITY_FIXTURE_ONLY')
        row['family_key']=sm.upsert_question_family(c,row,review_status='Approved',active=1)
        values={k:v for k,v in row.items() if k in columns}
        c.execute('INSERT INTO questions('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()))
    # Explicit software presentation rows exercise SQLite subject matching,
    # raw opaque/whitespace keys and native exact/fallback programme priority.
    for programme,subject,chapter,label,source in [
        ('FSc Part 1','Biology','opaque::chapter/α','Exact generated','SOURCE_LABEL'),
        ('MDCAT','Biology','opaque::chapter/α','Other governed','POWER_HOUSE'),
        ('','Biology','opaque::chapter/α','Default governed','ADMIN_GOVERNED'),
        ('FSc Part 1','BIOLOGY','opaque::chapter/α','Exact governed','GOVERNED_IMPORT'),
        ('','Física','opaque::unicode','Unicode lower fallback','POWER_HOUSE'),
        ('MDCAT','FÍSICA','opaque::unicode','Unicode distinct','SOURCE_LABEL'),
        ('','Biology','2 — Biological Molecules','Default label','SOURCE_LABEL')]:
        c.execute("INSERT INTO chapter_catalogue(programme,subject,source_chapter,chapter_number,chapter_name,display_label,identity_status,metadata_source) VALUES(?,?,?,?,?,?,?,?)",
            (programme,subject,chapter,'opaque-number',label,label,'SOFTWARE_ONLY',source))
    c.commit()
    env=fixture.content('atomic-count-native')
    fixture.send_content(env);fixture.activate(env)
    ph=env['payload']['questions'][0]
    question=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(ph['question_id'],)).fetchone()
    assert question
    subjects=['Biology','BIOLOGY','FÍSICA','Física','İSTANBUL','Unknown',question['subject']]
    chapters=['opaque::chapter/α','opaque::chapter/α ','2 — Biological Molecules','OPAQUE::CHAPTER/Α',
              'opaque::unicode','',question['chapter']]+['empty::'+str(n) for n in range(35)]
    checks=[]
    def parity(stage):
        menu_cases=[]
        if stage in ('active_native_signed_version_and_legacy_shapes','signed_matching_withdrawal_next_read'):
            for home in ('FSc Part 1','FSc Part 2','Grade 9','MDCAT','unknown::programme'):
                for programme in ('FSc Part 1','FSc Part 2','MDCAT','unknown::programme'):
                    for declared in ('Biology,Chemistry,Physics','FÍSICA,Física',''):
                        c.execute('UPDATE users SET academic_level=?,active_programme=?,subjects=? WHERE id=?',(home,programme,declared,uid));c.commit()
                        for route in ('/student/learn-vnext','/student/subject/Biology','/test/setup','/student/pathways'):
                            outputs=[]
                            for function in (old_inject,sm.inject_ui_preferences):
                                with sm.app.test_request_context(route,method='GET'):
                                    from flask import session
                                    session.update(user_id=uid,role='student',session_version=0)
                                    outputs.append(function())
                            for output in outputs:
                                output['subject_nav_global']=[{key:row.get(key) for key in ('subject','answered','accuracy','access_state','url')} for row in output['subject_nav_global']]
                            assert outputs[0]==outputs[1],(stage,home,programme,declared,route,outputs)
                            menu_cases.append((home,programme,declared,route))
            c.execute("UPDATE users SET academic_level='FSc Part 1',active_programme='FSc Part 1',subjects='Biology,FÍSICA,Física' WHERE id=?",(uid,));c.commit()
        print('EXACT_MENU_CONTEXT_PARITY',stage,len(menu_cases),flush=True)
        changes=c.total_changes
        for programme in ('FSc Part 1','FSc Part 2','MDCAT','unknown::programme'):
            for subject in subjects:
                expected={}
                for chapter in dict.fromkeys(chapters):
                    clause,params=sm._programme_chapter_scope_sql(programme,chapter,'q')
                    row=c.execute(f"SELECT COUNT(*) n FROM questions q WHERE {sm.live_question_clause('q')} AND lower(COALESCE(q.subject,''))=lower(?) AND {clause}",[subject]+params).fetchone()
                    expected[chapter]=int(row['n'] or 0)
                got=cards._chapter_scope_counts_once(c,programme,subject,chapters)
                assert expected==got,(stage,programme,subject,expected,got)
        assert sm.student_programme_options(c,uid)==old_options(c,uid),stage
        exact=old_options(c,uid)
        present=sm.student_programme_options(c,uid,content_presence_only=True)
        assert len(exact)==len(present)
        for old,new in zip(exact,present):
            assert bool(old['question_count'])==bool(new['question_count'])
            assert {k:v for k,v in old.items() if k!='question_count'}=={k:v for k,v in new.items() if k!='question_count'}
        assert c.total_changes==changes,'Count reads mutated state'
        with sm.app.test_request_context('/student/subject/Biology',method='GET'):
            from flask import session
            session.update(user_id=uid,role='student',session_version=0)
            current_cards=cards._chapter_snapshots(c,uid,'Biology')
            with patch.object(sm,'chapter_mastery_opportunity',old_mastery):
                reference_cards=old_cards(c,uid,'Biology')
            assert current_cards==reference_cards,stage
            for programme,subject,chapter in [('FSc Part 1','Biology','opaque::chapter/α'),('MDCAT','Física','opaque::unicode')]:
                assert sm.chapter_mastery_opportunity(c,uid,subject,chapter,programme)==old_mastery(c,uid,subject,chapter,programme),stage
        with sm.app.test_request_context('/student/learn-vnext',method='GET'):
            original_map=old_map(c,uid)
        with sm.app.test_request_context('/student/learn-vnext',method='GET'):
            cached_map=sm._subject_map(c,uid)
        assert original_map==cached_map,(stage,'subject map changed')
        with sm.app.test_request_context('/student/learn-vnext',method='GET'):
            full=sm._subject_map(c,uid)
            summary=sm._subject_map(c,uid,_summary_only=True)
            assert [{k:v for k,v in row.items() if k!='chapters'} for row in full]==[{k:v for k,v in row.items() if k!='chapters'} for row in summary],stage
            assert all(not row['chapters'] for row in summary),stage
            assert sm._subject_map(c,uid)==full,'SUMMARY_CACHE_CONTAMINATED_FULL_MAP'
        checks.append({'stage':stage,'programme_subject_pairs':28,'chapter_inputs':len(chapters)})
    parity('active_native_signed_version_and_legacy_shapes')
    c.execute('UPDATE questions SET ph_question_checksum_sha256=? WHERE id=?',('0'*64,question['id']));c.commit()
    parity('checksum_mismatch')
    c.execute('UPDATE questions SET ph_question_checksum_sha256=? WHERE id=?',(question['ph_question_checksum_sha256'],question['id']));c.commit()
    c.execute('UPDATE integration_ph_product_activation_authorizations SET activation_status=?',('REVOKED',));c.commit()
    parity('activation_revoked')
    c.execute('UPDATE integration_ph_product_activation_authorizations SET activation_status=?',('AUTHORIZED',));c.commit()
    c.execute('UPDATE question_families SET active=0 WHERE family_key=?',(question['family_key'],));c.commit()
    parity('family_held')
    c.execute('UPDATE question_families SET active=1 WHERE family_key=?',(question['family_key'],));c.commit()
    fixture.send_stop(fixture.withdrawal('atomic-count-stop',ph))
    parity('signed_matching_withdrawal_next_read')
    check=c.execute('PRAGMA integrity_check').fetchone()[0]
    fk=c.execute('PRAGMA foreign_key_check').fetchall()
    assert check=='ok' and not fk
    formal=c.execute('SELECT COUNT(*) FROM mastery_records WHERE student_id=?',(uid,)).fetchone()[0]
    assert formal==0
    c.close()
    return {'version':'SCOREMAX-DISPLAY-INVENTORY-NATIVE-SELF-AUDIT-6','status':'PASSED',
        'runtime':str(runtime),'reference':str(reference),'checks':checks,
        'native_signed_http_used':True,'academic_approval_conferred':False,
        'native_opaque_unicode_whitespace_null_scope_parity':True,
        'chunked_more_than_16_chapters':True,'full_chapter_snapshot_parity':True,
        'menu_or_programme_qualification_count_parity':True,'formal_mastery_records_created':formal,
        'integrity_check':check,'foreign_key_violations':len(fk),'production_mutated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('reference',type=Path)
    p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=run(a.runtime.resolve(),a.reference.resolve(),a.state.resolve())
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,sort_keys=True))
