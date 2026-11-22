"""Signed, resealed receiver controls against borrowed or escalated contracts."""
from pathlib import Path
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scoremax_runtime_v669b'))
from native_delivery_fixture import NativeDeliveryFixture
from pending_saq_software_fixture_20261122 import content
from pending_saq_delivery_contract_v1 import digest


def run(runtime):
    cases=[]
    with tempfile.TemporaryDirectory(prefix='pending-native-adversarial-') as directory:
        f=NativeDeliveryFixture(runtime,directory)
        for mutation in ('weight_zero','wrong_marks','different_stem','borrowed_question_id',
                         'borrowed_source','wrong_destination','official_ai_on','false_assessor_claim'):
            e=content(f,'invalid-'+mutation);q=e['payload']['questions'][0]
            c=q['content'];marking=c['marking'];contract=marking['rubric']['assessment_eligibility']
            if mutation=='weight_zero':q['architecture']['independent_mastery_weight']=0
            if mutation=='wrong_marks':marking['marks']=3
            if mutation=='different_stem':c['stem']='Different software-only criterion.'
            if mutation=='borrowed_question_id':contract['question_id']='another-opaque-question'
            if mutation=='borrowed_source':contract['source_question_id']='another-opaque-source'
            if mutation=='wrong_destination':contract['destination']['chapter_id']='another-opaque-chapter'
            if mutation=='official_ai_on':contract['official_ai_scoring_enabled']=True
            if mutation=='false_assessor_claim':
                proof=contract['publication_approval'];proof['independent_assessor_approval_conferred']=True
                proof['proof_sha256']=digest({k:v for k,v in proof.items() if k!='proof_sha256'})
            contract['contract_sha256']=digest({k:v for k,v in contract.items() if k!='contract_sha256'})
            q['provenance']['lineage']['scored_assessment_contract']['contract_sha256']=contract['contract_sha256']
            q['question_checksum_sha256']=f.integration._object_checksum(q,'question_checksum_sha256')
            f.seal(e)
            status,result=f.signed_post('/api/integration/v1/power-house/content-releases',e,
                expected_statuses=(200,202,400,409,422))
            # A soft staging hold is permitted; learner activation must fail.
            try:f.activate(e)
            except (ValueError,RuntimeError):pass
            row=f.active(q)
            assert not row or row['active']==0,(mutation,status,result,row)
            cases.append({'mutation':mutation,'native_http_status':status,'learner_active':False})
        c=f.native.db()
        try:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()
        finally:c.close()
    return {'status':'PASSED','cases':cases,'authority':'SOFTWARE_FIXTURES_ONLY',
        'native_signature_and_question_checksums_resealed':True,'production_mutated':False}


if __name__=='__main__':
    result=run(Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'scoremax_runtime_v669b')
    output=Path(sys.argv[1]);assert not output.exists();output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
