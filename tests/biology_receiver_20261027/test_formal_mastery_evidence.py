"""Targeted formal-mastery boundary checks; no app startup or production writes.

PH_MASTERY_SOURCE_FIXTURES may point to the private native architecture export.
The committed cases carry only anonymised architecture, with no source questions,
answer keys, production identities, receipts, or learner data.
"""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT/'scoremax_runtime_v669b'
OVERLAY = ROOT/'ux_vnext_overlay/biology_receiver_20261027'
sys.path.insert(0, str(OVERLAY))
sys.path.insert(0, str(RUNTIME))
import ph_mastery_evidence as evidence
import mastery_evidence_boundary_runtime as installer
from blueprint_engine import normalize_difficulty

FIXTURES = json.loads(Path(os.environ.get('PH_MASTERY_SOURCE_FIXTURES',
    str(Path(__file__).with_name('formal_mastery_source_architecture.json')))).read_text())
POLICIES = {
    'Foundation': (70, 10, 1, .2, .5, .5),
    'Exam Ready': (80, 20, 1, .25, .5, .7),
    'Advanced': (88, 15, 2, .3, .6, .8),
    'Distinction': (94, 20, 2, .35, .65, .9),
    'Expert': (95, 25, 2, .4, .7, .95),
    'Elite': (97, 20, 3, .45, .75, 1),
}


def policy(level='Foundation'):
    accuracy, count, forms, band, unseen, breadth = POLICIES[level]
    return dict(mastery_level=level, min_accuracy=accuracy, min_questions=count,
                min_forms=forms, target_band_pct=band, unseen_family_pct=unseen,
                min_breadth_pct=breadth, verification_days=90)


def legacy(key):
    return dict(id=key, level='Foundation', difficulty='Moderate',
        family_id='UNIT-LEGACY-'+str(key), is_demo=0, chapter='Unit fixture',
        programme='FSc Part 1', subject='Biology', qtype='True/False',
        source_type='UNIT TEST NATIVE', ph_question_id='', ph_question_version_id='',
        ph_question_checksum_sha256='', ph_release_id='', ph_projection_owner='',
        ph_dependency_type='', ph_evidence_role='', ph_independent_mastery_weight=0,
        ph_knowledge_node_ids_json='["UNIT_ONLY::NODE_1"]')


def independent(key):
    q=legacy(key)
    q.update(ph_question_id='UNIT-PH-'+str(key), ph_projection_owner='POWER_HOUSE',
             ph_evidence_role='INDEPENDENT', ph_dependency_type='NONE',
             ph_independent_mastery_weight=1)
    return q


def connection(rows):
    # Isolated test placement only; original source/version records are not edited.
    rows=deepcopy(rows)
    for q in rows:
        q.update(chapter='Unit fixture',subject='Biology',programme='FSc Part 1')
        q.setdefault('is_demo',0)
    columns=sorted({k for q in rows for k in q}|{'calibration_status'})
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    definitions=[k+(' INTEGER PRIMARY KEY' if k=='id' else '') for k in columns]
    c.execute('CREATE TABLE questions('+','.join(definitions)+')')
    for q in rows:
        c.execute('INSERT INTO questions('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                  [q.get(k) for k in columns])
    c.execute('''CREATE TABLE mastery_form_results(student_id,assessment_session_id,attempt_id,
        scope_type,scope_key,programme,subject,chapter,target_level,score,question_count,
        passed,demo_only,breadth_ok,unseen_family_ratio,family_ids_json,policy_snapshot_json,
        assembly_policy_id,assembly_policy_version,effective_policy_json)''')
    return c


