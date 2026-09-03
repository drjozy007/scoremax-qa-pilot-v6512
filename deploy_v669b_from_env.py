from __future__ import annotations

import base64
import hashlib
import json
import lzma
import shutil
import subprocess
from pathlib import Path

BASE = Path("hosted_runtime_base_v6512")
OUT = Path("scoremax_runtime_v669b")
PATHS_FILE = Path("qualification/v6610f_runtime_paths.json")
MANIFEST_FILE = Path("qualification/v6611c_direct_patch_manifest.json")
PATCH_DIR = Path("qualification/v6611c_direct_patch")
ADDED_11C = {
    "account_security_engine.py",
    "production_startup_engine.py",
    "simple_onboarding_engine.py",
    "sqlite_mutation_engine.py",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def governed_paths() -> set[str]:
    paths = set(json.loads(PATHS_FILE.read_text(encoding="utf-8")))
    paths.discard("README_SCOREMAX_V6_6_9B.md")
    paths.discard("V6_6_9B_PACKAGE_MANIFEST.json")
    paths.add("production_content_seed_policy.py")
    paths.update(ADDED_11C)
    return paths


def tree_digest(paths: set[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(paths):
        path = OUT / rel
        h.update(f"{rel}\0{sha256_file(path)}\0{path.stat().st_size}\n".encode())
    return h.hexdigest()


def main() -> None:
    if not BASE.is_dir():
        raise SystemExit("V6611C_DIRECT_BASELINE_MISSING")
    if not PATHS_FILE.is_file() or not MANIFEST_FILE.is_file():
        raise SystemExit("V6611C_DIRECT_GOVERNANCE_INPUT_MISSING")

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    paths = governed_paths()
    expected_count = int(manifest["runtime_file_count"])
    if len(paths) != expected_count:
        raise SystemExit(f"V6611C_DIRECT_PATH_CONTRACT_INVALID got={len(paths)} expected={expected_count}")

    parts = sorted(PATCH_DIR.glob("part*.b64"))
    if len(parts) != 12:
        raise SystemExit(f"V6611C_DIRECT_PATCH_PART_COUNT_MISMATCH got={len(parts)} expected=12")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    try:
        patch_xz = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"V6611C_DIRECT_PATCH_BASE64_INVALID:{type(exc).__name__}") from exc
    if len(patch_xz) != int(manifest["patch_xz_size"]):
        raise SystemExit("V6611C_DIRECT_PATCH_XZ_SIZE_MISMATCH")
    if sha256_bytes(patch_xz) != manifest["patch_xz_sha256"]:
        raise SystemExit("V6611C_DIRECT_PATCH_XZ_SHA_MISMATCH")
    try:
        patch = lzma.decompress(patch_xz)
    except Exception as exc:
        raise SystemExit(f"V6611C_DIRECT_PATCH_XZ_INVALID:{type(exc).__name__}") from exc
    if sha256_bytes(patch) != manifest["patch_sha256"]:
        raise SystemExit("V6611C_DIRECT_PATCH_SHA_MISMATCH")

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for rel in sorted(paths):
        source = BASE / rel
        if source.is_file():
            target = OUT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    result = subprocess.run(
        ["patch", "-d", str(OUT), "-p2", "--batch", "--forward"],
        input=patch,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise SystemExit("V6611C_DIRECT_PATCH_APPLY_FAILED:" + result.stdout.decode(errors="replace")[-2400:])

    actual = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file())
    if actual != sorted(paths):
        missing = sorted(paths - set(actual))
        extra = sorted(set(actual) - paths)
        raise SystemExit(
            f"V6611C_DIRECT_RUNTIME_PATH_SET_MISMATCH actual={len(actual)} expected={len(paths)} "
            f"missing={missing[:8]} extra={extra[:8]}"
        )

    digest = tree_digest(paths)
    if digest != manifest["final_runtime_tree_sha256"]:
        raise SystemExit(
            f"V6611C_DIRECT_RUNTIME_TREE_SHA_MISMATCH got={digest} expected={manifest['final_runtime_tree_sha256']}"
        )

    app = (OUT / "app.py").read_text(encoding="utf-8")
    integ = (OUT / "scoremax_integration_v1.py").read_text(encoding="utf-8")
    if "SCOREMAX_RELEASE_VERSION='6.6.11C'" not in app:
        raise SystemExit("V6611C_DIRECT_APP_RELEASE_IDENTITY_MISSING")
    if "SCOREMAX_INTEGRATION_RELEASE='6.6.11C'" not in integ:
        raise SystemExit("V6611C_DIRECT_INTEGRATION_RELEASE_IDENTITY_MISSING")

    procfile = (OUT / "Procfile").read_text(encoding="utf-8").splitlines()
    if not procfile or procfile[0].strip() != "web: python scoremax_production_entrypoint.py":
        raise SystemExit("V6611C_DIRECT_PROCFILE_NOT_CANONICAL")
    render_cfg = (OUT / "render.production.candidate.yaml").read_text(encoding="utf-8")
    if "startCommand: python scoremax_production_entrypoint.py" not in render_cfg:
        raise SystemExit("V6611C_DIRECT_RENDER_START_NOT_CANONICAL")
    requirements = (OUT / "requirements.txt").read_text(encoding="utf-8")
    for required in ("Flask==3.1.3", "Werkzeug==3.1.6"):
        if required not in requirements:
            raise SystemExit("V6611C_DIRECT_DEPENDENCY_PIN_MISSING:" + required)

    print(
        "V6611C_HOSTED_RUNTIME_VERIFIED",
        "lineage=V6512_DIRECT_TO_V6611C_SHA_BOUND_PATCH",
        f"source_zip_sha256={manifest['source_candidate_sha256']}",
        f"patch_xz_sha256={manifest['patch_xz_sha256']}",
        f"patch_sha256={manifest['patch_sha256']}",
        f"runtime_tree_sha256={digest}",
        f"files={len(paths)}",
        "release=6.6.11C",
        "status=PRE_DOMAIN_PREQUALIFICATION_CANDIDATE_NOT_FROZEN",
    )


if __name__ == "__main__":
    main()
