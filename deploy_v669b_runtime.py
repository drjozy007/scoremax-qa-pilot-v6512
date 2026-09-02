from __future__ import annotations

import shutil
from pathlib import Path

import deploy_v6610f_from_env

SOURCE = Path("scoremax_runtime_v6610f")
TARGET = Path("scoremax_runtime_v669b")


def main() -> None:
    """Materialize the exact verified V6.6.10F bridge at the legacy build target path.

    The Render service build command is intentionally unchanged. V6.6.10F is rebuilt
    from its historical SHA-bound Git overlay, independently verifies its full runtime
    tree, and only then becomes the input to the existing V6.6.10G delta verifier.
    """
    deploy_v6610f_from_env.main()
    if not SOURCE.is_dir():
        raise SystemExit("V6610F_VERIFIED_RUNTIME_MISSING_AFTER_RECONSTRUCTION")
    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.move(str(SOURCE), str(TARGET))
    print("V6610F_BRIDGE_MATERIALIZED_AT_LEGACY_HOSTED_TARGET", f"path={TARGET}")


if __name__ == "__main__":
    main()
