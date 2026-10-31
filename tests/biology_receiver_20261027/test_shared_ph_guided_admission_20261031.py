"""Targeted contract-boundary protection. Does not touch production databases."""
import ast
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCH = ROOT / "ux_vnext_overlay/biology_receiver_20261027/shared_ph_guided_admission_20261031.py"

class ContractError(Exception):
    pass

class GuidedAdmission(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("_guided_admission_patch", PATCH)
        self.patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.patch)
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "scoremax_integration_v1.py"
            path.write_text("""import question_contracts
def admit_content_envelope(c,envelope,content_sha_header=''):
    try:
        projection = envelope
        question_contracts.validate_assessment_contract(projection)
    except (question_contracts.QuestionContractError,KeyError,TypeError) as exc:
        pass
    return None
""")
            self.patch.apply(path.parent)
            before=path.read_bytes()
            self.patch.apply(path.parent)
            self.assertEqual(path.read_bytes(),before)
            tree=ast.parse(path.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                      and n.name=="_ph_validate_scored_or_guided_assessment")
        self.check=compile(ast.Module(body=[function],type_ignores=[]),"<isolated-helper>","exec")
        guided=types.ModuleType("guided_self_assessment")
        self.guided=guided
        self._old=sys.modules.get("guided_self_assessment")
        sys.modules["guided_self_assessment"]=guided
        self.env={"question_contracts":types.SimpleNamespace(
            QuestionContractError=ContractError,
            validate_assessment_contract=lambda row: {"mode":"SCORED"})}
        exec(self.check,self.env)

    def tearDown(self):
        if self._old is None: sys.modules.pop("guided_self_assessment",None)
        else: sys.modules["guided_self_assessment"]=self._old

    def invoke(self,row):
        return self.env["_ph_validate_scored_or_guided_assessment"](row)

    def test_scored_path_unchanged(self):
        self.guided.from_question=lambda row:None
        self.assertEqual(self.invoke({"ph_is_auto_markable":1})["mode"],"SCORED")

    def test_missing_guided_is_not_approved(self):
        self.guided.from_question=lambda row:None
        self.env["question_contracts"].validate_assessment_contract=lambda row: (_ for _ in ()).throw(ContractError("SELF_MARKING_CONTRACT_REQUIRED"))
        with self.assertRaisesRegex(ContractError,"SELF_MARKING_CONTRACT_REQUIRED"):
            self.invoke({"ph_is_auto_markable":0})

    def test_source_bound_unscored_only(self):
        authority={k:False for k in ("automatic_marking","human_marking","exam_readiness_evidence","formal_assessment","ai_marking","ai_fallback","learner_activation_authorised")}
        self.guided.from_question=lambda row:{"mode":"GUIDED_SELF_ASSESSMENT","authority":authority}
        self.assertFalse(self.invoke({"ph_is_auto_markable":0})["scoring_authorised"])
        with self.assertRaisesRegex(ContractError,"GUIDED_AUTO_MARKING_AUTHORITY_CONFLICT"):
            self.invoke({"ph_is_auto_markable":1})
        authority["ai_marking"]=True
        with self.assertRaisesRegex(ContractError,"GUIDED_AUTHORITY_NOT_UNSCORED"):
            self.invoke({"ph_is_auto_markable":0})

    def test_bad_source_contract_holds(self):
        self.guided.from_question=lambda row:(_ for _ in ()).throw(ValueError("GUIDED_CONTRACT_REQUIRED"))
        with self.assertRaisesRegex(ContractError,"SOURCE_BOUND_GUIDED_CONTRACT_INVALID"):
            self.invoke({"ph_is_auto_markable":0})

if __name__=="__main__":unittest.main()
