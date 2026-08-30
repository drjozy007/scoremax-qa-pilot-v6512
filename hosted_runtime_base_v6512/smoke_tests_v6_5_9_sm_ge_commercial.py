from release_compatibility import is_compatible_descendant
import os, json, tempfile, pathlib, hashlib

fd, dbpath=tempfile.mkstemp(prefix='scoremax_v659_smge_',suffix='.db'); os.close(fd); os.unlink(dbpath)
os.environ['SCOREMAX_DB']=dbpath
os.environ['SCOREMAX_SECRET']='test-secret'
os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD']='test-bootstrap'
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ
app.init(); c=app.db()
checks=[]
def ok(name, cond):
    if not cond: raise AssertionError(name)
    checks.append(name); print('PASS:',name)

ok('V6.5.9 commercial semantics active in descendant', is_compatible_descendant(app.SCOREMAX_RELEASE_VERSION,'6.5.9') and is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.9'))
schema_path=pathlib.Path(__file__).resolve().parent/'integration_contracts'/'SM_GE_PRODUCT_EVENT_V1.schema.json'
ok('frozen SM_GE_PRODUCT_EVENT_V1 schema bytes unchanged',hashlib.sha256(schema_path.read_bytes()).hexdigest()=='b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb')

# Configure the already-existing one-level referral programmes; do not create another reward ledger.
c.execute("UPDATE referral_programs SET reward_rate=0.10,hold_days=7,active=1 WHERE role_group='teacher_direct'")
c.execute("UPDATE referral_programs SET reward_rate=0.02,hold_days=7,active=1 WHERE role_group='teacher_override'")
def user(uid,role,name,email):
    cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level,subjects,login_provider) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (uid,role,name,email,uid.lower().replace('-',''),app.generate_password_hash('Pass123!'),'active','FSc Part 1','Chemistry','local'))
    return cur.lastrowid
A=user('TCH-659-A','teacher','Teacher A','a659@t.test')
B=user('TCH-659-B','teacher','Teacher B','b659@t.test')
S=user('STU-659','student','Student 659','s659@s.test')
ca=app.ensure_referral_code(c,A); cb=app.ensure_referral_code(c,B)
app.apply_referral_attribution(c,B,ca,'teacher_referral'); app.apply_referral_attribution(c,S,cb,'teacher_referral')
plan_id=int(c.execute('SELECT id FROM plans ORDER BY id LIMIT 1').fetchone()['id'])

# A real ScoreMax payment must produce a governed PAYMENT_CLEARED event.
tx=app.record_payment(c,S,plan_id,100000,'PKR','successful',provider='stripe',provider_ref='sk_test_DO_NOT_EXPORT',payment_method='tokenised-card')
c.commit(); integ.sync_growth_outbox(c,'6.5.9'); c.commit()
rows=c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' ORDER BY id").fetchall()
events=[json.loads(r['envelope_json']) for r in rows]
payment=[e for e in events if e['payload']['event_type']=='PAYMENT_CLEARED' and e['payload']['event_data'].get('payment_transaction_id')==tx]
ok('real record_payment projects PAYMENT_CLEARED',len(payment)==1)
pe=payment[0]
ok('exact payment event passes frozen ScoreMax schema',not integ._schema_errors(pe,'SM_GE_PRODUCT_EVENT_V1','1.0.0'))
meta=pe['payload']['event_data']['metadata']
ok('payment metadata uses governed payment_provider key',meta=={'payment_provider':'stripe'})
ok('ungoverned provider key absent everywhere in payment event','provider' not in meta)
raw=json.dumps(pe,sort_keys=True).lower()
ok('provider credential/ref/contact fields are not emitted','provider_transaction_ref' not in raw and 'payment_method' not in raw and 'sk_test_do_not_export' not in raw and 'authorization' not in raw and 'secret' not in raw)
rr=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(tx,)).fetchone()
ok('existing direct reward ledger remains authoritative',rr and int(rr['reward_amount_minor'])==10000 and rr['status']=='pending')
ok('existing one-upstream reward remains authoritative',int(rr['override_reward_amount_minor'])==2000 and rr['override_status']=='pending')

# Central's frozen Growth semantic requirements, reproduced verbatim as producer-side contract assertions.
def growth_semantic_gate(env):
    p=env['payload']; et=p['event_type']; ed=p['event_data']; md=ed.get('metadata') or {}
    if et.startswith('PAYMENT_') and any(k not in {'payment_provider'} for k in md):
        return False,'METADATA_FIELD_NOT_ALLOWLISTED'
    if et in {'PAYMENT_REFUNDED','PAYMENT_REVERSED'}:
        positive=(int(ed.get('direct_reward_amount_minor') or 0)>0 or int(ed.get('upstream_reward_amount_minor') or 0)>0)
        if positive and str(ed.get('reward_status') or '').lower() not in {'reversed','ineligible','cancelled','voided'}:
            return False,'REWARD_PAYMENT_STATE_INVALID'
    if et=='PAYMENT_FAILED':
        positive=(int(ed.get('direct_reward_amount_minor') or 0)>0 or int(ed.get('upstream_reward_amount_minor') or 0)>0)
        if positive and str(ed.get('reward_status') or '').lower() not in {'reversed','ineligible','cancelled','voided'}:
            return False,'REWARD_PAYMENT_STATE_INVALID'
    return True,'ACCEPTED'
ok('PAYMENT_CLEARED satisfies central Growth semantic allowlist',growth_semantic_gate(pe)==(True,'ACCEPTED'))

