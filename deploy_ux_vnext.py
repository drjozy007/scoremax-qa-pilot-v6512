from __future__ import annotations

import re
import shutil
from pathlib import Path

import deploy_v669b_from_env

OUT = Path("scoremax_runtime_v669b")
OVERLAY = Path("ux_vnext_overlay")


def replace_public_nav(text: str, replacement: str, *, occurrence: int) -> str:
    pattern = re.compile(
        r'<a href="\{\{url_for\(\'how_it_works\'\)\}\}">How It Works</a>'
        r'.*?'
        r'<a(?: class="(?:nav-cta|btn)")? href="\{\{url_for\(\'register\',role=\'student\'\)\}\}">Start Free</a>',
        re.S,
    )
    matches = list(pattern.finditer(text))
    if len(matches) < occurrence:
        raise SystemExit(f"UX_VNEXT_PUBLIC_NAV_MATCH_MISSING occurrence={occurrence} matches={len(matches)}")
    m = matches[occurrence - 1]
    return text[:m.start()] + replacement + text[m.end():]


def main() -> None:
    deploy_v669b_from_env.main()

    for rel in (
        "templates/index.html",
        "static/ux_vnext.css",
        "static/ux_header_fix.css",
        "static/ux_text_editor.js",
    ):
        src = OVERLAY / rel
        dst = OUT / rel
        if not src.is_file():
            raise SystemExit(f"UX_VNEXT_OVERLAY_MISSING:{rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    base = OUT / "templates/base.html"
    text = base.read_text(encoding="utf-8")

    marker = '<link rel="stylesheet" href="{{url_for(\'static\',filename=\'styles.css\')}}">'
    inject = marker + '\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_vnext.css\')}}">\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_header_fix.css\')}}">'
    if marker not in text:
        raise SystemExit("UX_VNEXT_BASE_STYLESHEET_MARKER_MISSING")
    text = text.replace(marker, inject, 1)

    old_brand = '<a class="brand" href="{{url_for(\'index\')}}">ScoreMax</a>'
    new_brand = '''<a class="brand ux-brand" href="{{url_for('index')}}" aria-label="ScoreMax home"><span class="ux-brand-mark" aria-hidden="true"><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i></span><span class="ux-brand-name"><span class="ux-brand-score">Score</span><span class="ux-brand-max">Max</span></span></a>'''
    if old_brand not in text:
        raise SystemExit("UX_VNEXT_BRAND_MARKER_MISSING")
    text = text.replace(old_brand, new_brand, 1)

    desktop_nav = '''<a href="{{url_for('index')}}#choose-programme">Programmes</a><a href="{{url_for('how_it_works')}}">How It Works</a><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('updates_page')}}">Updates</a><a href="{{url_for('about_page')}}">About</a><a href="{{url_for('faq_page')}}">Help</a><a href="{{url_for('login')}}">Login</a><a class="nav-cta" href="{{url_for('register',role='student')}}">Start Free</a>'''
    mobile_nav = '''<a href="{{url_for('index')}}#choose-programme">Programmes</a><a href="{{url_for('how_it_works')}}">How It Works</a><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('updates_page')}}">Updates</a><a href="{{url_for('about_page')}}">About</a><a href="{{url_for('faq_page')}}">Help</a><a href="{{url_for('login')}}">Login</a><a class="btn" href="{{url_for('register',role='student')}}">Start Free</a>'''

    text = replace_public_nav(text, desktop_nav, occurrence=1)
    text = replace_public_nav(text, mobile_nav, occurrence=1)

    script_marker = '<button id="backTop" class="back-top" aria-label="Back to top" title="Back to top">↑</button>'
    script_inject = script_marker + '\n{% if not session.get(\'user_id\') and request.endpoint == \'index\' %}<script src="{{url_for(\'static\',filename=\'ux_text_editor.js\')}}"></script>{% endif %}'
    if script_marker not in text:
        raise SystemExit("UX_VNEXT_TEXT_EDITOR_SCRIPT_MARKER_MISSING")
    text = text.replace(script_marker, script_inject, 1)

    base.write_text(text, encoding="utf-8")

    landing = (OUT / "templates/index.html").read_text(encoding="utf-8")
    forbidden = ("Power House", "Growth Engine", "qualification", "runtime", "release_id", "build_id")
    leaked = [term for term in forbidden if term.lower() in landing.lower()]
    if leaked:
        raise SystemExit("UX_VNEXT_PUBLIC_LEAKAGE:" + ",".join(leaked))

    print("SCOREMAX_UX_VNEXT_STAGING_MATERIALIZED base_release=6.6.11C presentation_only=true text_editor=true public_nav=ordered header_collision_fix=true brand_lockup=true")


if __name__ == "__main__":
    main()
