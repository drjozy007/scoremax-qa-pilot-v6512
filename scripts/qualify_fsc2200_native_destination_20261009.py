"""Disposable receiver contract: 2,180 FSc question versions, 971 MDCAT placements.
No live database, HTTP sends, learner release or fabricated academic authority.
"""
from __future__ import annotations
import copy, hashlib, json, time
from qualify_assessment_contract_repair import AssessmentRepair, ROOT, integration

COUNTS={"BIOLOGY":388,"CHEMISTRY":693,"MATHEMATICS":600,"PHYSICS":499}
MD=[("BIOLOGY","BIOLOGY","04",59),("CHEMISTRY","CHEMISTRY","03",80),
    ("CHEMISTRY","CHEMISTRY","04",387),("CHEMISTRY","CHEMISTRY","05",125),
    ("PHYSICS","CHEMISTRY","03",320)]
def h(s):return hashlib.sha256(str(s).encode()).hexdigest()
def count(c,sql,params=()):return int(c.execute(sql,params).fetchone()[0])
def verify(ok,msg):
    if not ok:raise AssertionError(msg)
def main():
    t=time.monotonic()
    case=AssessmentRepair("test_native_eight_response_journeys");case.setUp()
    try:
        c=case.c
        tpl=json.loads((ROOT/"integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json").read_text())
        sources={};receipts=[];seq=0
        for subject,total in COUNTS.items():
            grade="12" if subject=="PHYSICS" else "11"
            programme="FSC_PART_II" if grade=="12" else "FSC_PART_I"
            chapter="CHAPTER::"+subject+"::"+grade+"::"+("13" if grade=="12" else "01")
            qlist=[]
            for i in range(total):
                q=copy.deepcopy(tpl["payload"]["questions"][0])
                qid="PH-RS-Q-"+h(subject+str(i))[:24].upper()
                q.update(question_id=qid,question_version_id="QV::"+qid+"::v1",
                         question_version_number=1,supersedes_question_version_id=None,effective_from=None)
                q["curriculum"].update(market_id="PK",qualification_id="FSC",
                      programme_id=programme,subject_id=subject,chapter_id=chapter,
                      grade_year_id="YEAR_"+grade,section_id=None,topic_id=None,subtopic_id=None,
                      learning_outcome_ids=[],teaching_learning_outcome_ids=[])
                q["curriculum"]["display"].update(programme="FSc Part "+("2" if grade=="12" else "1"),
                      grade_year="Year "+grade,subject=subject.title(),
                      chapter_number=chapter.split("::")[-1],chapter="Synthetic test chapter",
                      section=None,topic=None,subtopic=None,outcome_text=None)
                q["content"].update(stem="Synthetic contract test "+qid,stimulus_ref=None,inline_stimulus=None)
                q["architecture"].update(knowledge_node_ids=[],claim_family_id=None,
                      reasoning_seed_id=None,parent_question_id=None,dependency_group_id=None,
                      dependency_type=None,evidence_role="DEPENDENT",
                      independent_mastery_eligible=False,independent_mastery_weight=0,
                      transfer_level=None,common_cr=None,mastery_level="FOUNDATION",
                      mastery_ceiling="EXAM_READY",misconception_ids=[])
                q["governance"].update(academic_review_state="APPROVED",hold_status="CLEAR",
                      source_check_status="CLEAR",release_readiness="READY",rights_status="OWNED",
                      r2_status="NOT_REQUIRED",generated_clearance_status="NOT_APPLICABLE")
                q["provenance"]["primary_source"].update(source_id="SYNTHETIC-CONTRACT-ONLY",
                      source_type="SCOREMAX_CREATED",source_title="Synthetic fixture (not textbook)",
                      source_version="SYNTHETIC",source_file_sha256=None,rights_status="OWNED",metadata={})
                q["provenance"]["lineage"]["original_question_id"]=qid
                q["question_checksum_sha256"]=integration._object_checksum(q,"question_checksum_sha256")
                qlist.append(q)
            sources[subject]=(programme,chapter,qlist)
        def admit(rid,programme,subject,chapter,questions):
            nonlocal seq
            seq+=1
            e=copy.deepcopy(tpl)
            e.update(schema_version="1.2.0",message_id="msg::PH-SYN-"+str(seq),
                     idempotency_key="PH-SYN::"+rid,
                     producer_version="FSC2200-CONTRACT-20261009")
            p=e["payload"];p.update(delivery_mode="INLINE",package_download_url=None,
                     release_operation="PUBLISH_SNAPSHOT",questions=questions,stimuli=[])
            p["release"].update(release_id=rid,release_version="1",release_status="ACADEMICALLY_READY",
                     market_id="PK",programme_id=programme,subject_id=subject,chapter_id=chapter,
                     question_count=len(questions),stimulus_count=0,effective_at=None,
                     package_checksum_sha256=h(rid+"::archive"),
                     manifest_checksum_sha256=h(rid+"::manifest"))
            e["payload_checksum_sha256"]=integration.payload_checksum(p)
            rec,status=integration.admit_content_envelope(c,e,e["payload_checksum_sha256"])
            c.commit()
            verify(status==202 and rec["status"]=="ACCEPTED",
                   "NOT_ACCEPTED "+rid+" "+str(status)+" "+str(rec)[:600])
            receipts.append(rec["receipt_id"])
            return e
        for subject,(programme,chapter,questions) in sources.items():
            admit("REL::PK::"+programme+"::"+subject+"::"+chapter,programme,subject,chapter,questions)
        for src,dest,unit,n in MD:
            q=sources[src][2][:n]
            rid="REL::PK::MDCAT::"+dest+"::U"+unit+"::SRC::"+src
            admit(rid,"MDCAT",dest,"MDCAT::"+dest+"::UNIT::"+unit,q)
            verify(count(c,"SELECT COUNT(*) FROM integration_ph_release_question_membership WHERE release_id=?",(rid,))==n,
                   "MDCAT_RELEASE_MEMBERSHIPS_WRONG "+rid)
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_question_version_store")==2180,"CANONICAL_VERSION_DUPLICATED")
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_release_question_membership")==3151,"PROGRAMME_MEMBERSHIP_TOTAL_WRONG")
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_content_releases")==9,"RELEASE_GROUP_COUNT_WRONG")
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_content_releases WHERE local_status='STAGED'")==9,"NOT_ALL_STAGED")
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_product_activation_authorizations")==0,"ACTIVATION_AUTHORIZATION_CREATED")
        verify(count(c,"SELECT COUNT(*) FROM integration_ph_content_releases WHERE local_status='ACTIVE'")==0,"ACTIVATION_ESCAPED")
        rid="REL::PK::MDCAT::CHEMISTRY::U03::SRC::PHYSICS"
        rows=c.execute("""SELECT m.question_id,m.question_version_id,v.question_checksum_sha256,
                       v.curriculum_json,r.programme_id,r.subject_id,r.chapter_id
                       FROM integration_ph_release_question_membership m
                       JOIN integration_ph_question_version_store v
                         ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
                       JOIN integration_ph_content_releases r
                         ON r.release_id=m.release_id AND r.release_version=m.release_version
                       WHERE m.release_id=?""",(rid,)).fetchall()
        verify(len(rows)==320,"PHYSICS_MDCAT_CHEM_GASES_COUNT")
        original={q["question_id"]:q for q in sources["PHYSICS"][2]}
        for row in rows:
            q=original[row["question_id"]]
            verify(row["question_version_id"]==q["question_version_id"] and
                   row["question_checksum_sha256"]==q["question_checksum_sha256"],
                   "CANONICAL_QUESTION_VERSION_CHANGED")
            cur=json.loads(row["curriculum_json"])
            verify((cur["programme_id"],cur["subject_id"])==("FSC_PART_II","PHYSICS"),
                   "FSC_CURRICULUM_REWRITTEN")
            verify((row["programme_id"],row["subject_id"],row["chapter_id"])==
                   ("MDCAT","CHEMISTRY","MDCAT::CHEMISTRY::UNIT::03"),"MDCAT_DESTINATION_WRONG")
        print("SCOREMAX_FSC2200_MEMBERSHIP_RECEIVER_PASS "+json.dumps({
            "canonical":2180,"fsc_memberships":2180,"mdcat_memberships":971,
            "programme_memberships":3151,"releases":9,"physics_to_mdcat_chemistry":320,
            "no_activation":True,"synthetic_only":True,"real_bank_not_verified":True,
            "elapsed_seconds":round(time.monotonic()-t,2)},sort_keys=True),flush=True)
    finally:case.tearDown()
if __name__=="__main__":main()
