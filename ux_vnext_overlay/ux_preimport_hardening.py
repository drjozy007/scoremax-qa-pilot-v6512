from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

PRIMARY_SEED_CONDITION="if preexisting_question_count==0 and content_seed_policy.demo_seed_allowed(SCOREMAX_ENV):"
SYNTHETIC_POPULATION_CONDITION="if content_seed_policy.demo_seed_allowed(SCOREMAX_ENV):"


def _disable_demo_seed(text: str) -> str:
    if PRIMARY_SEED_CONDITION in text:
        text=text.replace(PRIMARY_SEED_CONDITION,"if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",1)
    anchor="built_in_demo_ids=('BIO001','BIO002','BIO003','BIO004','BIO005')"
    pos=text.find(anchor)
    if pos>=0:
        cond=text.find(SYNTHETIC_POPULATION_CONDITION,pos)
        if cond<0 or cond-pos>3000:
            raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_CONDITION_MISSING')
        text=text[:cond]+"if False:  # PRE-IMPORT HARDENING: synthetic qualification population disabled"+text[cond+len(SYNTHETIC_POPULATION_CONDITION):]
    historical=re.compile(r"if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:")
    if PRIMARY_SEED_CONDITION not in text and 'PRE-IMPORT HARDENING: governed question bank starts empty' not in text and historical.search(text):
        text=historical.sub("if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",text,count=1)
    return text


def _disable_staging_academic_reviewer_overlay(text: str) -> str:
    text=text.replace("install_content_reviewer(app)","# PRE-IMPORT HARDENING: ScoreMax academic reviewer overlay disabled; Power House is authoritative")
    text=text.replace("ensure_reviewer_accounts()","# PRE-IMPORT HARDENING: staging reviewer accounts disabled")
    return text


def _fence_historical_admin_reviewer_workspace(text: str) -> str:
    anchor="def admin_reviewer_workspace():\n    if not require('admin'): return redirect(url_for('login'))"
    replacement="def admin_reviewer_workspace():\n    if not require('admin'): return redirect(url_for('login'))\n    # PRE-IMPORT HARDENING: academic review is owned by Power House.\n    return redirect(url_for('admin_integration_health'))"
    if anchor in text:
        text=text.replace(anchor,replacement,1)
    elif 'PRE-IMPORT HARDENING: academic review is owned by Power House.' not in text:
        raise SystemExit('PREIMPORT_ADMIN_REVIEWER_WORKSPACE_ANCHOR_MISSING')
    return text


def _disable_demo_progress_default(text: str) -> str:
    anchor="def load_demo_progress():\n    if not require('student'): return redirect(url_for('login'))\n    if SCOREMAX_ENV=='production':"
    replacement="def load_demo_progress():\n    if not require('student'): return redirect(url_for('login'))\n    if os.environ.get('SCOREMAX_ALLOW_DEMO_PROGRESS','0').strip()!='1':\n        flash('Demo progress is disabled.','error'); return redirect(url_for('student_dashboard'))\n    if SCOREMAX_ENV=='production':"
    if anchor in text:
        text=text.replace(anchor,replacement,1)
    elif "SCOREMAX_ALLOW_DEMO_PROGRESS" not in text:
        raise SystemExit('PREIMPORT_DEMO_PROGRESS_ANCHOR_MISSING')
    return text


def _harden_admin_payment_plan_validation(text: str) -> str:
    old="plan=c.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone(); raw=request.form.get('amount','').strip(); gross=int(round(float(raw)*100)) if raw else int(plan['price_minor'] or 0)"
    new="plan=c.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone(); raw=request.form.get('amount','').strip()\n            if not plan:\n                c.close(); flash('Choose a valid access plan before recording a payment.','error'); return redirect(url_for('admin_payments'))\n            try:\n                gross=int(round(float(raw)*100)) if raw else int(plan['price_minor'] or 0)\n            except (TypeError,ValueError):\n                c.close(); flash('Enter a valid payment amount.','error'); return redirect(url_for('admin_payments'))"
    if old in text:
        text=text.replace(old,new,1)
    elif 'Choose a valid access plan before recording a payment.' not in text:
        raise SystemExit('PREIMPORT_PAYMENT_VALIDATION_ANCHOR_MISSING')
    return text


