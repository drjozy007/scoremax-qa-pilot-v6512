"""Native weighted-count query parity, unknown-emitter fallback and commit freshness."""
from pathlib import Path
import argparse,json,sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]

def run(runtime,state):
    if not state.resolve().is_relative_to(ROOT):raise ValueError('OWNED_DISPOSABLE_STATE_REQUIRED')
    sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
    from native_delivery_fixture import NativeDeliveryFixture
    f=NativeDeliveryFixture(runtime,state);sm=f.native
    import ux_student_batch as cards
    assert cards._known_native_chapter_scope_v11(sm._programme_chapter_scope_sql)
    c=sm.db();columns={r[1] for r in c.execute('PRAGMA table_info(questions)')}
    shapes=['opaque::01','opaque::01 ','OPAQUE::01',None,'','FÍSICA','Física','a\t','a']
    for n in range(180):
        row=dict(question_id='SOFTWARE-WEIGHTED-'+str(n),family_id='WEIGHTED-FAMILY-'+str(n),
            country='Pakistan',qualification='FSc Part 1',programme='FSc Part 1',subject='Biology',
            chapter=shapes[n%len(shapes)],topic='Fixture',qtype='single_choice',level='Foundation',
            question='Disposable weighted count',option_a='A',option_b='B',answer='A',
            status='Approved',review_status='Approved',active=1,is_demo=0)
        row['family_key']=sm.upsert_question_family(c,row,review_status='Approved',active=1)
        row={k:v for k,v in row.items() if k in columns}
        c.execute('INSERT INTO questions('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
    c.commit();e=f.content('weighted-native-scope');f.send_content(e);f.activate(e)
    q=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(e['payload']['questions'][0]['question_id'],)).fetchone()
    chapters=shapes+[q['chapter']]+['empty::'+str(n) for n in range(35)]
    native=sm._programme_chapter_scope_sql;checks=[]
    def parity(stage):
        before=c.total_changes
        for programme in ('FSc Part 1','FSc Part 2','MDCAT','unknown::programme'):
            expected={}
            for chapter in dict.fromkeys(chapters):
                clause,args=native(programme,chapter,'q')
                row=c.execute('SELECT COUNT(*) n FROM questions q WHERE '+sm.live_question_clause('q')+" AND lower(COALESCE(q.subject,''))=lower(?) AND "+clause,['Biology']+args).fetchone()
                expected[chapter]=int(row['n'] or 0)
            weighted=cards._chapter_scope_counts_once(c,programme,'Biology',chapters)
            assert weighted==expected,(stage,programme,weighted,expected)
            def unknown(*args,**kwargs):return native(*args,**kwargs)
            assert not cards._known_native_chapter_scope_v11(unknown)
            queries=[];c.set_trace_callback(queries.append)
            try:
                with patch.object(sm,'_programme_chapter_scope_sql',unknown):
                    fallback=cards._chapter_scope_counts_once(c,programme,'Biology',chapters)
            finally:c.set_trace_callback(None)
            assert fallback==expected,(stage,'fallback',programme)
        assert c.total_changes==before
        checks.append(stage)
    parity('current_signed_and_legacy')
    c.execute("UPDATE questions SET active=0 WHERE question_id='SOFTWARE-WEIGHTED-0'");c.commit();parity('legacy_commit_invalidates')
    c.execute("UPDATE integration_ph_product_activation_authorizations SET activation_status='REVOKED'");c.commit();parity('revoked_native_authority')
    c.execute("UPDATE integration_ph_product_activation_authorizations SET activation_status='AUTHORIZED'");c.commit()
    f.send_stop(f.withdrawal('weighted-native-stop',e['payload']['questions'][0]));parity('exact_signed_withdrawal')
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    c.close()
    return {'status':'PASSED','stages':checks,'native_and_unknown_emitter_parity':True,
        'opaque_unicode_null_whitespace_and_binary_chapter_keys':True,'unchanged_native_predicates':True,
        'source_authority':'SOFTWARE_FIXTURES_ONLY','production_actions':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();result=run(a.runtime.resolve(),a.state.resolve());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
