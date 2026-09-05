from __future__ import annotations

import re
import shutil
from pathlib import Path

import deploy_v669b_from_env

OUT = Path("scoremax_runtime_v669b")
OVERLAY = Path("ux_vnext_overlay")


def replace_public_nav_pair(text: str, desktop_replacement: str, mobile_replacement: str) -> str:
    pattern = re.compile(
        r'<a href="\{\{url_for\(\'how_it_works\'\)\}\}">How It Works</a>'
        r'.*?'
        r'<a(?: class="(?:nav-cta|btn)")? href="\{\{url_for\(\'register\',role=\'student\'\)\}\}">Start Free</a>',
        re.S,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 2:
        raise SystemExit(f"UX_VNEXT_PUBLIC_NAV_PAIR_MISMATCH matches={len(matches)}")
    for match, replacement in ((matches[1], mobile_replacement), (matches[0], desktop_replacement)):
        text = text[:match.start()] + replacement + text[match.end():]
    return text


def copy_overlay(rel: str) -> None:
    src = OVERLAY / rel
    dst = OUT / rel
    if not src.is_file():
        raise SystemExit(f"UX_VNEXT_OVERLAY_MISSING:{rel}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    deploy_v669b_from_env.main()

    for rel in (
        "templates/index.html",
        "templates/ux_register_interest.html",
        "templates/ux_nominate_school.html",
        "static/ux_vnext.css",
        "static/ux_header_fix.css",
        "static/ux_structure_v2.css",
        "static/ux_text_editor.js",
        "ux_staging_routes.py",
    ):
        copy_overlay(rel)

    base = OUT / "templates/base.html"
    text = base.read_text(encoding="utf-8")

    marker = '<link rel="stylesheet" href="{{url_for(\'static\',filename=\'styles.css\')}}">'
    inject = (
        marker
        + '\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_vnext.css\')}}">'
        + '\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_header_fix.css\')}}">'
        + '\n<link rel="stylesheet" href="{{url_for(\'static\',filename=\'ux_structure_v2.css\')}}">'
    )
    if marker not in text:
        raise SystemExit("UX_VNEXT_BASE_STYLESHEET_MARKER_MISSING")
    text = text.replace(marker, inject, 1)

    old_brand = '<a class="brand" href="{{url_for(\'index\')}}">ScoreMax</a>'
    new_brand = '''<a class="brand ux-brand" href="{{url_for('index')}}" aria-label="ScoreMax home"><span class="ux-brand-mark" aria-hidden="true"><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i></span><span class="ux-brand-name"><span class="ux-brand-score">Score</span><span class="ux-brand-max">Max</span></span></a>'''
    if old_brand not in text:
        raise SystemExit("UX_VNEXT_BRAND_MARKER_MISSING")
    text = text.replace(old_brand, new_brand, 1)

    desktop_nav = '''<a href="{{url_for('about_page')}}">About Us</a><a href="{{url_for('how_it_works')}}">How It Works</a><a href="{{url_for('index')}}#programmes">Programmes</a><a href="/science-genius">Science Genius of the Year</a><a href="{{url_for('teacher_of_year_page')}}">Teacher of the Year</a><details class="ux-nav-dropdown"><summary>Get Involved</summary><div class="ux-nav-menu"><a href="/science-genius">Science Genius of the Year</a><a href="{{url_for('teacher_of_year_page')}}">Teacher of the Year</a><a href="{{url_for('ux_register_interest',programme='Student Council')}}">Student Council</a><a href="{{url_for('index')}}#impact">Our 10% Commitment</a><a href="{{url_for('ux_nominate_school')}}">Nominate a School</a><a href="{{url_for('ux_register_interest',programme='Education Impact supporter')}}">Support Education</a></div></details><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('faq_page')}}">Help</a><a href="{{url_for('login')}}">Login</a><a class="nav-cta" href="{{url_for('register',role='student')}}">Start Free</a>'''
    mobile_nav = '''<a href="{{url_for('about_page')}}">About Us</a><a href="{{url_for('how_it_works')}}">How It Works</a><a href="{{url_for('index')}}#programmes">Programmes</a><a href="/science-genius">Science Genius of the Year</a><a href="{{url_for('teacher_of_year_page')}}">Teacher of the Year</a><p class="mobile-menu-label">Get Involved</p><a href="{{url_for('ux_register_interest',programme='Student Council')}}">Student Council</a><a href="{{url_for('index')}}#impact">Our 10% Commitment</a><a href="{{url_for('ux_nominate_school')}}">Nominate a School</a><a href="{{url_for('ux_register_interest',programme='Education Impact supporter')}}">Support Education</a><p class="mobile-menu-label">Explore</p><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('faq_page')}}">Help</a><a href="{{url_for('login')}}">Login</a><a class="btn" href="{{url_for('register',role='student')}}">Start Free</a>'''

    text = replace_public_nav_pair(text, desktop_nav, mobile_nav)

    desktop_segment = text[text.find('<nav class="desktop-nav"'):text.find('</nav>', text.find('<nav class="desktop-nav"'))]
    if desktop_segment.count('>About Us</a>') != 1:
        raise SystemExit("UX_VNEXT_DESKTOP_ABOUT_DUPLICATE")
    for required_nav in ("Science Genius of the Year", "Teacher of the Year", "Get Involved"):
        if required_nav not in desktop_segment:
            raise SystemExit("UX_VNEXT_REQUIRED_TOP_NAV_MISSING:" + required_nav)

    script_marker = '<button id="backTop" class="back-top" aria-label="Back to top" title="Back to top">↑</button>'
    script_inject = script_marker + '\n{% if not session.get(\'user_id\') and request.endpoint == \'index\' %}<script src="{{url_for(\'static\',filename=\'ux_text_editor.js\')}}"></script>{% endif %}'
    if script_marker not in text:
        raise SystemExit("UX_VNEXT_TEXT_EDITOR_SCRIPT_MARKER_MISSING")
    text = text.replace(script_marker, script_inject, 1)
    base.write_text(text, encoding="utf-8")

    app_py = OUT / "app.py"
    app_text = app_py.read_text(encoding="utf-8")
    public_pattern = re.compile(r"public_endpoints\s*=\s*\{(?P<body>[^}]*)\}")
    public_match = public_pattern.search(app_text)
    if not public_match:
        raise SystemExit("UX_VNEXT_PUBLIC_ENDPOINT_SET_MISSING")
    body = public_match.group("body")
    for endpoint in ("ux_register_interest", "ux_nominate_school"):
        if f"'{endpoint}'" not in body:
            body = body.rstrip() + f",'{endpoint}'"
    app_text = app_text[:public_match.start()] + "public_endpoints={" + body + "}" + app_text[public_match.end():]

    installer_marker = "\nif __name__=='__main__':\n"
    installer = "\nfrom ux_staging_routes import install_ux_staging_routes\ninstall_ux_staging_routes(app)\n"
    if installer_marker not in app_text:
        raise SystemExit("UX_VNEXT_ROUTE_INSTALL_MARKER_MISSING")
    app_text = app_text.replace(installer_marker, installer + installer_marker, 1)
    app_py.write_text(app_text, encoding="utf-8")

    landing = (OUT / "templates/index.html").read_text(encoding="utf-8")
    forbidden = ("Power House", "Growth Engine", "qualification", "runtime", "release_id", "build_id")
    leaked = [term for term in forbidden if term.lower() in landing.lower()]
    if leaked:
        raise SystemExit("UX_VNEXT_PUBLIC_LEAKAGE:" + ",".join(leaked))

    required_landing = (
        "PREPARING FOR", "MDCAT", "ECAT", "FSc", "Matric",
        "Foundation", "Exam Ready", "Advanced", "Distinction", "Expert", "Elite",
        "Mastery", "Weak Areas", "Practice", "Past Papers", "Mock Exams", "Study Plan", "Progress", "Exam Centre", "Daily Spark",
        "GET INVOLVED", "Science Genius", "Student Council", "Teacher of the Year",
        "SCOREMAX IMPACT", "Nominate a school", "Register interest",
    )
    missing = [term for term in required_landing if term not in landing]
    if missing:
        raise SystemExit("UX_VNEXT_REQUIRED_PUBLIC_CONTENT_MISSING:" + ",".join(missing))
    if "Choose the route you are preparing for." in landing:
        raise SystemExit("UX_VNEXT_REMOVED_PROGRAMME_SECTION_STILL_PRESENT")

    print("SCOREMAX_UX_VNEXT_STAGING_MATERIALIZED base_release=6.6.11C staging_routes=true public_nav=flagship_tabs larger_nav=true get_involved=expanded feature_showcase=true daily_spark_collapsed=true")


if __name__ == "__main__":
    main()
