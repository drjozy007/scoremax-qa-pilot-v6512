"""Explicit software-only signed fixture; confers no real source approval."""
from copy import deepcopy
import json
from pending_saq_delivery_contract_v1 import digest,VERSION,PURPOSE,POLICY,PROOF,validate


def content(fixture,label,marks=2):
    envelope=fixture.content(label);question=envelope['payload']['questions'][0]
    release=envelope['payload']['release'];body=question['content']
    body.update(question_family_type='SHORT_RESPONSE',exam_question_type='SHORT_RESPONSE',
        stem='State the software-only fixture criterion.',options=[],command_word='State')
    rubric={'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':marks,
        'source_marking_evidence_sha256':digest({'software_fixture_only':label}),
        'scoring_type':'EXACT_BOUNDED','auto_marking_eligibility':'RUBRIC_SEMANTICALLY_SCORABLE',
        'required_mark_points':[{'id':'opaque::point/001','description':'Software-only fixture criterion.',
            'marks':marks,'accepted_expressions':[],'accepted_synonyms':[],'contradictions':[]}]}
    rubric['contract_sha256']=digest(rubric)
    fields={'source_workbook_sha256':'3'*64,'truth_source_sha256':'4'*64,
        'source_snapshot_sha256':'5'*64,'academic_evidence_sha256':'6'*64,
        'source_question_id':'00001::opaque-source/'+label}
    proof={'policy':PROOF,'native_question_id':17,'material_checksum_sha256':'1'*64,
        'integrity_certificate_checksum_sha256':'7'*64,'quality_assessment_checksum_sha256':'8'*64,
        'native_review_snapshot_checksum_sha256':'9'*64,'source_binding_sha256':digest(fields),
        'independent_assessor_approval_conferred':False,'marking_authority_conferred':False}
    proof['proof_sha256']=digest(proof)
    answer='Software-only fixture criterion.'
    contract={'version':VERSION,'assessment_purpose':PURPOSE,'availability_policy':POLICY,
        'assessed_credit_pending':True,'official_ai_scoring_enabled':False,
        'question_id':question['question_id'],'native_question_id':17,'material_checksum_sha256':'1'*64,
        'source_question_id':fields['source_question_id'],'source_workbook_sha256':fields['source_workbook_sha256'],
        'source_row_sha256':rubric['source_marking_evidence_sha256'],'truth_source_sha256':fields['truth_source_sha256'],
        'source_snapshot_sha256':fields['source_snapshot_sha256'],
        'source_academic_evidence_sha256':fields['academic_evidence_sha256'],
        'rubric_contract_sha256':rubric['contract_sha256'],'maximum_marks':marks,
        'independent_mastery_weight':1,'publication_approval':proof,
        'destination':{**{k:release[k] for k in ('market_id','programme_id','subject_id','chapter_id')},
            'release_profile_id':'software-profile::'+label,'release_profile_checksum_sha256':'a'*64},
        'response_requirement':{'response_type':'TEXT','source_response_mode':'FREE_TEXT_CONSTRUCTED_RESPONSE',
            'source_output_type':'PLAIN_TEXT','required_produced_representation':'NONE'},
        'mastery_scope':{'mastery_level':'EXAM_READY','assessment_ceiling':'ADVANCED'},
        'learner_content_sha256':digest({'question':body['stem'],'answer':answer,'marks':float(marks),'rubric':rubric})}
    contract['contract_sha256']=digest(contract);validate(contract,rubric)
    body['marking'].update(key_type='TEXT',key=answer,accepted_answers=[],marks=marks,
        rubric={'scoring_contract':rubric,'assessment_eligibility':contract})
    question['provenance']['lineage']['scored_assessment_contract']={
        'version':VERSION,'contract_sha256':contract['contract_sha256'],
        'material_checksum_sha256':contract['material_checksum_sha256'],
        'publication_approval_proof_sha256':proof['proof_sha256']}
    question['question_checksum_sha256']=fixture.integration._object_checksum(question,'question_checksum_sha256')
    return fixture.seal(envelope)
