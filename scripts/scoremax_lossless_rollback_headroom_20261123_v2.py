"""One finite lossless rollback archive before the unchanged native storage guard.

No application/database writes, reserve reduction, authority, resource or secret
changes. Fixed production source is an independently verified inactive snapshot.
An independently re-read compressed copy and durable manifest precede removal
of its redundant uncompressed representation. Every original byte is retained.
"""
from contextlib import closing, contextmanager
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import uuid
import subprocess
import select


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            result.update(block)
    return result.hexdigest()


def identity(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_nlink != 1:
        raise ValueError('REGULAR_UNLINKED_PRIVATE_SNAPSHOT_REQUIRED')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


@contextmanager
def snapshot_exclusive_guard(path):
    # Like native backup I/O isolation, a separate process owns SQLite locks.
    # Parent hashing descriptors cannot cancel those POSIX SQLite locks.
    identity(path)
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
        '--hold-snapshot-nonwriting', str(path)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        readable, _, _ = select.select([child.stdout], [], [], 120)
        if not readable or child.stdout.readline().strip() != 'LOCKED_QUICK_CHECK_OK':
            raise RuntimeError('SNAPSHOT_NONWRITING_EXCLUSIVE_LOCK_UNAVAILABLE')
        yield
        child.stdin.write('STOP'+chr(10));child.stdin.flush()
        if child.wait(timeout=10) != 0:
            raise RuntimeError('SNAPSHOT_NONWRITING_LOCK_RELEASE_FAILED')
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):stream.close()


def hold_snapshot_exclusive(path):
    # A non-writing EXCLUSIVE transaction, with zero data/DDL writes. Busy databases fail before
    # archival; no platform /proc descriptor visibility assumptions are needed.
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=0)) as connection:
        connection.execute('BEGIN EXCLUSIVE')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('SNAPSHOT_QUICK_CHECK_FAILED')
        print('LOCKED_QUICK_CHECK_OK',flush=True)
        if sys.stdin.readline().strip() != 'STOP':
            raise RuntimeError('SNAPSHOT_LOCK_HOLDER_PARENT_LOST')
        connection.rollback()


def decompressed_identity(path):
    result = hashlib.sha256()
    size = 0
    with gzip.open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            result.update(block)
            size += len(block)
    return size, result.hexdigest()


