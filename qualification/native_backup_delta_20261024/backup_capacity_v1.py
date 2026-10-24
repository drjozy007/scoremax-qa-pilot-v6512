"""Capacity fence for the existing reviewer backup functions; no DB policy changes.

Managed backups are serialized and retain at least one verified rollback. Release
rollbacks, qualification evidence and the live database are never pruned here.
"""
from contextlib import closing, contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

RESERVE_BYTES = 512 * 1024 * 1024
# Existing Docker/Render disk contract. A mount migration requires requalification.
EXPECTED_PERSISTENT_MOUNT = Path('/data')
_LOCK = threading.RLock()
_HELD_LOCKS = threading.local()
NATIVE_COPY_LOCK_TIMEOUT_SECONDS = 30.0
COPY_IO_WINDOW_BYTES = 32 * 1024 * 1024


def _io_advice_worker(source, target):
    """Separate-process descriptors cannot cancel the parent's SQLite POSIX locks."""
    import stat
    handles = {}
    try:
        for name, path in (('source', source), ('target', target)):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            handles[name] = fd
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError('BACKUP_IO_NONPRIVATE_FILE')
            if (info.st_dev, info.st_ino) != (os.stat(path).st_dev, os.stat(path).st_ino):
                raise RuntimeError('BACKUP_IO_IDENTITY_CHANGED')
        print('READY', flush=True)
        for line in sys.stdin:
            command = line.strip()
            if command not in ('TARGET', 'BOTH', 'STOP'):
                raise RuntimeError('BACKUP_IO_INVALID_COMMAND')
            if command == 'STOP':
                print('OK', flush=True)
                return
            os.fdatasync(handles['target'])
            os.posix_fadvise(handles['target'], 0, 0, os.POSIX_FADV_DONTNEED)
            if command == 'BOTH':
                os.posix_fadvise(handles['source'], 0, 0, os.POSIX_FADV_DONTNEED)
            print('OK', flush=True)
    finally:
        for fd in handles.values():
            os.close(fd)


@contextmanager
def _copy_io_window(source, target):
    """Bound clean/dirty copy cache without changing bytes or verification policy.

    Destination synchronization is mandatory before cache advice. Never open/close
    extra SQLite-file descriptors in this process while SQLite owns its locks.
    Windows retains the existing copy semantics; resource qualification is Linux.
    """
    if os.name != 'posix':
        yield lambda both=False: None
        return
    if not all(hasattr(os, name) for name in ('fdatasync', 'posix_fadvise', 'POSIX_FADV_DONTNEED')):
        raise RuntimeError('BACKUP_IO_ADVICE_UNAVAILABLE')
    import select
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                              '--copy-io-advice', str(source), str(target)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, bufsize=1)
    def receive(expected):
        readable, _, _ = select.select([child.stdout], [], [], 30)
        if not readable or child.stdout.readline().strip() != expected:
            raise RuntimeError('BACKUP_IO_ADVICE_FAILED')
    def advise(both=False):
        child.stdin.write('BOTH\n' if both else 'TARGET\n')
        child.stdin.flush()
        receive('OK')
    try:
        receive('READY')
        yield advise
        child.stdin.write('STOP\n'); child.stdin.flush(); receive('OK')
        if child.wait(timeout=10) != 0:
            raise RuntimeError('BACKUP_IO_ADVICE_FAILED')
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            stream.close()


def _filesystem_root(destination):
    root = Path(destination).resolve()
    while not root.exists():
        if root.parent == root:
            raise FileNotFoundError(root)
        root = root.parent
    device = root.stat().st_dev
    while root.parent != root and root.parent.stat().st_dev == device:
        root = root.parent
    return root


def require_storage_boundary(destination):
    """Render DB copies require the configured mounted persistent data disk.

    Host disk_usage() cannot establish a budget for provider-limited ephemeral
    storage. Refuse those destinations rather than guessing their quota.
    Local/CI disposable qualification retains its existing filesystem behavior.
    """
    if os.environ.get('RENDER', '').lower() != 'true':
        return
    try:
        configured = Path(os.environ.get('POWER_HOUSE_REVIEW_SERVICE_DATA_DIR', '/data'))
        if not configured.is_absolute():
            raise ValueError('data root must be absolute')
        data = configured.resolve(strict=True)
        if not data.is_dir():
            raise ValueError('data root must be a directory')
        target = Path(destination).resolve()
        if EXPECTED_PERSISTENT_MOUNT.is_symlink():
            raise ValueError('persistent mount must not be a symlink')
        mount = EXPECTED_PERSISTENT_MOUNT.resolve(strict=True)
        if (mount.parent == mount or _filesystem_root(mount) != mount
                or not data.is_relative_to(mount) or _filesystem_root(data) != mount
                or not target.is_relative_to(data) or _filesystem_root(target) != mount):
            raise ValueError('destination is not on the configured persistent disk')
    except (OSError, ValueError, RuntimeError) as exc:
        raise RuntimeError('BACKUP_PERSISTENT_STORAGE_REQUIRED') from exc


