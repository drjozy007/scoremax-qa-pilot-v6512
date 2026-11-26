"""Portable exact-build, typed marking and scoped-worker safety controls."""
from copy import deepcopy
import hashlib,importlib.util,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT/'scoremax_runtime_v669b';PACKAGE=ROOT/'native_receiver_recovery_20261126_v1'
sys.path.insert(0,str(RUNTIME))
import ph_practice_contracts as p,ph_typed_cloze_contracts_v2 as c
spec=importlib.util.spec_from_file_location('sealed_receiver_build',PACKAGE/'apply.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def contract(answer='Pa'):
 body={'version':'PH-CLOZE-GAPS-3','source_row_sha256':'a'*64,'source_workbook_sha256':'b'*64,'source_locator':'Software negative-control fixture; no academic authority','stem_sha256':c.digest('Unit: ____.'),'gap_count':1,
 'gaps':[{'id':'opaque::gap/01','label':'G1','canonical_answer':answer,'accepted_answers':[answer],
 'normalization':{'kind':'NORMALIZED_LITERAL','casefold':False,'nfkc':True,'unicode_minus':True,'collapse_spaces':False,'remove_ascii_spaces':False}}],
 'maximum_marks':1.0,'scoring_policy':'ALL_GAPS_WITH_EXPLICIT_SOURCE_RULES','trim_spaces':True,'normalization_evidence_sha256':'c'*64}
 body['contract_sha256']=c.digest(body);return body
class Marking(unittest.TestCase):
 def test_case_sign_power_and_opaque_gap_identity(self):
  for correct,wrong in [('Pa','pA'),('x2','x²'),('x2','x₂'),('-W','W'),('Tc','tc'),('p','P')]:
   with self.subTest(correct=correct):
    x=contract(correct);p.validate_cloze(x,'Unit: ____.',1)
    self.assertTrue(p.score_gaps(x,{'opaque::gap/01':correct})[0]);self.assertFalse(p.score_gaps(x,{'opaque::gap/01':wrong})[0])
 def test_resealed_unsafe_casefold_is_rejected(self):
  for answer in ('Pa','p','Tc','N m'):
   x=contract(answer);x['gaps'][0]['normalization']['casefold']=True;x['contract_sha256']=c.digest({k:v for k,v in x.items() if k!='contract_sha256'})
   with self.assertRaisesRegex(ValueError,'SYMBOL_POLICY_CONFLICT'):p.validate_cloze(x,'Unit: ____.',1)
 def test_unknown_gap_and_unsealed_mutation_rejected(self):
  x=contract()
  with self.assertRaises(ValueError):p.score_gaps(x,{'01':'Pa'})
  x['gaps'][0]['accepted_answers'].append('pA')
  with self.assertRaises(ValueError):p.validate_cloze(x,'Unit: ____.',1)
class Packaging(unittest.TestCase):
 def test_installed_tree_is_exact_and_repeat_idempotent(self):
  self.assertEqual(build.tree(RUNTIME),build.AFTER)
  with patch.dict(os.environ,{'RENDER':'','RENDER_SERVICE_ID':''}):self.assertTrue(build.apply(RUNTIME)['replayed'])
 def test_unowned_file_drift_fails_before_any_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'runtime';shutil.copytree(RUNTIME,root,ignore=shutil.ignore_patterns('__pycache__'))
   (root/'unexpected.py').write_text('x=1\n');before=build.tree(root)
   with patch.dict(os.environ,{'RENDER':'','RENDER_SERVICE_ID':''}),self.assertRaisesRegex(ValueError,'EXACT_ACCEPTED_PARENT'):build.apply(root)
   self.assertEqual(build.tree(root),before)
 def test_linked_and_production_roots_rejected(self):
  with patch.dict(os.environ,{'RENDER_SERVICE_ID':'production'}),self.assertRaisesRegex(RuntimeError,'BUILD_ONLY'):build.apply(RUNTIME)
  with tempfile.TemporaryDirectory() as tmp:
   alias=Path(tmp)/'linked';alias.symlink_to(RUNTIME,target_is_directory=True)
   with patch.dict(os.environ,{'RENDER':'','RENDER_SERVICE_ID':''}),self.assertRaises(ValueError):build.apply(alias)
if __name__=='__main__':unittest.main()
