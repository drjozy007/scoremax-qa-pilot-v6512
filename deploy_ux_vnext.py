from __future__ import annotations

import json
import subprocess
import shutil
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


def _install_save_scoremax_prompt() -> None:
    source_static = Path("ux_vnext_overlay") / "static"
    target_static = OUT / "static"
    target_static.mkdir(parents=True, exist_ok=True)
    assets = (
        "scoremax.webmanifest",
        "scoremax_install.css",
        "scoremax_install.js",
        "scoremax-icon-32.png",
        "scoremax-icon-180.png",
        "scoremax-icon-192.png",
        "scoremax-icon-512.png",
        "scoremax-icon-maskable-512.png",
    )
    for name in assets:
        src = source_static / name
        if not src.is_file():
            raise SystemExit("SCOREMAX_INSTALL_ASSET_MISSING:" + name)
        shutil.copy2(src, target_static / name)

    base_path = OUT / "templates" / "base.html"
    base = base_path.read_text(encoding="utf-8")
    if "scoremax-install-metadata" not in base:
        head_patch = """<!-- scoremax-install-metadata -->
<link rel="manifest" href="{{url_for('static',filename='scoremax.webmanifest')}}">
<link rel="icon" type="image/png" sizes="32x32" href="{{url_for('static',filename='scoremax-icon-32.png')}}">
<link rel="apple-touch-icon" sizes="180x180" href="{{url_for('static',filename='scoremax-icon-180.png')}}">
<meta name="theme-color" content="#2563eb">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="ScoreMax">
<link rel="stylesheet" href="{{url_for('static',filename='scoremax_install.css')}}">
"""
        if "</head>" not in base:
            raise SystemExit("SCOREMAX_INSTALL_HEAD_MARKER_MISSING")
        base = base.replace("</head>", head_patch + "</head>", 1)

    if "scoremaxInstallNudge" not in base:
        body_patch = """
{% if request.endpoint not in ['take_test_v4','assessment_review_v4','qa_synthetic_session'] %}
<aside id="scoremaxInstallNudge" hidden aria-label="Save ScoreMax to this device">
  <span class="scoremax-install-mark" aria-hidden="true"><i></i><i></i><i></i></span>
  <span class="scoremax-install-copy"><strong>Save ScoreMax</strong><span>Keep ScoreMax as an icon for one-tap access.</span></span>
  <button id="scoremaxInstallButton" type="button">Save</button>
</aside>
<div id="scoremaxInstallHelp" hidden role="dialog" aria-modal="true" aria-labelledby="scoremaxInstallHelpTitle">
  <section class="scoremax-install-help-card">
    <span class="scoremax-install-mark" aria-hidden="true"><i></i><i></i><i></i></span>
    <h2 id="scoremaxInstallHelpTitle">Save ScoreMax to this device</h2>
    <p>Follow these steps once. ScoreMax will then appear with its own icon on your Home Screen, Dock or desktop app list.</p>
    <ol id="scoremaxInstallSteps" class="scoremax-install-steps"></ol>
    <div class="scoremax-install-help-actions">
      <button id="scoremaxInstallDone" type="button">Done - saved</button>
      <button id="scoremaxInstallClose" type="button">Back</button>
    </div>
  </section>
</div>
<script src="{{url_for('static',filename='scoremax_install.js')}}" defer></script>
{% endif %}
<!-- /scoremax-install-prompt -->
"""
        if "</body>" not in base:
            raise SystemExit("SCOREMAX_INSTALL_BODY_MARKER_MISSING")
        base = base.replace("</body>", body_patch + "</body>", 1)

    required = (
        "scoremax.webmanifest",
        "scoremax-icon-180.png",
        "scoremaxInstallNudge",
        "scoremaxInstallButton",
        "scoremax_install.js",
        "apple-mobile-web-app-title",
    )
    missing = [token for token in required if token not in base]
    if missing:
        raise SystemExit("SCOREMAX_INSTALL_BASE_CONTROL_MISSING:" + ",".join(missing))
    base_path.write_text(base, encoding="utf-8")


def main() -> None:
    # Reuse the accepted UX materializer unchanged, replacing only its exact
    # parent reconstruction step with 11C -> already-qualified 11D bridge.
    ux.deploy_v669b_from_env.main = _apply_qualified_v6611d_parent
    ux.main()
    _install_save_scoremax_prompt()

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

    install_base = (OUT / "templates" / "base.html").read_text(encoding="utf-8")
    if "scoremaxInstallNudge" not in install_base or "scoremax.webmanifest" not in install_base:
        raise SystemExit("SCOREMAX_INSTALL_POSTBUILD_ASSERTION_FAILED")

    compile(app, str(app_path), "exec")
    compile(bridge, str(bridge_path), "exec")
    print(
        "SCOREMAX_UX_VNEXT_V6611D_COMPATIBILITY_PASS "
        "parent_release=6.6.11D ux_overlay_preserved=true "
        "ph_import_staged_ack=true ph_activation_ack=true withdrawal_bridge=true "
        "learner_cross_system_calls=false release_authority=false "
        "save_scoremax_prompt=true pwa_manifest=true apple_touch_icon=true",
        flush=True,
    )


if __name__ == "__main__":
    main()
