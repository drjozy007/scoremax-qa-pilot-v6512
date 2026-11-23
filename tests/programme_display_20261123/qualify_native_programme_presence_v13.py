"""Exact native programme presence counts on current committed SQLite state."""
from pathlib import Path
import argparse,ast,json,sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]

def run(runtime,state):
    if not state.resolve().is_relative_to(ROOT):raise ValueError('OWNED_DISPOSABLE_STATE_REQUIRED')
    sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
    from native_delivery_fixture import NativeDeliveryFixture
    f=NativeDeliveryFixture(runtime,state);sm=f.native;c=sm.db();uid=f.learner('programme-presence-v13')
    columns={r[1] for r in c.execute('PRAGMA table_info(questions)')}
    shapes=[('Grade 9','Grade 10'),('FSc Part 1',''),(' FSc Part 1 ','Grade 9'),
        ('MDCAT','FSc Part 2'),('FÍSICA','Física'),(None,'FSc Part 1'),('',None),('000016','16')]
    for n,(programme,qualification) in enumerate(shapes):
        row=dict(question_id='SOFTWARE-PROGRAMME-'+str(n),family_id='PROGRAMME-FAMILY-'+str(n),
            country='Pakistan',programme=programme,qualification=qualification,subject='Biology',
            chapter='opaque::programme',topic='Fixture',qtype='single_choice',level='Foundation',
            question='Disposable native programme count',option_a='A',option_b='B',answer='A',
            status='Approved',review_status='Approved',active=1,is_demo=0)
        row['family_key']=sm.upsert_question_family(c,row,review_status='Approved',active=1)
        values={k:v for k,v in row.items() if k in columns}
        c.execute('INSERT INTO questions('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()))
    c.commit();e=f.content('programme-presence-v13');f.send_content(e);f.activate(e);checks=[]
    def parity(stage):
        changed=c.total_changes
        for values in ([],['Grade 9'],[r['value'] for r in sm.STUDENT_PROGRAMME_CHOICES],
                       ['Grade 9','Grade 10','FSc Part 1',' FSc Part 1 ','MDCAT','FÍSICA','Física','000016','16','unknown::value']*2,
                       ['unknown::'+str(n) for n in range(65)]):
            expected=[]
            for value in values:
                row=c.execute("SELECT EXISTS(SELECT 1 FROM questions q WHERE (lower(COALESCE(q.programme,''))=lower(?) OR lower(COALESCE(q.qualification,''))=lower(?)) AND "+sm.live_question_clause('q')+") n",(value,value)).fetchone();expected.append(int(row['n'] or 0))
            assert sm._programme_presence_once_v12(c,values)==expected,(stage,values)
        counts=sm.student_programme_options(c,uid);presence=sm.student_programme_options(c,uid,content_presence_only=True)
        assert len(counts)==len(presence)
        for a,b in zip(counts,presence):
            assert bool(a['question_count'])==bool(b['question_count'])
            assert {k:v for k,v in a.items() if k!='question_count'}=={k:v for k,v in b.items() if k!='question_count'}
        assert c.total_changes==changed
        checks.append(stage)
    parity('native_active_and_legacy_raw_scope')
    c.execute("UPDATE questions SET active=0 WHERE question_id='SOFTWARE-PROGRAMME-0'");c.commit();parity('current_question_commit')
    c.execute("UPDATE question_families SET active=0 WHERE family_key IN (SELECT family_key FROM questions WHERE question_id='SOFTWARE-PROGRAMME-1')");c.commit();parity('current_family_hold')
    c.execute("UPDATE integration_ph_product_activation_authorizations SET activation_status='REVOKED'");c.commit();parity('revoked_activation')
    c.execute("UPDATE integration_ph_product_activation_authorizations SET activation_status='AUTHORIZED'");c.commit();f.send_stop(f.withdrawal('programme-presence-stop',e['payload']['questions'][0]));parity('exact_signed_withdrawal')
    with patch.object(sm.sqlite3,'sqlite_version_info',(3,34,0)):
        parity('older_sqlite_exact_fallback')
    import sqlite3
    with sm.app.test_request_context('/student/subject/Biology',method='GET'):
        assert sm._programme_presence_once_v12(c,['000016'])==[1]
        assert sm._programme_presence_once_v12(c,['000016'])==[1]
        writer=sqlite3.connect(f.state_directory/'native.db')
        try:
            writer.execute("UPDATE questions SET active=0 WHERE question_id='SOFTWARE-PROGRAMME-7'");writer.commit()
        finally:writer.close()
        assert sm._programme_presence_once_v12(c,['000016'])==[0], 'STALE_DISPLAY_AFTER_EXTERNAL_COMMIT'
    checks.append('warm_GET_display_cache_external_commit')
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall();c.close()
    return {'status':'PASSED','stages':checks,'raw_programme_or_qualification_semantics_preserved':True,
        'unicode_null_whitespace_and_opaque_labels_preserved':True,'full_counts_unchanged':True,
        'read_only_and_commit_fresh':True,'bounded_16_and_large_fallback':True,'production_actions':False,
        'academic_or_marking_authority_created':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve(),a.state.resolve());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,sort_keys=True))
