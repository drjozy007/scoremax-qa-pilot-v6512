"""UK 11+ Maths 85-case native scorer CHARACTERISATION ONLY.

Replays the immutable held v0.4 case register against the exact assembled
ScoreMax mark_question_response function. No question is activated, marked
for real mastery or academically cleared; constructed response and unresolved
policies fail closed rather than being guessed into a scorer contract.
"""
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import sys
import traceback

SRC=Path('/qualifier/fixtures/math20_v04_scoring_cases.csv')
OUT=Path('/evidence/UK11_MATH85_NATIVE_CHARACTERISATION.json')
OUT.parent.mkdir(parents=True, exist_ok=True)

SPEC={
    'Q004': {'qtype':'Numerical','question':'Thirteen flatbreads are divided equally among four families.', 'answer':'3.25','option_a':'','answer_config':{},'marking_config':{'correct_value':3.25,'tolerance':0,'auto_markable':True,'marks':1}},
    'Q008': {'qtype':'Fill Blank','question':'Which village has the larger fraction recycling?', 'answer':'Village B','option_a':'Village B','answer_config':{'accepted_answers':['Village B','B'],'trim_spaces':True,'case_sensitive':False},'marking_config':{'auto_markable':True,'marks':1}},
    'Q016': {'qtype':'True/False','question':'Is 9 × (7 + 3) = 9 × 7 + 3 correct?', 'answer':'No','option_a':'No','answer_config':{'options':[{'id':'Yes','text':'Yes'},{'id':'No','text':'No'}]},'marking_config':{'correct_option_ids':['No','FALSE'],'auto_markable':True,'marks':1}},
    'Q018': {'qtype':'Fill Blank','question':'Which school club had greatest increase?', 'answer':'Art club','option_a':'Art club','answer_config':{'accepted_answers':['Art','Art club'],'trim_spaces':True,'case_sensitive':False},'marking_config':{'auto_markable':True,'marks':1}},
    'Q020': {'qtype':'Fill Blank','question':'Which strip has greater shaded fraction?', 'answer':'Strip A','option_a':'Strip A','answer_config':{'accepted_answers':['Strip A','A'],'trim_spaces':True,'case_sensitive':False},'marking_config':{'auto_markable':True,'marks':1}},
}
UNSUPPORTED={'Q011':'MULTIPART_SOURCE_CONTRACT_UNQUALIFIED','Q014':'MULTIPART_SOURCE_CONTRACT_UNQUALIFIED'}


def row_for_native(q):
    s=SPEC[q]
    return {**s,'answer_config':json.dumps(s['answer_config'],sort_keys=True),'marking_config':json.dumps(s['marking_config'],sort_keys=True),'marks':1,'misconception_tags':'[]'}


def cast_input(q, response):
    if isinstance(response,dict):return None,'MULTIPART_RESPONSE_UNSUPPORTED'
    if isinstance(response,bool):
        if q=='Q016':return 'Yes' if response else 'No','BOOLEAN_UI_LABEL_ADAPTER_PROVISIONAL'
        return None,'UNEXPECTED_BOOLEAN'
    if response is None:return '','RAW_INPUT'
    return str(response),'RAW_INPUT'


