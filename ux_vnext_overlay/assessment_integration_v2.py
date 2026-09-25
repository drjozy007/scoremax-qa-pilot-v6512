"""Build-time donors for existing scoremax_integration_v1. Immutable source stays intact."""

def effective_projection(stored,content):
    if not isinstance(stored,dict) or not isinstance(content,dict):
        raise question_contracts.QuestionContractError('IMMUTABLE_QUESTION_OBJECT_REQUIRED')
    out=dict(stored)
    # Reuse the existing immutable PH curriculum snapshot for older projections too.
    raw_curriculum=out.get('ph_curriculum_snapshot_json')
    if raw_curriculum not in (None,'','{}'):
        curriculum=strict_json_loads(raw_curriculum) if isinstance(raw_curriculum,str) else raw_curriculum
        out['programme']=question_contracts.programme_from_curriculum(curriculum)
    # Reuse the qualified PH projection, not a second independent mapping table.
    fresh=_projection_base({'content':content}, {})
    fields=('qtype','question','option_a','option_b','option_c','option_d','answer','marks','command_word','answer_config','marking_config','ph_is_auto_markable')
    for key in fields:out[key]=fresh[key]
    ac=strict_json_loads(out['answer_config']); mc=strict_json_loads(out['marking_config'])
    marking=content.get('marking') or {}
    for key in ('scoring_contract','auto_markable','partial_credit','allow_duplicate_targets'):
        if key in marking:mc[key]=marking[key]
    for key in ('case_sensitive','trim_spaces','unit','scoring_contract'):
        if key in marking:ac[key]=marking[key]
    if str(marking.get('key_type') or '').upper()=='NUMERIC':
        mc['correct_value']=marking.get('key')
        mc['tolerance']=marking.get('numeric_tolerance') if marking.get('numeric_tolerance') is not None else 0
    kind=mc.get('key_type')
    if kind=='SINGLE_OPTION':out['qtype']='MCQ'
    elif kind=='MULTIPLE_OPTIONS':out['qtype']='Multiple Select'
    elif kind=='TWO_TIER':
        raise question_contracts.QuestionContractError('UNQUALIFIED_TWO_TIER_INTERACTION')
    qt=question_contracts.canonical_runtime_type(out['qtype'])
    if kind=='MATCHING' or qt=='matching':
        out['qtype']='Matching';qt='matching'
        mapping=mc.get('matching_key') or mc.get('correct_mapping')
        if not ac.get('left_items') or not ac.get('right_options'):
            from ux_matching_support import parse_matching_surface
            parsed=parse_matching_surface(out.get('stimulus_data') or '',marking.get('key'))
            if parsed.get('valid'):
                ac['left_items']=parsed['left'];ac['right_options']=parsed['right']
        mc['correct_mapping']=mapping
        mc['allow_duplicate_targets']=bool(ac.get('allow_duplicate_targets',mc.get('allow_duplicate_targets',False)))
    if qt=='ordering':
        parsed=question_contracts.parse_ordering_contract(statements=content.get('statements'),key=marking.get('key'))
        ac['ordering_items']=parsed['items'];mc['correct_order']=parsed['correct_order']
        mc['auto_markable']=True
    if qt=='constructed_response':
        from ux_constructed_auto_marker import compile_contract
        mc['auto_markable']=bool(compile_contract(ac,out.get('answer') or '',out['marks'],out.get('question') or '',out.get('command_word') or '',mc))
    out['answer_config']=canonical_json(ac);out['marking_config']=canonical_json(mc)
    out['ph_response_contract']=qt
    out['ph_is_auto_markable']=1 if mc.get('auto_markable') is True else 0
    out['_response_adapter_version']='SM-ASSESSMENT-CONTRACT-2'
    return out


def _projection(q,stimuli):
    base=_projection_base(q,stimuli)
    return effective_projection(base,q.get('content') or {})


def _strict_pin_map(row):
    try:
        raw=row['ph_question_pins_json'] if 'ph_question_pins_json' in row.keys() else '{}'
        pins=strict_json_loads(raw or '{}')
        if not isinstance(pins,dict):raise ValueError()
        return pins
    except (ValueError,TypeError):
        raise question_contracts.QuestionContractError('CORRUPT_SESSION_QUESTION_PINS')


