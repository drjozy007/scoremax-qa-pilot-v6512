"""Build-time structured-result adapters for the existing app assessment route."""

def mark_question_result(q,selected,blueprint_marking_rules=None):
    import math
    q=dict(q)
    validated=question_contracts.validate_assessment_contract(q)
    qt=validated['qtype'];maximum=validated['maximum_marks']
    ac,mc,_=question_contracts.assessment_configs(q)
    rules=blueprint_marking_rules if isinstance(blueprint_marking_rules,dict) else {}
    def number(value,label,positive=False):
        try:
            if isinstance(value,bool) or not math.isfinite(float(value)) or (positive and float(value)<=0):raise ValueError()
            return float(value)
        except (TypeError,ValueError,OverflowError):
            raise question_contracts.QuestionContractError('INVALID_MARKING_RULE_'+label)
    correct_max=number(rules.get('correct_marks',maximum),'CORRECT',True)
    incorrect=number(rules.get('incorrect_marks',mc.get('negative_marks',0)),'INCORRECT')
    unanswered=number(rules.get('unanswered_marks',0),'UNANSWERED')
    if incorrect>correct_max or unanswered>correct_max:
        raise question_contracts.QuestionContractError('MARKING_RULE_OUT_OF_BOUNDS')
    if 'partial_credit_allowed' in rules and not isinstance(rules['partial_credit_allowed'],bool):
        raise question_contracts.QuestionContractError('PARTIAL_CREDIT_RULE_INVALID')
    text=str(selected or '').strip()
    if len(text)>10000:raise question_contracts.QuestionContractError('RESPONSE_LIMIT_EXCEEDED')
    if qt=='constructed_response':
        from ux_constructed_auto_marker import mark
        result=mark(validated['constructed_contract'],text)
        final=result.get('status')=='MARK_CONFIRMED' and result.get('evidence_eligible') is True
        earned=None
        if final:
            fraction=float(result['marks_awarded'])/maximum
            partial=rules.get('partial_credit_allowed',True)
            if not isinstance(partial,bool):raise question_contracts.QuestionContractError('PARTIAL_CREDIT_RULE_INVALID')
            if not text:earned=unanswered
            elif fraction>=1:earned=correct_max
            elif fraction<=0:earned=incorrect
            else:earned=correct_max*fraction if partial else incorrect
        return {**result,'marks_awarded':earned,'maximum_marks':correct_max,'source_maximum_marks':maximum,'confirmed':final,
                'evidence_eligible':final,'response_type':qt,'result_contract_version':'SM-MARK-RESULT-2','misconception':''}
    # Existing objective marker remains authoritative; do not duplicate its scoring logic.
    q['answer_config']=json.dumps(ac);q['marking_config']=json.dumps(mc)
    ok,earned,misconception=_mark_objective_response(q,text,rules)
    if misconception=='__PENDING_REVIEW__':
        raise question_contracts.QuestionContractError('HUMAN_MARKING_NOT_AVAILABLE')
    earned=number(earned,'AWARDED')
    if earned>correct_max:raise question_contracts.QuestionContractError('AWARD_EXCEEDS_MAXIMUM')
    return {'is_correct':bool(ok),'marks_awarded':earned,'maximum_marks':correct_max,'confirmed':True,
            'evidence_eligible':True,'confidence':1.0,'status':'MARK_CONFIRMED','feedback':[],
            'response_type':qt,'result_contract_version':'SM-MARK-RESULT-2','marker_version':'objective-v1',
            'misconception':misconception}


def mark_question_response(q,selected,blueprint_marking_rules=None):
    result=mark_question_result(q,selected,blueprint_marking_rules)
    if not result['confirmed']:
        raise question_contracts.QuestionContractError('AUTOMATIC_MARK_UNRESOLVED')
    return result['is_correct'],result['marks_awarded'],result['misconception']


