"""Wild attack 2/3 — ScoreMax mastery policy and evidence architecture."""
from __future__ import annotations
import json,math,os,socket,sys,tempfile,unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1];ROOT=REPO/"scoremax_runtime_v669b"
STATE=tempfile.TemporaryDirectory(prefix="scoremax-wild-mastery-");BASE=Path(STATE.name)
for k in tuple(os.environ):
    if k.startswith(("SCOREMAX_","POWER_HOUSE_","GROWTH_ENGINE_")):del os.environ[k]
os.environ.update({
"SCOREMAX_ENV":"production","SCOREMAX_SECRET":"wild-mastery-secret-0123456789abcdef-0123456789abcdef",
"SCOREMAX_STAGING_SESSION_SECRET":"wild-mastery-secret-0123456789abcdef-0123456789abcdef",
"SCOREMAX_DB":str(BASE/"mastery.db"),"SCOREMAX_PERSISTENT_ROOT":str(BASE),
"SCOREMAX_BACKUP_DIR":str(BASE/"backup"),"SCOREMAX_CONTENT_INTAKE_DIR":str(BASE/"intake"),
"SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"qa@scoremax.test",
"SCOREMAX_PUBLIC_BASE_URL":"https://localhost","SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
"SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0","SCOREMAX_ENFORCE_PAYWALL":"0","SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Wild-Mastery-Only!"})
def deny(*a,**k):raise RuntimeError("NETWORK_DISABLED")
socket.socket.connect=deny;socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))
import scoremax_production
import app as sm

EXPECTED_TOTAL={"Foundation":10,"Exam Ready":20,"Advanced":30,"Distinction":40,"Expert":50,"Elite":60}
EXPECTED_ACC={"Foundation":70,"Exam Ready":80,"Advanced":88,"Distinction":94,"Expert":95,"Elite":97}
EXPECTED_BREADTH={"Foundation":.50,"Exam Ready":.70,"Advanced":.80,"Distinction":.90,"Expert":.95,"Elite":1.0}

def q(i,fam,level,node,difficulty="Moderate"):
    return {"id":i,"family_id":fam,"level":level,"difficulty":difficulty,
      "ph_knowledge_node_ids_json":json.dumps([node])}

