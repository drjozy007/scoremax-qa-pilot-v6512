"""Pure resolver equivalence plus native live-membership checks; disposable only."""
import ast
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
PATCH_FILE = REPO / 'ux_vnext_overlay/biology_receiver_20261027/programme_resolution_cache_20261121.py'
spec = importlib.util.spec_from_file_location('programme_cache_candidate', PATCH_FILE)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)
NAMES = {'_programme_alias_groups', 'canonical_programme', 'programme_from_curriculum', 'programme_for_release'}


def resolver_namespace():
    donor = REPO / 'ux_vnext_overlay/assessment_question_contracts_v2.py'
    source = donor.read_text(encoding='utf8')
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
    assert {n.name for n in nodes} == NAMES
    class QuestionContractError(ValueError):
        pass
    ns = {'json': json, 're': re, 'QuestionContractError': QuestionContractError}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(donor), 'exec'), ns)
    original = ns['programme_for_release']
    exec(compile(patch.RUNTIME_PATCH, str(PATCH_FILE), 'exec'), ns)
    return original, ns['programme_for_release'], ns


class ProgrammeResolutionCacheTests(unittest.TestCase):
    def setUp(self):
        self.original, self.resolve, self.namespace = resolver_namespace()

    def test_differential_source_and_conflict_cases(self):
        sources = [None, '', '{}', '[]', 'null', '{bad', 17, {}, [],
                   json.dumps({'programme_id': 'FSC', 'grade_year_id': '11'}),
                   json.dumps({'programme_id': 'FSC', 'grade_year_id': '12'}),
                   json.dumps({'programme_id': 'MDCAT'}),
                   json.dumps({'programme_id': 'opaque::α/β', 'qualification_id': 'FSc', 'grade_year_id': '11'}),
                   json.dumps({'programme_id': 'FSc Part 1', 'grade_year_id': '12'}),
                   json.dumps({'programme_id': 'FSc Part 1', 'display': {'programme': 'MDCAT'}}),
                   json.dumps({'programme_id': 'FSC', 'grade_year_id': '11', 'display': {'grade_year': '12'}})]
        releases = [None, '', 'FSC', 'FSC_PART_I', 'FSc Part II', 'MDCAT', 'ECAT', 'opaque::α/β', {}, 17]
        for release in releases:
            for source in sources:
                with self.subTest(release=release, source=source):
                    self.assertEqual(self.resolve(release, source), self.original(release, source))

    def test_exact_inputs_reused_and_changed_source_rechecked(self):
        good = json.dumps({'programme_id': 'FSC', 'grade_year_id': '11'})
        changed = json.dumps({'programme_id': 'FSC', 'grade_year_id': '12'})
        for _ in range(300):
            self.assertEqual(self.resolve('FSc Part 1', good), 'FSc Part 1')
        self.assertEqual(self.resolve.cache_info().misses, 1)
        self.assertEqual(self.resolve.cache_info().hits, 299)
        self.assertEqual(self.resolve('FSc Part 1', changed), '')
        self.assertEqual(self.resolve.cache_info().misses, 2)

    def test_cache_is_bounded(self):
        for i in range(1500):
            source = json.dumps({'programme_id': 'FSC', 'grade_year_id': '11', 'opaque': str(i)})
            self.assertEqual(self.resolve('FSc Part 1', source), 'FSc Part 1')
        self.assertEqual(self.resolve.cache_info().currsize, 128)
        self.assertEqual(self.resolve.cache_info().maxsize, 128)

    def test_large_and_non_string_inputs_bypass_retention(self):
        for release, source in [('FSC', {'grade_year_id': '11'}), ('FSC', []),
                                ('x' * 257, '{}'), ('FSC', ' ' * 4097), (None, None)]:
            self.assertEqual(self.resolve(release, source), self.original(release, source))
        self.assertEqual(self.resolve.cache_info().currsize, 0)

    def test_concurrent_reuse_has_identical_results(self):
        source = json.dumps({'programme_id': 'FSC', 'grade_year_id': '11'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(lambda _: self.resolve('FSc Part 1', source), range(1500)))
        self.assertEqual(set(result), {'FSc Part 1'})
        self.assertEqual(self.resolve.cache_info().currsize, 1)

    def test_unknown_build_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'question_contract_engine.py'
            target.write_text('def programme_for_release(a,b): return "unsafe"\n')
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'):
                patch.apply(directory)
            self.assertEqual(target.read_bytes(), before)

    @unittest.skipUnless((REPO / 'scoremax_runtime_v669b/app.py').exists(), 'assembled native runtime required in CI')
    def test_assembled_runtime_hash_and_live_membership_invalidation(self):
        runtime = REPO / 'scoremax_runtime_v669b'
        self.assertEqual(hashlib.sha256((runtime / 'question_contract_engine.py').read_bytes()).hexdigest(), patch.AFTER_SHA256)
        source = (runtime / 'app.py').read_text(encoding='utf8')
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_programme_scope_sql')
        ns = {'re': re}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'native-scope', 'exec'), ns)
        clause, params = ns['_programme_scope_sql'](['FSc Part 1'])
        c = sqlite3.connect(':memory:')
        c.create_function('scoremax_release_programme', 2, self.resolve, deterministic=True)
        c.executescript('''
          CREATE TABLE questions(id INTEGER,ph_projection_owner,programme,qualification,ph_question_id,ph_question_version_id,ph_question_checksum_sha256);
          CREATE TABLE integration_ph_question_version_store(question_id,question_version_id,local_question_db_id,question_checksum_sha256,curriculum_json);
          CREATE TABLE integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id);
          CREATE TABLE integration_ph_content_releases(release_id,release_version,package_checksum_sha256,programme_id,local_status);
          CREATE TABLE integration_ph_product_activation_authorizations(release_id,release_version,package_checksum_sha256,activation_status);
          CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id,release_version,question_id,question_version_id);
          INSERT INTO questions VALUES(1,'POWER_HOUSE','FSc Part 1','','opaque::question','opaque::version','question-sha');
          INSERT INTO integration_ph_release_question_membership VALUES('release','1','opaque::question','opaque::version');
          INSERT INTO integration_ph_content_releases VALUES('release','1','package-sha','FSc Part 1','ACTIVE');
          INSERT INTO integration_ph_product_activation_authorizations VALUES('release','1','package-sha','ACTIVATED');
        ''')
        good = json.dumps({'programme_id': 'FSC', 'grade_year_id': '11'})
        c.execute('INSERT INTO integration_ph_question_version_store VALUES(?,?,?,?,?)', ('opaque::question', 'opaque::version', 1, 'question-sha', good))
        available = lambda: c.execute('SELECT q.id FROM questions q WHERE ' + clause, params).fetchall()
        self.assertEqual(available(), [(1,)])
        c.execute("UPDATE integration_ph_content_releases SET local_status='STAGED'")
        self.assertEqual(available(), [])
        c.execute("UPDATE integration_ph_content_releases SET local_status='ACTIVE'")
        self.assertEqual(available(), [(1,)])
        c.execute("INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e VALUES('release','1','opaque::question','opaque::version')")
        self.assertEqual(available(), [])
        c.execute('DELETE FROM ph_bridge_staged_withdrawal_exclusions_v6611e')
        c.execute("UPDATE integration_ph_product_activation_authorizations SET package_checksum_sha256='different'")
        self.assertEqual(available(), [])
        c.execute("UPDATE integration_ph_product_activation_authorizations SET package_checksum_sha256='package-sha'")
        c.execute("UPDATE questions SET ph_question_version_id='new-version'")
        self.assertEqual(available(), [])
        c.execute("UPDATE questions SET ph_question_version_id='opaque::version'")
        c.execute('UPDATE integration_ph_question_version_store SET curriculum_json=?', (json.dumps({'programme_id': 'FSC', 'grade_year_id': '12'}),))
        self.assertEqual(available(), [])
        c.execute('UPDATE integration_ph_question_version_store SET curriculum_json=?', (good,))
        self.assertEqual(available(), [(1,)])
        self.assertGreater(self.resolve.cache_info().hits, 0)
        c.close()


if __name__ == '__main__':
    unittest.main()
