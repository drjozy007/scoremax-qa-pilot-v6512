from __future__ import annotations

import json
import subprocess
from pathlib import Path

import deploy_ux_vnext_c as ux

OUT = Path("scoremax_runtime_v669b")
_V6611C_PARENT_MAIN = ux.deploy_v669b_from_env.main


def _apply_qualified_v6611d_parent() -> None:
    # Preserve the exact SHA-bound 6.6.11C reconstruction function before
    # substituting this compatibility hook into the frozen UX materializer.
    _V6611C_PARENT_MAIN()
    result = subprocess.run(
        ["python", "apply_v6611d_bridge_overlay.py", str(OUT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit("UX_VNEXT_V6611D_PARENT_APPLY_FAILED:" + result.stdout[-3000:])
    print(result.stdout.strip(), flush=True)

    app = (OUT / "app.py").read_text(encoding="utf-8")
    integration = (OUT / "scoremax_integration_v1.py").read_text(encoding="utf-8")
    marker_path = OUT / "V6611D_PH_BRIDGE_MARKER.json"
    if "SCOREMAX_RELEASE_VERSION='6.6.11D'" not in app:
        raise SystemExit("UX_VNEXT_V6611D_APP_RELEASE_IDENTITY_MISSING")
    if "SCOREMAX_INTEGRATION_RELEASE='6.6.11D'" not in integration:
        raise SystemExit("UX_VNEXT_V6611D_INTEGRATION_RELEASE_IDENTITY_MISSING")
    if not marker_path.is_file():
        raise SystemExit("UX_VNEXT_V6611D_MARKER_MISSING")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("marker") != "SM-PH-BRIDGE-V6611D-1":
        raise SystemExit("UX_VNEXT_V6611D_MARKER_INVALID")
    if marker.get("release_authority_changed") is not False:
        raise SystemExit("UX_VNEXT_V6611D_RELEASE_AUTHORITY_CHANGED")
    if marker.get("cross_system_calls_on_learner_request") is not False:
        raise SystemExit("UX_VNEXT_V6611D_LEARNER_REQUEST_BOUNDARY_CHANGED")


def main() -> None:
    # Reuse the accepted UX materializer unchanged, replacing only its exact
    # parent reconstruction step with 11C -> already-qualified 11D bridge.
    ux.deploy_v669b_from_env.main = _apply_qualified_v6611d_parent
    ux.main()

    app_path = OUT / "app.py"
    bridge_path = OUT / "scoremax_ph_bridge_v6611d.py"
    marker_path = OUT / "V6611D_PH_BRIDGE_MARKER.json"
    app = app_path.read_text(encoding="utf-8")
    bridge = bridge_path.read_text(encoding="utf-8")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))

    required_app = (
        "SCOREMAX_RELEASE_VERSION='6.6.11D'",
        "import scoremax_ph_bridge_v6611d as ph_bridge_v6611d",
        "/api/integration/v1/power-house/question-withdrawals",
        "install_student_batch(app)",
        "install_student_mastery_strip(app)",
    )
    missing = [token for token in required_app if token not in app]
    if missing:
        raise SystemExit("UX_VNEXT_V6611D_FINAL_APP_CONTROL_MISSING:" + ",".join(missing))
    for token in ("IMPORTED_STAGED", "ACTIVATED_LEARNER_LIVE", "historical_attempts_preserved"):
        if token not in bridge:
            raise SystemExit("UX_VNEXT_V6611D_BRIDGE_CONTROL_MISSING:" + token)
    if marker.get("release") != "6.6.11D":
        raise SystemExit("UX_VNEXT_V6611D_FINAL_MARKER_RELEASE_MISMATCH")

    compile(app, str(app_path), "exec")
    compile(bridge, str(bridge_path), "exec")
    print(
        "SCOREMAX_UX_VNEXT_V6611D_COMPATIBILITY_PASS "
        "parent_release=6.6.11D ux_overlay_preserved=true "
        "ph_import_staged_ack=true ph_activation_ack=true withdrawal_bridge=true "
        "learner_cross_system_calls=false release_authority=false",
        flush=True,
    )


if __name__ == "__main__":
    main()
