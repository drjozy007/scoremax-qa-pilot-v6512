"""Read pending attempts after a code-only rollback/forward; never restore data."""
from pathlib import Path
import hashlib,json,os,re,socket,sqlite3,sys
from contextlib import closing

ROOT=Path(__file__).resolve().parents[1]
runtime=Path(sys.argv[1]).resolve();database=Path(sys.argv[2]).resolve();output=Path(sys.argv[3]).resolve()
assert runtime.is_relative_to(ROOT) and database.is_relative_to(ROOT) and database.is_file()
tables=('users','questions','question_families','attempts','attempt_answers','assessment_sessions',
        'mastery_records','mastery_form_results','mastery_history','integration_ph_question_version_store',
        'integration_ph_release_question_membership','integration_ph_content_releases',
        'integration_ph_product_activation_authorizations','ph_bridge_staged_withdrawal_exclusions_v6611e',
        'integration_outbox','integration_receipts')
def fingerprint():
    with closing(sqlite3.connect(database)) as c:
        return {table:hashlib.sha256(repr(c.execute('SELECT * FROM "'+table+'" ORDER BY rowid').fetchall()).encode()).hexdigest() for table in tables}
before=fingerprint()
def columns_snapshot():
    with closing(sqlite3.connect(database)) as c:
        return {t:([r[1] for r in c.execute('PRAGMA table_info("'+t+'")')],c.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall()) for t in tables}
raw_before=columns_snapshot()

with closing(sqlite3.connect(database)) as c:
    attempts=c.execute('SELECT id,student_id,maximum_marks,score,total_marks_awarded FROM attempts ORDER BY id').fetchall()
assert len(attempts)==4 and {r[2] for r in attempts}=={1,2,3,4} and all(r[3] is None and r[4] is None for r in attempts)
os.environ.update(SCOREMAX_ENV='local',SCOREMAX_DB=str(database),
    SCOREMAX_SECRET='software-withdrawal-only-secret-20261122',
    SCOREMAX_STAGING_SESSION_SECRET='software-withdrawal-only-secret-20261122',
    SCOREMAX_SEND_EMAIL_VERIFICATION='0',POWER_HOUSE_TO_SCOREMAX_TOKEN='software-ph-token',
    POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET='software-ph-hmac',SCOREMAX_SMTP_HOST='invalid.test')
def denied(*args,**kwargs):raise RuntimeError('QUALIFICATION_NETWORK_DISABLED')
socket.socket.connect=denied;socket.socket.connect_ex=denied
sys.path.insert(0,str(runtime));import app as sm
import ux_content_reviewer as reviewer;reviewer.install_content_reviewer(sm.app)
import ux_catalogue_browser as catalogue;catalogue.install_catalogue_browser(sm.app)
for aid,uid,maximum,_,_ in attempts:
    with sm.app.test_client() as client:
        with client.session_transaction() as session:session.update(user_id=uid,role='student',session_version=0,_csrf_token='software-rollback-csrf')
        response=client.get('/result/'+str(aid));assert response.status_code==200
        assert '<div class="score">Unscored</div>' in response.get_data(as_text=True)
with closing(sqlite3.connect(database)) as c:
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert c.execute('SELECT COUNT(*) FROM mastery_records').fetchone()[0]==0
    assert c.execute('SELECT COUNT(*) FROM attempt_answers WHERE marks_awarded IS NOT NULL').fetchone()[0]==0
after=fingerprint();raw_after=columns_snapshot();verified_backfills={}
for table in tables:
    if before[table]==after[table]:continue
    names,old=raw_before[table];other_names,new=raw_after[table]
    assert names==other_names and len(old)==len(new),'NATIVE_RESTART_CHANGED_ROW_CENSUS'
    changed=0
    for oldrow,newrow in zip(old,new):
        oldrow=dict(zip(names,oldrow));newrow=dict(zip(names,newrow))
        for name in names:
            prior=oldrow[name];value=newrow[name]
            if prior==value:continue
            if table=='users' and name=='parent_link_code':
                assert oldrow['role']=='student' and not prior and re.fullmatch(r'P-[A-Z0-9_-]{16}',value)
            elif table=='users' and name=='own_referral_code':
                stem=''.join(ch for ch in (oldrow['full_name'] or 'USER').upper() if ch.isalnum())[:5] or 'USER'
                assert not prior and value==f"{stem}{int(oldrow['id']):05d}"
            elif table=='questions' and name=='review_status':
                assert prior=='Approved' and oldrow['status']==newrow['status']=='Withdrawn' and value=='Withdrawn'
                assert oldrow['active']==newrow['active']==0
            else:raise AssertionError('UNEXPECTED_NATIVE_RESTART_MUTATION:'+table+'.'+name)
            changed+=1
    verified_backfills[table]=changed
helper=sys.modules.get('navigation_request_connections_v1')
if helper is not None:helper.clear_idle()
report={'status':'PASSED','runtime':runtime.name,'existing_unscored_attempts':4,'original_marks':[1,2,3,4],
        'protected_tables_exactly_unchanged':16-len(verified_backfills),'native_existing_startup_backfills_verified':verified_backfills,'all_existing_answer_attempt_mastery_release_outbox_values_preserved':True,'formal_mastery_rows':0,'restored_database':False,
        'production_actions':False,'academic_authority':'SOFTWARE_FIXTURES_ONLY'}
output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
