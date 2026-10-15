"""Destination-review regression on the actual assembled app, disposable storage only."""
from __future__ import annotations
import hashlib,json,unittest
from urllib.parse import urlencode,urlsplit,parse_qs
from unittest.mock import patch
from qualify_assessment_contract_repair import AssessmentRepair,sm,reviewer,Tags,question
from qualify_qa_agents_admin import ph_item,table_fingerprint

ROOT='/student/content-review/staged'
BIO={'programme':'MDCAT','destination_subject':'BIOLOGY','destination_chapter':'MDCAT::BIOLOGY::UNIT::04'}
CHEM={'programme':'MDCAT','destination_subject':'CHEMISTRY','destination_chapter':'MDCAT::CHEMISTRY::UNIT::03'}

class DestinationReview(AssessmentRepair):
    def setUp(self):
        super().setUp()
        self.c.execute('UPDATE users SET content_reviewer_enabled=1 WHERE id=?',(self.uid,))
        self.c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,account_status,session_version) VALUES('SYN-ADMIN','admin','Synthetic Admin','admin@scoremax.test','syn-admin','active',0)")
        self.members={}
        self.release('FSC-BIO','FSC_PART_I','BIOLOGY','CHAPTER::BIOLOGY::11::01',['B1','B2'])
        self.release('MDCAT-BIO','MDCAT','BIOLOGY','MDCAT::BIOLOGY::UNIT::04',['B1','B2'])
        self.release('FSC-PHY','FSC_PART_II','PHYSICS','CHAPTER::PHYSICS::12::13',['P1'])
        self.release('MDCAT-CHEM','MDCAT','CHEMISTRY','MDCAT::CHEMISTRY::UNIT::03',['P1']+[f'P{i}' for i in range(2,126)])
        self.release('REL::CROSS50-QA13::TEST','FSC_PART_I','BIOLOGY','SYN-LEGACY',['B1'])
        self.c.commit()
        self.protected=['integration_receipts','integration_ph_content_releases','integration_ph_release_question_membership',
          'integration_ph_question_version_store','integration_ph_product_activation_authorizations','questions',
          'attempts','attempt_answers','mastery_records','written_mastery_evidence']
        self.before={t:table_fingerprint(self.c,t) for t in self.protected}

    def release(self,rid,programme,subject,chapter,ids):
        digest=hashlib.sha256(rid.encode()).hexdigest()
        self.c.execute("""INSERT INTO integration_ph_content_releases(release_id,release_version,package_checksum_sha256,
          manifest_checksum_sha256,payload_checksum_sha256,semantic_checksum_sha256,release_status,local_status,
          market_id,programme_id,subject_id,chapter_id,question_count,stimulus_count,readiness_policy_version,
          source_system_version,immutable_payload_json,admitted_at,schema_version,release_operation)
          VALUES(?,'1',?,?,?,?,'STAGED','STAGED','PK',?,?,?,?,0,'','','{}',CURRENT_TIMESTAMP,'1.3.0','QA_STAGE')""",
          (rid,digest,digest,digest,digest,programme,subject,chapter,len(ids)))
        self.c.execute("""INSERT INTO integration_receipts(receipt_id,message_id,contract_name,receiver_system,received_at,status,
          payload_checksum_sha256) VALUES(?,?,'PH_SM_APPROVED_CONTENT_V1','SCOREMAX',CURRENT_TIMESTAMP,'ACCEPTED',?)""",('RCPT-'+rid,'MSG-'+rid,digest))
        for i,qid in enumerate(ids):
            qvid='QV-'+qid
            if not self.c.execute('SELECT 1 FROM integration_ph_question_version_store WHERE question_version_id=?',(qvid,)).fetchone():
                raw,proj=ph_item(qid,qvid,[('A','one'),('B','two')],'B')
                source='Biology' if qid.startswith('B') else 'Physics'
                proj.update(subject=source,chapter='Original source chapter',ph_programme_id='FSC_SOURCE',ph_subject_id=source.upper(),ph_chapter_id='SOURCE-ONLY')
                proj['question']='[SYNTHETIC] '+qid+' <script>alert(1)</script>'
                raw['content']['stem']=proj['question']
                self.c.execute("""INSERT INTO integration_ph_question_version_store(question_id,question_version_id,
                  question_version_number,question_checksum_sha256,curriculum_json,content_json,architecture_json,
                  governance_json,provenance_json,scoremax_projection_json,first_admitted_at)
                  VALUES(?,?,1,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(qid,qvid,'a'*64,json.dumps(raw['curriculum']),json.dumps(raw['content']),json.dumps(raw['architecture']),json.dumps(raw['governance']),json.dumps(raw['provenance']),json.dumps(proj)))
            mid=self.c.execute("""INSERT INTO integration_ph_release_question_membership(release_id,release_version,question_id,
              question_version_id,ordinal,admitted_at) VALUES(?,'1',?,?,?,CURRENT_TIMESTAMP)""",(rid,qid,qvid,i+1)).lastrowid
            self.members[rid,qid]=mid

    def tearDown(self):
        self.assertEqual(self.before,{t:table_fingerprint(self.c,t) for t in self.protected})
        super().tearDown()

    def get(self,path=ROOT,filters=None,client=None):
        return (client or self.client).get(path+('?' + urlencode(filters) if filters else ''),base_url='https://localhost')

    def links(self,body):
        return [a['href'] for tag,a in Tags(body).tags if tag=='a' and a.get('href','').startswith(ROOT+'/')]

    def test_destination_scope_uses_membership_not_source(self):
        response=self.get(filters=CHEM);self.assertEqual(response.status_code,200)
        body=response.get_data(as_text=True)
        self.assertIn('Unit 03 — Gases',body);self.assertIn('Original source: Physics',body)
        self.assertIn('<strong>125</strong>',body);self.assertNotIn('[SYNTHETIC] B1',body)
        rows=reviewer._staged_scoped_rows(reviewer._staged_rows(self.c),CHEM)
        q=reviewer._staged_question_dict(rows[0])
        self.assertEqual((q['ph_programme_id'],q['ph_subject_id'],q['ph_chapter_id']),('MDCAT','CHEMISTRY',CHEM['destination_chapter']))
        self.assertEqual(q['subject'],'Physics');self.assertEqual(q['ph_question_version_id'],'QV-P1')

    def test_biology_filters_and_receipt_detail(self):
        response=self.get(filters=BIO);body=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200);self.assertEqual(len(self.links(body)),2)
        mid=self.members['MDCAT-BIO','B1']
        body=self.get(ROOT+'/'+str(mid),dict(BIO,view='reviewer')).get_data(as_text=True)
        for text in ('Cell Structure &amp; Function','RCPT-MDCAT-BIO','MDCAT-BIO','QV-B1','SOURCE-ONLY'):
            if text=='SOURCE-ONLY':self.assertNotIn(text,body)
            else:self.assertIn(text,body)
        self.assertNotIn('<script>alert(1)</script>',body)
        self.assertIn('&lt;script&gt;',body)

    def test_navigation_toggle_back_and_forms_preserve_scope(self):
        mid=self.members['MDCAT-BIO','B1']
        body=self.get(ROOT+'/'+str(mid),dict(BIO,view='reviewer')).get_data(as_text=True)
        tags=Tags(body).tags
        for tag,attrs in tags:
            href=attrs.get('href','')
            if tag=='a' and href.startswith(ROOT):
                args=parse_qs(urlsplit(href).query)
                for k,v in BIO.items():self.assertEqual(args[k],[v])
        hidden={(a.get('name'),a.get('value')) for t,a in tags if t=='input' and a.get('type')=='hidden'}
        self.assertTrue(set(BIO.items())<=hidden)
        nextmid=self.members['MDCAT-BIO','B2']
        self.assertIn(ROOT+'/'+str(nextmid)+'?',body)
        self.assertNotIn(ROOT+'/'+str(self.members['FSC-BIO','B2'])+'?',body)

    def test_pagination_has_no_unreachable_memberships(self):
        first=self.get(filters=CHEM).get_data(as_text=True)
        second=self.get(filters=dict(CHEM,page=2)).get_data(as_text=True)
        ids1=self.links(first);ids2=self.links(second)
        self.assertEqual((len(ids1),len(ids2)),(120,5));self.assertFalse(set(ids1)&set(ids2))
        self.assertIn('[SYNTHETIC] P125',second)
        self.assertEqual(self.get(filters=dict(CHEM,page='invalid')).status_code,200)
        self.assertIn('Page 2 of 2',self.get(filters=dict(CHEM,page=999)).get_data(as_text=True))

    def test_permission_and_out_of_scope_fail_closed(self):
        mid=self.members['MDCAT-BIO','B1']
        self.assertEqual(self.get(ROOT+'/'+str(mid),CHEM).status_code,404)
        self.assertEqual(self.get(client=self.client_for('syn-2')).status_code,403)
        self.assertIn(self.get(client=sm.app.test_client()).status_code,(302,403))
        self.assertEqual(self.get(filters=BIO,client=self.client_for('syn-admin')).status_code,200)
        body=self.get(filters=dict(BIO,destination_chapter='UNKNOWN')).get_data(as_text=True)
        self.assertIn('No staged questions match',body)
        before=table_fingerprint(self.c,'staged_human_review_decisions_v1')
        response=self.client.post(ROOT+'/'+str(mid)+'/decision',data=dict(CHEM,decision='APPROVED',_csrf_token='synthetic-csrf'),base_url='https://localhost')
        self.assertEqual(response.status_code,404)
        self.assertEqual(before,table_fingerprint(self.c,'staged_human_review_decisions_v1'))

    def test_existing_approval_moves_only_within_unit(self):
        mid=self.members['MDCAT-BIO','B1']
        response=self.client.post(ROOT+'/'+str(mid)+'/decision',data=dict(BIO,decision='APPROVED',_csrf_token='synthetic-csrf'),base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        self.assertEqual(urlsplit(response.location).path,ROOT+'/'+str(self.members['MDCAT-BIO','B2']))
        for k,v in BIO.items():self.assertEqual(parse_qs(urlsplit(response.location).query)[k],[v])

    def test_rejection_context_has_destination_authority(self):
        mid=self.members['MDCAT-CHEM','P1']
        row=reviewer._staged_question(self.c,mid)
        captured={}
        with patch.object(reviewer,'_queue_staged_incident',side_effect=lambda c,q,*args:captured.update(q) or ''):
            response=self.client.post(ROOT+'/'+str(mid)+'/decision',data=dict(CHEM,decision='REJECTED',reason='SYLLABUS',notes='Synthetic test only',_csrf_token='synthetic-csrf'),base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        self.assertEqual(captured['ph_subject_id'],'CHEMISTRY');self.assertEqual(captured['subject'],'Physics')
        self.assertEqual(captured['ph_chapter_id'],CHEM['destination_chapter'])
        self.assertEqual(captured['ph_release_id'],'MDCAT-CHEM')

    def test_legacy_cross50_and_source_filter_links(self):
        body=self.get(filters={'batch':'cross50'}).get_data(as_text=True)
        self.assertEqual(len(self.links(body)),1)
        body=self.get(filters={'subject':'Physics','chapter':'Original source chapter'}).get_data(as_text=True)
        self.assertIn('126 matching placements',body)

if __name__=='__main__':
    names=[n for n in DestinationReview.__dict__ if n.startswith('test_')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(DestinationReview(n) for n in names))
    print('STAGED_DESTINATION_REVIEW',json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,
      'production_database_used':False,'network_disabled':True,'governed_tables_unchanged':result.wasSuccessful()}))
    raise SystemExit(not result.wasSuccessful())
