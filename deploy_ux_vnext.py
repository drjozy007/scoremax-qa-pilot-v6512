from __future__ import annotations

import shutil
from pathlib import Path

import deploy_v669b_from_env

OUT = Path("scoremax_runtime_v669b")
OVERLAY = Path("ux_vnext_overlay")


def main() -> None:
    # First reconstruct and verify the exact qualified V6.6.11C runtime.
    deploy_v669b_from_env.main()

    # Then apply presentation-only staging files.
    for rel in ("templates/index.html", "static/ux_vnext.css", "static/ux_text_editor.js"):
        src = OVERLAY / rel
        dst = OUT / rel
        if not src.is_file():
            raise SystemExit(f"UX_VNEXT_OVERLAY_MISSING:{rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    base = OUT / "templates/base.html"
    text = base.read_text(encoding="utf-8")
    marker = '<link rel="stylesheet" href="{{url_for(\'static\',filename=\'styles.css\')}}">'
    inject = marker + '\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_vnext.css\')}}">'
    if marker not in text:
        raise SystemExit("UX_VNEXT_BASE_STYLESHEET_MARKER_MISSING")
    text = text.replace(marker, inject, 1)
    base.write_text(text, encoding="utf-8")

    # Presentation-only leakage gate for the public landing template.
    landing = (OUT / "templates/index.html").read_text(encoding="utf-8")
    forbidden = ("Power House", "Growth Engine", "qualification", "runtime", "release_id", "build_id")
    leaked = [term for term in forbidden if term.lower() in landing.lower()]
    if leaked:
        raise SystemExit("UX_VNEXT_PUBLIC_LEAKAGE:" + ",".join(leaked))

    print("SCOREMAX_UX_VNEXT_STAGING_MATERIALIZED base_release=6.6.11C presentation_only=true text_editor=true")


if __name__ == "__main__":
    main()