def evaluate():
    if not SRC.exists():raise FileNotFoundError(str(SRC))
    with SRC.open(encoding='utf-8',newline='') as fh:rows=list(csv.DictReader(fh))
    assert len(rows)==85 and len({r['Case_ID'] for r in rows})==85
    assert sum(r['Suite']=='BASE_V0_3' for r in rows)==55
    assert sum(r['Suite']=='ADVERSARIAL_V0_4' for r in rows)==30

    # Only the exact pre-built ScoreMax runtime, never local reference scorer.
    os.environ.update({
        'SCOREMAX_ENV':'production','SCOREMAX_PERSISTENT_ROOT':'/data/scoremax',
        'SCOREMAX_DB':'/data/scoremax/state/scoremax.db',
        'SCOREMAX_BACKUP_DIR':'/data/scoremax/backup',
        'SCOREMAX_CONTENT_INTAKE_DIR':'/data/scoremax/intake',
        'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data',
        'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-UK11-Maths85-Only-2026',
        'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'math85-only@example.test',
        'SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1',
        'SCOREMAX_SECRET':'synthetic-math85-runtime-only-secret-long-enough',
        'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-math85-stage-only',
        'SCOREMAX_SMTP_FROM':'noreply@example.test',
        'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
        'SCOREMAX_PUBLIC_BASE_URL':'https://localhost',
        'SCOREMAX_SEND_EMAIL_VERIFICATION':'0',
        'SCOREMAX_SMTP_HOST':'smtp.invalid',
        'SCOREMAX_PAID_AI_FEEDBACK':'0',
        'SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0',
        'SCOREMAX_INTERNAL_FULL_ACCESS':'0',
    })
    os.environ.pop('DEEPSEEK_API_KEY',None)
    sys.path.insert(0,'/app')
    sys.path.insert(0,'/checks/native_guard')
    import scoremax_persistent_storage_guard as persistent_guard
    persistent_guard.main()
    import scoremax_production as hosted
    scorer=hosted.scoremax.mark_question_response
    results=[]
    for r in rows:
        cid=r['Case_ID'];qid=r['Question']
        try:response=json.loads(r['Learner submission (JSON-encoded)'])
        except Exception as exc:
            results.append({'case':cid,'question':qid,'state':'INPUT_DATA_ERROR','error_type':type(exc).__name__});continue
        expected=(None if r['Expected marks'].strip()=='' else float(r['Expected marks']))
        rec={'case':cid,'question':qid,'suite':r['Suite'],'scenario':r['Scenario'],
             'expected_marks':expected,'native_marks':None,
             'contract_status':'PROVISIONAL_CASE_REGISTER_NOT_FROZEN',
             'original_response':response}
        if expected is None:
            rec['state']='POLICY_HOLD'
            rec['reason']='EXPECTED_MARKS_NOT_APPROVED'
        elif qid in UNSUPPORTED:
            rec['state']='UNSUPPORTED_SOURCE_FORMAT'
            rec['reason']=UNSUPPORTED[qid]
        elif qid not in SPEC:
            rec['state']='UNSUPPORTED_SOURCE_FORMAT';rec['reason']='UNKNOWN_QUESTION_CONTRACT'
        else:
            selected,adapter=cast_input(qid,response)
            rec['adapter']=adapter
            if selected is None:
                rec['state']='UNSUPPORTED_RESPONSE'
            else:
                try:
                    ok,marks,_=scorer(row_for_native(qid),selected,{})
                    rec['native_marks']=float(marks)
                    rec['native_is_correct']=bool(ok)
                    rec['state']='NATIVE_REFERENCE_MATCH' if abs(float(marks)-expected)<1e-9 else 'NATIVE_REFERENCE_MISMATCH'
                except Exception as exc:
                    rec['state']='NATIVE_EXCEPTION'
                    rec['error_type']=type(exc).__name__
                    rec['error_code']=str(exc)[:160]
        results.append(rec)
    states=Counter(r['state'] for r in results)
    by_q={q:dict(Counter(x['state'] for x in results if x['question']==q)) for q in sorted({x['question'] for x in results})}
    final={
       'title':'UK11 Maths 85 held cases — native scorer characterisation',
       'classification':'SYNTHETIC_PROVISIONAL_NOT_QUALIFIED',
       'runtime':'EXACT_ASSEMBLED_SCOREMAX_CI',
       'case_register':'ScoreMax_11Plus_Maths_20Q_Native_Scoring_and_WCA_PreAdmission_v0_4.xlsx / SCORING_FIXTURES',
       'total':len(results), 'baseline':55,'adversarial':30,'state_counts':dict(states),'per_question':by_q,
       'native_exception_codes':dict(Counter(str(x.get('error_type'))+':'+str(x.get('error_code')) for x in results if x['state']=='NATIVE_EXCEPTION')),
       'source_policy':'No approved UK response contracts/mark demands; do not count provisional comparison as academic clearance',
       'real_marks_or_mastery_updated':False,'paid_provider_calls':0,'status':'CHARACTERIZED_NOT_CLEARED',
       'cases':results,
    }
    OUT.write_text(json.dumps(final,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('UK11_MATH85_NATIVE_RESULT '+json.dumps({k:v for k,v in final.items() if k!='cases'},sort_keys=True,ensure_ascii=False),flush=True)
    assert len(results)==85 and sum(states.values())==85
    assert not states['INPUT_DATA_ERROR'] and not states['NATIVE_EXCEPTION'], 'NATIVE_SCORER_CHARACTERIZATION_ERROR'
    return final

try:evaluate()
except Exception as exc:
    print('UK11_MATH85_FATAL '+type(exc).__name__+' '+str(exc),flush=True)
    traceback.print_exc()
    raise