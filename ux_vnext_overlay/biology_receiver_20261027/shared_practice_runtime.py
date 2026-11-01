"""Bounded delta over the accepted ScoreMax assessment engine and signed dispatcher."""
from pathlib import Path
import hashlib
import importlib.util

MARKER = 'SM-SHARED-PRACTICE-CONTRACTS-1'


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise RuntimeError('SHARED_PRACTICE_SOURCE_DRIFT: '+old[:100])
    return text.replace(old, new)


def apply(root):
    root = Path(root)
    if (root/'ph_practice_contracts.py').exists():
        raise RuntimeError('SHARED_PRACTICE_PARTIAL_OR_REPEATED_BUILD')
    spec = importlib.util.spec_from_file_location('guided_admission_delta', Path(__file__).with_name('shared_ph_guided_admission_20261031.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.apply(root)
    changes = {}

    p = root/'question_contract_engine.py'; text = p.read_text()
    text = replace(text, '    "cloze": "cloze",', '    "cloze": "cloze",\n    "cloze_constructed_response": "cloze_constructed_response",')
    text = replace(text, '    "cloze": "fill_blank",', '    "cloze": "fill_blank",\n    "multi_gap_cloze": "multi_gap_cloze",', count=2)
    text = replace(text, '    "matching", "ordering", "constructed_response",', '    "matching", "ordering", "constructed_response", "multi_gap_cloze",')
    anchor = '    family = canonical_family(raw_family)\n'
    text = replace(text, anchor, anchor+'''    if family == 'cloze_constructed_response':
        explicit = _explicit_response(content, marking)
        from ph_practice_contracts import validate_cloze
        try:
            gaps = validate_cloze((marking.get('rubric') or {}).get('cloze_gap_contract'),
                                  content.get('stem'), marking.get('marks'))
        except (ValueError, TypeError, KeyError) as exc:
            raise QuestionContractError(str(exc)) from exc
        response = 'fill_blank' if gaps['gap_count'] == 1 else 'multi_gap_cloze'
        if explicit and explicit != response:
            raise QuestionContractError('CLOZE_RESPONSE_CONTRACT_CONFLICT')
        return QuestionContract(family, response, 'exact' if response == 'fill_blank' else 'all_gaps_exact', True,
                                derivation='SOURCE_BOUND_CLOZE_GAPS')
''')
    text = replace(text, "    if qtype=='matching':\n        mapping=", """    if qtype=='multi_gap_cloze':
        if 'answer' in form:
            raise QuestionContractError('CLOZE_SINGLE_FIELD_NOT_ALLOWED')
        mapping={}
        for key in form:
            if not str(key).startswith('gap::'): continue
            if hasattr(form,'getlist') and len(form.getlist(key)) != 1:
                raise QuestionContractError('CLOZE_DUPLICATE_GAP_RESPONSE')
            value=form.get(key)
            if not isinstance(value,str) or len(value)>1000:
                raise QuestionContractError('CLOZE_GAP_RESPONSE_INVALID')
            mapping[str(key)[5:]]=value.strip()
        return json.dumps(mapping,sort_keys=True,separators=(',',':')) if any(mapping.values()) else ''
    if qtype=='matching':
        mapping=""")
    text = replace(text, "    elif qt=='fill_blank':\n", """    elif qt=='multi_gap_cloze':
        from ph_practice_contracts import validate_cloze
        try:
            contract=validate_cloze(ac.get('cloze_contract'),q.get('question'),maximum)
        except (ValueError,TypeError,KeyError) as exc:
            raise QuestionContractError(str(exc)) from exc
        if contract['gap_count']<2 or mc.get('partial_credit') is not False:
            raise QuestionContractError('CLOZE_MARKING_POLICY_CONFLICT')
        return {'qtype':qt,'maximum_marks':maximum,'cloze_contract':contract}
    elif qt=='fill_blank':
""")
    text = replace(text, "    if qt in {'single_choice','true_false','multiple_select'}:\n", """    if qt in {'fill_blank','multi_gap_cloze'} and ac.get('cloze_contract') is not None:
        from ph_practice_contracts import validate_cloze, number
        try:
            cloze=validate_cloze(ac['cloze_contract'],q.get('question'),q.get('marks'))
            if number(q.get('marks'))!=number(maximum):
                raise ValueError('CLOZE_MARKS_CONFLICT')
            if qt=='fill_blank' and (cloze['gap_count']!=1 or ac.get('accepted_answers')!=cloze['gaps'][0]['accepted_answers']):
                raise ValueError('CLOZE_SINGLE_GAP_KEY_CONFLICT')
        except (ValueError,TypeError,KeyError) as exc:
            raise QuestionContractError(str(exc)) from exc
    if qt in {'single_choice','true_false','multiple_select'}:
""")
    text = replace(text, "prefix={'matching':'match::','ordering':'order::'}.get(qtype)", "prefix={'matching':'match::','ordering':'order::','multi_gap_cloze':'gap::'}.get(qtype)")
    changes[p] = text

    p = root/'scoremax_integration_v1.py'; text = p.read_text()
    text = replace(text, "      'ordering':'Ordering','constructed_response':'Constructed Response'", "      'ordering':'Ordering','constructed_response':'Constructed Response','multi_gap_cloze':'Multi Gap Cloze'")
    text = replace(text, "    kind=mc.get('key_type')\n", """    cloze=(marking.get('rubric') or {}).get('cloze_gap_contract')
    if cloze is not None:
        from ph_practice_contracts import validate_cloze
        cloze=validate_cloze(cloze,out.get('question'),out['marks'])
        ac={'options':[],'cloze_contract':cloze,'case_sensitive':False,'trim_spaces':True}
        mc.update(auto_markable=True,partial_credit=False,scoring_contract='all_gaps_exact')
        if cloze['gap_count']==1:
            ac['accepted_answers']=cloze['gaps'][0]['accepted_answers']
            out['answer']=cloze['gaps'][0]['canonical_answer'];out['qtype']='Fill Blank'
        else:
            out['answer']=canonical_json({g['id']:g['canonical_answer'] for g in cloze['gaps']})
            out['qtype']='Multi Gap Cloze'
    kind=mc.get('key_type')
""")
    text = replace(text, 'def _claim_due(c,limit=100,lease_seconds=60):', 'def _claim_due(c,limit=100,lease_seconds=60,outbox_ids=None):')
    text = replace(text, '    now=utcnow(); _begin_immediate(c)\n    # Crash recovery:', '''    scope=''; scope_args=()
    if outbox_ids is not None:
        if (not isinstance(outbox_ids,(list,tuple)) or not outbox_ids or len(outbox_ids)>100
                or any(isinstance(x,bool) or not isinstance(x,int) or x<=0 for x in outbox_ids)
                or len(set(outbox_ids))!=len(outbox_ids)):
            raise ValueError('INVALID_OUTBOX_SCOPE')
        scope=' AND id IN ('+','.join('?' for _ in outbox_ids)+')'
        scope_args=tuple(outbox_ids)
    now=utcnow(); _begin_immediate(c)
    # Crash recovery:''')
    text = replace(text, "claim_expires_at<=?\",(now,now))", "claim_expires_at<=?\"+scope,(now,now,*scope_args))")
    text = replace(text, "next_attempt_at<=?) ORDER BY contract_name\",(now,)).fetchall()]", "next_attempt_at<=?)\"+scope+\" ORDER BY contract_name\",(now,*scope_args)).fetchall()]")
    text = replace(text, "next_attempt_at<=?) ORDER BY created_at,id LIMIT ?\",(contract,now,int(limit))).fetchall())", "next_attempt_at<=?)\"+scope+\" ORDER BY created_at,id LIMIT ?\",(contract,now,*scope_args,int(limit))).fetchall())")
    text = replace(text, 'def dispatch_due(c,limit=100,timeout=8):\n    rows=_claim_due(c,limit=int(limit),lease_seconds=max(30,int(timeout)*4))', 'def dispatch_due(c,limit=100,timeout=8,*,outbox_ids=None):\n    rows=_claim_due(c,limit=int(limit),lease_seconds=max(30,int(timeout)*4),outbox_ids=outbox_ids)')
    changes[p] = text

    p = root/'guided_self_assessment.py'; text = p.read_text()
    text = replace(text, 'learner_payload=None, amendment_evidence=()):', 'learner_payload=None, amendment_evidence=(), source_workbook_sha256=None):')
    text = replace(text, "source.get('Learner_Output_Type') != 'TEXT_SHORT_RESPONSE'", "source.get('Learner_Output_Type') not in ('TEXT_SHORT_RESPONSE','TEXT')")
    text = replace(text, "evidence = str(source.get('Canonical_Accepted_Evidence') or '').split(' | ')\n    weights = str(source.get('Mark_Point_Values') or '').split(';')", "evidence_text = str(source.get('Canonical_Accepted_Evidence') or '')\n    evidence = evidence_text.split(' || ') if ' || ' in evidence_text else evidence_text.split(' | ')\n    import re\n    weights = re.split(r'[;|]',str(source.get('Mark_Point_Values') or ''))")
    text = replace(text, "'source_master_sha256': source.get('_PH_Original_Master_SHA256'),", "'source_master_sha256': source_workbook_sha256 or source.get('_PH_Original_Master_SHA256'),")
    changes[p] = text

    p = root/'app.py'; text = p.read_text()
    text = replace(text, "    if qt=='constructed_response':\n        from ux_constructed_auto_marker import mark\n", """    if qt=='multi_gap_cloze':
        from ph_practice_contracts import score_gaps
        try:
            if text:
                ok,checks=score_gaps(validated['cloze_contract'],text)
                earned=correct_max if ok else incorrect
            else:
                ok=False;checks={g['id']:False for g in validated['cloze_contract']['gaps']};earned=unanswered
        except (ValueError,TypeError,KeyError) as exc:
            raise question_contracts.QuestionContractError(str(exc)) from exc
        return {'is_correct':ok,'marks_awarded':earned,'maximum_marks':correct_max,'confirmed':True,
                'evidence_eligible':True,'status':'MARK_CONFIRMED','response_type':qt,'gap_results':checks,
                'result_contract_version':'SM-MARK-RESULT-2','marker_version':'source-gap-exact-v1','misconception':''}
    if qt=='constructed_response':
        from ux_constructed_auto_marker import mark
""")
    text = replace(text, "        saved_struct=safe_json(saved_current,{} if qtype=='matching' else []) if qtype in {'matching','ordering'} else {}", "        saved_struct=safe_json(saved_current,{} if qtype in {'matching','multi_gap_cloze'} else []) if qtype in {'matching','ordering','multi_gap_cloze'} else {}")
    text = replace(text, "LIVE_MARKABLE_TYPES.update({'constructed_response','short_response','extended_response'})", "LIVE_MARKABLE_TYPES.update({'constructed_response','short_response','extended_response','multi_gap_cloze'})")
    text = replace(text, "'fill_blank':'Fill in the blank','numerical':'Numerical','matching':'Matching',", "'fill_blank':'Fill in the blank','multi_gap_cloze':'Multiple blanks','numerical':'Numerical','matching':'Matching',")
    changes[p] = text

    p = root/'templates/_learner_question_surface.html'; text = p.read_text()
    text = replace(text, "{% elif qtype=='fill_blank' %}", """{% elif qtype=='multi_gap_cloze' %}
  <p class="muted">Answer each blank in its order in the question.</p>
  {% for gap in answer_cfg.get('cloze_contract',{}).get('gaps',[]) %}
  <label>Blank {{ loop.index }}<input name="gap::{{ gap.id }}" value="{{ saved_struct.get(gap.id,'') }}" autocomplete="off" maxlength="1000" aria-label="Blank {{ loop.index }}"></label>
  {% endfor %}
{% elif qtype=='fill_blank' %}""")
    changes[p] = text
    for p,text in changes.items():
        if p.suffix=='.py': compile(text,str(p),'exec')
    # Write only after every exact source anchor and Python compilation passed.
    for p,text in changes.items(): p.write_text(text,encoding='utf8')
    (root/'ph_practice_contracts.py').write_bytes(Path(__file__).with_name('ph_practice_contracts.py').read_bytes())
    return {'contract':MARKER,'changed_files':[p.relative_to(root).as_posix() for p in changes],
            'new_files':['ph_practice_contracts.py'],'learner_activation':False,'schema_changes':False}
