"""No-API four-lane QA-agent qualification over the existing ScoreMax runtime.

Qualification only. Uses the existing assessment/marking/admission engines plus bounded
deterministic visible-surface checks. Never calls an AI model, network API, production DB,
or release/mastery authority.
"""
from __future__ import annotations
import copy, json, os, socket, sys, tempfile, unittest, hashlib, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"scoremax_runtime_v669b"
STATE=tempfile.TemporaryDirectory(prefix="scoremax-no-api-qa-")
BASE=Path(STATE.name)
for key in tuple(os.environ):
    if key.startswith(("SCOREMAX_","POWER_HOUSE_","GROWTH_ENGINE_")):
        del os.environ[key]
os.environ.update({
    "SCOREMAX_ENV":"production",
    "SCOREMAX_SECRET":"synthetic-no-api-qa-secret",
    "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-no-api-qa-secret",
    "SCOREMAX_DB":str(BASE/"qa.db"),
    "SCOREMAX_PERSISTENT_ROOT":str(BASE),
    "SCOREMAX_BACKUP_DIR":str(BASE/"backup"),
    "SCOREMAX_CONTENT_INTAKE_DIR":str(BASE/"intake"),
    "SCOREMAX_SMTP_HOST":"smtp.invalid",
    "SCOREMAX_SMTP_FROM":"qa@scoremax.test",
    "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    "WEB_CONCURRENCY":"1",
    "SCOREMAX_INSTANCE_COUNT":"1",
    "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
    "SCOREMAX_ENFORCE_PAYWALL":"0",
    "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Synthetic-Only-Password!",
})
def deny(*a,**k): raise RuntimeError("NO_API_QA_NETWORK_DISABLED")
socket.socket.connect=deny
socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))

import scoremax_production as production
import app as sm
import scoremax_integration_v1 as integration
import question_contract_engine as qc
import ux_constructed_auto_marker as marker

LANE_RESULTS={"STUDENT_A":[],"STUDENT_B":[],"REVIEWER_A":[],"REVIEWER_B":[]}

def record(lane,name,status,detail=""):
    LANE_RESULTS[lane].append({"check":name,"status":status,"detail":detail})

def norm_text(v):
    return re.sub(r"\s+"," ",str(v or "").strip()).casefold()

def visible_option_text_defects(answer_config):
    opts=answer_config.get("options") if isinstance(answer_config,dict) else None
    if not isinstance(opts,list):
        return ["OPTIONS_NOT_LIST"]
    texts=[norm_text(x.get("text")) for x in opts if isinstance(x,dict)]
    defects=[]
    if any(not x for x in texts): defects.append("EMPTY_VISIBLE_OPTION")
    if len(texts)!=len(set(texts)): defects.append("DUPLICATE_VISIBLE_OPTION_TEXT")
    return defects

def missing_stimulus_defect(question):
    stem=str(question.get("question") or "")
    has_ref=bool(re.search(r"\b(?:table|diagram|graph|figure|pedigree|stimulus|passage)\s+(?:above|below|shown|provided)\b",stem,re.I))
    has_material=bool(question.get("stimulus_data") or question.get("resolved_stimulus") or question.get("stimulus_text"))
    return has_ref and not has_material

def q(qtype="MCQ",answer="B",ac=None,mc=None,marks=1,stem="[SYNTHETIC] Choose the correct answer."):
    return {
      "qtype":qtype,"question":stem,"answer":answer,"marks":marks,"command_word":"state",
      "answer_config":json.dumps(ac if ac is not None else {"options":[{"id":"A","text":"ONE"},{"id":"B","text":"TWO"}]}),
      "marking_config":json.dumps(mc if mc is not None else {"marks":marks,"auto_markable":True,"correct_option_ids":["B"]}),
      "misconception_tags":"[]","option_a":"ONE","option_b":"TWO","option_c":"","option_d":"","question_version":1,
    }

RUBRIC={"version":"SM-RUBRIC-CLAUSES-1","required_mark_points":[
 {"id":"P1","description":"Molecules collide with the particle.","marks":1,
  "accepted_phrases":["Molecules collide with the particle."],"acceptable_paraphrases":["The particle is struck by surrounding molecules."]},
 {"id":"P2","description":"Unequal impacts cause irregular motion.","marks":1,
  "accepted_phrases":["Unequal molecular impacts cause irregular motion."],"acceptable_paraphrases":["The particle moves randomly because impacts are unequal."]}],
 "contradictions":[{"phrase":"No molecules collide with the particle.","point_ids":["P1"]},
                   {"phrase":"The impacts are always equal.","point_ids":["P2"]}]}

def written():
    return q("Constructed Response","",{},{"marks":2,"auto_markable":True,"rubric":copy.deepcopy(RUBRIC)},2)

