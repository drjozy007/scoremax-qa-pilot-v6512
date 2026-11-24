import gzip
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('recovery', ROOT/'scripts/scoremax_lossless_rollback_headroom_20261123_v1.py')
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class LosslessRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'verified_rollback.db'
        with closing(sqlite3.connect(self.source)) as connection:
            connection.execute('CREATE TABLE questions(id TEXT PRIMARY KEY, original BLOB)')
            connection.executemany('INSERT INTO questions VALUES(?,?)', [('opaque::'+str(n), bytes(range(256))*17) for n in range(25)])
            connection.commit()
        self.before = self.source.read_bytes()
        self.expected = recovery.sha(self.source)
        self.size = len(self.before)
        self.capacity = SimpleNamespace(RESERVE_BYTES=512*1024*1024)

    def run_recovery(self):
        return recovery.archive_snapshot(self.source, self.expected, self.size, self.capacity)

    def test_restore_is_byte_exact_and_normal_guard_still_required(self):
        result = self.run_recovery()
        self.assertFalse(self.source.exists())
        archive = Path(result['archive_path'])
        self.assertEqual(gzip.decompress(archive.read_bytes()), self.before)
        restored = self.root/'restored.db'
        restored.write_bytes(gzip.decompress(archive.read_bytes()))
        with closing(sqlite3.connect(restored)) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM questions').fetchone()[0], 25)
        self.assertTrue(result['native_backup_guard_required_next'])
        self.assertFalse(result['unique_snapshot_bytes_discarded'])
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_replay_does_not_touch_unrelated_live_database(self):
        live = self.root/'live.db'
        live.write_bytes(self.before)
        first = self.run_recovery()
        self.assertEqual(self.run_recovery(), first)
        self.assertEqual(live.read_bytes(), self.before)

    def test_wrong_source_sha_cannot_retire_original(self):
        self.expected = '0'*64
        with self.assertRaisesRegex(ValueError, 'SOURCE_SNAPSHOT_BYTES_CHANGED'):
            self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_open_snapshot_is_not_retired(self):
        with self.source.open('rb'):
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IN_USE'):
                self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_wal_sidecar_is_not_ignored(self):
        Path(str(self.source)+'-wal').write_bytes(b'pending transaction')
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_SIDECAR'):
            self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_archive_corruption_before_retirement_preserves_original(self):
        real_read = recovery.decompressed_identity
        calls = []
        def corrupt_after_first(path):
            result = real_read(path)
            calls.append(str(path))
            if len(calls) == 1:
                path.write_bytes(b'corrupted archive')
            return result
        with patch.object(recovery, 'decompressed_identity', side_effect=corrupt_after_first):
            with self.assertRaises((ValueError, gzip.BadGzipFile)):
                self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_crash_after_retirement_recovers_only_from_verified_archive(self):
        real_write = recovery.durable_json
        def interrupted(path, payload):
            if path.name == 'work_b_SMV10_LOSSLESS_HEADROOM_20261123_V1.json':
                raise RuntimeError('simulated process loss after bytes preserved')
            return real_write(path, payload)
        with patch.object(recovery, 'durable_json', side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.run_recovery()
        self.assertFalse(self.source.exists())
        result = self.run_recovery()
        self.assertEqual(gzip.decompress(Path(result['archive_path']).read_bytes()), self.before)

    def test_unrelated_existing_archive_is_not_adopted(self):
        Path(str(self.source)+'.gz').write_bytes(b'not owned')
        with self.assertRaisesRegex(ValueError, 'UNOWNED_OR_PARTIAL'):
            self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_source_symlink_is_rejected(self):
        alternate = self.root/'original.db'
        self.source.rename(alternate)
        self.source.symlink_to(alternate)
        with self.assertRaisesRegex(ValueError, 'REGULAR_UNLINKED_PRIVATE_SNAPSHOT'):
            self.run_recovery()
        self.assertEqual(alternate.read_bytes(), self.before)

    def test_native_reserve_is_never_lowered(self):
        with patch.object(recovery.shutil, 'disk_usage', return_value=SimpleNamespace(free=self.capacity.RESERVE_BYTES-1)):
            with self.assertRaisesRegex(RuntimeError, 'UNCHANGED_NATIVE_RESERVE_REQUIRED'):
                self.run_recovery()
        self.assertEqual(self.source.read_bytes(), self.before)


if __name__ == '__main__':
    unittest.main()
