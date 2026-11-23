"""Exercise the real materializer inputs, output and source rollback in isolation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'ux_vnext_overlay/biology_receiver_20261027/sqlite_navigation_build_20261123_v2.py'
spec=importlib.util.spec_from_file_location('work_b_receiver_build',SCRIPT)
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
DATA=json.loads(SCRIPT.with_name('sqlite_navigation_delta_20261123_v2.json').read_bytes())

class NavigationBuild(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'runtime'
        shutil.copytree(ROOT/'scoremax_runtime_v669b',self.root,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        # A qualified candidate supplies its exact original source rollback.
        # An unmaterialised local checkout can also supply the prior component.
        if build.tree(self.root)==build.AFTER_TREE:
            for row in reversed(DATA['files']):
                p=self.root/row['path'];raw=p.read_bytes()
                self.assertEqual(build.digest(raw),row['after_sha256'])
                if row['before_sha256'] is None:p.unlink();continue
                text=raw.decode('utf8')
                for h in reversed(row['hunks']):
                    self.assertEqual(text.count(h['new']),1);text=text.replace(h['new'],h['old'],1)
                self.assertEqual(build.digest(text.encode()),row['before_sha256']);p.write_bytes(text.encode())
        self.assertEqual(build.tree(self.root),build.BASE_TREE)

    def test_native_build_exact_result_and_idempotence(self):
        self.assertFalse(build.apply(self.root)['replayed'])
        self.assertEqual(build.tree(self.root),build.AFTER_TREE)
        self.assertTrue(build.apply(self.root)['replayed'])
        self.assertEqual(build.tree(self.root),build.AFTER_TREE)

    def test_modified_runtime_is_rejected_before_any_further_write(self):
        p=self.root/'app.py';p.write_bytes(p.read_bytes()+b'\n# source drift\n')
        before=build.tree(self.root)
        with self.assertRaisesRegex(ValueError,'EXACT_PRIOR'):build.apply(self.root)
        self.assertEqual(build.tree(self.root),before)

    def test_changed_delta_pin_is_rejected_before_any_write(self):
        with patch.object(build,'DELTA_SHA','0'*64),self.assertRaisesRegex(ValueError,'DELTA_BYTES_DRIFT'):
            build.apply(self.root)
        self.assertEqual(build.tree(self.root),build.BASE_TREE)

    def test_source_delta_has_only_the_declared_existing_receiver_seams(self):
        self.assertEqual({r['path'] for r in DATA['files']},build.ALLOWED)
        self.assertEqual(build.digest(SCRIPT.with_name('sqlite_navigation_delta_20261123_v2.json').read_bytes()),build.DELTA_SHA)
        self.assertFalse(DATA['production_mutated']);self.assertFalse(DATA['official_ai_scoring_enabled'])

if __name__=='__main__':unittest.main()