def _repair_digital_coach_mock_state(root: Path) -> None:
    path=root/'digital_coach_engine.py'
    if not path.exists():
        raise SystemExit('PREIMPORT_DIGITAL_COACH_ENGINE_MISSING')
    text=path.read_text(encoding='utf-8')
    old="""def _mock_state(c,student_id):
    if not _table(c,'student_mock_forms'): return {'count':0,'avg':0.0,'last_score':None}
    if not _table(c,'attempts'): return {'count':0,'avg':0.0,'last_score':None}
    row=c.execute('''SELECT COUNT(*) n,COALESCE(ROUND(AVG(a.score),1),0) avg FROM student_mock_forms smf LEFT JOIN attempts a ON a.id=smf.attempt_id WHERE smf.student_id=?''',(student_id,)).fetchone()
    last=c.execute('''SELECT a.score FROM student_mock_forms smf JOIN attempts a ON a.id=smf.attempt_id WHERE smf.student_id=? ORDER BY smf.id DESC LIMIT 1''',(student_id,)).fetchone()
    return {'count':int(row['n'] or 0),'avg':float(row['avg'] or 0),'last_score':float(last['score']) if last and last['score'] is not None else None}
"""
    new="""def _mock_state(c,student_id):
    if not _table(c,'student_mock_forms'): return {'count':0,'avg':0.0,'last_score':None}
    form_cols=_cols(c,'student_mock_forms')
    count_row=c.execute('SELECT COUNT(*) n FROM student_mock_forms WHERE student_id=?',(student_id,)).fetchone()
    form_count=int(count_row['n'] or 0)
    if not _table(c,'attempts'):
        return {'count':form_count,'avg':0.0,'last_score':None}
    attempt_cols=_cols(c,'attempts')
    if not {'paper_id','student_id'}.issubset(form_cols) or not {'exam_paper_id','student_id','score'}.issubset(attempt_cols):
        return {'count':form_count,'avg':0.0,'last_score':None}
    scored=c.execute('''SELECT COALESCE(ROUND(AVG(a.score),1),0) avg
      FROM attempts a WHERE a.student_id=? AND a.exam_paper_id IN
      (SELECT smf.paper_id FROM student_mock_forms smf WHERE smf.student_id=? AND smf.paper_id IS NOT NULL)
      AND a.score IS NOT NULL''',(student_id,student_id)).fetchone()
    last=c.execute('''SELECT a.score FROM attempts a WHERE a.student_id=? AND a.exam_paper_id IN
      (SELECT smf.paper_id FROM student_mock_forms smf WHERE smf.student_id=? AND smf.paper_id IS NOT NULL)
      AND a.score IS NOT NULL ORDER BY a.id DESC LIMIT 1''',(student_id,student_id)).fetchone()
    return {'count':form_count,'avg':float(scored['avg'] or 0),'last_score':float(last['score']) if last and last['score'] is not None else None}
"""
    if old in text:
        text=text.replace(old,new,1)
    elif "form_cols=_cols(c,'student_mock_forms')" not in text:
        raise SystemExit('PREIMPORT_DIGITAL_COACH_MOCK_STATE_ANCHOR_MISSING')
    path.write_text(text,encoding='utf-8')


def _remove_inactive_reviewer_runtime_templates(root: Path) -> None:
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        path=root/'templates'/name
        if path.exists(): path.unlink()


def _scrub_credential_logging(text: str) -> str:
    patterns=(
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
    )
    for pattern,replacement in patterns: text=re.sub(pattern,replacement,text)
    return text



