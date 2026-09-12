from __future__ import annotations

import re
from pathlib import Path


ADMIN_STYLE = r'''<style id="ux-admin-workspace-v1-style">
.ux-admin-home{max-width:1180px;margin:0 auto}.ux-admin-hero{border-top:6px solid #2f7f7d;background:linear-gradient(135deg,#eef9f7,#fff 62%,#fff8e9);padding:30px}.ux-admin-hero h1{margin:.15rem 0 .45rem;font-size:clamp(2rem,4vw,3rem);color:#173f3d}.ux-admin-hero p{max-width:820px;color:#586b68}.ux-admin-boundary{border-left:5px solid #d6a74d;background:#fffaf0}.ux-admin-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.ux-admin-kpis .metric{display:flex;flex-direction:column;gap:6px;min-height:92px}.ux-admin-kpis .metric span{color:#667875;font-size:.78rem}.ux-admin-kpis .metric strong{font-size:1.7rem;color:#173f3d}.ux-admin-sections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.ux-admin-section{margin:0}.ux-admin-section h2{margin:.1rem 0 .35rem;color:#205f5c}.ux-admin-section p{margin:.2rem 0 1rem;color:#667875}.ux-admin-actions{display:flex;gap:8px;flex-wrap:wrap}.ux-admin-actions a{margin:0!important}.ux-admin-secondary{margin-top:16px}.ux-admin-secondary .actions{display:flex;gap:8px;flex-wrap:wrap}.ux-admin-secondary .actions a{margin:0!important}.ux-admin-nav-menu{position:relative;margin-left:14px}.ux-admin-nav-menu summary{cursor:pointer;list-style:none;font-weight:700}.ux-admin-nav-menu summary::-webkit-details-marker{display:none}.ux-admin-nav-menu>div{position:absolute;right:0;top:calc(100% + 8px);z-index:90;min-width:220px;padding:10px;background:#fff;border:1px solid #dfe8e7;border-radius:12px;box-shadow:0 12px 30px rgba(15,23,42,.14)}.ux-admin-nav-menu>div a{display:block;margin:0!important;padding:9px 10px;border-radius:8px}.ux-admin-nav-menu>div a:hover{background:#f3f8f7}
@media(max-width:900px){.ux-admin-kpis{grid-template-columns:repeat(2,1fr)}.ux-admin-sections{grid-template-columns:1fr}}
@media(max-width:560px){.ux-admin-kpis{grid-template-columns:1fr}.ux-admin-hero{padding:22px}}
</style>'''


def _replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    rx=re.compile(pattern,re.S)
    matches=list(rx.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'UX_ADMIN_{label}_MISMATCH:{len(matches)}')
    return rx.sub(replacement,text,count=1)


