"""UK 11+ Maths B01 40Q / 244-case governed *candidate* native characterisation.

Never mark this batch as Power House approved. Uses isolated CI assembled ScoreMax
native direct scorer for clearly representable responses. Unit/fraction cases
are exploratory probes and explicitly NOT admission-ready contracts.
"""
from __future__ import annotations
import base64,collections,decimal,fractions,gzip,hashlib,json,os,re,sys,traceback
from pathlib import Path

SOURCE=Path('/qualifier/fixtures/b01_40q_private_qualification_fixture.json.gz.b64')
OUTPUT=Path('/evidence/UK11_B01_40Q_244_NATIVE_CHARACTERISATION.json')
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
PACKAGE_SHA='2d170f01e6ec0cdd1d3ab6586a10cb33a09f1189a0eed040c013d1f8c0c86ee3'

def load():
    blob=gzip.decompress(base64.b64decode(''.join(SOURCE.read_text().split()),validate=True))
    assert hashlib.sha256(blob).hexdigest()==PACKAGE_SHA,'CANDIDATE_FIXTURE_SHA_CHANGED'
    obj=json.loads(blob)
    assert obj['metadata']['source_raw_sha256']=='6221c6085ff0bd4368754759c109d017344a734aef13201d9531ead0ff8d52b8'
    assert obj['metadata']['classification']=='HELD_CANDIDATE_PRIVATE_DO_NOT_RELEASE'
    assert len(obj['questions'])==40 and len(obj['fixtures'])==244
    assert not obj['metadata']['scan_flags']
    return obj

def numeric_target(text):
    """Provisional numeric extraction for scorer probing, not learner policy.

    Only enough to read candidate reference values. Typed input is always left
    unchanged and passed to the *actual native* marker.
    """
    s=str(text or '').strip().replace('−','-')
    if s.startswith('£'):s=s[1:]
    s=s.replace(',','')
    m=re.match(r'^([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s+\d+/\d+|/\d+)?)\s*',s)
    if not m: raise ValueError('UNRECOGNISED_REFERENCE_NUMBER')
    a=m.group(1)
    if re.fullmatch(r'[+-]?\d+\s+\d+/\d+',a):
        whole,part=a.split(); result=fractions.Fraction(whole)+fractions.Fraction(part)
    elif '/' in a: result=fractions.Fraction(a)
    else: result=fractions.Fraction(decimal.Decimal(a))
    return float(result)

def native_row(q):
    fmt=q['response_kind']
    qtype='MCQ' if fmt=='single_select' else 'Numerical'
    if fmt=='single_select':
        cfg={'options':[{'id':k,'text':v} for k,v in q['options'].items()]}
        mark={'marks':1,'auto_markable':True,'correct_option_ids':[q['correct_option_letter']]}
        answer=q['correct_option_letter']
    else:
        cfg={}
        mark={'marks':1,'auto_markable':True,'correct_value':numeric_target(q['correct_answer_private']),'tolerance':0}
        answer=q['correct_answer_private']
    return {'qtype':qtype,'answer':answer,'option_a':q['options'].get('A',''),
            'answer_config':json.dumps(cfg,sort_keys=True),
            'marking_config':json.dumps(mark,sort_keys=True),
            'marks':1,'misconception_tags':'[]'}

def native_runtime():
    env={
      'SCOREMAX_ENV':'production','SCOREMAX_PERSISTENT_ROOT':'/data/scoremax',
      'SCOREMAX_DB':'/data/scoremax/state/scoremax.db','SCOREMAX_BACKUP_DIR':'/data/scoremax/backup',
      'SCOREMAX_CONTENT_INTAKE_DIR':'/data/scoremax/intake','SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data',
      'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-UK11-B01-40Q-Only-2026',
      'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'b01-only@example.test',
      'SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1',
      'SCOREMAX_SECRET':'synthetic-b01-direct-marker-runtime-only-secret-long-enough',
      'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-b01-stage-only',
      'SCOREMAX_SMTP_FROM':'noreply@example.test','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
      'SCOREMAX_PUBLIC_BASE_URL':'https://localhost','SCOREMAX_SEND_EMAIL_VERIFICATION':'0',
      'SCOREMAX_SMTP_HOST':'smtp.invalid','SCOREMAX_PAID_AI_FEEDBACK':'0',
      'SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0','SCOREMAX_INTERNAL_FULL_ACCESS':'0',
    }
    os.environ.update(env);os.environ.pop('DEEPSEEK_API_KEY',None)
    sys.path.insert(0,'/app');sys.path.insert(0,'/checks/native_guard')
    import scoremax_persistent_storage_guard as guard
    guard.main()
    import scoremax_production as hosted
    return hosted.scoremax.mark_question_response

