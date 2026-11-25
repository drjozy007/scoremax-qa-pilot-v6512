"""Additional native browser-form acceptance, after native_login_replay.py setup.

Runs in the SAME disposable Python process with existing synthetic users.
Requires globals app, sm, users, paced_get, paced_post, csrf, login, BASEURL, record.
"""
with app.test_client() as family_client:
    login(family_client,1)
    child_view=paced_get(family_client,'/uk11/api/me/guardian-onboarding',base_url=BASEURL)
    assert child_view.status_code==200,('CHILD_GUARDIAN_PAGE',child_view.status_code)
    html=child_view.get_data(as_text=True)
    assert 'Parent or guardian access' in html
    assert 'No parent or guardian is currently linked' in html
    assert 'FSc' not in html and 'MDCAT' not in html
    assert 'no-store' in child_view.headers.get('Cache-Control','')
    record('native_child_parent_access_view',status=child_view.status_code,private=True)

    paced_get(family_client,'/logout',base_url=BASEURL)
    login(family_client,3)
    empty_parent=paced_get(family_client,'/uk11/api/guardian/home',base_url=BASEURL)
    assert empty_parent.status_code==200,('EMPTY_PARENT_UK_VIEW',empty_parent.status_code)
    assert 'No linked UK 11+ learners yet' in empty_parent.get_data(as_text=True)
    link=paced_post(family_client,'/parent/link-student',base_url=BASEURL,data={
        '_csrf_token':csrf(family_client),
        'student_email':'uk11native1@example.test',
        'link_code':'P-SYNTHETIC-UK11-ONLY','relationship':'Guardian'
    },follow_redirects=False)
    assert link.status_code==302,('NATIVE_LINK',link.status_code)
    parent_home=paced_get(family_client,'/parent',base_url=BASEURL,follow_redirects=False)
    assert parent_home.status_code==302 and parent_home.headers.get('Location')=='/uk11/api/guardian/home'
    family_home=paced_get(family_client,'/uk11/api/guardian/home',base_url=BASEURL)
    family_html=family_home.get_data(as_text=True)
    assert family_home.status_code==200 and 'Synthetic UK 1' in family_html
    assert 'Record acknowledgement' in family_html and 'Withdraw acknowledgement' in family_html
    assert all(s not in family_html for s in ('FSc','MDCAT','Chemistry','Biology'))
    assert 'no-store' in family_home.headers.get('Cache-Control','')
    form_path=f'/uk11/api/guardian/students/{users[0]}/form-decision'
    no_csrf=paced_post(family_client,form_path,base_url=BASEURL,data={
        'text_version':'UK11-ONBOARDING-CANDIDATE-20261125','decision':'APPROVED'
    },follow_redirects=False)
    assert no_csrf.status_code==400,('BROWSER_FORM_CSRF',no_csrf.status_code)
    stale=paced_post(family_client,form_path,base_url=BASEURL,data={
        '_csrf_token':csrf(family_client),'text_version':'INVALID','decision':'APPROVED'
    },follow_redirects=False)
    assert stale.status_code==400,('BROWSER_FORM_TEXT_VERSION',stale.status_code)
    approved=paced_post(family_client,form_path,base_url=BASEURL,data={
        '_csrf_token':csrf(family_client),'text_version':'UK11-ONBOARDING-CANDIDATE-20261125','decision':'APPROVED'
    },follow_redirects=False)
    assert approved.status_code==303,('BROWSER_FORM_APPROVED',approved.status_code)
    withdrawn=paced_post(family_client,form_path,base_url=BASEURL,data={
        '_csrf_token':csrf(family_client),'text_version':'UK11-ONBOARDING-CANDIDATE-20261125','decision':'REVOKED'
    },follow_redirects=False)
    assert withdrawn.status_code==303,('BROWSER_FORM_REVOKED',withdrawn.status_code)
    record('native_parent_form_approval_and_withdrawal',status=withdrawn.status_code,csrf=True,version_check=True)

    paced_get(family_client,'/logout',base_url=BASEURL)
    login(family_client,4)
    unauthorized=paced_post(family_client,form_path,base_url=BASEURL,data={
        '_csrf_token':csrf(family_client),'text_version':'UK11-ONBOARDING-CANDIDATE-20261125','decision':'APPROVED'
    },follow_redirects=False)
    assert unauthorized.status_code==403,('CROSS_FAMILY_FORM_ACCESS',unauthorized.status_code)
    record('native_family_ui_cross_parent_denied',status=unauthorized.status_code)

print('UK11_NATIVE_GUARDIAN_BROWSER_VIEWS_PASSED')
