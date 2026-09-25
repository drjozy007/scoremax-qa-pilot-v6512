"""Qualification for Admin-operable deterministic QA agents.

Uses disposable storage only. Proves Admin visibility, run-one/run-all, cumulative
statistics, rerun accounting and zero mutation of governed question/release/mastery data.
"""
from __future__ import annotations
import hashlib,json,os,socket,sys,tempfile,unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"scoremax_runtime_v669b"
STATE=tempfile.TemporaryDirectory(prefix="scoremax-qa-admin-")
BASE=Path(STATE.name)
for key in tuple(os.environ):
    if key.startswith(("SCOREMAX_","POWER_HOUSE_","GROWTH_ENGINE_")):del os.environ[key]
os.environ.update({
 "SCOREMAX_ENV":"production","SCOREMAX_SECRET":"synthetic-qa-admin-secret-0123456789abcdef",
 "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-qa-admin-secret-0123456789abcdef",
 "SCOREMAX_DB":str(BASE/"qa.db"),"SCOREMAX_PERSISTENT_ROOT":str(BASE),
 "SCOREMAX_BACKUP_DIR":str(BASE/"backup"),"SCOREMAX_CONTENT_INTAKE_DIR":str(BASE/"intake"),
 "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"qa@scoremax.test",
 "SCOREMAX_PUBLIC_BASE_URL":"https://localhost","SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
 "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0","SCOREMAX_ENFORCE_PAYWALL":"0",
 "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Synthetic-Only-Password!",
})
def deny(*a,**k):raise RuntimeError("QA_ADMIN_NETWORK_DISABLED")
socket.socket.connect=deny;socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))
import scoremax_production
import app as sm
import ux_qa_agents_admin as qa

def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))

def ph_item(qid,qvid,options,key,marks=1):
    content={"question_family_type":"STANDARD_MCQ","exam_question_type":"STANDARD_MCQ",
      "stem":f"Question {qid}?","options":[{"option_id":a,"text":t} for a,t in options],
      "marking":{"key_type":"SINGLE_OPTION","key":key,"marks":marks,"negative_marks":0}}
    curr={"market_id":"PK","programme_id":"FSC1","subject_id":"CHEM","chapter_id":"CH1",
      "display":{"programme":"FSc Part 1","subject":"Chemistry","chapter":"Chapter 1","topic":"Topic"}}
    arch={"mastery_level":"EXAM_READY","mastery_ceiling":"DISTINCTION","cognitive_demand":"APPLICATION","knowledge_node_ids":["N1"]}
    gov={"rights_status":"owned"};prov={"primary_source":{"source_id":"SRC","locator":"p1"}}
    raw={"question_id":qid,"question_version_id":qvid,"question_version_number":1,"question_checksum_sha256":"0"*64,
      "curriculum":curr,"content":content,"architecture":arch,"governance":gov,"provenance":prov}
    projection=sm.integration_v1._projection(raw,{})
    return raw,projection

