"""Coach selection projects the same native fields without catalogue scans."""
import ast,copy,sqlite3,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT/'scoremax_runtime_v669b'
def function(name,namespace):
 node=next(n for n in ast.parse((RUNTIME/'app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),'native-function-test','exec'),namespace);return namespace[name]
class CoachProjection(unittest.TestCase):
 def test_selection_fields_match_full_snapshot_for_current_native_user_and_preference_states(self):
  c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.executescript('CREATE TABLE users(id INTEGER,academic_level TEXT,future_pathway_code TEXT);CREATE TABLE student_pathway_preferences(student_id INTEGER,pathway_code TEXT);');calls=[]
  def inventory(c,sql,values,columns):
   calls.append(columns);return [{'subject':'Biology'}] if columns==('subject',) else [{'programme':'FSc Part 1'}] if columns==('programme',) else [{'framework_name':'MDCAT'}]
  module=types.SimpleNamespace(display_inventory=inventory);ns={'pathway_definition':lambda code:{'code':code},'is_matric_level':lambda level:level in ('Grade 9','Grade 10'),'live_question_clause':lambda q:'1=1','PATHWAY_CATALOGUE':[{'code':'science','subjects':['Biology','Unknown'],'future_assessments':['MDCAT']}]};f=function('student_pathway_snapshot',ns)
  with patch.dict(sys.modules,{'navigation_display_reads_v5':module}):
   for level in ('Grade 9','Grade 10','FSc Part 1','FSc Part 2','MDCAT','opaque::unknown',''):
    for saved,preference in [('',''),('science',''),('science','other'),('science',None)]:
     c.execute('DELETE FROM users');c.execute('DELETE FROM student_pathway_preferences');c.execute('INSERT INTO users VALUES(1,?,?)',(level,saved))
     if preference is not None:c.execute('INSERT INTO student_pathway_preferences VALUES(1,?)',(preference,))
     full=f(c,1);before=len(calls);selection=f(c,1,_selection_only=True)
     self.assertEqual(selection,{k:full[k] for k in ('is_matric','selected_code')});self.assertEqual(len(calls),before);self.assertIn('options',full)
   full=f(c,999);before=len(calls);selection=f(c,999,_selection_only=True);self.assertEqual(selection,{k:full[k] for k in selection});self.assertEqual(len(calls),before)
  c.close()
 def test_coach_requests_selection_only_and_full_view_default_is_preserved(self):
  tree=ast.parse((RUNTIME/'app.py').read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='scoremax_coach_candidates');calls=[n for n in ast.walk(f) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='student_pathway_snapshot'];self.assertEqual(len(calls),1);self.assertTrue(next(k.value.value for k in calls[0].keywords if k.arg=='_selection_only'))
  f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='student_pathway_snapshot');self.assertIs(f.args.defaults[0].value,False)
 def test_mutable_returned_record_never_inherits_private_scalar_proof(self):
  outer=next(n for n in ast.parse((RUNTIME/'app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='learner_answer_evidence');inner=next(n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='_clone_frozen_rows');g=types.SimpleNamespace();ns={'g':g,'deepcopy':copy.deepcopy};exec(compile(ast.Module(body=[inner],type_ignores=[]),'native-clone-test','exec'),ns);f=ns['_clone_frozen_rows'];private=[{'id':1,'metadata':'opaque'}];public=f(private);self.assertNotIn(id(public[0]),g._scoremax_scalar_shape_proofs_v4);public[0]['new_nested']={'items':[]};again=f(public);again[0]['new_nested']['items'].append('changed');self.assertEqual(public[0]['new_nested'],{'items':[]});self.assertEqual(private,[{'id':1,'metadata':'opaque'}])
if __name__=='__main__':unittest.main()