def _simplify_admin_navigation(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    desktop='''{% elif session.get('role')=='admin' %}
        <a href="{{url_for('admin_dashboard')}}">Home</a><a href="{{url_for('admin_users')}}">Users</a><a href="{{url_for('admin_analytics')}}">Analytics</a><a href="{{url_for('admin_payments')}}">Payments</a><a href="{{url_for('admin_referrals')}}">Referrals</a><a href="{{url_for('admin_integration_health')}}">Integration</a><a href="{{url_for('admin_exams')}}">Exams</a><details class="ux-admin-nav-menu"><summary>More</summary><div><a href="{{url_for('admin_challenges')}}">Challenges</a><a href="{{url_for('admin_daily_spark')}}">Daily Spark</a><a href="{{url_for('admin_community')}}">Community</a><a href="{{url_for('admin_knowledge')}}">Knowledge</a><a href="{{url_for('admin_learning_capsules')}}">Learning Capsules</a><a href="{{url_for('admin_sustainability')}}">Sustainability</a><a href="{{url_for('admin_social_links')}}">Social Links</a></div></details><a href="{{url_for('logout')}}">Logout</a>
      {% else %}'''
    text=_replace_once(text,r"\{% elif session\.get\('role'\)=='admin' %\}.*?\{% else %\}",desktop,'DESKTOP_NAV')

    mobile='''{% elif session.get('user_id') and session.get('role')=='admin' %}
    <a href="{{url_for('admin_dashboard')}}">Admin Home</a><a href="{{url_for('admin_users')}}">Users</a><a href="{{url_for('admin_analytics')}}">Analytics</a><a href="{{url_for('admin_payments')}}">Payments</a><a href="{{url_for('admin_referrals')}}">Referrals</a><a href="{{url_for('admin_integration_health')}}">Integration</a><a href="{{url_for('admin_exams')}}">Exams</a><a href="{{url_for('admin_challenges')}}">Challenges</a><a href="{{url_for('admin_daily_spark')}}">Daily Spark</a><a href="{{url_for('admin_community')}}">Community</a><a href="{{url_for('logout')}}">Logout</a>
  {% elif session.get('user_id') %}'''
    text=_replace_once(text,r"\{% elif session\.get\('user_id'\) and session\.get\('role'\)=='parent' %\}(.*?)\{% elif session\.get\('user_id'\) %\}",lambda m: "{% elif session.get('user_id') and session.get('role')=='parent' %}"+m.group(1)+mobile,'MOBILE_NAV')

    if 'ux-admin-workspace-v1-style' not in text:
        if '</head>' not in text: raise SystemExit('UX_ADMIN_HEAD_MISSING')
        text=text.replace('</head>',ADMIN_STYLE+'\n</head>',1)
    for token in ("url_for('admin_dashboard')","url_for('admin_users')","url_for('admin_integration_health')",'>Logout</a>','ux-admin-nav-menu'):
        if token not in text: raise SystemExit('UX_ADMIN_NAV_POSTCHECK_MISSING:'+token)
    # Academic-review/reviewer controls must not be in the normal admin navigation.
    admin_block=text[text.find("session.get('role')=='admin'"):text.find("{% else %}",text.find("session.get('role')=='admin'"))]
    for forbidden in ('Reviewer Workspace','Question Families','Governance Audit','Direct Intake','Power House Bridge'):
        if forbidden in admin_block: raise SystemExit('UX_ADMIN_LEGACY_NAV_SURVIVED:'+forbidden)
    path.write_text(text,encoding='utf-8')


def _replace_admin_home(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    if "{% extends 'base.html' %}" not in text:
        raise SystemExit('UX_ADMIN_HOME_BASELINE_MISSING')
    replacement='''{% extends 'base.html' %}{% block title %}Admin · ScoreMax{% endblock %}{% block content %}
<section class="ux-admin-home">
  <section class="card ux-admin-hero"><p class="eyebrow">SCOREMAX ADMIN</p><h1>Platform operations</h1><p>Manage accounts, access, payments, product operations and system integration. Academic question review and academic release authority remain in Power House.</p></section>
  <section class="card ux-admin-boundary"><strong>System boundary</strong><p>ScoreMax controls learner/product operations and activates exact Power House releases after governed admission. Academic review, rectification and approval are not performed here.</p><a class="btn small" href="{{url_for('admin_integration_health')}}">Open integration health</a></section>
  <section class="ux-admin-kpis">
    <div class="card metric"><span>Students</span><strong>{{m.students}}</strong></div>
    <div class="card metric"><span>Teachers</span><strong>{{m.teachers}}</strong></div>
    <div class="card metric"><span>Institutions</span><strong>{{m.institutions}}</strong></div>
    <div class="card metric"><span>Active subscriptions</span><strong>{{m.active_subscriptions}}</strong></div>
  </section>
  <section class="ux-admin-sections">
    <article class="card ux-admin-section"><p class="eyebrow">PEOPLE & ACCESS</p><h2>Accounts</h2><p>Manage user status, pilot access and institutions.</p><div class="ux-admin-actions"><a class="btn" href="{{url_for('admin_users')}}">Users</a><a class="btn alt" href="{{url_for('institutions')}}">Institutions</a></div></article>
    <article class="card ux-admin-section"><p class="eyebrow">COMMERCIAL</p><h2>Payments & referrals</h2><p>Manage subscriptions, payments, access packages and referral rewards.</p><div class="ux-admin-actions"><a class="btn" href="{{url_for('admin_payments')}}">Payments</a><a class="btn alt" href="{{url_for('admin_referrals')}}">Referrals</a></div></article>
    <article class="card ux-admin-section"><p class="eyebrow">OPERATIONS</p><h2>Analytics & integration</h2><p>Monitor platform activity and operational exceptions across connected systems.</p><div class="ux-admin-actions"><a class="btn" href="{{url_for('admin_analytics')}}">Analytics</a><a class="btn alt" href="{{url_for('admin_integration_health')}}">Integration health</a></div></article>
    <article class="card ux-admin-section"><p class="eyebrow">ASSESSMENT DELIVERY</p><h2>Exams & challenges</h2><p>Operate learner-facing exam simulations and voluntary competitions.</p><div class="ux-admin-actions"><a class="btn" href="{{url_for('admin_exams')}}">Exam Centre</a><a class="btn alt" href="{{url_for('admin_challenges')}}">Challenges</a></div></article>
  </section>
  <section class="card ux-admin-secondary"><p class="eyebrow">PRODUCT OPERATIONS</p><h2>Other controls</h2><div class="actions"><a class="btn alt" href="{{url_for('admin_daily_spark')}}">Daily Spark</a><a class="btn alt" href="{{url_for('admin_community')}}">Community</a><a class="btn alt" href="{{url_for('admin_knowledge')}}">Knowledge</a><a class="btn alt" href="{{url_for('admin_learning_capsules')}}">Learning Capsules</a><a class="btn alt" href="{{url_for('admin_sustainability')}}">Sustainability</a><a class="btn alt" href="{{url_for('admin_social_links')}}">Social Links</a></div></section>
</section>
{% endblock %}
'''
    path.write_text(replacement,encoding='utf-8')


def apply_admin_workspace(root: Path) -> None:
    base=root/'templates'/'base.html'
    home=root/'templates'/'admin.html'
    if not base.is_file() or not home.is_file():
        raise SystemExit('UX_ADMIN_REQUIRED_TEMPLATE_MISSING')
    _simplify_admin_navigation(base)
    _replace_admin_home(home)
    base_text=base.read_text(encoding='utf-8')
    home_text=home.read_text(encoding='utf-8')
    for token in ('SCOREMAX ADMIN','System boundary','Academic question review and academic release authority remain in Power House.',"url_for('admin_integration_health')"):
        if token not in home_text: raise SystemExit('UX_ADMIN_HOME_POSTCHECK_MISSING:'+token)
    print('SCOREMAX_UX_ADMIN_WORKSPACE_V1_PASS nav=simplified mobile_admin=true power_house_boundary=true legacy_routes_preserved=true',flush=True)