def run():
    data=load()
    questions={q['draft_label']:q for q in data['questions']}
    marker=native_runtime()
    observed=[]
    for f in data['fixtures']:
        cid=f['case_id']; q=questions[f['draft_label']]
        fmt=q['response_kind']; expect=f['expected']
        rec={'case_id':cid,'draft_label':f['draft_label'],'response_format':fmt,
             'governed_route':q['governed_route_status'],
             'learner_sha256':f['learner_sha256'],'expected_candidate_outcome':expect,
             'native_marks':None,'status':None,'reason':None,
             'eligible_for_bank_or_mastery':False}
        assert f['learner_sha256']==q['learner_sha256']
        if expect in ('POLICY_HOLD','BLOCK_SCORING'):
            rec['status']=expect
            rec['reason']='AUTHOR_POLICY_NOT_SETTLED' if expect=='POLICY_HOLD' else 'AUTHOR_EXPLICIT_BLOCK_SCORING'
        else:
            try:
                nq=native_row(q)
                selected=f['response']
                native_ok,native_mark,_=marker(nq,selected,{})
                rec['native_marks']=float(native_mark)
                rec['native_is_correct']=bool(native_ok)
                rec['comparison_matched']=abs(rec['native_marks'] - (1 if expect=='MARK_1' else 0))<=1e-9
                if fmt=='single_select':
                    rec['status']='NATIVE_MC_MATCH' if rec['comparison_matched'] else 'NATIVE_MC_MISMATCH'
                elif fmt=='numeric':
                    rec['status']='NATIVE_NUMERIC_MATCH' if rec['comparison_matched'] else 'NATIVE_NUMERIC_MISMATCH'
                    rec['reason']='PROVISIONAL_FORMAT_NOT_ACADEMICALLY_FROZEN'
                elif fmt=='fraction':
                    rec['status']='FRACTION_CONTRACT_HOLD'
                    rec['reason']='DIRECT_NUMERIC_FALLBACK_NOT_QUALIFIED_FRACTION_ENTRY'
                elif fmt=='unit_value':
                    rec['status']='UNIT_CONTRACT_HOLD'
                    rec['reason']='UNIT_REQUIREMENT_HAS_NO_APPROVED_NATIVE_RESPONSE_AND_MARKING_CONTRACT'
                else:
                    raise AssertionError('UNKNOWN_RESPONSE_KIND')
            except Exception as exc:
                rec['status']='NATIVE_TEST_ERROR';rec['error_class']=type(exc).__name__
                rec['error_code']=str(exc)[:160]
        observed.append(rec)
    # Additional red-team probe. This is NOT a scoring approval.
    bare_unit_bypass=[]
    for q in questions.values():
        if q['response_kind']!='unit_value':continue
        try:
            bare=numeric_target(q['correct_answer_private']);nq=native_row(q)
            score=marker(nq,str(bare),{})[1]
            bare_unit_bypass.append({'draft_label':q['draft_label'],
             'required_unit':q['required_unit'],'bare_value_would_score_in_naive_numeric_mapping':bool(score==1.0)})
        except Exception as exc:
            bare_unit_bypass.append({'draft_label':q['draft_label'],'error':type(exc).__name__})
    states=dict(collections.Counter(x['status'] for x in observed))
    bykind={fmt:dict(collections.Counter(x['status'] for x in observed if x['response_format']==fmt)) for fmt in ('single_select','numeric','unit_value','fraction')}
    mismatches=[x for x in observed if x['status'] in ('NATIVE_MC_MISMATCH','NATIVE_NUMERIC_MISMATCH')]
    result={
      'title':'ScoreMax UK11 Maths B01 — 40 held candidates, 244 proposed native response cases',
      'source_file':data['metadata']['source_filename'],
      'source_raw_sha256':data['metadata']['source_raw_sha256'],
      'fixture_json_sha256':PACKAGE_SHA,
      'runtime':'EXACT_RENDER_ASSEMBLED_SCOREMAX_ISOLATED_CI',
      'scope':'DIRECT_NATIVE_MARKER_CHARACTERISATION_ONLY',
      'status':'EVALUATED_HOLD_NO_BANK_ADMISSION',
      'total_questions':40,'total_cases':len(observed),
      'all_questions_source_approved':False,'all_expected_mark_rules_approved':False,
      'production_database_modified':False,'mastery_modified':False,'provider_calls':0,
      'category_counts':states,'counts_by_response_kind':bykind,
      'source_route_counts':data['metadata']['routes'],
      'source_mcq_static_flags':data['metadata']['scan_flags'],
      'native_determinate_mismatches':len(mismatches),
      'non_authoritative_bare_numeric_unit_probes':bare_unit_bypass,
      'case_results':observed,
      'conclusions':['No question academically accepted by this characterisation',
                     'Units and fractions require approved format and native scorer','Scored attempts must be replayed through live-style native renderer before release',
                     'All four source-opportunity held drafts remain held',
                     'True school/provider/cycle memberships not inferred'],
    }
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print('UK11_B01_NATIVE_RESULT '+json.dumps({k:v for k,v in result.items() if k not in ('case_results','non_authoritative_bare_numeric_unit_probes')},sort_keys=True),flush=True)
    print('UK11_B01_UNIT_BARE_NUMBER_PROBES '+json.dumps(bare_unit_bypass,sort_keys=True),flush=True)
    assert len(observed)==244 and sum(states.values())==244
    assert not states.get('NATIVE_TEST_ERROR'), 'NATIVE_CHARACTERISATION_EXCEPTION'
    assert len(bare_unit_bypass)==12
    return result

try:run()
except Exception as exc:
    print('UK11_B01_FATAL '+type(exc).__name__+' '+str(exc),flush=True)
    traceback.print_exc();raise