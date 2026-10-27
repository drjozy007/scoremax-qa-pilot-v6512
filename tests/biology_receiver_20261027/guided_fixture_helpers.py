import json
import guided_self_assessment as guided

def source_fixture():
    return {'Capability_Status':'READY','Required_Produced_Representation':'NONE',
        'Learner_Output_Type':'TEXT_SHORT_RESPONSE','Learner_Question':'[SYNTHETIC] Describe the sample.',
        'Model_Answer':'The sample is rectangular. Its surface is smooth.', 'Marks':3,
        'Mark_Point_Count':2,'Mark_Point_Values':'1;2',
        'Canonical_Accepted_Evidence':'The sample is rectangular. | Its surface is smooth.',
        '_PH_Original_Master_SHA256':'0'*64}


def fixture():
    source = source_fixture()
    rubric = {'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':3,
        'auto_marking_eligibility':'RUBRIC_SEMANTICALLY_SCORABLE','scoring_type':'SEMANTIC_MARK_POINT',
        'required_mark_points':[
            {'id':'p1','description':'The sample is rectangular.','marks':1},
            {'id':'p2','description':'Its surface is smooth.','marks':2}],
        'source_scoring_policies':{'Contradiction_Rule':'A contradiction removes credit for that point.'}}
    rubric['contract_sha256']=guided.digest(rubric)
    bound=guided.bind(rubric,source,{'mode':guided.MODE,'reference':'SYNTHETIC_TEST_ONLY'})
    return {'qtype':'Constructed Response','question':source['Learner_Question'],'answer':source['Model_Answer'],
        'marks':3,'ph_is_auto_markable':0,'question_version':2,'stimulus_data':'','command_word':'describe',
        'answer_config':'{}','marking_config':json.dumps({'auto_markable':False,'marks':3,'rubric':bound})}


