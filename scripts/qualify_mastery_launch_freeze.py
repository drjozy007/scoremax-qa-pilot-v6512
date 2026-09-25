"""Launch mastery freeze qualification.\n\nCandidate policy: SCOREMAX-MASTERY-LAUNCH-FREEZE-1.

Qualification only. Runs against a disposable database assembled from the exact live
ScoreMax base plus the candidate overlay. It never enables learner release/mastery
authority and never touches the production database.
"""
from __future__ import annotations
import json, os, socket, sys, tempfile, unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"scoremax_runtime_v669b"
STATE=tempfile.TemporaryDirectory(prefix="scoremax-mastery-freeze-")
BASE=Path(STATE.name)
for key in tuple(os.environ):
    if key.startswith(("SCOREMAX_","POWER_HOUSE_","GROWTH_ENGINE_")):
        del os.environ[key]
os.environ.update({
    "SCOREMAX_ENV":"production",
    "SCOREMAX_SECRET":"synthetic-mastery-freeze-secret-0123456789abcdef",
    "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-mastery-freeze-secret-0123456789abcdef",
    "SCOREMAX_DB":str(BASE/"mastery.db"),
    "SCOREMAX_PERSISTENT_ROOT":str(BASE),
    "SCOREMAX_BACKUP_DIR":str(BASE/"backup"),
    "SCOREMAX_CONTENT_INTAKE_DIR":str(BASE/"intake"),
    "SCOREMAX_SMTP_HOST":"smtp.invalid",
    "SCOREMAX_SMTP_FROM":"qa@scoremax.test",
    "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    "SCOREMAX_INSTANCE_COUNT":"1",
    "WEB_CONCURRENCY":"1",
    "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
    "SCOREMAX_ENFORCE_PAYWALL":"0",
    "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Synthetic-Only-Password!",
})
def deny(*a,**k): raise RuntimeError("MASTERY_FREEZE_NETWORK_DISABLED")
socket.socket.connect=deny
socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))

import scoremax_production
import app as sm

EXPECTED={
 "Foundation":dict(min_forms=1,min_questions=10,min_accuracy=70.0,verification_days=120,target_band_pct=.20,unseen_family_pct=.50,min_breadth_pct=.50),
 "Exam Ready":dict(min_forms=1,min_questions=20,min_accuracy=80.0,verification_days=90,target_band_pct=.25,unseen_family_pct=.50,min_breadth_pct=.70),
 "Advanced":dict(min_forms=2,min_questions=30,min_accuracy=88.0,verification_days=75,target_band_pct=.30,unseen_family_pct=.60,min_breadth_pct=.80),
 "Distinction":dict(min_forms=2,min_questions=40,min_accuracy=94.0,verification_days=60,target_band_pct=.35,unseen_family_pct=.65,min_breadth_pct=.90),
 "Expert":dict(min_forms=2,min_questions=50,min_accuracy=95.0,verification_days=45,target_band_pct=.40,unseen_family_pct=.70,min_breadth_pct=.95),
 "Elite":dict(min_forms=3,min_questions=60,min_accuracy=97.0,verification_days=30,target_band_pct=.45,unseen_family_pct=.75,min_breadth_pct=1.00),
}

def q(i,level,node):
    return {"id":i,"family_id":f"F{i}","level":level,"difficulty":"Moderate",
            "ph_knowledge_node_ids_json":json.dumps([node])}

