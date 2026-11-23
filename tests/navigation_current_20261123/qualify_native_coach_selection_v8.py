"""Compare exact native coach results across home levels and saved preferences."""
from pathlib import Path
import argparse,ast,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
from native_delivery_fixture import NativeDeliveryFixture

def run(runtime,reference,state):
 f=NativeDeliveryFixture(runtime,state);sm=f.native;node=next(n for n in ast.parse((reference/'app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='scoremax_coach_candidates');scope=dict(sm.__dict__);exec(compile(ast.Module(body=[node],type_ignores=[]),'previous-native-coach','exec'),scope);old=scope['scoremax_coach_candidates'];uid=f.learner('native-coach-selection-v8');c=sm.db();checks=[]
 try:
  choice=sm.PATHWAY_CATALOGUE[0]['code'];before={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['questions','attempts','attempt_answers','mastery_records','integration_outbox']}
  for level in ('Grade 9','Grade 10','FSc Part 1','FSc Part 2','MDCAT','opaque::unknown',''):
   for pref in (None,'',choice):
    for enabled in (0,1):
     c.execute('UPDATE users SET academic_level=?,future_pathway_code=?,coach_enabled=? WHERE id=?',(level,choice,enabled,uid));c.execute('DELETE FROM student_pathway_preferences WHERE student_id=?',(uid,))
     if pref is not None:c.execute('INSERT INTO student_pathway_preferences(student_id,pathway_code) VALUES(?,?)',(uid,pref))
     c.commit();expected=old(c,uid);actual=sm.scoremax_coach_candidates(c,uid);assert actual==expected,(level,pref,enabled,'NATIVE_COACH_BEHAVIOUR_DRIFT');checks.append({'home_level':level,'preference_kind':'absent' if pref is None else 'explicit_empty' if pref=='' else 'selected','enabled':bool(enabled),'native_candidates_equal':True})
  assert before=={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in before};assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
 finally:c.close()
 return {'status':'PASSED_NATIVE_COACH_SELECTION_PROJECTION','native_cases':len(checks),'checks':checks,'question_answer_mastery_outbox_rows_unchanged':True,'academic_authority':'SOFTWARE_FIXTURES_ONLY','production_actions':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('reference',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve(),a.reference.resolve(),a.state.resolve());a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
