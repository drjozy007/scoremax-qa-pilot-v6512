"""Build-time extension over the exact accepted ScoreMax receiver runtime."""
from pathlib import Path
import hashlib
import json

BASE_TREE = '81bc459edce19b54b701e6be2d1068b08336ceb63933ea5b40eda7e6c2e6d522'
AFTER_TREE = '056c8707eb48abccf12f66ddba799678c490e617c194f42910f44283e1d390ab'
HELPER_SHA256 = '3dc6f2bdf9a4a2f98f0da03175d724821768a96279540bacbf9ffa0f8ff17524'


def _once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('SCORED_SAQ_BUILD_SOURCE_DRIFT:' + old[:100])
    return text.replace(old, new, 1)


def tree(root):
    rows = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def apply(root):
    root = Path(root)
    if tree(root) == AFTER_TREE:
        return {'policy':'SM-SCORED-SAQ-BOUNDARY-1','replayed':True,
                'after_tree_sha256':AFTER_TREE,'official_ai_scoring_enabled':False,
                'database_tables_added':0,'production_mutated':False}
    if tree(root) != BASE_TREE:
        raise ValueError('SCORED_SAQ_ACCEPTED_RUNTIME_REQUIRED')
    changes = {}
    p = root / 'ux_constructed_auto_marker.py'; text = p.read_text()
    text = _once(text, "        rubric = mc.get('rubric')\n", """        rubric = mc.get('rubric')
        if isinstance(rubric,dict) and 'assessment_eligibility' in rubric:
            from scored_saq_runtime_v1 import parts, compile_scored_contract
            source_rubric, eligibility = parts(mc)
            return compile_scored_contract({'scoring_contract':source_rubric,
                'assessment_eligibility':eligibility}, marks, stem, fallback_answer)
""")
    text = _once(text, "    unsigned = dict(contract); expected_hash = unsigned.pop('contract_sha256', None)\n", """    if contract.get('version') == 'SM-SCORED-SAQ-MARKER-1':
        from scored_saq_runtime_v1 import mark_scored_contract
        return mark_scored_contract(contract,response)
    unsigned = dict(contract); expected_hash = unsigned.pop('contract_sha256', None)
""")
    changes[p] = text
    p = root / 'question_contract_engine.py'; text = p.read_text()
    old = "    if qt=='constructed_response':\n        from ux_constructed_auto_marker import compile_contract\n"
    text = _once(text, old, """    if qt=='constructed_response':
        from scored_saq_runtime_v1 import capability
        try:
            scored = capability(q)
        except (ValueError,TypeError,KeyError) as exc:
            raise QuestionContractError(str(exc)) from exc
        if scored is not None:
            if not scored['marking_qualified']:
                raise QuestionContractError('SCORED_MARKING_CAPABILITY_PENDING_ACCEPTANCE')
            return {'qtype':qt,'maximum_marks':maximum,
                    'constructed_contract':scored['contract'],
                    'assessment_eligibility':scored['eligibility']}
        from ux_constructed_auto_marker import compile_contract
""")
    changes[p] = text
    p = root / 'ph_mastery_evidence.py'; text = p.read_text()
    old = "    role = str(q.get('ph_evidence_role') or '').strip().upper()\n"
    text = _once(text, old, """    # New scored SAQs must carry exact approval, source, rubric and version
    # binding; the original independent role/weight fence still runs below.
    try:
        from scored_saq_runtime_v1 import capability, parts
        if parts(q.get('marking_config') or {}) is not None:
            decision = capability(q)
            if not decision or not decision['marking_qualified']:
                return False
    except (ValueError,TypeError,KeyError):
        return False
    role = str(q.get('ph_evidence_role') or '').strip().upper()
""")
    changes[p] = text
    p = root / 'scoremax_integration_v1.py'; text = p.read_text()
    text = _once(text, '    valid_cloze = set()\n', '    valid_cloze = set()\n    valid_scored = set()\n')
    old = '        rubric = marking.get("rubric") or {}\n'
    text = _once(text, old, old + """        if isinstance(rubric,dict) and 'assessment_eligibility' in rubric:
            try:
                projection = _projection(question,lookup)
                decision = question_contracts.validate_assessment_contract(projection)
                if decision.get('assessment_eligibility'):
                    valid_scored.add(index)
            except (question_contracts.QuestionContractError,KeyError,TypeError,ValueError):
                pass
""")
    text = _once(text, '            for index in valid\n', '            for index in valid | valid_scored\n')
    text = _once(text, '            for index in valid | valid_cloze\n',
                 '            for index in valid | valid_cloze | valid_scored\n')
    changes[p] = text
    helper = Path(__file__).with_name('scored_saq_runtime_v1.py').read_bytes()
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA256:
        raise ValueError('SCORED_SAQ_CANDIDATE_HELPER_MISMATCH')
    for path, source in changes.items():
        compile(source, str(path), 'exec')
    compile(helper, 'scored_saq_runtime_v1.py', 'exec')
    # Verify every source anchor before creating the candidate runtime bytes.
    for path, source in changes.items():
        path.write_text(source, encoding='utf8', newline='\n')
    (root / 'scored_saq_runtime_v1.py').write_bytes(helper)
    if tree(root) != AFTER_TREE:
        raise ValueError('SCORED_SAQ_DERIVED_RUNTIME_MISMATCH')
    return {'policy':'SM-SCORED-SAQ-BOUNDARY-1', 'before_tree_sha256':BASE_TREE,
            'after_tree_sha256':tree(root),'official_ai_scoring_enabled':False,
            'database_tables_added':0,'production_mutated':False}