def _harden_account_revocation(root: Path, text: str) -> str:
    """Use the existing account-security engine for every live password/status mutation."""
    path=root/'account_security_engine.py'
    engine=path.read_text(encoding='utf-8')
    marker='# SCOREMAX_ACCOUNT_REVOCATION_REPAIR_V1'
    if marker not in engine:
        engine += r'''

# SCOREMAX_ACCOUNT_REVOCATION_REPAIR_V1

def replace_password(c, *, user_id: int, password_hash: str, changed_at: str) -> None:
    """Caller owns commit/rollback. Changing a password revokes sessions and reset links."""
    if not password_hash:
        raise ValueError('PASSWORD_HASH_REQUIRED')
    sqlite_mutation.begin_immediate(c)
    result=c.execute("UPDATE users SET password_hash=?,session_version=COALESCE(session_version,0)+1 WHERE id=?",
                     (str(password_hash),int(user_id)))
    if result.rowcount != 1:
        raise ValueError('USER_NOT_FOUND')
    c.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND COALESCE(used_at,'')=''",
              (str(changed_at),int(user_id)))


def set_account_status(c, *, user_id: int, status: str, changed_at: str) -> None:
    """A disable/re-enable cycle must never revive an old browser/preview session."""
    if status not in {'active','disabled'}:
        raise ValueError('INVALID_ACCOUNT_STATUS')
    sqlite_mutation.begin_immediate(c)
    row=c.execute('SELECT account_status FROM users WHERE id=?',(int(user_id),)).fetchone()
    if not row:
        raise ValueError('USER_NOT_FOUND')
    if str(row['account_status'] or 'active') != status:
        c.execute("UPDATE users SET account_status=?,session_version=COALESCE(session_version,0)+1 WHERE id=?",
                  (status,int(user_id)))
    if status == 'disabled':
        c.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND COALESCE(used_at,'')=''",
                  (str(changed_at),int(user_id)))
'''
        compile(engine,str(path),'exec')
        path.write_text(engine,encoding='utf-8')
    replacements=(
        ("            c.execute(\"UPDATE users SET password_hash=?,session_version=COALESCE(session_version,0)+1 WHERE id=?\",(generate_password_hash(password),claimed['user_id']))",
         "            account_security.replace_password(c,user_id=claimed['user_id'],password_hash=generate_password_hash(password),changed_at=now_reset)"),
        ("    c=db(); c.execute(\"UPDATE users SET password_hash=? WHERE id=?\",(generate_password_hash(password),user_id)); c.commit(); c.close()",
         "    c=db()\n    try:\n        with c:\n            if not c.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone(): abort(404)\n            account_security.replace_password(c,user_id=user_id,password_hash=generate_password_hash(password),changed_at=datetime.now().isoformat(timespec='seconds'))\n    finally:\n        c.close()"),
        ("    if status not in ('active','disabled'): status='active'\n    c=db(); c.execute(\"UPDATE users SET account_status=? WHERE id=?\",(status,user_id)); c.commit(); c.close()",
         "    if status not in ('active','disabled'): abort(400)\n    c=db()\n    try:\n        with c:\n            if not c.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone(): abort(404)\n            account_security.set_account_status(c,user_id=user_id,status=status,changed_at=datetime.now().isoformat(timespec='seconds'))\n    finally:\n        c.close()"),
    )
    for old,new in replacements:
        if new in text:
            continue
        if text.count(old)!=1:
            raise SystemExit('SCOREMAX_ACCOUNT_REVOCATION_ANCHOR_MISMATCH')
        text=text.replace(old,new,1)
    return text


def _guard_account_route_connection(source: str, *, endpoint: str, role_argument=False) -> str:
    """Apply the existing caller-owned rollback/close contract to one route block."""
    lines=source.splitlines(keepends=True)
    starts=[i for i,line in enumerate(lines) if 'c=db()' in line]
    if len(starts)!=1:raise SystemExit('ACCOUNT_CONNECTION_OWNER_ANCHOR_MISMATCH')
    start=starts[0];line=lines[start];indent=line[:len(line)-len(line.lstrip())]
    before,after=line.strip().split('c=db()',1)
    end=start+1
    while end<len(lines) and (not lines[end].strip() or len(lines[end])-len(lines[end].lstrip())>=len(indent)):
        end+=1
    body=([indent+after.lstrip('; ')+'\n'] if after.lstrip('; ') else [])+lines[start+1:end]
    clean=[]
    for item in body:
        if item.strip()=='c.close()':continue
        clean.append(item.replace('c.close(); ','').replace('; c.close()',''))
    target="url_for('"+endpoint+"'"+(",role=role" if role_argument else '')+")"
    guarded=(indent+'c=db()\n'+indent+'try:\n'+textwrap.indent(''.join(clean),'    ')+
        '\n'+indent+'except Exception as exc:\n'+indent+'    c.rollback()\n'+
        indent+'    from werkzeug.exceptions import HTTPException\n'+
        indent+'    if isinstance(exc,HTTPException):raise\n'+
        indent+"    app.logger.error('Account request failed safely (%s).',type(exc).__name__)\n"+
        indent+"    flash('We could not complete that request. Please try again.','error')\n"+
        indent+'    return redirect('+target+')\n'+indent+'finally:\n'+indent+'    c.close()\n')
    prefix=indent+before.rstrip('; ')+'\n' if before else ''
    changed=''.join(lines[:start])+prefix+guarded+''.join(lines[end:])
    compile(changed,'account_connection_owner','exec')
    return changed


