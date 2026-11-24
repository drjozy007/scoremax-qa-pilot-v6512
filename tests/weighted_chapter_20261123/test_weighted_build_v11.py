"""Exact code-only V10 continuation and drift controls; no application import."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('weighted_builder_v11',ROOT/'ux_vnext_overlay/biology_receiver_20261027/weighted_chapter_build_20261123_v11.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
BASE=Path(os.environ.get('SM_WEIGHTED_REFERENCE_RUNTIME',str(ROOT/'qualification/reference_v10')))


class ExactSuccessorBuild(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.runtime=Path(self.tmp.name)/'runtime'
        shutil.copytree(BASE,self.runtime,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        self.assertEqual(build.tree(self.runtime),build.BASE_TREE)

    def test_exact_continuation_is_one_file_and_idempotent(self):
        before={p.relative_to(self.runtime).as_posix():p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()}
        result=build.apply(self.runtime)
        after={p.relative_to(self.runtime).as_posix():p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()}
        self.assertEqual([p for p in before if before[p]!=after[p]],['ux_student_batch.py'])
        self.assertEqual(len(before),274)
        self.assertEqual(build.tree(self.runtime),build.AFTER_TREE)
        self.assertFalse(result['production_mutated'])
        self.assertTrue(build.apply(self.runtime)['replayed'])

    def test_unrelated_runtime_drift_cannot_partially_patch(self):
        target=self.runtime/'ux_student_batch.py'
        original=target.read_bytes()
        (self.runtime/'app.py').write_text('# unrelated drift\n')
        with self.assertRaises(ValueError):build.apply(self.runtime)
        self.assertEqual(target.read_bytes(),original)

    def test_wrong_qualification_input_cannot_patch(self):
        target=self.runtime/'ux_student_batch.py';target.write_text('# altered input\n')
        before={p.relative_to(self.runtime).as_posix():p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):build.apply(self.runtime)
        self.assertEqual(before,{p.relative_to(self.runtime).as_posix():p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
