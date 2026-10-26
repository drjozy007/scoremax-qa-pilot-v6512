"""New learner-display regression only; no historical qualification."""
import ast,copy,importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve()
sys.argv=sys.argv[:1]
source=(ROOT/'app.py').read_text(encoding='utf8')
names={'chapter_identity','learner_answer'}
nodes=[copy.deepcopy(n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
for n in nodes:n.decorator_list=[]
space={'json':json,'canonical_programme':lambda p:p}
sys.path.insert(0,str(ROOT))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<exact-new-display-functions>','exec'),space)
local_dependencies=Path(__file__).resolve().parents[2]/'.test_deps'
if local_dependencies.is_dir():sys.path.insert(0,str(local_dependencies))
from jinja2 import Environment,DictLoader,select_autoescape
class DisplayTests(unittest.TestCase):
 def test_official_unit_labels_preserve_exact_destination_keys(self):
  for subject,number in [('Chemistry',3),('Chemistry',4),('Chemistry',5),('Biology',4)]:
   key=f'MDCAT::{subject.upper()}::UNIT::{number:02d}'
   value=space['chapter_identity'](None,'MDCAT',subject,key)
   self.assertEqual(value['chapter'],key)
   self.assertEqual(value['chapter_kind'],'Unit')
   self.assertTrue(value['chapter_name'])
   self.assertTrue(value['display_label'].startswith(f'Unit {number} — '))
   self.assertNotIn('::',value['display_label'])
 def test_fsc_catalogue_labels_remain_unchanged(self):
  row={'chapter_number':'13','chapter_name':'Thermal Physics','display_label':'Chapter 13 — Thermal Physics','identity_status':'RESOLVED','metadata_source':'GOVERNED_IMPORT'}
  class Connection:
   def execute(self,*a):return self
   def fetchone(self):return row
  value=space['chapter_identity'](Connection(),'FSc Part 2','Physics','13 — Thermal Physics')
  self.assertEqual(value['display_label'],row['display_label'])
  self.assertEqual(value['chapter'],'13 — Thermal Physics')
 def test_plain_mcq_and_written_answers_are_unchanged(self):
  for answer in ('A','R = 0.0821 dm3 atm mol-1 K-1','PV=nRT'):
   self.assertEqual(space['learner_answer'](answer),answer)
  self.assertEqual(space['learner_answer'](''),'No answer')
 def test_structured_answers_show_statements_equations_and_working(self):
  raw=json.dumps({'version':'PH-STRUCTURED-PRACTICE-1','assertions':[{'subject':'n','relation':'represents','object':'amount of gas'}],'equations':['PV=nRT'],'values':[{'value':'273','unit':'K','working':'T = 0 + 273'}]})
  before=raw
  result=space['learner_answer'](raw)
  for text in ('n represents amount of gas','PV=nRT','273 K','Working: T = 0 + 273'):self.assertIn(text,result)
  self.assertNotIn('PH-STRUCTURED',result);self.assertNotIn('assertions',result)
  self.assertEqual(raw,before)
 def test_saved_scientific_text_is_still_html_escaped(self):
  raw=json.dumps({'version':'PH-STRUCTURED-PRACTICE-1','assertions':[{'subject':'<script>alert(1)</script>','relation':'is','object':'a submitted string'}],'equations':[],'values':[]})
  env=Environment(autoescape=True);env.filters['learner_answer']=space['learner_answer']
  rendered=env.from_string('{{answer|learner_answer}}').render(answer=raw)
  self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
 def test_actual_practice_builder_renders_units_with_raw_routing_values(self):
  template=(ROOT/'templates/test_setup.html').read_text(encoding='utf8')
  env=Environment(loader=DictLoader({'base.html':'{% block content %}{% endblock %}','test_setup.html':template}),autoescape=True)
  env.globals.update(url_for=lambda *a,**k:'/',csrf_token=lambda:'synthetic-local-token')
  key='MDCAT::CHEMISTRY::UNIT::03';identity=space['chapter_identity'](None,'MDCAT','Chemistry',key)
  prefill=dict(programme='MDCAT',subject='Chemistry',chapter=key,response_mode='',scope='chapter',mode='practice',topic='')
  rendered=env.get_template('test_setup.html').render(prefill=prefill,programmes=['MDCAT'],subjects=['Chemistry'],subject_programmes=[{'programme':'MDCAT','subject':'Chemistry'}],chapters=[dict(identity,programme='MDCAT',subject='Chemistry')],topics=[],subject_cards=[],access={'mastery_ceiling':'Foundation'},levels=['Foundation','Exam Ready'])
  self.assertIn('One unit</option>',rendered);self.assertIn('Several units</option>',rendered)
  self.assertIn('Unit<select',rendered)
  self.assertIn(key,rendered);self.assertIn('Unit 3',rendered)
  result=(ROOT/'templates/result.html').read_text(encoding='utf8')
  self.assertEqual(result.count('d.selected_answer|learner_answer'),3)
  env.parse(result);env.parse((ROOT/'templates/chapter_page.html').read_text(encoding='utf8'))
if __name__=='__main__':unittest.main()