def capacity_lock_path(destination):
    """One stable lock per filesystem, including independent backup/job roots."""
    root = _filesystem_root(destination)
    # Persistent mounts share their lock on the mount itself. The OS/system
    # volume uses one local control directory, never a job-specific directory.
    if root.parent == root:
        control = (Path('/tmp') if os.name == 'posix' else Path(tempfile.gettempdir())) / 'powerhouse-capacity'
        control.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256((str(root.stat().st_dev) + ':' + os.path.normcase(str(root))).encode()).hexdigest()[:24]
        return control / (identity + '.lock')
    return root / '.powerhouse-capacity.lock'


@contextmanager
def capacity_lock(destination, *, timeout_seconds=None):
    """Serialize capacity checks, copies and managed retention on the same disk."""
    if timeout_seconds is not None and (type(timeout_seconds) not in (int, float)
                                       or not 0 <= timeout_seconds <= 3600):
        raise ValueError('BACKUP_CAPACITY_INVALID_LOCK_TIMEOUT')
    deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
    acquired = (_LOCK.acquire() if deadline is None
                else _LOCK.acquire(timeout=max(0, deadline - time.monotonic())))
    if not acquired:
        raise TimeoutError('BACKUP_CAPACITY_LOCK_TIMEOUT')
    try:
        lock_path = capacity_lock_path(destination)
        key = str(lock_path.resolve())
        held = getattr(_HELD_LOCKS, 'paths', None)
        if held is None:
            held = _HELD_LOCKS.paths = set()
        if key in held:
            # Nested native backup/checkpoint calls retain the same OS lock.
            yield
            return
        with lock_path.open('a+b') as lock:
            if os.name == 'posix':
                import fcntl
            elif os.name == 'nt':
                import msvcrt
                if lock.seek(0, os.SEEK_END) == 0:
                    lock.write(b'\0'); lock.flush()
                lock.seek(0)
            else:
                raise RuntimeError('BACKUP_CAPACITY_LOCK_PLATFORM_UNSUPPORTED')
            while True:
                try:
                    if os.name == 'posix':
                        fcntl.flock(lock, fcntl.LOCK_EX if deadline is None
                                    else fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK if deadline is None
                                       else msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    import errno
                    if deadline is None or exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('BACKUP_CAPACITY_LOCK_TIMEOUT') from exc
                    time.sleep(min(0.05, remaining))
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                if os.name == 'posix':
                    fcntl.flock(lock, fcntl.LOCK_UN)
                else:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        _LOCK.release()
    # Keep the lock inode: unlinking it can split waiting processes into domains.


def database_bytes(source):
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as c:
        return int(c.execute('PRAGMA page_count').fetchone()[0]) * int(c.execute('PRAGMA page_size').fetchone()[0])


def require_capacity(source, destination, *, copies=1, temporary_bytes=0):
    """Also usable before an isolated publisher snapshot; fails before any copy."""
    if type(copies) is not int or copies < 1 or type(temporary_bytes) is not int or temporary_bytes < 0:
        raise ValueError('BACKUP_CAPACITY_INVALID_BUDGET')
    destination = Path(destination).resolve()
    require_storage_boundary(destination)
    size = database_bytes(source)
    free = shutil.disk_usage(destination).free
    required = size * copies + temporary_bytes + RESERVE_BYTES
    if free < required:
        raise RuntimeError(f'BACKUP_CAPACITY_REFUSED free={free} required={required} reserve={RESERVE_BYTES}')
    return {'database_bytes': size, 'free_bytes': free, 'required_bytes': required}


@contextmanager
def database_copy_reservation(source, destination, *, copies=1, temporary_bytes=0):
    """Use the existing disk lock/budget for native trials and checkpoints.

    These directories contain evidence, not managed backups: no retention or
    deletion is authorized here. Hold the lock through verification and cleanup.
    """
    destination = Path(destination).resolve()
    require_storage_boundary(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with capacity_lock(destination, timeout_seconds=NATIVE_COPY_LOCK_TIMEOUT_SECONDS):
        require_capacity(source, destination, copies=copies, temporary_bytes=temporary_bytes)
        yield


def require_copy_destination(target):
    """A mount check does not establish ownership of symlinks or active journals."""
    target = Path(os.path.abspath(os.fspath(target)))
    for path in (target, *target.parents):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise RuntimeError('BACKUP_DESTINATION_ALIAS_REFUSED')
    if target.exists() and not target.is_file():
        raise RuntimeError('BACKUP_DESTINATION_NOT_REGULAR')
    for suffix in ('-wal', '-shm', '-journal', '.manifest.json'):
        sidecar = Path(str(target) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise RuntimeError('BACKUP_DESTINATION_PROTECTED_SIDECAR')
    return target


def _destination_identity(path):
    try:
        s = path.stat()
    except FileNotFoundError:
        return None
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def require_retention_candidate(path):
    """Retire only private regular files with no live SQLite sidecars or aliases."""
    import stat
    target = Path(os.path.abspath(os.fspath(path)))
    for parent in (target, *target.parents):
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise RuntimeError('BACKUP_RETENTION_ALIAS_REFUSED')
    for candidate in (target, Path(str(target) + '.manifest.json')):
        if candidate.exists() or candidate.is_symlink():
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError('BACKUP_RETENTION_NONPRIVATE_FILE')
    if not target.is_file():
        raise RuntimeError('BACKUP_RETENTION_FILE_MISSING')
    for suffix in ('-wal', '-shm', '-journal', '.restore.partial', '.partial'):
        candidate = Path(str(target) + suffix)
        if candidate.exists() or candidate.is_symlink():
            raise RuntimeError('BACKUP_RETENTION_SQLITE_SIDECAR')
    return target


@contextmanager
def owned_copy_publication(target, *, overwrite=False):
    """Use a private temporary namespace and one atomic final replacement.

    A predictable .partial left by another operation is never removed. Only
    this context's new directory is cleaned. The caller holds the disk lock.
    """
    target = require_copy_destination(target)
    require_storage_boundary(target.parent)
    before = _destination_identity(target)
    if before is not None and not overwrite:
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(prefix='.' + target.name + '.copy-',
                                     dir=target.parent) as directory:
        tmp = Path(directory) / 'database.partial'

        def publish(*, already_synced=False):
            require_copy_destination(target)
            if _destination_identity(target) != before:
                raise RuntimeError('BACKUP_DESTINATION_CHANGED_DURING_COPY')
            if not already_synced:
                # Windows FlushFileBuffers requires a writable handle.
                # Streamed promotion already fsyncs before copying source mode.
                with tmp.open('r+b') as handle:
                    os.fsync(handle.fileno())
            # Path.replace is atomic on this filesystem and does not first
            # discard the existing target if the final rename fails.
            tmp.replace(target)

        yield tmp, publish


def guarded_database_copy(original, source_getter, target_getter):
    @wraps(original)
    def run(*args, **kwargs):
        source = Path(source_getter(*args, **kwargs))
        target = require_copy_destination(target_getter(*args, **kwargs))
        with database_copy_reservation(source, target.parent):
            require_copy_destination(target)
            return original(*args, **kwargs)
    return run


def guarded_verified_backup(original):
    @wraps(original)
    def run(database, backup_dir, *, retain=3, verify_restore=True, probe_dir=None):
        source, out = Path(database), Path(backup_dir).resolve()
        probe = Path(probe_dir).resolve() if probe_dir is not None else out
        # Refuse incompatible destinations before native retention or mkdir.
        require_storage_boundary(out)
        if verify_restore:
            require_storage_boundary(probe)
        with database_copy_reservation(source, out, copies=2 if verify_restore else 1):
            return original(database, backup_dir, retain=retain,
                            verify_restore=verify_restore, probe_dir=probe_dir)
    return run


def capacity_copy2(source, target):
    """Preserve checkpoint bytes without an unguarded whole-file copy.

    Caller holds database_copy_reservation. Refuse a chunk before it can consume
    the existing reserve; the native caller owns partial-file cleanup.
    """
    source, target = Path(source), Path(target)
    require_storage_boundary(target.resolve().parent)
    with source.open('rb') as src, target.open('xb') as dst:
        with _copy_io_window(source, target) as advise:
            window = 0
            for block in iter(lambda: src.read(1024 * 1024), b''):
                if shutil.disk_usage(target.parent).free < RESERVE_BYTES + len(block):
                    raise RuntimeError('BACKUP_CAPACITY_RESERVE_REACHED')
                dst.write(block); window += len(block)
                if window >= COPY_IO_WINDOW_BYTES:
                    dst.flush(); advise(); window = 0
            dst.flush()
            os.fsync(dst.fileno())
            advise(both=True)
    shutil.copystat(source, target)
    return str(target)


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        consumed = 0
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
            consumed += len(block)
            if consumed >= COPY_IO_WINDOW_BYTES and hasattr(os, 'posix_fadvise'):
                os.posix_fadvise(f.fileno(), f.tell() - consumed, consumed, os.POSIX_FADV_DONTNEED)
                consumed = 0
        if hasattr(os, 'posix_fadvise'):
            os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return h.hexdigest()


def _verified(path):
    try:
        require_retention_candidate(path)
        before = _destination_identity(path)
        m = json.loads(Path(str(path) + '.manifest.json').read_text())
        if m.get('integrity_result') != 'ok' or m.get('backup_sha256') != _digest(path):
            return False
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as c:
            healthy = c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        require_retention_candidate(path)
        if _destination_identity(path) != before:
            return False
        with _copy_io_window(path, path) as advise:
            advise(both=True)
        return healthy
    except (OSError, ValueError, sqlite3.Error):
        return False


def _managed(root):
    return sorted((p for p in root.glob('*.sqlite3') if p.is_file() and not p.is_symlink()),
                  key=lambda p: p.stat().st_mtime_ns, reverse=True)


def _remove(path):
    for suffix in ('', '.manifest.json', '-wal', '-shm', '-journal'):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _prune_after_verified(root):
    files = _managed(root)
    keep = max(1, int(os.environ.get('POWER_HOUSE_STORAGE_GUARD_KEEP', '1')))
    if len(files) <= keep:
        return
    for p in files:
        require_retention_candidate(p)
    # Only complete, manifest-bound new backups authorise removal of older copies.
    verified = [p for p in files[:keep] if _verified(p)]
    if len(verified) != keep:
        return
    for p in files[keep:]:
        _remove(p)


@contextmanager
def reservation(source, root):
    root = Path(root).resolve()
    # Refuse before directory creation, retention, lock acquisition or copy.
    require_storage_boundary(root)
    root.mkdir(parents=True, exist_ok=True)
    with capacity_lock(root):
        require_storage_boundary(root)
        _prune_after_verified(root)
        require_capacity(source, root)
        before = set(_managed(root))
        try:
            yield
        except BaseException:
            for p in set(_managed(root)) - before:
                _remove(p)
            raise
        _prune_after_verified(root)


def guarded_backup(original, source_getter, paths_getter):
    @wraps(original)
    def run(*args, **kwargs):
        source = Path(source_getter(*args, **kwargs))
        if not source.exists() or not source.stat().st_size:
            return original(*args, **kwargs)
        with reservation(source, paths_getter()['backups']):
            return original(*args, **kwargs)
    return run


def capacity_backup(source_connection, target_connection, target, *, progress_hook=None, pages=256,
                    backup_artifact=False):
    """Recheck reserve during SQLite's existing online backup, including WAL growth."""
    require_storage_boundary(Path(target).resolve().parent)
    if type(pages) is not int or not 1 <= pages <= 8192:
        raise ValueError('BACKUP_CAPACITY_INVALID_PAGE_BATCH')
    if os.environ.get('RENDER', '').lower() == 'true':
        files = [row[2] for row in target_connection.execute('PRAGMA database_list')
                 if row[1] == 'main']
        if len(files) != 1 or not files[0] or Path(files[0]).resolve() != Path(target).resolve():
            raise RuntimeError('BACKUP_DESTINATION_CONNECTION_MISMATCH')
    source_files = [row[2] for row in source_connection.execute('PRAGMA database_list') if row[1] == 'main']
    if len(source_files) != 1 or not source_files[0]:
        raise RuntimeError('BACKUP_SOURCE_CONNECTION_MISMATCH')
    page_size = int(source_connection.execute('PRAGMA page_size').fetchone()[0])
    with _copy_io_window(source_files[0], target) as advise:
        last_advice = 0
        def progress(status, remaining, total):
            nonlocal last_advice
            if shutil.disk_usage(Path(target).parent).free < RESERVE_BYTES:
                raise RuntimeError('BACKUP_CAPACITY_RESERVE_REACHED')
            copied = (total - remaining) * page_size
            if copied < last_advice:
                last_advice = 0
            if copied - last_advice >= COPY_IO_WINDOW_BYTES:
                advise(); last_advice = copied
            if progress_hook is not None:
                progress_hook(status, remaining, total)
        source_connection.backup(target_connection, pages=pages, progress=progress)
        if backup_artifact:
            # Only this newly created private artifact is canonicalized; live mode is untouched.
            mode = str(target_connection.execute('PRAGMA journal_mode=DELETE').fetchone()[0]).lower()
            if mode != 'delete':
                raise RuntimeError('BACKUP_ARTIFACT_JOURNAL_MODE_REFUSED')
        advise(both=True)


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--copy-io-advice':
        raise SystemExit('Internal backup cache-advice worker only')
    _io_advice_worker(sys.argv[2], sys.argv[3])

