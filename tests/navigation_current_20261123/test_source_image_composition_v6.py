"""Pure-work reduction preserves native aliases and private evidence isolation."""
import ast,copy,importlib.util,sys,types,unittest
from pathlib import Path
from jinja2 import Environment,DictLoader
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT/'scoremax_runtime_v669b'

def function(path,name,namespace):
 node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace);return namespace[name]
class PureExistingSemantics(unittest.TestCase):
 def test_existing_canonical_and_alias_and_unknown_values_keep_exact_meaning(self):
  source=RUNTIME/'question_contract_engine.py';ns={};groups=function(source,'_programme_alias_groups',ns);new=function(source,'canonical_programme',ns)
  def original(value):
   value=str(value or '').strip();key=' '.join(value.split()).casefold()
   return next((name for name,aliases in ns['_programme_alias_groups']().items() if key in {str(x).casefold() for x in aliases}),value)
  values=[None,False,0,1,['opaque'],{},'Ω::00001','Unrecognised programme',' FSc   Part 1 ']
  for name,aliases in groups().items():values.extend([name,*aliases,*[str(x).swapcase() for x in aliases]])
  for value in values:self.assertEqual(new(value),original(value))
  ns['_programme_alias_groups']=lambda:{'Changed native label':('FSc Part 1','opaque::known')}
  self.assertEqual(new('FSc Part 1'),'Changed native label');self.assertEqual(new('opaque::known'),'Changed native label')
 def test_private_row_copy_preserves_unknown_nested_values_and_detaches_returned_records(self):
  outer=next(n for n in ast.parse((RUNTIME/'app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='learner_answer_evidence')
  inner=next(n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='_clone_frozen_rows');scope={'g':types.SimpleNamespace(),'deepcopy':copy.deepcopy};exec(compile(ast.Module(body=[inner],type_ignores=[]),'native-row-copy','exec'),scope)
  private=[{'id':1,'future_opaque':'Ω/0001','bytes':b'future','none':None},{'id':2,'future':{'items':['unchanged']}}];before=copy.deepcopy(private)
  public=scope['_clone_frozen_rows'](private);public[0]['future_opaque']='changed';public[1]['future']['items'].append('changed')
  self.assertEqual(private,before);self.assertEqual(scope['_clone_frozen_rows'](private),before)
 def test_template_compilation_uses_existing_code_cache_without_rendering(self):
  spec=importlib.util.spec_from_file_location('static_template_compile_test',RUNTIME/'navigation_template_compile_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  env=Environment(loader=DictLoader({'take_test_v4.html':"{% extends 'base.html' %}{% block x %}{{ secret() }}{% include '_image.html' %}{% endblock %}",'result.html':"{% extends 'base.html' %}",'base.html':'{% block x %}{% endblock %}','_image.html':'{{secret()}}'}));calls=[];env.globals['secret']=lambda:calls.append('rendered');out=m.compile_learner_templates(env)
  self.assertEqual(out['compiled'],4);self.assertFalse(out['rendered']);self.assertFalse(out['database_opened']);self.assertFalse(out['authority_cached']);self.assertEqual(calls,[]);self.assertGreaterEqual(len(env.cache),4)
 def test_template_dependency_work_is_bounded(self):
  spec=importlib.util.spec_from_file_location('static_template_bound_test',RUNTIME/'navigation_template_compile_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);templates={'take_test_v4.html':'', 'result.html':"{% include '0.html' %}"}
  for n in range(34):templates[str(n)+'.html']="{% include '"+str(n+1)+".html' %}"
  with self.assertRaisesRegex(RuntimeError,'DEPENDENCY_BUDGET'):m.compile_learner_templates(Environment(loader=DictLoader(templates)))
if __name__=='__main__':unittest.main()