def _harden_registration_boundary(root: Path, text: str) -> str:
    """Keep registration in its native route, with the shared mutation lifecycle."""
    engine_path=root/'account_security_engine.py'
    engine=engine_path.read_text(encoding='utf-8')
    if "request.environ['scoremax.created_account_id']=uid" in text:
        if 'def normalize_registration_email(' not in engine:
            raise SystemExit('REGISTRATION_EMAIL_VALIDATOR_MISSING')
        return text
    engine += '''

def normalize_registration_email(value):
    """Validate the supported mailbox shape before persisting an account identity."""
    import re
    email=str(value or '').strip().lower()
    if len(email)>254 or email.count('@')!=1:
        raise ValueError('INVALID_REGISTRATION_EMAIL')
    local,domain=email.split('@')
    if (not local or len(local)>64 or local.startswith('.') or local.endswith('.')
            or '..' in local or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+",local)
            or not domain or len(domain)>253):
        raise ValueError('INVALID_REGISTRATION_EMAIL')
    labels=domain.split('.')
    if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels):
        raise ValueError('INVALID_REGISTRATION_EMAIL')
    return email
'''
    compile(engine,str(engine_path),'exec')
    engine_path.write_text(engine,encoding='utf-8')
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='register')
    original=ast.get_source_segment(text,node)
    changed=original

    def replace(old,new):
        nonlocal changed
        if changed.count(old)!=1:
            raise SystemExit('REGISTRATION_BOUNDARY_ANCHOR_MISMATCH:'+old[:60])
        changed=changed.replace(old,new,1)

    replace('    pending_referral=pending_referral_for_role(c,role)',
            "    pending_referral=pending_referral_for_role(c,role)\n"
            "    if request.method=='POST' and any(len(request.form.getlist(key))>1 for key in ('email','password','academic_level')):\n"
            "        flash('Submit one email, password and programme selection.','error')\n"
            "        return redirect(url_for('register',role=role))")

    replace("        requested_programme=(request.form.get('academic_level','') if request.method=='POST' else request.args.get('programme','')).strip()",
            "        requested_programme=canonical_programme(request.form.get('academic_level','') if request.method=='POST' else request.args.get('programme',''))\n"
            "        if requested_programme and requested_programme not in {item['value'] for item in STUDENT_PROGRAMME_CHOICES}:\n"
            "            flash('Choose a supported programme, or leave study details for later.','error')\n"
            "            return redirect(url_for('register',role=role))")
    replace("        email=request.form.get('email','').strip().lower()",
            "        try:\n"
            "            email=account_security.normalize_registration_email(request.form.get('email',''))\n"
            "        except ValueError:\n"
            "            flash('Enter a valid personal email address.','error')\n"
            "            return redirect(url_for('register',role=role))")
    duplicate='''        if c.execute("SELECT 1 FROM users WHERE lower(COALESCE(email,''))=?",(email,)).fetchone():'''
    replace(duplicate,
            "        account_programme=requested_programme if role=='student' else request.form.get('academic_level','').strip()\n"
            "        password_hash=generate_password_hash(password)\n"
            "        sqlite_mutation.begin_immediate(c)\n"+duplicate)
    replace("c.close(); flash('If this email can be used for a new ScoreMax account,", "c.rollback(); flash('If this email can be used for a new ScoreMax account,")
    replace('email,temp_username,generate_password_hash(password),','email,temp_username,password_hash,')
    changed=changed.replace("request.form.get('academic_level','').strip()","account_programme")
    # The assignment's non-student fallback must still read its existing form field.
    changed=changed.replace("account_programme=requested_programme if role=='student' else account_programme",
                            "account_programme=requested_programme if role=='student' else request.form.get('academic_level','').strip()")
    replace('        uid=cur.lastrowid',
            "        uid=cur.lastrowid\n"
            "        email_policy=request.environ.get('scoremax.registration_email_policy',{})\n"
            "        if role=='student' and email_policy.get('send'):\n"
            "            c.execute(\"UPDATE users SET email_verified=0,email_verified_at='',account_status=? WHERE id=?\",\n"
            "                      ('pending_email_verification' if email_policy.get('required') else 'active',uid))")
    replace("            session.pop('pending_referral',None)\n",'')
    replace('        c.commit(); c.close()',
            "        c.commit()\n"
            "        request.environ['scoremax.created_account_id']=uid\n"
            "        if pending_referral:session.pop('pending_referral',None)")
    changed=_guard_account_route_connection(changed,endpoint='register',role_argument=True)
    compile(changed,'registration_boundary','exec')
    return text.replace(original,changed,1)