class MasteryLaunchFreeze(unittest.TestCase):
    def setUp(self):
        self.c=sm.db()
    def tearDown(self):
        self.c.close()

    def test_01_exact_launch_thresholds(self):
        rows={r["mastery_level"]:dict(r) for r in self.c.execute("SELECT * FROM mastery_policies WHERE active=1")}
        self.assertEqual(set(EXPECTED),set(rows))
        for level,expected in EXPECTED.items():
            for key,value in expected.items():
                self.assertAlmostEqual(float(rows[level][key]),float(value),places=6)

    def test_02_external_percentile_claims_not_fabricated(self):
        rows=self.c.execute("SELECT external_percentile_target FROM mastery_policies WHERE active=1").fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(r["external_percentile_target"] is None for r in rows))

    def test_03_launch_policy_migration_is_idempotent(self):
        before=self.c.execute("SELECT COUNT(*) n FROM mastery_policy_change_audit_v1 WHERE reason='SCOREMAX_MASTERY_LAUNCH_POLICY_V1'").fetchone()["n"]
        changed=sm.ensure_mastery_launch_policy_v1(self.c)
        after=self.c.execute("SELECT COUNT(*) n FROM mastery_policy_change_audit_v1 WHERE reason='SCOREMAX_MASTERY_LAUNCH_POLICY_V1'").fetchone()["n"]
        self.assertFalse(changed)
        self.assertEqual(before,6); self.assertEqual(after,6)

    def test_04_item_mastery_taxonomy_remains_four_tier(self):
        self.assertEqual(sm.mastery_evidence_band_levels("Foundation"),{"Foundation"})
        self.assertEqual(sm.mastery_evidence_band_levels("Exam Ready"),{"Exam Ready"})
        self.assertEqual(sm.mastery_evidence_band_levels("Advanced"),{"Advanced"})
        self.assertEqual(sm.mastery_evidence_band_levels("Distinction"),{"Distinction"})

    def test_05_expert_is_aggregate_high_tier_evidence(self):
        self.assertEqual(sm.mastery_evidence_band_levels("Expert"),{"Advanced","Distinction"})

    def test_06_elite_is_aggregate_high_tier_evidence(self):
        self.assertEqual(sm.mastery_evidence_band_levels("Elite"),{"Advanced","Distinction"})

    def test_07_scope_ceilings_preserved(self):
        self.assertEqual(sm.mastery_scope_ceiling("chapter"),"Distinction")
        self.assertEqual(sm.mastery_scope_ceiling("subject"),"Expert")
        self.assertEqual(sm.mastery_scope_ceiling("overall"),"Elite")

    def test_08_expert_selector_needs_no_expert_labelled_items(self):
        required=[f"N{i}" for i in range(1,21)]
        pool=[]
        for i in range(1,61):
            level="Advanced" if i<=15 else "Distinction" if i<=30 else "Exam Ready"
            pool.append(q(i,level,required[(i-1)%len(required)]))
        coverage={"required_node_ids":required,"mandatory_node_ids":required[:3],"min_breadth_pct":.95}
        chosen=sm.select_mastery_coverage_questions(pool,50,"Expert",.40,.70,set(),coverage,50)
        self.assertEqual(len(chosen),50)
        self.assertFalse(any(x["level"]=="Expert" for x in chosen))
        high=sum(x["level"] in {"Advanced","Distinction"} for x in chosen)
        self.assertGreaterEqual(high,20)

    def test_09_elite_selector_needs_no_elite_labelled_items(self):
        required=[f"N{i}" for i in range(1,20)]
        pool=[]
        for i in range(1,73):
            level="Advanced" if i<=18 else "Distinction" if i<=36 else "Exam Ready"
            pool.append(q(i,level,required[(i-1)%len(required)]))
        coverage={"required_node_ids":required,"mandatory_node_ids":required[:4],"min_breadth_pct":1.0}
        chosen=sm.select_mastery_coverage_questions(pool,60,"Elite",.45,.75,set(),coverage,50)
        self.assertEqual(len(chosen),60)
        self.assertFalse(any(x["level"]=="Elite" for x in chosen))
        high=sum(x["level"] in {"Advanced","Distinction"} for x in chosen)
        self.assertGreaterEqual(high,27)

    def test_10_family_repetition_cannot_fill_form(self):
        required=["N1","N2","N3"]
        pool=[{"id":i,"family_id":"SAME","level":"Exam Ready","difficulty":"Moderate",
               "ph_knowledge_node_ids_json":json.dumps([required[(i-1)%3]])} for i in range(1,30)]
        coverage={"required_node_ids":required,"mandatory_node_ids":[],"min_breadth_pct":.70}
        with self.assertRaises(ValueError):
            sm.select_mastery_coverage_questions(pool,20,"Exam Ready",.25,.50,set(),coverage,50)

    def test_11_seen_family_novelty_is_enforced(self):
        required=[f"N{i}" for i in range(1,8)]
        pool=[q(i,"Exam Ready",required[(i-1)%len(required)]) for i in range(1,26)]
        previous={f"F{i}" for i in range(1,21)}
        coverage={"required_node_ids":required,"mandatory_node_ids":[],"min_breadth_pct":.70}
        with self.assertRaises(ValueError):
            sm.select_mastery_coverage_questions(pool,20,"Exam Ready",.25,.50,previous,coverage,50)

    def test_12_neutral_active_global_standard_preserved(self):
        p=self.c.execute("""SELECT * FROM assessment_assembly_policies
          WHERE status='ACTIVE' AND scope_type='global' AND scope_key='' ORDER BY id DESC LIMIT 1""").fetchone()
        self.assertIsNotNone(p)
        self.assertEqual(int(p["mastery_standard_score"]),50)
        self.assertEqual(int(p["rigor_score"]),50)

    def test_13_mastery_authority_not_enabled_by_freeze(self):
        # The freeze configures evidence rules only; it does not activate staged content.
        tables={r["name"] for r in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "integration_ph_release_store" in tables:
            active=self.c.execute("""SELECT COUNT(*) n FROM integration_ph_release_store
              WHERE upper(COALESCE(status,'')) IN ('ACTIVE','LEARNER_ACTIVE','RELEASED')""").fetchone()["n"]
            self.assertEqual(active,0)

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MasteryLaunchFreeze)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    summary={"policy":"SCOREMAX-MASTERY-LAUNCH-FREEZE-1","tests_run":result.testsRun,
      "failures":len(result.failures),"errors":len(result.errors),"production_db_used":False,
      "network_disabled":True,"release_authority":False,"mastery_authority":False,
      "status":"PASS" if result.wasSuccessful() else "FAIL"}
    out=Path(os.environ.get("MASTERY_FREEZE_EVIDENCE","/tmp/mastery_launch_freeze.json"))
    out.write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    print("SCOREMAX_MASTERY_LAUNCH_FREEZE "+json.dumps(summary,sort_keys=True),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
