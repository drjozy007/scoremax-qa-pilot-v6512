"""Targeted existing-contract checks: no database or SEND."""
import ast
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
PATCH=ROOT/"ux_vnext_overlay/biology_receiver_20261027/shared_ph_guided_admission_20261031.py"

class ContractError(Exception): pass

class GuidedContract(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location("ph_guided_patch",PATCH)
  patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
  with tempfile.TemporaryDirectory() as tmp:
   target=pathlib.Path(tmp)/"scoremax_integration_v1.py"
   target.write_text("""import question_contracts
def admit_content_envelope(c,envelope,content_sha_header=''):
    errors.extend(_semantic_content_errors(questions,stimuli,schema_version))
    for q in questions:
        projection = _projection(q,stimuli)
        question_contracts.validate_assessment_contract(projection)
    return None
""")
   patch.apply(target.parent)
   before=target.read_bytes()
   patch.apply(target.parent)
   self.assertEqual(target.read_bytes(),before)
   tree=ast.parse(target.read_text())
  blocks=[node for node in tree.body if isinstance(node,ast.FunctionDef) and
          node.name in {"_ph_validate_scored_or_guided_assessment","_ph_semantic_errors_with_governed_guided"}]
  self.assertEqual(len(blocks),2)
  fake=types.ModuleType("guided_self_assessment")
  self.fake=fake
  self.old=sys.modules.get("guided_self_assessment")
  sys.modules["guided_self_assessment"]=fake
  self.env={"question_contracts":types.SimpleNamespace(
    QuestionContractError=ContractError,validate_assessment_contract=lambda p:{"mode":"SCORED"}),
    "strict_json_loads":__import__("json").loads}
  exec(compile(ast.Module(body=blocks,type_ignores=[]),"<boundary>","exec"),self.env)
  self.authority={key:False for key in ("automatic_marking","human_marking",
    "exam_readiness_evidence","formal_assessment","ai_marking",
    "ai_fallback","learner_activation_authorised")}
  self.valid={"ph_is_auto_markable":0,"marks":3,"question":"What is observed?",
    "answer":"Model answer","answer_config":"{}",
    "marking_config":'{"marks":3,"negative_marks":0,"auto_markable":false}'}
 def tearDown(self):
  if self.old is None:sys.modules.pop("guided_self_assessment",None)
  else:sys.modules["guided_self_assessment"]=self.old
 def validate(self,projection):
  return self.env["_ph_validate_scored_or_guided_assessment"](projection)
 def test_scored_still_native(self):
  self.fake.from_question=lambda q:None
  self.assertEqual(self.validate({"ph_is_auto_markable":1})["mode"],"SCORED")
 def test_missing_guided_not_rescued(self):
  self.fake.from_question=lambda q:None
  self.env["question_contracts"].validate_assessment_contract=lambda q:(_ for _ in ()).throw(ContractError("SELF_MARKING_CONTRACT_REQUIRED"))
  with self.assertRaisesRegex(ContractError,"SELF_MARKING_CONTRACT_REQUIRED"):self.validate(self.valid)
 def test_only_signed_guided_is_unscored(self):
  self.fake.from_question=lambda q:{"mode":"GUIDED_SELF_ASSESSMENT","authority":self.authority}
  self.assertFalse(self.validate(self.valid)["scoring_authorised"])
  with self.assertRaisesRegex(ContractError,"GUIDED_AUTO_MARKING_AUTHORITY_CONFLICT"):
   self.validate(dict(self.valid,ph_is_auto_markable=1))
  self.authority["ai_marking"]=True
  with self.assertRaisesRegex(ContractError,"GUIDED_AUTHORITY_NOT_UNSCORED"):self.validate(self.valid)
 def test_invalid_guided_does_not_pass(self):
  self.fake.from_question=lambda q:(_ for _ in ()).throw(ValueError("bad source"))
  with self.assertRaisesRegex(ContractError,"SOURCE_BOUND_GUIDED_CONTRACT_INVALID"):self.validate(self.valid)
 def test_semantic_filter_narrow(self):
  self.fake.from_question=lambda q:{"mode":"GUIDED_SELF_ASSESSMENT","authority":self.authority}
  self.env["_semantic_content_errors"]=lambda qs,ss,sv:[
    {"code":"UNSUPPORTED_RUBRIC_ONLY_DELIVERY","path":"payload.questions[0].content.marking.key_type"},
    {"code":"OTHER_DEFECT","path":"payload.questions[0].content"},
    {"code":"UNSUPPORTED_RUBRIC_ONLY_DELIVERY","path":"payload.questions[1].content.marking.key_type"}]
  self.env["_projection"]=lambda q,st:q["projected"]
  self.env["_ph_validate_scored_or_guided_assessment"](self.valid)
  qs=[{"content":{"marking":{"key_type":"RUBRIC_ONLY"}},"projected":self.valid},
      {"content":{"marking":{"key_type":"RUBRIC_ONLY"}},"projected":dict(self.valid,ph_is_auto_markable=1)}]
  result=self.env["_ph_semantic_errors_with_governed_guided"](qs,[],"1.2.0")
  self.assertEqual([r["code"] for r in result],
    ["OTHER_DEFECT","UNSUPPORTED_RUBRIC_ONLY_DELIVERY"])

if __name__=="__main__":unittest.main()
