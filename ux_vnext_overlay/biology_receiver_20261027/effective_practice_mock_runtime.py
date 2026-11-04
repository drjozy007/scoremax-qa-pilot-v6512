"""Apply the signed effective-practice exclusion to ScoreMax's official pools."""
import ast
import hashlib

BEFORE_APP = '88ff6087c5a270df327a6dbb61489a1d3a8d535400209d0917debf3a4aaadaee'


def derive(source):
    if hashlib.sha256(source.encode()).hexdigest() != BEFORE_APP:
        raise RuntimeError('SM_EFFECTIVE_PRACTICE_MOCK_BASE_MISMATCH')
    functions = {node.name: ast.get_source_segment(source, node)
                 for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    pool = functions['blueprint_question_pool']
    practice = functions['assemble_blueprint_practice']
    header = 'def blueprint_question_pool(c, blueprint, subject, student_id=None):'
    fence = '    if student_id:\n'
    practice_arg = 'student_id=student_id)'
    if pool.count(header) != 1 or pool.count(fence) != 1 or practice.count(practice_arg) != 2:
        raise RuntimeError('SM_EFFECTIVE_PRACTICE_MOCK_SOURCE_DRIFT')
    new_header = 'def blueprint_question_pool(c, blueprint, subject, student_id=None, *, official=True):'
    new_pool = pool.replace(header, new_header, 1).replace(
        fence,
        "    if official:\n"
        "        def practice_only(row):\n"
        "            provenance = safe_json(dict(row).get('ph_provenance_snapshot_json'), {})\n"
        "            lineage = provenance.get('lineage') if isinstance(provenance, dict) else None\n"
        "            return isinstance(lineage, dict) and 'effective_practice_projection' in lineage\n"
        "        rows = [row for row in rows if not practice_only(row)]\n"
        + fence, 1)
    new_practice = practice.replace(practice_arg, 'student_id=student_id, official=False)')
    result = source.replace(pool, new_pool, 1).replace(practice, new_practice, 1)
    compile(result, 'scoremax_runtime_v669b/app.py', 'exec')
    return result


def apply(root):
    path = root / 'app.py'
    path.write_text(derive(path.read_text(encoding='utf8')), encoding='utf8', newline='\n')