# Direct/raw contradictory refund mutation must fail closed at producer projection.
tx_bad=app.record_payment(c,S,plan_id,80000,'PKR','successful',provider='manual'); c.commit(); integ.sync_growth_outbox(c,'6.5.9'); c.commit()
before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
c.execute('UPDATE payment_transactions SET refund_amount_minor=80000,status=\'refunded\',refund_status=\'refunded\' WHERE id=?',(tx_bad,)); c.commit()
integ.sync_growth_outbox(c,'6.5.9'); c.commit()
after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
bad_refund=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' AND envelope_json LIKE ?",(f'%PAYMENT::{tx_bad}::REFUNDED%',)).fetchone()['n']
pending=c.execute("SELECT COUNT(*) n FROM integration_source_change_queue WHERE source_table='payment_transactions' AND source_pk=? AND projected_at=''",(str(tx_bad),)).fetchone()['n']
ok('raw contradictory refund creates no Growth event',after==before and bad_refund==0)
ok('contradictory refund remains pending rather than falsely acknowledged',pending>=1)

# No governed partial-refund reward rule exists, so partial refund must fail closed.
tx_partial=app.record_payment(c,S,plan_id,60000,'PKR','successful',provider='manual'); c.commit()
try:
    app.refund_payment_transaction(c,tx_partial,30000,'partial attack')
    partial_blocked=False
except ValueError as exc:
    partial_blocked='partial refund reward policy is not governed' in str(exc)
ok('partial refund fails closed without governed reward rule',partial_blocked)
pt=c.execute('SELECT refund_amount_minor,status FROM payment_transactions WHERE id=?',(tx_partial,)).fetchone()
pr=c.execute('SELECT status FROM referral_rewards WHERE payment_transaction_id=?',(tx_partial,)).fetchone()
ok('failed partial refund leaves payment/reward authority unchanged',int(pt['refund_amount_minor'] or 0)==0 and pt['status']=='successful' and pr['status']=='pending')

# Governed full refund mutates the authoritative payment and reward ledger in one commit.
changed=app.refund_payment_transaction(c,tx,100000,'Connected qualification full refund')
ok('governed full refund transition committed',changed is True)
pt=c.execute('SELECT * FROM payment_transactions WHERE id=?',(tx,)).fetchone(); rr2=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(tx,)).fetchone()
ok('authoritative payment is REFUNDED',pt['status']=='refunded' and int(pt['refund_amount_minor'])==100000 and pt['refund_status']=='refunded')
ok('direct reward is authoritatively reversed',rr2['status']=='reversed' and bool(rr2['reversed_at']))
ok('one-upstream reward is authoritatively reversed',rr2['override_status']=='reversed' and bool(rr2['override_reversed_at']))

integ.sync_growth_outbox(c,'6.5.9'); c.commit()
all_events=[json.loads(r['envelope_json']) for r in c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' ORDER BY id").fetchall()]
refunds=[e for e in all_events if e['payload']['event_type']=='PAYMENT_REFUNDED' and e['payload']['event_data'].get('payment_transaction_id')==tx]
rewards=[e for e in all_events if e['payload']['event_type']=='REFERRAL_REWARD_ELIGIBILITY_CHANGED' and e['payload']['event_data'].get('payment_transaction_id')==tx]
ok('governed refund projects exactly one terminal payment fact',len(refunds)==1)
re=refunds[0]
ok('refund event carries reversed reward status',re['payload']['event_data']['reward_status']=='reversed')
ok('refund event retains exact direct/upstream reward IDs',re['payload']['event_data']['direct_reward_id']==rr2['id'] and re['payload']['event_data']['upstream_reward_id']==f"UPSTREAM::{rr2['id']}")
ok('refund event carries governed payment_provider metadata',re['payload']['event_data']['metadata']=={'payment_provider':'stripe'})
ok('refund event satisfies central Growth payment/reward guard',growth_semantic_gate(re)==(True,'ACCEPTED'))
ok('distinct reward eligibility reversal event is emitted',any(e['payload']['event_data'].get('reward_status')=='reversed' for e in rewards))

# Idempotent ScoreMax state transition and outbox projection.
count_before=len(all_events)
changed2=app.refund_payment_transaction(c,tx,100000,'Connected qualification full refund')
integ.sync_growth_outbox(c,'6.5.9'); c.commit()
count_after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
ok('identical governed refund transition is idempotent',changed2 is False)
ok('identical Growth synchronization adds no duplicate product events',count_after==count_before)

# Governed reversal path uses the same authoritative ledger and produces coherent terminal semantics.
tx_rev=app.record_payment(c,S,plan_id,50000,'PKR','successful',provider='manual'); c.commit(); integ.sync_growth_outbox(c,'6.5.9'); c.commit()
app.reverse_payment_transaction(c,tx_rev,'connected reversal'); integ.sync_growth_outbox(c,'6.5.9'); c.commit()
rev_events=[json.loads(r['envelope_json']) for r in c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' ORDER BY id").fetchall()]
revs=[e for e in rev_events if e['payload']['event_type']=='PAYMENT_REVERSED' and e['payload']['event_data'].get('payment_transaction_id')==tx_rev]
rr_rev=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(tx_rev,)).fetchone()
ok('governed reversal projects PAYMENT_REVERSED',len(revs)==1)
ok('reversal payment/reward state is coherent',rr_rev['status']=='reversed' and rr_rev['override_status']=='reversed' and growth_semantic_gate(revs[0])==(True,'ACCEPTED'))

ok('database integrity ok',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
ok('foreign keys clean',len(c.execute('PRAGMA foreign_key_check').fetchall())==0)
print(json.dumps({'status':'PASS','checks':len(checks),'confirmed_total':0,'P0':0,'P1':0,'payment':'PASS','referral':'PASS','refund_reversal':'PASS','replay':'PASS','privacy':'PASS','integrity':'ok','foreign_key_violations':0,'check_names':checks},indent=2))
c.close()
try: os.remove(dbpath)
except OSError: pass