def _validated_pin(session_row,qid,current_row=None):
    pins=_strict_pin_map(session_row);pin=pins.get(str(qid))
    current=dict(current_row or {})
    if pin is None:
        if current.get('ph_projection_owner')=='POWER_HOUSE' or current.get('ph_question_version_id'):
            raise question_contracts.QuestionContractError('GOVERNED_QUESTION_PIN_MISSING')
        return None
    if not isinstance(pin,dict) or isinstance(pin.get('question_db_id'),bool) or pin.get('question_db_id')!=int(qid):
        raise question_contracts.QuestionContractError('PIN_LOCAL_ID_MISMATCH')
    required=('question_id','question_version_id','question_checksum_sha256','release_id','release_version','release_checksum_sha256')
    if any(not isinstance(pin.get(k),str) or not pin[k] for k in required):
        raise question_contracts.QuestionContractError('PIN_IDENTITY_INCOMPLETE')
    projection=pin.get('projection')
    if not isinstance(projection,dict) or not projection or any(k not in projection for k in ('qtype','question','answer_config','marking_config','question_version')):
        raise question_contracts.QuestionContractError('PIN_PROJECTION_INCOMPLETE')
    for pin_key,proj_key in (('question_id','ph_question_id'),('question_version_id','ph_question_version_id'),('question_checksum_sha256','ph_question_checksum_sha256')):
        if projection.get(proj_key)!=pin[pin_key]:
            raise question_contracts.QuestionContractError('PIN_SOURCE_IDENTITY_MISMATCH')
    version=pin.get('adapter_version')
    if version:
        if version!='SM-ASSESSMENT-CONTRACT-2':
            raise question_contracts.QuestionContractError('PIN_ADAPTER_VERSION_UNSUPPORTED')
        unsigned=dict(pin);supplied=unsigned.pop('pin_sha256',None)
        if not supplied or supplied!=hashlib.sha256(canonical_json(unsigned).encode()).hexdigest():
            raise question_contracts.QuestionContractError('PIN_CHECKSUM_MISMATCH')
    if not version and current.get('ph_question_version_id')==pin['question_version_id']:
        if question_contracts.runtime_type_from_row(current)!=question_contracts.runtime_type_from_row(projection):
            raise question_contracts.QuestionContractError('LEGACY_RESPONSE_ADAPTER_RESTART_REQUIRED')
    # Legacy complete compatible pins stay frozen; never silently reinterpret history.
    question_contracts.validate_assessment_contract(projection)
    return pin


def build_session_content_pins(c,question_ids):
    releases={};questions={}
    for qid in question_ids:
        row=c.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()
        if not row:raise question_contracts.QuestionContractError('QUESTION_NOT_FOUND')
        current=dict(row)
        governed=current.get('ph_projection_owner')=='POWER_HOUSE' or bool(current.get('ph_question_version_id'))
        if not governed:
            question_contracts.validate_assessment_contract(current)
            continue
        v=c.execute('SELECT * FROM integration_ph_question_version_store WHERE question_id=? AND question_version_id=?',(current.get('ph_question_id'),current.get('ph_question_version_id'))).fetchone()
        if not v or v['question_checksum_sha256']!=current.get('ph_question_checksum_sha256'):
            raise question_contracts.QuestionContractError('IMMUTABLE_VERSION_MISSING_OR_MISMATCHED')
        projection=effective_projection(strict_json_loads(v['scoremax_projection_json']),strict_json_loads(v['content_json']))
        question_contracts.validate_assessment_contract(projection)
        scope={key:current.get('ph_'+key) or '' for key in ('market_id','programme_id','subject_id','chapter_id')}
        pin={'question_db_id':int(qid),'question_id':current.get('ph_question_id'),'question_version_id':current.get('ph_question_version_id'),
             'question_checksum_sha256':current.get('ph_question_checksum_sha256'),'release_id':current.get('ph_release_id'),
             'release_version':current.get('ph_release_version'),'release_checksum_sha256':current.get('ph_release_checksum_sha256'),
             **scope,'projection':projection,'adapter_version':'SM-ASSESSMENT-CONTRACT-2'}
        pin['pin_sha256']=hashlib.sha256(canonical_json(pin).encode()).hexdigest()
        questions[str(qid)]=pin
        _validated_pin({'ph_question_pins_json':canonical_json(questions)},qid,current)
        rid=pin['release_id']
        release={'release_id':rid,'release_version':pin['release_version'],'package_checksum_sha256':pin['release_checksum_sha256'],**scope}
        if rid in releases and releases[rid]!=release:
            raise question_contracts.QuestionContractError('MIXED_RELEASE_VERSIONS_IN_SESSION')
        releases[rid]=release
    return releases,questions


def pinned_question(session_row,qid,current_row):
    pin=_validated_pin(session_row,qid,current_row)
    if not pin:
        if current_row is None:raise question_contracts.QuestionContractError('QUESTION_NOT_FOUND')
        return current_row
    # Never source missing academic/answer fields from a newer mutable question version.
    result=dict(pin['projection']);result['id']=int(qid)
    result.update(ph_projection_owner='POWER_HOUSE',ph_release_id=pin['release_id'],ph_release_version=pin['release_version'],ph_release_checksum_sha256=pin['release_checksum_sha256'])
    return result


def answer_pin(session_row,qid):
    return _validated_pin(session_row,qid) or {}


def _projection_constructed_contract(proj):
    from ux_constructed_auto_marker import compile_contract
    ac,mc,maximum=question_contracts.assessment_configs(proj)
    return compile_contract(ac,proj.get('answer') or '',maximum,proj.get('question') or '',proj.get('command_word') or '',mc)


def _self_marking_release_errors(c,release_id,release_version):
    rows=_eligible_release_question_versions(c,release_id,release_version)
    errors=[]
    for row in rows:
        try:
            projection=effective_projection(strict_json_loads(row['scoremax_projection_json']),strict_json_loads(row['content_json']))
            question_contracts.validate_assessment_contract(projection)
        except (ValueError,TypeError,KeyError) as exc:
            errors.append({'question_id':row['question_id'],'question_version_id':row['question_version_id'],'code':'SELF_MARKING_REQUIRED','detail':str(exc)})
    return errors


def _eligible_release_question_versions(c,release_id,release_version):
    return c.execute("""SELECT v.*,m.ordinal FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE m.release_id=? AND m.release_version=? AND NOT EXISTS (
        SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
        WHERE e.release_id=m.release_id AND e.release_version=m.release_version
          AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id)
      ORDER BY m.ordinal,m.id""",(str(release_id),str(release_version))).fetchall()
