from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
import test_lossless_headroom_recovery_v1 as prior

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('readonly_recovery',ROOT/'scripts/scoremax_lossless_rollback_headroom_20261123_v2.py')
candidate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(candidate)
sys.path.insert(0,str(ROOT/'scoremax_runtime_v669b'))
import backup_capacity_v1 as capacity

class ReadonlyLockRecovery(prior.LosslessRecovery):
    def setUp(self):
        replacement=patch.object(prior,'recovery',candidate);replacement.start();self.addCleanup(replacement.stop)
        super().setUp();self.capacity=capacity

    def test_open_snapshot_is_not_retired(self):
        with closing(sqlite3.connect(self.source)) as c:
            c.execute('BEGIN');c.execute('SELECT COUNT(*) FROM questions').fetchone()
            with self.assertRaisesRegex(RuntimeError,'SNAPSHOT_NONWRITING_EXCLUSIVE_LOCK_UNAVAILABLE'):
                self.run_recovery()
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_concurrent_writer_is_not_retired(self):
        with closing(sqlite3.connect(self.source)) as c:
            c.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(RuntimeError,'SNAPSHOT_NONWRITING_EXCLUSIVE_LOCK_UNAVAILABLE'):
                self.run_recovery()
            c.rollback()
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_wal_sidecar_is_not_ignored(self):
        Path(str(self.source)+'-wal').write_bytes(b'pending transaction')
        with self.assertRaisesRegex(RuntimeError,'BACKUP_RETENTION_SQLITE_SIDECAR'):
            self.run_recovery()
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_source_symlink_is_rejected(self):
        alternate=self.root/'original.db';self.source.rename(alternate);self.source.symlink_to(alternate)
        with self.assertRaisesRegex(RuntimeError,'BACKUP_RETENTION_ALIAS_REFUSED'):
            self.run_recovery()
        self.assertEqual(alternate.read_bytes(),self.before)

    def test_crash_after_retirement_recovers_only_from_verified_archive(self):
        original=candidate.durable_json
        def interrupted(path,payload):
            if path.name=='work_b_SMV10_LOSSLESS_HEADROOM_20261123_V2.json':raise RuntimeError('simulated crash')
            return original(path,payload)
        with patch.object(candidate,'durable_json',side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError,'simulated crash'):self.run_recovery()
        self.assertFalse(self.source.exists());self.assertEqual(self.run_recovery()['status'],'PASSED')

    def test_parent_hashes_cannot_release_child_sqlite_lock(self):
        with candidate.snapshot_exclusive_guard(self.source):
            self.assertEqual(candidate.sha(self.source),self.expected)
            with closing(sqlite3.connect(self.source,timeout=0)) as c:
                with self.assertRaises(sqlite3.OperationalError):c.execute('BEGIN IMMEDIATE')
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_no_process_visibility_dependency(self):
        original=Path.iterdir
        def inaccessible(path):
            if str(path)=='/proc':raise PermissionError('platform process not inspectable')
            return original(path)
        with patch.object(Path,'iterdir',inaccessible):self.assertEqual(self.run_recovery()['status'],'PASSED')

if __name__=='__main__':unittest.main()