def written_evaluate_attempt(c,attempt_id,answer_version_id,creates_formal_evidence=True):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    c.execute('SAVEPOINT written_marking_v2')
    try:
        attempt=c.execute("SELECT * FROM written_attempts WHERE id=?",(attempt_id,)).fetchone()
        version=c.execute("SELECT * FROM written_answer_versions WHERE id=? AND attempt_id=?",(answer_version_id,attempt_id)).fetchone()
        q=written_package_question(c,attempt['written_question_id']) if attempt else None
        if not attempt or not version or not q: raise ValueError('Written attempt evidence is incomplete.')
        payload=written_question_payload(q)
        answer=version['confirmed_transcript'] or version['answer_text'] or ''
        # One evaluated result per exact answer version. Replays never create extra
        # marks, recovery or evidence, and no retry is scheduled for unknown language.
        idem=f'written-marking-v2:{attempt_id}:{answer_version_id}'
        source_sha=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        answer_sha=hashlib.sha256(answer.encode()).hexdigest()
        prior=c.execute('SELECT input_json,output_json FROM written_processing_jobs WHERE idempotency_key=?',(idem,)).fetchone()
        inputs={'source_sha256':source_sha,'answer_sha256':answer_sha}
        if prior:
            if safe_json(prior['input_json'],{})!=inputs:raise ValueError('WRITTEN_REPLAY_CONTENT_CONFLICT')
            stored=safe_json(prior['output_json'],{})
            return stored['result'],stored.get('marking_run_id')
        result=mark_written_response(payload,answer)
        if result.get('status')!='MARK_CONFIRMED' or result.get('evidence_eligible') is not True:
            c.execute("UPDATE written_attempts SET status='AUTO_UNSCORED',result_state='AUTO_UNSCORED',current_mark=NULL,marking_confidence=0,completed_at=? WHERE id=?",
                      (datetime.now().isoformat(timespec='seconds'),attempt_id))
            c.execute("""INSERT INTO written_processing_jobs(attempt_id,job_type,state,provider,provider_version,idempotency_key,input_json,output_json)
              VALUES(?,'MARKING','AUTO_UNSCORED','local','governed-clause-1',?,?,?)""",
              (attempt_id,idem,json.dumps(inputs),json.dumps({'result':result,'marking_run_id':None})))
            c.execute("INSERT INTO written_usage_ledger(student_id,attempt_id,operation,provider,units,metadata_json) VALUES(?,?,?,'local',1,?)",
                      (attempt['student_id'],attempt_id,'written_marking',json.dumps({'result_state':'AUTO_UNSCORED'})))
            return result,None
        # Feedback-led versions cannot become independent evidence via a caller flag.
        creates_formal_evidence=bool(creates_formal_evidence and version['version_type'] in {'ORIGINAL_TYPED','CONFIRMED_TRANSCRIPT'})
        cur=c.execute("""INSERT INTO written_marking_runs(attempt_id,answer_version_id,proposed_mark,maximum_mark,percentage,
          confidence,result_state,command_verb_met,grader_a_json,grader_b_json,reconciliation_json,feedback_json,
          contradictions_json,misconceptions_json,validation_boundary) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (attempt_id,answer_version_id,result['proposed_mark'],result['maximum_mark'],result['percentage'],result['confidence'],
           result['status'],1 if result['command_verb_met'] else 0,json.dumps(result['grader_a']),json.dumps(result['grader_b']),
           json.dumps({'policy_version':result['reconciliation_policy_version']}),json.dumps(result['feedback']),
           json.dumps(result.get('contradictions',[])),json.dumps(result.get('misconceptions',[])),result['validation_boundary']))
        run_id=cur.lastrowid
        for pt in result['mark_points']:
            c.execute("""INSERT INTO written_mark_point_results(marking_run_id,point_id,description,available_marks,awarded_marks,
              status,evidence_json,improvement_instruction,grader_a_status,grader_b_status) VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (run_id,pt['point_id'],pt['description'],pt['available_marks'],pt['awarded_marks'],pt['status'],json.dumps(pt['evidence']),
               pt['improvement_instruction'],pt['grader_a_status'],pt['grader_b_status']))
        c.execute("""UPDATE written_attempts SET status='MARKED',current_mark=?,maximum_mark=?,marking_confidence=?,result_state=?,
          grader_a_version=?,grader_b_version=?,reconciliation_policy_version=?,completed_at=? WHERE id=?""",
          (result['proposed_mark'],result['maximum_mark'],result['confidence'],result['status'],result['grader_a']['version'],
           result['grader_b']['version'],result['reconciliation_policy_version'],datetime.now().isoformat(timespec='seconds'),attempt_id))
        package=safe_json(q['immutable_payload_json'],{})
        if creates_formal_evidence and result['status']=='MARK_CONFIRMED' and attempt['support_level']=='independent':
            evidence_status='AWAITING_UNSEEN_RECONFIRMATION'
            # The legacy hidden input is not evidence of unseen exposure. The ordinary
            # governed assessment pipeline owns formal verification; do not mint it here.
            c.execute("""INSERT INTO written_mastery_evidence(student_id,attempt_id,package_id,framework_id,framework_version_id,
              subject_id,chapter_id,learning_outcome_ids_json,concept_ids_json,proposition_ids_json,command_verb,cognitive_demand,
              evidence_level,support_level,novelty_status,score_percentage,confidence,evidence_status,evidence_json)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (attempt['student_id'],attempt_id,attempt['package_id'],q['framework_id'],q['framework_version_id'],q['subject_id'],q['chapter_id'],
               json.dumps(payload.get('learning_outcome_ids',[])),json.dumps(payload.get('concept_ids',[])),json.dumps(payload.get('proposition_ids',[])),
               payload.get('command_verb',''),payload.get('cognitive_demand',''),'independent_production',attempt['support_level'],
               attempt['novelty_status'],result['percentage'],result['confidence'],evidence_status,json.dumps(result)))
        missing=[x for x in result['mark_points'] if x['status']!='awarded']
        for pt in missing[:3]:
            activity=(payload.get('recovery_activity_map') or {}).get(pt['point_id'],'')
            c.execute("""INSERT INTO written_recovery_tasks(student_id,attempt_id,task_type,title,reason,approved_activity_id,scheduled_for)
              VALUES(?,?,?,?,?,?,date('now','+1 day'))""",(attempt['student_id'],attempt_id,'targeted_recovery',
              f"Repair: {pt['description'][:80]}",pt['improvement_instruction'],activity))
        if missing:
            plan=c.execute("SELECT * FROM study_plans WHERE student_id=? AND status='active' ORDER BY id DESC LIMIT 1",(attempt['student_id'],)).fetchone()
            if plan:
                title=f"Written-answer recovery: {missing[0]['description'][:70]}"
                exists=c.execute("SELECT 1 FROM study_plan_activities WHERE plan_id=? AND title=? AND status<>'completed'",(plan['id'],title)).fetchone()
                if not exists:
                    c.execute("""INSERT INTO study_plan_activities(plan_id,student_id,activity_date,subject,chapter,topic,activity_type,title,
                      target_score,status,source_reason,priority,estimated_minutes,mandatory)
                      VALUES(?,?,date('now','+1 day'),?,?,?,'written_recovery',?,100,'planned',?,1,25,1)""",
                      (plan['id'],attempt['student_id'],q['subject_id'],q['chapter_id'],'',title,'Written response diagnostic evidence'))
        c.execute("INSERT INTO written_usage_ledger(student_id,attempt_id,operation,provider,units,metadata_json) VALUES(?,?,?,'local',1,?)",
                  (attempt['student_id'],attempt_id,'written_marking',json.dumps({'marking_run_id':run_id})))
        c.execute("""INSERT INTO written_processing_jobs(attempt_id,job_type,state,provider,provider_version,idempotency_key,input_json,output_json)
          VALUES(?,'MARKING','COMPLETED','local','governed-clause-1',?,?,?)""",
          (attempt_id,idem,json.dumps(inputs),json.dumps({'result':result,'marking_run_id':run_id})))
        return result,run_id
    except Exception:
        c.execute('ROLLBACK TO SAVEPOINT written_marking_v2')
        raise
    finally:
        c.execute('RELEASE SAVEPOINT written_marking_v2')