def functions():
    source=(RUNTIME/'app.py').read_text();tree=ast.parse(source)
    names={'select_mastery_coverage_questions','question_coverage_nodes',
        'mastery_evidence_band_levels','safe_json','build_mastery_form',
        'attach_mastery_coverage','process_mastery_result'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==names
    env=dict(json=json,random=random,hashlib=hashlib,normalize_difficulty=normalize_difficulty,
        MASTER_LEVELS=list(POLICIES), LIVE_MARKABLE_TYPES={'true_false'},
        mastery_rank=lambda value:list(POLICIES).index(value),
        mastery_scope_ceiling=lambda scope:'Elite', access_allows_level=lambda *args:True,
        mastery_policy=lambda c,level:policy(level), canonical_programme=lambda p:p,
        student_programme=lambda *args:'FSc Part 1', active_assessment_blueprint=lambda *args:None,
        active_assembly_policy=lambda *args,**kwargs:None,
        effective_mastery_requirements=lambda base,assembly:dict(base),
        live_question_clause=lambda alias:'1=1', _programme_aliases=lambda p:[p],
        _programme_scope_sql=lambda *args:('1=1',[]),
        canonical_question_type=lambda row:'true_false',
        _mastery_previous_families=lambda *args:set(),mastery_scope_key=lambda *args:'UNIT-SCOPE',
        policy_score=lambda score:50,
        integration_v1=type('Canonical',(),{'canonical_json':staticmethod(
            lambda value:json.dumps(value,sort_keys=True,separators=(',',':')))})())
    def absent_coverage(*args):raise ValueError('UNIT_TEST_NO_CURRICULUM_AUTHORITY')
    env['mastery_coverage_contract']=absent_coverage
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<assembled-formal-functions>','exec'),env)
    return env


class FormalMasteryEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.env=functions()

    def test_six_source_derived_biology_practice_architectures_are_excluded(self):
        self.assertEqual(len(FIXTURES),6)
        self.assertEqual({q['fixture_chapter_number'] for q in FIXTURES},{3,8,11})
        for q in FIXTURES:
            with self.subTest(chapter=q['fixture_chapter_number']):
                self.assertEqual(float(q['ph_independent_mastery_weight']),0)
                self.assertFalse(evidence.eligible_for_formal_mastery(q))

    def test_positive_independent_evidence_does_not_need_optional_node_ids_here(self):
        q=independent(1);q['ph_knowledge_node_ids_json']='[]'
        self.assertTrue(evidence.eligible_for_formal_mastery(q))

    def test_native_legacy_default_zero_columns_retain_existing_eligibility(self):
        self.assertTrue(evidence.eligible_for_formal_mastery(legacy(1)))
        self.assertTrue(evidence.eligible_for_formal_mastery({'id':1}))

    def test_source_only_recovery_dependent_and_unknown_roles_never_gain_credit(self):
        for role in ['DEPENDENT','SOURCE_ONLY','RECOVERY','SUPPORTING','INCIDENTAL','',None]:
            q=independent(1);q['ph_evidence_role']=role
            self.assertFalse(evidence.eligible_for_formal_mastery(q),role)

    def test_dependency_types_override_inconsistent_positive_weight(self):
        for dep in evidence.DEPENDENT_TYPES:
            q=independent(1);q['ph_dependency_type']=dep
            self.assertFalse(evidence.eligible_for_formal_mastery(q),dep)

    def test_missing_zero_negative_nonfinite_and_boolean_weights_are_rejected(self):
        for value in [None,'',0,-1,'NaN',float('nan'),float('inf'),'-inf',True,False,'bad']:
            q=independent(1);q['ph_independent_mastery_weight']=value
            self.assertFalse(evidence.eligible_for_formal_mastery(q),repr(value))

    def test_positive_numeric_protocol_weights_are_supported(self):
        for value in [1,1.0,'1',.5]:
            q=independent(1);q['ph_independent_mastery_weight']=value
            self.assertTrue(evidence.eligible_for_formal_mastery(q))

    def test_partial_ph_projection_cannot_masquerade_as_legacy(self):
        for marker in ['ph_question_id','ph_question_version_id','ph_release_id','ph_projection_owner']:
            q=legacy(1);q[marker]='POWER_HOUSE' if marker=='ph_projection_owner' else 'opaque::test'
            self.assertFalse(evidence.eligible_for_formal_mastery(q))

    def test_opaque_external_ids_do_not_determine_weight_or_eligibility(self):
        for identity in ['source::000','Q-1','1','non-numeric::opaque']:
            q=independent(1);q['ph_question_id']=identity
            self.assertTrue(evidence.eligible_for_formal_mastery(q))
            q['ph_independent_mastery_weight']=0
            self.assertFalse(evidence.eligible_for_formal_mastery(q))

    def test_real_practice_cannot_enter_any_formal_target_band(self):
        for target in POLICIES:
            with self.subTest(target=target),self.assertRaises(ValueError):
                self.env['select_mastery_coverage_questions'](FIXTURES,1,target,0,0,set(),
                    {'required_node_ids':[],'mandatory_node_ids':[],'min_breadth_pct':0},50)

    def test_practice_cannot_fill_independent_form_shortfall(self):
        with self.assertRaises(ValueError):
            self.env['select_mastery_coverage_questions']([legacy(1)]+FIXTURES,2,'Foundation',0,0,set(),
                {'required_node_ids':['UNIT_ONLY::NODE_1'],'mandatory_node_ids':['UNIT_ONLY::NODE_1'],'min_breadth_pct':1},50)

    def test_mixed_selector_keeps_independent_and_legacy_controls(self):
        selected=self.env['select_mastery_coverage_questions']([legacy(1),independent(2)]+FIXTURES,
            2,'Foundation',1,1,set(),{'required_node_ids':['UNIT_ONLY::NODE_1'],
            'mandatory_node_ids':['UNIT_ONLY::NODE_1'],'min_breadth_pct':1},50)
        self.assertEqual({q['id'] for q in selected},{1,2})

    def test_zero_weight_pool_is_removed_before_production_depth_check(self):
        rows=[dict(q,level='Foundation') for q in FIXTURES]+[legacy(100+i) for i in range(4)]
        c=connection(rows)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM questions WHERE subject='Biology' AND chapter='Unit fixture' AND level='Foundation'").fetchone()[0],10)
        with self.assertRaisesRegex(ValueError,'not deep enough'):
            self.env['build_mastery_form'](c,1,'chapter','Foundation','FSc Part 1','Biology','Unit fixture')
        c.close()

    def test_final_coverage_fence_rejects_a_practice_row_before_coverage(self):
        with self.assertRaisesRegex(ValueError,'practice-only or dependent'):
            self.env['attach_mastery_coverage'](None,[FIXTURES[0]],{'mastery_demo_only':False})

    def test_existing_coverage_gate_remains_closed_for_otherwise_eligible_rows(self):
        with self.assertRaisesRegex(ValueError,'NO_CURRICULUM_AUTHORITY'):
            self.env['attach_mastery_coverage'](None,[independent(1)],
                {'mastery_demo_only':False,'programme':'FSc Part 1','subject':'Biology',
                 'chapters':'Unit fixture','mastery_scope_type':'chapter'})

    def test_completed_form_lookup_rejects_duplicates_missing_keys_and_zero_weight(self):
        c=connection([legacy(1),independent(2),dict(FIXTURES[0],id=-1)])
        self.assertTrue(evidence.question_ids_have_formal_evidence(c,[1,2]))
        for ids in [[],[1,1],[1,999],[-1],[True],[None],['not-an-internal-key']]:
            self.assertFalse(evidence.question_ids_have_formal_evidence(c,ids))
        c.close()

    def test_inflight_practice_forms_never_record_a_formal_pass_at_any_level(self):
        for level in POLICIES:
            count=policy(level)['min_questions'];rows=[legacy(100+i) for i in range(count-1)]+[dict(FIXTURES[0],id=-1)]
            c=connection(rows);self._process(c,rows,level)
            result=c.execute('SELECT score,passed FROM mastery_form_results').fetchone()
            self.assertEqual(result['score'],100);self.assertEqual(result['passed'],0);c.close()

    def test_inflight_native_scoring_is_preserved(self):
        rows=[legacy(100+i) for i in range(10)];c=connection(rows);self._process(c,rows,'Foundation')
        result=c.execute('SELECT score,passed FROM mastery_form_results').fetchone()
        self.assertEqual(tuple(result),(100,1));c.close()

    def _process(self,c,rows,level):
        frozen={'UNIT_TEST_ONLY':True};frozen['checksum_sha256']=hashlib.sha256(
            json.dumps(frozen,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        meta=dict(assessment_kind='mastery',mastery_demo_only=False,mastery_target_level=level,
            mastery_effective_policy=policy(level),mastery_scope_type='chapter',mastery_scope_key='UNIT-SCOPE',
            mastery_coverage_snapshot=frozen,mastery_mandatory_covered=True,mastery_breadth_ratio=1,
            mastery_target_band_ratio=1,mastery_unseen_family_ratio=1,mastery_breadth_ok=True)
        self.env['process_mastery_result'](c,{'id':1,'student_id':1,'meta_json':json.dumps(meta)},
                                           1,100,[q['id'] for q in rows])

    def test_effective_practice_stays_out_of_official_mock_and_readiness_pools(self):
        source=(RUNTIME/'app.py').read_text()
        pool=next(node for node in ast.parse(source).body
                  if isinstance(node,ast.FunctionDef) and node.name=='blueprint_question_pool')
        namespace={'_powerhouse_blueprint_payload':lambda value:value,
                   'live_question_clause':lambda alias:'1=1',
                   'canonical_question_type':lambda row:'TRUE_FALSE',
                   'LIVE_MARKABLE_TYPES':{'TRUE_FALSE'},
                   'safe_json':lambda value,default:json.loads(value) if value else default}
        exec(compile(ast.Module(body=[pool],type_ignores=[]),'<mock-pool>','exec'),namespace)
        conn=sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory=sqlite3.Row
        conn.execute("""CREATE TABLE questions(id,subject,ph_projection_owner,ph_market_id,
            ph_programme_id,ph_subject_id,scoremax_ready,rights_status,calibration_status,
            response_count,ph_provenance_snapshot_json)""")
        legacy='{"lineage":{"original_question_id":"existing"}}'
        practice='{"lineage":{"effective_practice_projection":{"official_mock_eligible":false}}}'
        conn.executemany("""INSERT INTO questions VALUES
            (?, 'Biology','POWER_HOUSE','market','programme','subject',1,'owned',NULL,0,?)""",
            [(1,legacy),(2,practice)])
        blueprint={'market_id':'market','programme_id':'programme','subject_id':'subject'}
        select=namespace['blueprint_question_pool']
        self.assertEqual([row['id'] for row in select(conn,blueprint,'subject')],[1])
        self.assertEqual([row['id'] for row in select(conn,blueprint,'subject',official=False)],[1,2])

    @unittest.skipUnless(os.environ.get('PH_MASTERY_ACCEPTED_APP'),'Accepted build source is supplied for the native preflight')
    def test_installer_is_exact_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);before=Path(os.environ['PH_MASTERY_ACCEPTED_APP']).read_bytes()
            (root/'app.py').write_bytes(before)
            self.assertFalse(installer.apply(root)['replayed']);self.assertTrue(installer.apply(root)['replayed'])
            self.assertEqual(hashlib.sha256((root/'app.py').read_bytes()).hexdigest(),installer.AFTER_APP)

    @unittest.skipUnless(os.environ.get('PH_MASTERY_ACCEPTED_APP'),'Accepted build source is supplied for the native preflight')
    def test_installer_refuses_source_drift_and_partial_helper(self):
        before=Path(os.environ['PH_MASTERY_ACCEPTED_APP']).read_bytes()
        for altered,helper in [(before+b'\n',False),(before,True)]:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);(root/'app.py').write_bytes(altered)
                if helper:(root/'ph_mastery_evidence.py').write_text('partial')
                with self.assertRaises(RuntimeError):installer.apply(root)
                self.assertEqual((root/'app.py').read_bytes(),altered)

    @unittest.skipUnless(os.environ.get('PH_MASTERY_ACCEPTED_APP'),'Accepted build source is supplied for the native preflight')
    def test_only_formal_and_mock_pool_functions_changed_in_the_existing_app(self):
        before=Path(os.environ['PH_MASTERY_ACCEPTED_APP']).read_text();after=(RUNTIME/'app.py').read_text()
        def source_map(s):
            lines=s.splitlines(keepends=True)
            return {n.name:''.join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
        a=source_map(before);b=source_map(after);self.assertEqual(set(a),set(b))
        self.assertEqual({k for k in a if a[k]!=b[k]},
            {'build_mastery_form','chapter_mastery_opportunity','select_mastery_coverage_questions',
             'attach_mastery_coverage','process_mastery_result','blueprint_question_pool','assemble_blueprint_practice'})


if __name__=='__main__':unittest.main()