def durable_json(path, payload):
    descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(payload, output, sort_keys=True, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def sync_directory(root):
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _archive_snapshot_locked(source, expected, size, capacity):
    """Caller holds the native filesystem capacity lock for this finite action."""
    archive = Path(str(source)+'.gz')
    manifest = Path(str(archive)+'.manifest.json')
    receipt = source.parent/'work_b_SMV10_LOSSLESS_HEADROOM_20261123_V2.json'
    if not manifest.exists():
        if archive.exists() or receipt.exists():
            raise ValueError('UNOWNED_OR_PARTIAL_ARCHIVE_REQUIRES_RECONCILIATION')
        before = identity(source)
        if before[2] != size:
            raise ValueError('SNAPSHOT_SIZE_DRIFT')
        capacity.require_retention_candidate(source)
        partial = Path(str(archive)+'.'+uuid.uuid4().hex+'.partial')
        descriptor = os.open(partial, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        digest = hashlib.sha256()
        total = 0
        with source.open('rb') as stream, os.fdopen(descriptor, 'wb') as output:
            with gzip.GzipFile(fileobj=output, mode='wb', compresslevel=1,
                               filename=source.name, mtime=0) as compressed:
                for block in iter(lambda: stream.read(4194304), b''):
                    digest.update(block)
                    total += len(block)
                    compressed.write(block)
                    if shutil.disk_usage(source.parent).free < capacity.RESERVE_BYTES:
                        raise RuntimeError('UNCHANGED_NATIVE_RESERVE_REQUIRED')
            output.flush()
            os.fsync(output.fileno())
        if (total, digest.hexdigest()) != (size, expected) or identity(source) != before:
            raise ValueError('SOURCE_SNAPSHOT_BYTES_CHANGED')
        if decompressed_identity(partial) != (size, expected):
            raise ValueError('ARCHIVE_ROUNDTRIP_FAILED')
        archive_sha = sha(partial)
        os.rename(partial, archive)
        durable_json(manifest, {'source_path': str(source), 'source_identity': before,
            'source_bytes': size, 'source_sha256': expected, 'quick_check': 'ok',
            'archive_path': str(archive), 'archive_sha256': archive_sha,
            'archive_bytes': archive.stat().st_size, 'live_database_mutated': False})
        sync_directory(source.parent)
    saved = json.loads(manifest.read_text())
    if (saved['source_path'] != str(source) or saved['source_sha256'] != expected
            or saved['source_bytes'] != size or saved['archive_path'] != str(archive)):
        raise ValueError('ARCHIVE_MANIFEST_BINDING_DRIFT')
    archive_state = identity(archive)
    if (stat.S_IMODE(archive.stat().st_mode) != 0o600
            or sha(archive) != saved['archive_sha256']
            or archive_state[2] != saved['archive_bytes']
            or decompressed_identity(archive) != (size, expected)
            or identity(archive) != archive_state):
        raise ValueError('INDEPENDENT_ARCHIVE_RECHECK_FAILED')
    free_before = shutil.disk_usage(source.parent).free
    if source.exists():
        if receipt.exists() or identity(source) != saved['source_identity'] or sha(source) != expected:
            raise ValueError('ORIGINAL_OR_RETIREMENT_STATE_DRIFT')
        capacity.require_retention_candidate(source)
        source.unlink()
        sync_directory(source.parent)
    if not receipt.exists():
        durable_json(receipt, {'status': 'PASSED', 'archive_path': str(archive),
            'archive_sha256': saved['archive_sha256'], 'archive_manifest_sha256': sha(manifest),
            'decompressed_verified_bytes': size, 'decompressed_verified_sha256': expected,
            'retired_redundant_uncompressed_path': str(source),
            'unique_snapshot_bytes_discarded': False, 'live_database_mutated': False,
            'native_backup_guard_required_next': True, 'native_reserve_bytes': capacity.RESERVE_BYTES,
            'free_before': free_before, 'free_after': shutil.disk_usage(source.parent).free})
        sync_directory(source.parent)
    result = json.loads(receipt.read_text())
    if (result.get('status') != 'PASSED' or result['archive_sha256'] != saved['archive_sha256']
            or result['decompressed_verified_sha256'] != expected
            or result['archive_manifest_sha256'] != sha(manifest)):
        raise ValueError('RETIREMENT_RECEIPT_DRIFT')
    return result


def archive_snapshot(source, expected, size, capacity):
    if source.exists() or source.is_symlink():
        capacity.require_retention_candidate(source)
        with snapshot_exclusive_guard(source):
            return _archive_snapshot_locked(source, expected, size, capacity)
    return _archive_snapshot_locked(source, expected, size, capacity)


def main():
    if os.environ.get('RENDER_SERVICE_ID') != 'srv-daj5fbm7bikc73aq2gdg':
        raise ValueError('EXACT_EXISTING_SERVICE_REQUIRED')
    project = Path(__file__).resolve().parents[1]
    runtime = project/'scoremax_runtime_v669b'
    path = project/'ux_vnext_overlay/biology_receiver_20261027/legacy_formal_build_20261123_v16.py'
    spec = importlib.util.spec_from_file_location('v16_build_identity', path)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    if build.tree(runtime) != '5746e20cbf82bf01655289c6f97f82863a8ff72cb1bc011d90e2fa39cc12083d':
        raise ValueError('EXACT_QUALIFIED_V16_RUNTIME_REQUIRED')
    sys.path.insert(0, str(runtime))
    import backup_capacity_v1 as capacity
    root = Path('/data/scoremax/backup')
    source = root/'work_b_PRE_SUCCESSOR_V10_20261123_V1.db'
    proof = Path(str(source)+'.verified.json')
    expected = '8c6fb8c9d14413763db24424e1c5a93743b309a31d9c1987a2dee4da678dc5ff'
    if sha(proof) != 'c650a556b515174e24eb68b983852404fc3be19e10d0cb77bf87426e3e37399b':
        raise ValueError('EXISTING_NATIVE_VERIFICATION_BYTES_DRIFT')
    saved = json.loads(proof.read_text())
    if saved['status'] != 'PASSED' or saved['snapshot'] != str(source) or saved['sha256'] != expected:
        raise ValueError('EXISTING_VERIFIED_ROLLBACK_REQUIRED')
    os.nice(10)
    with capacity.capacity_lock(root):
        result = archive_snapshot(source, expected, 740851712, capacity)
    print('SCOREMAX_LOSSLESS_HEADROOM_PASSED '+json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--hold-snapshot-nonwriting':
        hold_snapshot_exclusive(sys.argv[2])
    else:main()
