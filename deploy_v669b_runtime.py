from __future__ import annotations

import base64
import hashlib
import io
import json
import lzma
import shutil
import tarfile
import zipfile
from pathlib import Path

EXPECTED_TEXT_PAYLOAD_SHA256 = "9a1d9aef81dfdb5aefc28d0a1c33645b4679347e6277afd21eddeb6682d2321a"
EXPECTED_SOURCE_ZIP_SHA256 = "70a181237cd028b86f34650b0fbc912174ee1516965dd62f8d4b2862bea63ffa"
EXPECTED_HERO_SHA256 = "ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5"
EXPECTED_RELEASE = "6.6.9B"
EXPECTED_TEXT_FILE_COUNT = 183
EXPECTED_RUNTIME_FILE_COUNT = 184
RUNTIME_DIR = Path("scoremax_runtime_v669b")
PAYLOAD_DIR = Path("runtime_payload")
BASE_ZIP = Path("SCOREMAX_ONLY_UPLOAD_TO_GITHUB_V6_5_12.zip")
HERO_REL = "static/scoremax_intelligence_hero.png"
EXCLUDED_NONRUNTIME_EXAMPLE = "integration_examples/v1_1_0/PH_SM_APPROVED_CONTENT_MANIFEST_DEMO_v1_1_0.zip"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_extract_tar(raw: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:xz") as tf:
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise SystemExit(f"V669B_TEXT_ARCHIVE_UNSAFE member={member.name}")
        tf.extractall(dest)


def find_verified_hero_in_zip_bytes(raw: bytes, *, depth: int = 0) -> bytes | None:
    if depth > 6:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if name.endswith(HERO_REL):
                    data = zf.read(info)
                    if sha256_bytes(data) == EXPECTED_HERO_SHA256:
                        return data
            for info in zf.infolist():
                if info.filename.lower().endswith(".zip") and info.file_size <= 50_000_000:
                    found = find_verified_hero_in_zip_bytes(zf.read(info), depth=depth + 1)
                    if found is not None:
                        return found
    except zipfile.BadZipFile:
        return None
    return None


def main() -> None:
    parts = sorted(PAYLOAD_DIR.glob("v669b_text_runtime.b64.part*"))
    if not parts:
        raise SystemExit("V669B_TEXT_PAYLOAD_MISSING")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"V669B_TEXT_PAYLOAD_BASE64_INVALID:{type(exc).__name__}") from exc
    got = sha256_bytes(compressed)
    if got != EXPECTED_TEXT_PAYLOAD_SHA256:
        raise SystemExit(f"V669B_TEXT_PAYLOAD_SHA_MISMATCH got={got} expected={EXPECTED_TEXT_PAYLOAD_SHA256}")

    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    safe_extract_tar(compressed, RUNTIME_DIR)

    text_files = [p for p in RUNTIME_DIR.rglob("*") if p.is_file()]
    if len(text_files) != EXPECTED_TEXT_FILE_COUNT:
        raise SystemExit(f"V669B_TEXT_FILE_COUNT_MISMATCH got={len(text_files)} expected={EXPECTED_TEXT_FILE_COUNT}")
    if (RUNTIME_DIR / EXCLUDED_NONRUNTIME_EXAMPLE).exists():
        raise SystemExit("V669B_NONRUNTIME_EXAMPLE_SHOULD_NOT_BE_DEPLOYED")

    if not BASE_ZIP.is_file():
        raise SystemExit("V6512_BASE_ZIP_MISSING_FOR_VERIFIED_HERO_REUSE")
    hero = find_verified_hero_in_zip_bytes(BASE_ZIP.read_bytes())
    if hero is None:
        raise SystemExit("V669B_VERIFIED_HERO_NOT_FOUND_IN_INHERITED_BASE")
    hero_path = RUNTIME_DIR / HERO_REL
    hero_path.parent.mkdir(parents=True, exist_ok=True)
    hero_path.write_bytes(hero)

    manifest_path = RUNTIME_DIR / "V6_6_9B_PACKAGE_MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit("V669B_PACKAGE_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if EXPECTED_RELEASE not in json.dumps(manifest, sort_keys=True):
        raise SystemExit("V669B_PACKAGE_MANIFEST_RELEASE_IDENTITY_MISSING")

    expected: dict[str, str] = {}
    def walk(obj):
        if isinstance(obj, dict):
            p = obj.get("path")
            s = obj.get("sha256")
            if isinstance(p, str) and isinstance(s, str) and len(s) == 64:
                expected[p.lstrip("./")] = s.lower()
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
    walk(manifest)

    runtime_files = []
    for path in sorted(RUNTIME_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(RUNTIME_DIR).as_posix()
        runtime_files.append(rel)
        want = expected.get(rel)
        if want and sha256_file(path) != want:
            raise SystemExit(f"V669B_RUNTIME_FILE_SHA_MISMATCH path={rel}")

    if len(runtime_files) != EXPECTED_RUNTIME_FILE_COUNT:
        raise SystemExit(f"V669B_RUNTIME_FILE_COUNT_MISMATCH got={len(runtime_files)} expected={EXPECTED_RUNTIME_FILE_COUNT}")
    if sha256_file(hero_path) != EXPECTED_HERO_SHA256:
        raise SystemExit("V669B_HERO_ASSET_SHA_MISMATCH")

    for required in (
        "app.py", "scoremax_production.py", "production_infrastructure_engine.py",
        "production_qualification_engine.py", "scoremax_integration_v1.py",
        "feature_availability_engine.py", "science_genius_engine.py",
        "digital_coach_engine.py", "requirements.txt",
    ):
        if not (RUNTIME_DIR / required).is_file():
            raise SystemExit(f"V669B_REQUIRED_RUNTIME_FILE_MISSING path={required}")

    print(
        "V669B_HOSTED_RUNTIME_VERIFIED "
        f"text_payload_sha256={got} source_candidate_sha256={EXPECTED_SOURCE_ZIP_SHA256} "
        f"hero_sha256={EXPECTED_HERO_SHA256} files={len(runtime_files)} "
        f"release={EXPECTED_RELEASE} status=DEPENDENT_CANDIDATE_NOT_FROZEN"
    )


if __name__ == "__main__":
    main()
