from __future__ import annotations

import base64, hashlib, io, json, lzma, os, shutil, tarfile
from pathlib import Path

BASE = Path('hosted_runtime_base_v6512')
TARGET_PATHS = Path('qualification/v6610f_runtime_paths.json')
OUT = Path('scoremax_runtime_v6610f')
OVERLAY_SHA256 = '989e05cd514c17d48fcee69fa5528f9aa915b6b07490b5b8f9f0fdc032d5ab35'
RUNTIME_FINGERPRINT_SHA256 = 'a7e143585bfa90e8abdb5476de81d335c671223dc25be3decf17a3fdddcc68b2'
RUNTIME_COUNT = 189


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_extract_xz_tar(raw: bytes, dest: Path) -> None:
    tar_raw = lzma.decompress(raw, format=lzma.FORMAT_XZ)
    with tarfile.open(fileobj=io.BytesIO(tar_raw), mode='r:') as tf:
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise SystemExit('V6610F_OVERLAY_UNSAFE_PATH:' + member.name)
        tf.extractall(dest)


def main() -> None:
    keys = sorted(k for k in os.environ if k.startswith('V6610F_OVERLAY_PART_'))
    if not keys:
        raise SystemExit('V6610F_OVERLAY_ENV_MISSING')
    encoded = ''.join(os.environ[k] for k in keys)
    try:
        overlay = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit('V6610F_OVERLAY_BASE64_INVALID') from exc
    got_overlay = sha256_bytes(overlay)
    if got_overlay != OVERLAY_SHA256:
        raise SystemExit(f'V6610F_OVERLAY_SHA_MISMATCH got={got_overlay} expected={OVERLAY_SHA256}')

    paths = json.loads(TARGET_PATHS.read_text(encoding='utf-8'))
    if not isinstance(paths, list) or len(paths) != RUNTIME_COUNT or len(set(paths)) != RUNTIME_COUNT:
        raise SystemExit('V6610F_TARGET_PATH_CONTRACT_INVALID')

    overlay_dir = Path('/tmp/v6610f_overlay')
    shutil.rmtree(overlay_dir, ignore_errors=True)
    overlay_dir.mkdir(parents=True)
    safe_extract_xz_tar(overlay, overlay_dir)

    overlay_files = {p.relative_to(overlay_dir).as_posix() for p in overlay_dir.rglob('*') if p.is_file()}
    if len(overlay_files) != 63:
        raise SystemExit(f'V6610F_OVERLAY_FILE_COUNT_MISMATCH got={len(overlay_files)} expected=63')
    if not overlay_files.issubset(set(paths)):
        raise SystemExit('V6610F_OVERLAY_CONTAINS_NONRUNTIME_PATH')

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for rel in paths:
        src = overlay_dir / rel if rel in overlay_files else BASE / rel
        if not src.is_file():
            raise SystemExit('V6610F_REQUIRED_SOURCE_MISSING:' + rel)
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    rows = []
    actual_paths = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file())
    if actual_paths != sorted(paths):
        raise SystemExit('V6610F_RUNTIME_PATH_SET_MISMATCH')
    for rel in actual_paths:
        data = (OUT / rel).read_bytes()
        rows.append({'path': rel, 'sha256': sha256_bytes(data), 'size': len(data)})
    canonical = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode('utf-8')
    fingerprint = sha256_bytes(canonical)
    if fingerprint != RUNTIME_FINGERPRINT_SHA256:
        raise SystemExit(f'V6610F_RUNTIME_FINGERPRINT_MISMATCH got={fingerprint} expected={RUNTIME_FINGERPRINT_SHA256}')

    print('V6610F_HOSTED_RUNTIME_VERIFIED',
          f'overlay_sha256={got_overlay}',
          f'files={len(rows)}',
          f'runtime_fingerprint_sha256={fingerprint}',
          'status=PREQUALIFICATION_CANDIDATE_NOT_FROZEN')


if __name__ == '__main__':
    main()