def _harden_reset_connection_owners(text: str) -> str:
    for name in ('forgot_password','reset_password'):
        node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
        original=ast.get_source_segment(text,node)
        if 'Account request failed safely' in original:continue
        changed=original
        if name=='reset_password':
            changed=changed.replace('        now_dt=datetime.now()',
                '        password_hash=generate_password_hash(password)\n        now_dt=datetime.now()',1)
            changed=changed.replace('password_hash=generate_password_hash(password),changed_at=now_reset',
                                    'password_hash=password_hash,changed_at=now_reset',1)
        changed=_guard_account_route_connection(changed,endpoint='forgot_password')
        text=text.replace(original,changed,1)
    return text

def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    text=_disable_demo_seed(text)
    text=_disable_staging_academic_reviewer_overlay(text)
    text=_fence_historical_admin_reviewer_workspace(text)
    text=_disable_demo_progress_default(text)
    text=_harden_admin_payment_plan_validation(text)
    text=_scrub_credential_logging(text)
    text=_harden_account_revocation(root,text)
    text=_harden_registration_boundary(root,text)
    text=_harden_reset_connection_owners(text)
    app_path.write_text(text,encoding='utf-8')
    _repair_digital_coach_mock_state(root)
    _remove_inactive_reviewer_runtime_templates(root)

    rendered=app_path.read_text(encoding='utf-8')
    coach=(root/'digital_coach_engine.py').read_text(encoding='utf-8')
    if PRIMARY_SEED_CONDITION in rendered: raise SystemExit('PREIMPORT_DEMO_SEED_EXECUTABLE_CONDITION_SURVIVED')
    if 'PRE-IMPORT HARDENING: governed question bank starts empty' not in rendered: raise SystemExit('PREIMPORT_DEMO_SEED_DISABLE_CONTROL_MISSING')
    anchor="built_in_demo_ids=('BIO001','BIO002','BIO003','BIO004','BIO005')"
    if anchor in rendered:
        pos=rendered.find(anchor); nearby=rendered[pos:pos+3500]
        if SYNTHETIC_POPULATION_CONDITION in nearby: raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_EXECUTABLE_CONDITION_SURVIVED')
        if 'synthetic qualification population disabled' not in nearby: raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_DISABLE_CONTROL_MISSING')
    if 'install_content_reviewer(app)' in rendered or 'ensure_reviewer_accounts()' in rendered: raise SystemExit('PREIMPORT_STAGING_REVIEWER_INSTALLER_SURVIVED')
    if 'PRE-IMPORT HARDENING: academic review is owned by Power House.' not in rendered: raise SystemExit('PREIMPORT_ADMIN_REVIEWER_FENCE_MISSING')
    if 'SCOREMAX_ALLOW_DEMO_PROGRESS' not in rendered: raise SystemExit('PREIMPORT_DEMO_PROGRESS_FENCE_MISSING')
    if 'Choose a valid access plan before recording a payment.' not in rendered: raise SystemExit('PREIMPORT_PAYMENT_VALIDATION_MISSING')
    if "form_cols=_cols(c,'student_mock_forms')" not in coach or 'smf.attempt_id' in coach: raise SystemExit('PREIMPORT_DIGITAL_COACH_SCHEMA_REPAIR_MISSING')
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        if (root/'templates'/name).exists(): raise SystemExit('PREIMPORT_INACTIVE_REVIEWER_TEMPLATE_SURVIVED:'+name)
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered: raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_seed_disabled=true synthetic_population_disabled=true staging_reviewer_overlay_disabled=true admin_reviewer_workspace_fenced=true demo_progress_default_off=true payment_input_validation=true digital_coach_mock_schema_compatible=true inactive_reviewer_templates_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