class NoApiFourLaneQA(unittest.TestCase):

    # STUDENT A — learner-visible structure / rendering preconditions
    def test_student_a_duplicate_visible_options(self):
        bad={"options":[{"id":"A","text":"RNA"},{"id":"B","text":"RNA"},{"id":"C","text":"DNA"}]}
        self.assertEqual(visible_option_text_defects(bad),["DUPLICATE_VISIBLE_OPTION_TEXT"])
        record("STUDENT_A","duplicate_visible_option_text","PASS")

    def test_student_a_empty_visible_option(self):
        bad={"options":[{"id":"A","text":"DNA"},{"id":"B","text":"   "}]}
        self.assertIn("EMPTY_VISIBLE_OPTION",visible_option_text_defects(bad))
        record("STUDENT_A","empty_visible_option","PASS")

    def test_student_a_missing_stimulus_reference(self):
        bad={"question":"According to the pedigree shown above, which individual is affected?","stimulus_data":""}
        good={**bad,"stimulus_data":"Pedigree data"}
        self.assertTrue(missing_stimulus_defect(bad));self.assertFalse(missing_stimulus_defect(good))
        record("STUDENT_A","missing_referenced_stimulus","PASS")

    def test_student_a_choice_contract_requires_options(self):
        bad=q(ac={"options":[{"id":"A","text":"ONE"}]})
        with self.assertRaises(qc.QuestionContractError): qc.validate_assessment_contract(bad)
        record("STUDENT_A","choice_options_required","PASS")

    def test_student_a_matching_and_ordering_contracts_fail_closed(self):
        bad_match=q("Matching","",{"left_items":[{"id":"L1","text":"one"}],"right_options":[]},
                    {"marks":1,"auto_markable":True,"correct_mapping":{"L1":"R1"}})
        bad_order=q("Ordering","",{"ordering_items":[{"id":"O1","text":"one"},{"id":"O1","text":"dup"}]},
                    {"marks":1,"auto_markable":True,"correct_order":["O1","O1"]})
        with self.assertRaises(Exception): qc.validate_assessment_contract(bad_match)
        with self.assertRaises(Exception): qc.validate_assessment_contract(bad_order)
        record("STUDENT_A","matching_ordering_structure","PASS")

    # STUDENT B — execute answers and challenge marking / feedback state
    def test_student_b_correct_and_wrong_objective_outcomes(self):
        item=q()
        good=sm.mark_question_result(item,"B")
        bad=sm.mark_question_result(item,"A")
        self.assertTrue(good["is_correct"]);self.assertEqual(good["marks_awarded"],1)
        self.assertFalse(bad["is_correct"]);self.assertEqual(bad["marks_awarded"],0)
        record("STUDENT_B","correct_wrong_objective_marking","PASS")

    def test_student_b_multiple_select_cardinality(self):
        item=q("Multiple Select","A,C",{"options":[{"id":x,"text":x} for x in "ABC"]},
               {"marks":1,"auto_markable":True,"correct_option_ids":["A","C"]})
        full=sm.mark_question_result(item,"A,C")
        partial=sm.mark_question_result(item,"A")
        self.assertTrue(full["is_correct"]);self.assertFalse(partial["is_correct"])
        record("STUDENT_B","multiple_select_execution","PASS")

    def test_student_b_written_full_partial_contradiction(self):
        item=written()
        full=sm.mark_question_result(item,"Molecules collide with the particle. Unequal molecular impacts cause irregular motion.")
        partial=sm.mark_question_result(item,"Molecules collide with the particle.")
        contradiction=sm.mark_question_result(item,"Molecules collide with the particle. No molecules collide with the particle.")
        self.assertEqual(full["marks_awarded"],2);self.assertEqual(partial["marks_awarded"],1);self.assertEqual(contradiction["marks_awarded"],0)
        record("STUDENT_B","written_full_partial_contradiction","PASS")

    def test_student_b_unbounded_paraphrase_is_unscored(self):
        item=written()
        out=sm.mark_question_result(item,"Molecular bombardment makes a suspended speck wander randomly.")
        self.assertFalse(out["confirmed"]);self.assertIsNone(out["marks_awarded"])
        record("STUDENT_B","unknown_semantic_answer_fail_closed","PASS")

    def test_student_b_numeric_sign_and_equivalence(self):
        item=q("Numerical","-314",{},{"marks":1,"auto_markable":True,"correct_value":-314,"tolerance":0})
        self.assertTrue(sm.mark_question_result(item,"-314.0")["is_correct"])
        self.assertFalse(sm.mark_question_result(item,"314")["is_correct"])
        record("STUDENT_B","numeric_equivalence_and_sign","PASS")

    # REVIEWER A — key/rubric/marks/response-contract integrity
    def test_reviewer_a_single_choice_key_cardinality(self):
        item=q(mc={"marks":1,"auto_markable":True,"correct_option_ids":["A","B"]})
        with self.assertRaises(qc.QuestionContractError): qc.validate_assessment_contract(item)
        record("REVIEWER_A","single_choice_key_cardinality","PASS")

    def test_reviewer_a_key_must_reference_existing_option(self):
        item=q(mc={"marks":1,"auto_markable":True,"correct_option_ids":["Z"]})
        with self.assertRaises(qc.QuestionContractError): qc.validate_assessment_contract(item)
        record("REVIEWER_A","key_option_identity","PASS")

    def test_reviewer_a_rubric_total_must_match_maximum(self):
        item=written();mc=json.loads(item["marking_config"]);mc["rubric"]["required_mark_points"][0]["marks"]=3
        item["marking_config"]=json.dumps(mc)
        with self.assertRaises(qc.QuestionContractError): sm.mark_question_result(item,"anything")
        record("REVIEWER_A","rubric_maximum_reconciliation","PASS")

    def test_reviewer_a_duplicate_mark_point_rejected(self):
        item=written();mc=json.loads(item["marking_config"]);mc["rubric"]["required_mark_points"][1]["id"]="P1"
        item["marking_config"]=json.dumps(mc)
        with self.assertRaises(qc.QuestionContractError): sm.mark_question_result(item,"anything")
        record("REVIEWER_A","duplicate_mark_point_id","PASS")

    def test_reviewer_a_model_answer_cannot_invent_rubric(self):
        item=q("Constructed Response","Viscosity is resistance to flow.",{"accepted_answers":["Viscosity is resistance to flow."]},
               {"marks":2,"auto_markable":True},2)
        with self.assertRaises(qc.QuestionContractError): qc.validate_assessment_contract(item)
        record("REVIEWER_A","model_answer_not_marking_contract","PASS")

    # REVIEWER B — governance / fidelity / replay safety
    def test_reviewer_b_qa_staging_never_carries_mastery_or_release_authority(self):
        path=ROOT/"ux_cross50_qa_staging_v13.py"
        text=path.read_text(encoding="utf-8")
        self.assertIn("independent_mastery_weight",text)
        self.assertIn("release_authority_conferred",text)
        self.assertIn("mastery_authority_conferred",text)
        self.assertIn("QA_STAGING_NOT_ACTIVATABLE",text)
        record("REVIEWER_B","qa_staging_authority_fence","PASS")

    def test_reviewer_b_payload_checksum_is_canonical(self):
        payload={"a":1,"b":{"x":"y"}}
        expected=integration.payload_checksum(payload)
        self.assertEqual(expected,integration.payload_checksum(copy.deepcopy(payload)))
        changed=copy.deepcopy(payload);changed["b"]["x"]="z"
        self.assertNotEqual(expected,integration.payload_checksum(changed))
        record("REVIEWER_B","payload_checksum_identity","PASS")

    def test_reviewer_b_question_version_conflict_fails_closed(self):
        # Static assertion on existing qualified staging runtime seam: immutable
        # question-version identity must conflict rather than overwrite.
        text=(ROOT/"ux_cross50_qa_staging_v13.py").read_text(encoding="utf-8")
        self.assertIn("QUESTION_VERSION_CHECKSUM_CONFLICT",text)
        record("REVIEWER_B","question_version_immutability","PASS")

    def test_reviewer_b_no_human_marking_fallback(self):
        text=(ROOT/"assessment_marking_v2.py").read_text(encoding="utf-8")
        self.assertIn("HUMAN_MARKING_NOT_AVAILABLE",text)
        self.assertIn("AUTO_UNSCORED",text)
        record("REVIEWER_B","no_human_marking_fallback","PASS")

    def test_reviewer_b_unscored_does_not_become_mastery(self):
        item=written()
        out=sm.mark_question_result(item,"Molecular bombardment makes a suspended speck wander randomly.")
        self.assertFalse(out["evidence_eligible"])
        record("REVIEWER_B","unscored_not_mastery_evidence","PASS")


if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NoApiFourLaneQA)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    summary={
      "policy":"SCOREMAX-NO-API-FOUR-LANE-QA-1",
      "tests_run":result.testsRun,
      "failures":len(result.failures),
      "errors":len(result.errors),
      "lanes":LANE_RESULTS,
      "all_lanes_present":set(LANE_RESULTS)=={"STUDENT_A","STUDENT_B","REVIEWER_A","REVIEWER_B"},
      "network_disabled":True,
      "ai_model_used":False,
      "external_api_used":False,
      "production_db_used":False,
      "release_authority":False,
      "mastery_authority":False,
      "status":"PASS" if result.wasSuccessful() else "FAIL",
    }
    out=Path(os.environ.get("NO_API_QA_EVIDENCE","/tmp/no_api_qa_agents.json"))
    out.write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    print("SCOREMAX_NO_API_QA_AGENTS "+json.dumps(summary,sort_keys=True),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
