from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

EXPECTED_BUNDLE = "ScoreMax_V6_6_9B_PRODUCTION_RUNTIME_BUNDLE.tar.gz"
EXPECTED_BUNDLE_SHA256 = "e8e92ec9ba81342bdabdde8d362e1fa780e547d786d901108a46aeabab929c9b"
EXPECTED_SOURCE_ZIP_SHA256 = "70a181237cd028b86f34650b0fbc912174ee1516965dd62f8d4b2862bea63ffa"
EXPECTED_HERO_SHA256 = "ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5"
EXPECTED_RELEASE = "6.6.9B"
EXPECTED_RUNTIME_FILE_COUNT = 184
RUNTIME_DIR = Path("scoremax_runtime_v669b")
EXCLUDED_NONRUNTIME_EXAMPLE = "integration_examples/v1_1_0/PH_SM_APPROVED_CONTENT_MANIFEST_DEMO_v1_1_0.zip"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    bundle = Path(EXPECTED_BUNDLE)
    if not bundle.is_file():
        raise SystemExit(
            f"V669B_RUNTIME_BUNDLE_MISSING expected={EXPECTED_BUNDLE}; "
            "do not deploy an older ScoreMax package"
        )
    got = sha256_file(bundle)
    if got != EXPECTED_BUNDLE_SHA256:
        raise SystemExit(f"V669B_RUNTIME_BUNDLE_SHA_MISMATCH got={got} expected={EXPECTED_BUNDLE_SHA256}")

    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle, "r:gz") as tf:
        members = tf.getmembers()
        for member in members:
            resolved = (RUNTIME_DIR / member.name).resolve()
            if RUNTIME_DIR.resolve() not in resolved.parents and resolved != RUNTIME_DIR.resolve():
                raise SystemExit(f"V669B_RUNTIME_ARCHIVE_UNSAFE member={member.name}")
        tf.extractall(RUNTIME_DIR)

    manifest_path = RUNTIME_DIR / "V6_6_9B_PACKAGE_MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit("V669B_PACKAGE_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    text = json.dumps(manifest, sort_keys=True)
    if "6.6.9B" not in text:
        raise SystemExit("V669B_PACKAGE_MANIFEST_RELEASE_IDENTITY_MISSING")

    # Build a path -> SHA table from every manifest object carrying both fields.
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

    if EXCLUDED_NONRUNTIME_EXAMPLE in runtime_files:
        raise SystemExit("V669B_NONRUNTIME_EXAMPLE_SHOULD_NOT_BE_DEPLOYED")
    if len(runtime_files) != EXPECTED_RUNTIME_FILE_COUNT:
        raise SystemExit(
            f"V669B_RUNTIME_FILE_COUNT_MISMATCH got={len(runtime_files)} expected={EXPECTED_RUNTIME_FILE_COUNT}"
        )

    hero = RUNTIME_DIR / "static" / "scoremax_intelligence_hero.png"
    if not hero.is_file() or sha256_file(hero) != EXPECTED_HERO_SHA256:
        raise SystemExit("V669B_HERO_ASSET_SHA_MISMATCH")

    for required in (
        "app.py",
        "scoremax_production.py",
        "production_infrastructure_engine.py",
        "production_qualification_engine.py",
        "scoremax_integration_v1.py",
        "feature_availability_engine.py",
        "science_genius_engine.py",
        "digital_coach_engine.py",
        "requirements.txt",
    ):
        if not (RUNTIME_DIR / required).is_file():
            raise SystemExit(f"V669B_REQUIRED_RUNTIME_FILE_MISSING path={required}")

    print(
        "V669B_HOSTED_RUNTIME_VERIFIED "
        f"bundle_sha256={got} source_candidate_sha256={EXPECTED_SOURCE_ZIP_SHA256} "
        f"files={len(runtime_files)} release={EXPECTED_RELEASE} status=DEPENDENT_CANDIDATE_NOT_FROZEN"
    )


if __name__ == "__main__":
    main()
