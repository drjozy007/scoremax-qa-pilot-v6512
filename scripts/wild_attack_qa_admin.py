"""Wild attack 1/3 — QA Admin / deterministic agents.

Disposable DB only. Deliberately attacks false-PASS paths, authority boundaries,
scope widening, projection drift, history accounting and 1,500-question scale.
"""
from __future__ import annotations
import hashlib,json,os,socket,sys,tempfile,time,unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]; ROOT=REPO/"scoremax_runtime_v669b"
STATE=tempfile.TemporaryDirectory(prefix="scoremax-wild-qa-"); BASE=Path(STATE.name)
for key in tuple(os.environ):
    if key.startswith(("SCOREMAX_","POWER_HOUSE_","GROWTH_ENGINE_")): del os.environ[key]
os.environ.update({
 "SCOREMAX_ENV":"production","SCOREMAX_SECRET":"wild-qa-secret-0123456789abcdef-0123456789abcdef",
 "SCOREMAX_STAGING_SESSION_SECRET":"wild-qa-secret-0123456789abcdef",
 "SCOREMAX_DB":str(BASE/"wild.db"),"SCOREMAX_PERSISTENT_ROOT":str(BASE),
 "SCOREMAX_BACKUP_DIR":str(BASE/"backup"),"SCOREMAX_CONTENT_INTAKE_DIR":str(BASE/"intake"),
 "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"qa@scoremax.test",
 "SCOREMAX_PUBLIC_BASE_URL":"https://localhost","SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
 "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0","SCOREMAX_ENFORCE_PAYWALL":"0",
 "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Wild-Attack-Only!",
})
def deny(*a,**k): raise RuntimeError("NETWORK_DISABLED")
socket.socket.connect=deny; socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))
import scoremax_production
import app as sm
import ux_qa_agents_admin as qa

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def fp(c,t):
    return hashlib.sha256(repr([tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]).encode()).hexdigest()

def make_raw(qid,qvid="V1", *, qtype="STANDARD_MCQ", stem=None, options=None, key="B"):
    options=options if options is not None else [("A","one"),("B","two")]
    content={"question_family_type":qtype,"exam_question_type":qtype,"stem":stem or f"Question {qid}?",
      "options":[{"option_id":a,"text":b} for a,b in options],
      "marking":{"key_type":"SINGLE_OPTION","key":key,"marks":1,"negative_marks":0}}
    curr={"market_id":"PK","programme_id":"FSC1","subject_id":"CHEM","chapter_id":"CH1",
      "display":{"programme":"FSc Part 1","subject":"Chemistry","chapter":"Chapter 1","topic":"Topic"}}
    arch={"mastery_level":"EXAM_READY","mastery_ceiling":"DISTINCTION","cognitive_demand":"APPLICATION","knowledge_node_ids":["N1"]}
    gov={"rights_status":"OWNED"}; prov={"primary_source":{"source_id":"SRC","locator":"p1"}}
    raw={"question_id":qid,"question_version_id":qvid,"question_version_number":1,"question_checksum_sha256":hashlib.sha256((qid+qvid).encode()).hexdigest(),
      "curriculum":curr,"content":content,"architecture":arch,"governance":gov,"provenance":prov}
    raw["projection"]=sm.integration_v1._projection(raw,{})
    return raw

def release(c,rid="REL-QA",rv="V1",status="STAGED",local="STAGED",count=0):
    pkg=hashlib.sha256((rid+rv).encode()).hexdigest()
    c.execute("""INSERT INTO integration_ph_content_releases(
      release_id,release_version,package_checksum_sha256,manifest_checksum_sha256,payload_checksum_sha256,
      semantic_checksum_sha256,release_status,local_status,effective_at,generated_at,market_id,programme_id,
      subject_id,chapter_id,question_count,stimulus_count,readiness_policy_version,supersedes_release_version,
      source_system_version,immutable_payload_json,admitted_at,schema_version,release_operation)
      VALUES(?,?,?,?,?,?,?, ?,NULL,NULL,'PK','FSC1','CHEM','CH1',?,0,'',NULL,'','{}',CURRENT_TIMESTAMP,'1.3.0','QA_STAGE')""",
      (rid,rv,pkg,"1"*64,"2"*64,"3"*64,status,local,count))
    return int(c.execute("SELECT last_insert_rowid()").fetchone()[0]),pkg

