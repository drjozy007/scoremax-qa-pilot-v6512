"""Compare complete native evidence dicts, including future/ambiguous columns."""
import argparse,ast,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
from native_delivery_fixture import NativeDeliveryFixture

def run(runtime,reference,state):
 f=NativeDeliveryFixture(runtime,state);sm=f.native
 source=reference/'app.py';node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='learner_answer_evidence')
 scope=dict(sm.__dict__);exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope);old=scope['learner_answer_evidence']
 e=f.content('row-fidelity');f.send_content(e);f.activate(e);uid=f.learner('row-fidelity');sid,qid,programme=f.session_for(uid,e);f.submit(uid,sid)
 c=sm.db();checks=[]
 try:
  def parity(label,expected_count=1):
   for method in ('POST','GET'):
    with sm.app.test_request_context('/student/chapter',method=method):a=old(c,uid,programme)
    with sm.app.test_request_context('/student/chapter',method=method):b=sm.learner_answer_evidence(c,uid,programme)
    assert a==b,(label,method,'COMPLETE_RECORD_VALUE_DRIFT');assert len(b)==expected_count,(label,b)
    checks.append({'stage':label,'method':method,'complete_records_equal':True,'records':len(b)})
  parity('native_final_signed_question_answer')
  for column,value in [('future_opaque_metadata','α/00000::source/ID'),('student_id',912345),('Ω','Unicode capital field'),('ω','Distinct SQLite Unicode field')]:
   c.execute('ALTER TABLE attempt_answers ADD COLUMN "'+column+'"');c.execute('UPDATE attempt_answers SET "'+column+'"=?',(value,));c.commit();parity('future_column_'+column)
  f.send_stop(f.withdrawal('row-fidelity-stop',e['payload']['questions'][0],target=f.exact_target(e)))
  parity('exact_signed_withdrawal_excludes_formal_evidence',0)
  assert c.execute('SELECT COUNT(*) FROM attempts WHERE assessment_session_id=?',(sid,)).fetchone()[0]==1
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
 finally:c.close()
 return {'status':'PASSED','checks':checks,'actual_native_signed_and_final_submission_used':True,'every_unknown_source_record_field_preserved':True,'ambiguous_or_nonascii_columns_use_original_native_path':True,'academic_authority':'SOFTWARE_FIXTURES_ONLY','production_actions':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('reference',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve(),a.reference.resolve(),a.state.resolve());a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