class WildMastery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=sm.db()
    @classmethod
    def tearDownClass(cls):cls.c.close()

    def test_01_neutral_50_exactly_matches_published_baseline(self):
        rows={r["mastery_level"]:r for r in self.c.execute("SELECT * FROM mastery_policies WHERE active=1")}
        self.assertEqual(set(rows),set(EXPECTED_TOTAL))
        for level,row in rows.items():
            self.assertEqual(int(row["min_forms"])*int(row["min_questions"]),EXPECTED_TOTAL[level])
            self.assertAlmostEqual(float(row["min_accuracy"]),EXPECTED_ACC[level])
            self.assertAlmostEqual(float(row["min_breadth_pct"]),EXPECTED_BREADTH[level])
            eff=sm.effective_mastery_requirements(row,{"mastery_standard_score":50})
            self.assertAlmostEqual(eff["min_accuracy"],float(row["min_accuracy"]))
            self.assertEqual(eff["min_questions"],int(row["min_questions"]))
            self.assertEqual(eff["min_forms"],int(row["min_forms"]))
            self.assertAlmostEqual(eff["min_breadth_pct"],float(row["min_breadth_pct"]))

    def test_02_slider_0_50_100_is_monotonic_both_directions(self):
        for row in self.c.execute("SELECT * FROM mastery_policies WHERE active=1"):
            lo=sm.effective_mastery_requirements(row,{"mastery_standard_score":0})
            mid=sm.effective_mastery_requirements(row,{"mastery_standard_score":50})
            hi=sm.effective_mastery_requirements(row,{"mastery_standard_score":100})
            for key in ("min_accuracy","min_questions","min_forms","target_band_pct","unseen_family_pct","min_breadth_pct"):
                self.assertLessEqual(lo[key],mid[key],(row["mastery_level"],key))
                self.assertLessEqual(mid[key],hi[key],(row["mastery_level"],key))
            self.assertGreaterEqual(lo["verification_days"],mid["verification_days"])
            self.assertGreaterEqual(mid["verification_days"],hi["verification_days"])

    def test_03_slider_scores_reject_nan_inf_fraction_bool_and_out_of_range(self):
        for bad in (-1,101,49.5,True,float("nan"),float("inf"),"nan","101"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):sm.policy_score(bad)

    def test_04_level_rule_validator_rejects_nonfinite_and_out_of_range(self):
        good={"min_forms":"1","min_questions":"20","min_accuracy":"80","verification_days":"90",
          "target_band_pct":".25","unseen_family_pct":".5","min_breadth_pct":".7","external_percentile_target":""}
        for field,bad in (("min_accuracy","nan"),("target_band_pct","1.1"),("unseen_family_pct","-0.1"),
                          ("min_breadth_pct","inf"),("min_forms","1.5"),("min_questions","4")):
            data=dict(good);data[field]=bad
            with self.subTest(field=field,bad=bad):
                with self.assertRaises(ValueError):sm.validate_mastery_policy_values(data)

    def test_05_scope_ceilings_cannot_escalate(self):
        self.assertEqual(sm.mastery_scope_ceiling("chapter"),"Distinction")
        self.assertEqual(sm.mastery_scope_ceiling("subject"),"Expert")
        self.assertEqual(sm.mastery_scope_ceiling("overall"),"Elite")

    def test_06_expert_elite_are_aggregate_not_item_labels(self):
        self.assertEqual(sm.mastery_evidence_band_levels("Expert"),{"Advanced","Distinction"})
        self.assertEqual(sm.mastery_evidence_band_levels("Elite"),{"Advanced","Distinction"})
        for level in ("Foundation","Exam Ready","Advanced","Distinction"):
            self.assertEqual(sm.mastery_evidence_band_levels(level),{level})
        self.assertEqual(sm.mastery_evidence_band_levels("Made Up"),set())

    def test_07_duplicate_family_cannot_fill_mastery_form(self):
        pool=[q(i,"SAME","Exam Ready",f"N{(i%5)+1}") for i in range(1,101)]
        coverage={"required_node_ids":[f"N{i}" for i in range(1,6)],"mandatory_node_ids":[],"min_breadth_pct":.7}
        with self.assertRaises(ValueError):
            sm.select_mastery_coverage_questions(pool,20,"Exam Ready",.25,.5,set(),coverage,50)

    def test_08_seen_families_cannot_fake_unseen_evidence(self):
        pool=[q(i,f"F{i}","Exam Ready",f"N{(i%10)+1}") for i in range(1,31)]
        coverage={"required_node_ids":[f"N{i}" for i in range(1,11)],"mandatory_node_ids":[],"min_breadth_pct":.7}
        previous={f"F{i}" for i in range(1,31)}
        with self.assertRaises(ValueError):
            sm.select_mastery_coverage_questions(pool,20,"Exam Ready",.25,.5,previous,coverage,50)

    def test_09_inventory_size_cannot_replace_frozen_curriculum_register(self):
        with self.assertRaises(ValueError):
            sm.mastery_coverage_contract(self.c,"FSc Part 1","Chemistry","Chapter 1","chapter")

    def test_10_topic_family_and_question_ids_are_not_curriculum_nodes(self):
        row={"ph_knowledge_node_ids_json":"[]","topic":"Acids","family_id":"F1","question_id":"Q1"}
        self.assertEqual(sm.question_coverage_nodes(row),set())

    def test_11_mandatory_nodes_are_absolute_not_percentage_only(self):
        pool=[q(i,f"F{i}","Exam Ready",f"N{i}") for i in range(1,21)]
        coverage={"required_node_ids":[f"N{i}" for i in range(1,21)],"mandatory_node_ids":["N99"],"min_breadth_pct":.7}
        with self.assertRaises(ValueError):
            sm.select_mastery_coverage_questions(pool,20,"Exam Ready",.25,.5,set(),coverage,50)

    def test_12_expert_can_be_built_without_expert_questions_but_with_high_tier_evidence(self):
        required=[f"N{i}" for i in range(1,21)]
        pool=[]
        for i in range(1,41):
            level="Advanced" if i<=12 else "Distinction" if i<=24 else "Exam Ready"
            pool.append(q(i,f"F{i}",level,required[(i-1)%20]))
        coverage={"required_node_ids":required,"mandatory_node_ids":required[:3],"min_breadth_pct":.95}
        chosen=sm.select_mastery_coverage_questions(pool,25,"Expert",.40,.70,set(),coverage,50)
        self.assertEqual(len(chosen),25)
        self.assertFalse(any(x["level"]=="Expert" for x in chosen))
        self.assertGreaterEqual(sum(x["level"] in {"Advanced","Distinction"} for x in chosen),10)

    def test_13_policy_scope_does_not_cross_programmes(self):
        p={"scope_type":"programme","scope_key":"FSc Part 1"}
        self.assertTrue(sm.policy_matches_context(p,{"programme":"FSc Part 1"}))
        self.assertFalse(sm.policy_matches_context(p,{"programme":"FSc Part 2"}))
        self.assertFalse(sm.policy_matches_context(p,{"programme":"MDCAT"}))

    def test_14_invalid_scope_keys_fail_closed(self):
        for kind,key in (("global","x"),("programme",""),("chapter","A|B|C|D"),("assessment_type","weird"),("bad","x")):
            with self.subTest(kind=kind,key=key):
                with self.assertRaises(ValueError):sm.normalise_policy_scope(kind,key)

    def test_15_tightening_detected_lowering_not_detected(self):
        before={"min_accuracy":80,"min_questions":20,"min_forms":1,"target_band_pct":.25,"unseen_family_pct":.5,"min_breadth_pct":.7,"verification_days":90}
        higher=dict(before,min_accuracy=81)
        lower=dict(before,min_accuracy=79,verification_days=100)
        self.assertTrue(sm._stricter_mastery(before,higher))
        self.assertFalse(sm._stricter_mastery(before,lower))

    def test_16_launch_policy_is_idempotent_and_no_external_percentile_claim(self):
        before=self.c.execute("SELECT COUNT(*) n FROM mastery_policy_change_audit_v1 WHERE reason='SCOREMAX_MASTERY_LAUNCH_POLICY_V1'").fetchone()["n"]
        self.assertFalse(sm.ensure_mastery_launch_policy_v1(self.c))
        after=self.c.execute("SELECT COUNT(*) n FROM mastery_policy_change_audit_v1 WHERE reason='SCOREMAX_MASTERY_LAUNCH_POLICY_V1'").fetchone()["n"]
        self.assertEqual(before,after)
        self.assertEqual(after,6)
        self.assertEqual(self.c.execute("SELECT COUNT(*) n FROM mastery_policies WHERE external_percentile_target IS NOT NULL").fetchone()["n"],0)

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(WildMastery)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    payload={"suite":"WILD_MASTERY_ATTACK_V1","tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
      "status":"PASS" if result.wasSuccessful() else "FAIL","production_db_used":False,"historical_attempts_rewritten":False}
    print("WILD_MASTERY_ATTACK "+json.dumps(payload,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