def insert(c,raw,rel="REL-QA",rv="V1",ordinal=1):
    c.execute("""INSERT INTO integration_ph_question_version_store(
      question_id,question_version_id,question_version_number,question_checksum_sha256,supersedes_question_version_id,effective_from,
      curriculum_json,content_json,architecture_json,governance_json,provenance_json,scoremax_projection_json,first_admitted_at)
      VALUES(?,?,?,?,NULL,NULL,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
      (raw["question_id"],raw["question_version_id"],1,raw["question_checksum_sha256"],canon(raw["curriculum"]),canon(raw["content"]),
       canon(raw["architecture"]),canon(raw["governance"]),canon(raw["provenance"]),canon(raw["projection"])))
    c.execute("""INSERT INTO integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id,ordinal,admitted_at)
      VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)""",(rel,rv,raw["question_id"],raw["question_version_id"],ordinal))

class WildQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=sm.db(); qa.ensure_schema(cls.c)
        cls.release_id,cls.pkg=release(cls.c,count=8)
        fixtures=[
          make_raw("Q-CLEAN"),
          make_raw("Q-DUP",options=[("A","same"),("B","same")]),
          make_raw("Q-BLANK",options=[("A",""),("B","two")]),
          make_raw("Q-STIM",stem="Using the diagram shown below, choose the answer."),
          make_raw("Q-UNKNOWN"),
          make_raw("Q-DRIFT"),
          make_raw("Q-IDDRIFT"),
          make_raw("Q-KEY",key="Z"),
        ]
        for i,q in enumerate(fixtures,1): insert(cls.c,q,ordinal=i)
        # Unknown runtime family: learner lane must never silently PASS it.
        p=json.loads(cls.c.execute("SELECT scoremax_projection_json FROM integration_ph_question_version_store WHERE question_id='Q-UNKNOWN'").fetchone()[0])
        p["qtype"]="ALIEN_RESPONSE"; cls.c.execute("UPDATE integration_ph_question_version_store SET scoremax_projection_json=? WHERE question_id='Q-UNKNOWN'",(canon(p),))
        # Learner projection drift with unchanged immutable source.
        p=json.loads(cls.c.execute("SELECT scoremax_projection_json FROM integration_ph_question_version_store WHERE question_id='Q-DRIFT'").fetchone()[0])
        p["question"]="Tampered learner stem"; cls.c.execute("UPDATE integration_ph_question_version_store SET scoremax_projection_json=? WHERE question_id='Q-DRIFT'",(canon(p),))
        # Identity drift inside projection.
        p=json.loads(cls.c.execute("SELECT scoremax_projection_json FROM integration_ph_question_version_store WHERE question_id='Q-IDDRIFT'").fetchone()[0])
        p["ph_question_id"]="OTHER"; cls.c.execute("UPDATE integration_ph_question_version_store SET scoremax_projection_json=? WHERE question_id='Q-IDDRIFT'",(canon(p),))
        cls.c.commit()

    @classmethod
    def tearDownClass(cls): cls.c.close()

    def test_01_student_a_duplicate_options_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-DUP")
        self.assertEqual(qa._student_a(sm,g)[0],"HOLD")

    def test_02_student_a_blank_option_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-BLANK")
        self.assertEqual(qa._student_a(sm,g)[0],"HOLD")

    def test_03_student_a_missing_referenced_stimulus_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-STIM")
        self.assertEqual(qa._student_a(sm,g)[0],"HOLD")

    def test_04_unknown_qtype_must_not_false_pass_student_a(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-UNKNOWN")
        status=qa._student_a(sm,g)[0]; q=qa._question(g); resolved=sm.canonical_question_type(q)
        self.assertNotEqual(status,"PASS",f"stored_qtype={q.get('qtype')!r} canonical={resolved!r} keys={sorted(q.keys())}")

    def test_05_invalid_key_reviewer_a_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-KEY")
        self.assertEqual(qa._reviewer_a(sm,g)[0],"HOLD")

    def test_06_reviewer_b_projection_content_drift_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-DRIFT")
        self.assertEqual(qa._reviewer_b(sm,self.c,g)[0],"HOLD")

    def test_07_reviewer_b_projection_identity_drift_hold(self):
        pop,_,_=qa._population(self.c,f"release:{self.release_id}")
        g=next(x for x in pop if x["row"]["question_id"]=="Q-IDDRIFT")
        self.assertEqual(qa._reviewer_b(sm,self.c,g)[0],"HOLD")

    def test_08_invalid_scope_fails_closed(self):
        with self.assertRaises(ValueError): qa.run_agents(sm,"STUDENT_A","typo-scope",None)

    def test_09_nonadmin_cannot_post_runner(self):
        client=sm.app.test_client()
        with client.session_transaction() as s:
            s["user_id"]=999999;s["role"]="student";s["session_version"]=0
        r=client.post("/admin/mastery-lab/qa-agents/run",data={"agent_code":"ALL","scope":"staged"},base_url="https://localhost")
        self.assertIn(r.status_code,(302,400,403))

    def test_10_qa_run_never_mutates_governed_or_mastery_tables(self):
        sensitive=["integration_ph_content_releases","integration_ph_question_version_store","integration_ph_release_question_membership","questions","attempts","attempt_answers","mastery_records"]
        before={t:fp(self.c,t) for t in sensitive}
        qa.run_agents(sm,"ALL",f"release:{self.release_id}",None)
        after={t:fp(self.c,t) for t in sensitive}
        self.assertEqual(before,after)

    def test_11_latest_problem_state_is_latest_by_id(self):
        qa.run_agents(sm,"STUDENT_A",f"release:{self.release_id}",None)
        latest=qa._latest_results(self.c)
        keys=[(r["agent_code"],r["question_id"],r["question_version_id"]) for r in latest]
        self.assertEqual(len(keys),len(set(keys)))

    def test_12_history_order_must_be_explicit(self):
        src=Path(ROOT/"ux_qa_agents_admin.py").read_text()
        self.assertIn("ORDER BY id",src)

    def test_13_full_history_not_same_20_row_dashboard_cap(self):
        src=Path(ROOT/"ux_qa_agents_admin.py").read_text()
        self.assertRegex(src,r"problem_limit|history_limit|LIMIT \?")

    def test_14_1500_question_four_lane_scale(self):
        rid,pkg=release(self.c,"REL-SCALE","V1",count=1500)
        base=make_raw("SCALE")
        for i in range(1500):
            q={**base,"question_id":f"S-{i:04d}","question_version_id":f"SV-{i:04d}","question_checksum_sha256":hashlib.sha256(str(i).encode()).hexdigest()}
            q["content"]=json.loads(json.dumps(base["content"]));q["content"]["stem"]=f"Scale question {i}?"
            q["projection"]=sm.integration_v1._projection(q,{})
            insert(self.c,q,"REL-SCALE","V1",i+1)
        self.c.commit()
        t=time.monotonic();out=qa.run_agents(sm,"ALL",f"release:{rid}",None);elapsed=time.monotonic()-t
        self.assertEqual(out["population"],1500)
        self.assertLess(elapsed,30.0,f"1,500 x four lanes took {elapsed:.2f}s")

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(WildQA)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    payload={"suite":"WILD_QA_ATTACK_V1","tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
      "status":"PASS" if result.wasSuccessful() else "FAIL","production_db_used":False,"release_authority":False,"mastery_authority":False}
    print("WILD_QA_ATTACK "+json.dumps(payload,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