def insert_fixture(c,qid,qvid,options,key,ordinal):
    raw,proj=ph_item(qid,qvid,options,key)
    c.execute("""INSERT INTO integration_ph_question_version_store(
      question_id,question_version_id,question_version_number,question_checksum_sha256,
      supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,
      governance_json,provenance_json,scoremax_projection_json,first_admitted_at)
      VALUES(?,?,?,?,NULL,NULL,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
      (qid,qvid,1,raw["question_checksum_sha256"],canon(raw["curriculum"]),canon(raw["content"]),
       canon(raw["architecture"]),canon(raw["governance"]),canon(raw["provenance"]),canon(proj)))
    c.execute("""INSERT INTO integration_ph_release_question_membership(
      release_id,release_version,question_id,question_version_id,ordinal,admitted_at)
      VALUES('REL-QA','V1',?,?,?,CURRENT_TIMESTAMP)""",(qid,qvid,ordinal))

def table_fingerprint(c,table):
    rows=[tuple(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]
    return hashlib.sha256(repr(rows).encode()).hexdigest()

class QAAdminQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=sm.db();qa.ensure_schema(cls.c)
        cls.c.execute("""INSERT OR IGNORE INTO integration_ph_content_releases(
          release_id,release_version,package_checksum_sha256,manifest_checksum_sha256,payload_checksum_sha256,
          semantic_checksum_sha256,release_status,local_status,effective_at,generated_at,market_id,programme_id,
          subject_id,chapter_id,question_count,stimulus_count,readiness_policy_version,supersedes_release_version,
          source_system_version,immutable_payload_json,admitted_at,schema_version,release_operation)
          VALUES('REL-QA','V1',?,?,?,?,?,'STAGED','STAGED',NULL,NULL,'PK','FSC1','CHEM','CH1',2,0,'',NULL,'','{}',
          CURRENT_TIMESTAMP,'1.3.0','QA_STAGE')""",("1"*64,"2"*64,"3"*64,"4"*64,"STAGED"))
        insert_fixture(cls.c,"Q-CLEAN","QV-CLEAN",[("A","one"),("B","two")],"B",1)
        insert_fixture(cls.c,"Q-DUP","QV-DUP",[("A","same"),("B","same")],"B",2)
        cls.c.commit()

    @classmethod
    def tearDownClass(cls):cls.c.close()

    def setUp(self):
        self.sensitive=["integration_ph_content_releases","integration_ph_question_version_store",
          "integration_ph_release_question_membership","questions","attempts","attempt_answers","mastery_records"]
        self.before={t:table_fingerprint(self.c,t) for t in self.sensitive}

    def tearDown(self):
        after={t:table_fingerprint(self.c,t) for t in self.sensitive}
        self.assertEqual(self.before,after)

    def test_01_all_four_agents_run_and_persist(self):
        out=qa.run_agents(sm,"ALL","release:1",None)
        self.assertEqual(out["population"],2);self.assertEqual(len(out["summaries"]),4)
        agents={r["agent_code"] for r in self.c.execute("SELECT * FROM qa_agent_runs")}
        self.assertTrue(set(qa.AGENTS)<=agents)

    def test_02_student_a_detects_duplicate_visible_option(self):
        qa.run_agents(sm,"STUDENT_A","release:1",None)
        r=self.c.execute("""SELECT * FROM qa_agent_results WHERE agent_code='STUDENT_A' AND question_id='Q-DUP'
          ORDER BY id DESC LIMIT 1""").fetchone()
        self.assertEqual(r["status"],"HOLD")
        self.assertIn("DUPLICATE_VISIBLE_OPTION_TEXT",r["findings_json"])

    def test_03_clean_question_passes_structural_and_contract_lanes(self):
        qa.run_agents(sm,"ALL","release:1",None)
        rows=self.c.execute("""SELECT agent_code,status FROM qa_agent_results WHERE question_id='Q-CLEAN'
          AND id IN (SELECT MAX(id) FROM qa_agent_results WHERE question_id='Q-CLEAN' GROUP BY agent_code)""").fetchall()
        self.assertEqual({r["agent_code"]:r["status"] for r in rows},
          {"STUDENT_A":"PASS","STUDENT_B":"PASS","REVIEWER_A":"PASS","REVIEWER_B":"PASS"})

    def test_04_rerun_count_is_separate_from_unique_question_count(self):
        qa.run_agents(sm,"STUDENT_A","release:1",None);qa.run_agents(sm,"STUDENT_A","release:1",None)
        data=qa.dashboard_data(sm)["agents"]["STUDENT_A"]
        self.assertEqual(data["unique_questions"],2)
        self.assertGreaterEqual(data["executions"],4)

    def test_05_dashboard_has_three_section_data(self):
        data=qa.dashboard_data(sm)
        self.assertEqual(set(data["agents"]),set(qa.AGENTS))
        self.assertIn("overall",data);self.assertIn("problems",data);self.assertIn("recent_runs",data)
        self.assertIn("historical",data)

    def test_06_admin_mastery_lab_renders_named_agents_and_three_sections(self):
        admin=self.c.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        client=sm.app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"]=admin["id"];sess["role"]="admin";sess["full_name"]="QA Admin";sess["session_version"]=0
        response=client.get("/admin/mastery-lab",base_url="https://localhost")
        body=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        for text in ("QA Agents","QA Performance","Problems & History","Student A","Student B","Reviewer A","Reviewer B","Run all QA agents"):
            self.assertIn(text,body)

    def test_07_runner_has_zero_release_and_mastery_authority(self):
        out=qa.run_agents(sm,"ALL","release:1",None)
        for summary in out["summaries"]:
            self.assertFalse(summary["release_authority"]);self.assertFalse(summary["mastery_authority"])
            self.assertFalse(summary["question_mutation"])

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(QAAdminQualification)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    summary={"suite":"QA_AGENTS_ADMIN_V1","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
      "production_db_used":False,"network_disabled":True,"release_authority":False,"mastery_authority":False,
      "status":"PASS" if result.wasSuccessful() else "FAIL"}
    Path(os.environ.get("QA_ADMIN_EVIDENCE","/tmp/qa_agents_admin.json")).write_text(json.dumps(summary,indent=2,sort_keys=True))
    print("SCOREMAX_QA_AGENTS_ADMIN "+json.dumps(summary,sort_keys=True),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
