"""Build-only correction over the exact accepted, assembled ScoreMax runtime."""
import ast
import hashlib
from pathlib import Path

BEFORE_APP = 'ed939e2e53fcbecc36454d253ee38cf84c0e428497b52c8f6ca6c99563818a9d'
AFTER_APP = '88ff6087c5a270df327a6dbb61489a1d3a8d535400209d0917debf3a4aaadaee'
HELPER_SHA256 = '16251873c3e0b596aaed3652fd71209ab85eaaf1f03acc220b12502713ec6a7f'


def _once(source, before, after):
    if source.count(before) != 1:
        raise RuntimeError('PH_MASTERY_BOUNDARY_SOURCE_DRIFT: ' + before[:100])
    return source.replace(before, after, 1)


def derive(source):
    """Change only the common formal selectors and their final evidence fences."""
    if hashlib.sha256(source.encode()).hexdigest() != BEFORE_APP:
        raise RuntimeError('PH_MASTERY_BOUNDARY_ACCEPTED_APP_REQUIRED')
    tree = ast.parse(source)
    changes = {}
    expected = {'build_mastery_form', 'chapter_mastery_opportunity',
                'select_mastery_coverage_questions', 'attach_mastery_coverage',
                'process_mastery_result'}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in expected:
            continue
        old = ast.get_source_segment(source, node)
        new = old
        if node.name == 'build_mastery_form':
            new = _once(new,
                "    rows=[r for r in all_rows if canonical_question_type(r) in LIVE_MARKABLE_TYPES",
                "    from ph_mastery_evidence import eligible_for_formal_mastery\n"
                "    rows=[r for r in all_rows if eligible_for_formal_mastery(r) and canonical_question_type(r) in LIVE_MARKABLE_TYPES")
        elif node.name == 'chapter_mastery_opportunity':
            new = _once(new,
                "    markable=[r for r in all_rows if canonical_question_type(r) in LIVE_MARKABLE_TYPES]",
                "    from ph_mastery_evidence import eligible_for_formal_mastery\n"
                "    markable=[r for r in all_rows if eligible_for_formal_mastery(r) and canonical_question_type(r) in LIVE_MARKABLE_TYPES]")
        elif node.name == 'select_mastery_coverage_questions':
            new = _once(new, '    import math\n',
                '    import math\n'
                '    from ph_mastery_evidence import eligible_for_formal_mastery\n'
                '    pool=[q for q in pool if eligible_for_formal_mastery(q)]\n')
        elif node.name == 'attach_mastery_coverage':
            new = _once(new, "    if meta.get('mastery_demo_only'):return chosen,meta\n",
                "    if meta.get('mastery_demo_only'):return chosen,meta\n"
                "    from ph_mastery_evidence import eligible_for_formal_mastery\n"
                "    if not all(eligible_for_formal_mastery(q) for q in chosen):\n"
                "        raise ValueError('The mastery form contains practice-only or dependent Power House evidence.')\n")
        elif node.name == 'process_mastery_result':
            new = _once(new, "    demo_only=1 if meta.get('mastery_demo_only') else 0\n",
                "    demo_only=1 if meta.get('mastery_demo_only') else 0\n"
                "    from ph_mastery_evidence import question_ids_have_formal_evidence\n"
                "    independent_evidence_ok=bool(demo_only or question_ids_have_formal_evidence(c,question_ids))\n")
            new = _once(new, '    passed=bool(policy and score is not None',
                '    passed=bool(independent_evidence_ok and policy and score is not None')
            new = _once(new, '    if demo_only or not policy: return\n',
                '    if demo_only or not policy or not independent_evidence_ok: return\n')
        if new != old:
            changes[node.name] = (old, new)
    if set(changes) != expected:
        raise RuntimeError('PH_MASTERY_BOUNDARY_FUNCTION_SET_DRIFT')
    for old, new in changes.values():
        source = _once(source, old, new)
    compile(source, 'scoremax_runtime_v669b/app.py', 'exec')
    return source


def apply(root):
    root = Path(root)
    app = root / 'app.py'
    target = root / 'ph_mastery_evidence.py'
    helper = Path(__file__).with_name('ph_mastery_evidence.py').read_bytes()
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA256:
        raise RuntimeError('PH_MASTERY_BOUNDARY_HELPER_MISMATCH')
    current = app.read_bytes()
    if hashlib.sha256(current).hexdigest() == AFTER_APP:
        if not target.is_file() or target.read_bytes() != helper:
            raise RuntimeError('PH_MASTERY_BOUNDARY_PARTIAL_BUILD')
        return {'policy': 'SM-PH-FORMAL-INDEPENDENT-EVIDENCE-1', 'replayed': True}
    if target.exists():
        raise RuntimeError('PH_MASTERY_BOUNDARY_PARTIAL_BUILD')
    derived = derive(current.decode())
    if hashlib.sha256(derived.encode()).hexdigest() != AFTER_APP:
        raise RuntimeError('PH_MASTERY_BOUNDARY_DERIVED_APP_MISMATCH')
    compile(helper, str(target), 'exec')
    app.write_text(derived, encoding='utf8', newline='\n')
    target.write_bytes(helper)
    return {'policy': 'SM-PH-FORMAL-INDEPENDENT-EVIDENCE-1', 'replayed': False,
            'changed_files': ['app.py'], 'new_files': ['ph_mastery_evidence.py'],
            'database_changes': False, 'academic_authority_conferred': False,
            'learner_activation': False}
