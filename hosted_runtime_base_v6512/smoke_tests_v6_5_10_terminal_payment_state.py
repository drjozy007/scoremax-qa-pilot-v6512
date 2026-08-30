from release_compatibility import is_compatible_descendant
import os, json, tempfile, pathlib, hashlib, copy

fd, dbpath=tempfile.mkstemp(prefix='scoremax_v6510_terminal_',suffix='.db'); os.close(fd); os.unlink(dbpath)
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

ok('V6.5.10 release identity active', is_compatible_descendant(app.SCOREMAX_RELEASE_VERSION,'6.5.10') and is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.10'))
schema_path=pathlib.Path(__file__).resolve().parent/'integration_contracts'/'SM_GE_PRODUCT_EVENT_V1.schema.json'
ok('frozen SM_GE_PRODUCT_EVENT_V1 schema bytes unchanged',
   hashlib.sha256(schema_path.read_bytes()).hexdigest()=='b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb')

# Existing referral ledgers remain the sole authority.
c.execute("UPDATE referral_programs SET reward_rate=0.10,hold_days=7,active=1 WHERE role_group='teacher_direct'")
c.execute("UPDATE referral_programs SET reward_rate=0.02,hold_days=7,active=1 WHERE role_group='teacher_override'")
def user(uid,role,name,email):
    cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level,subjects,login_provider) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (uid,role,name,email,uid.lower().replace('-',''),app.generate_password_hash('Pass123!'),'active','FSc Part 1','Chemistry','local'))
    return cur.lastrowid
A=user('TCH-6510-A','teacher','Teacher A','a6510@t.test')
B=user('TCH-6510-B','teacher','Teacher B','b6510@t.test')
S=user('STU-6510','student','Student 6510','s6510@s.test')
ca=app.ensure_referral_code(c,A); cb=app.ensure_referral_code(c,B)
app.apply_referral_attribution(c,B,ca,'teacher_referral'); app.apply_referral_attribution(c,S,cb,'teacher_referral')
plan_id=int(c.execute('SELECT id FROM plans ORDER BY id LIMIT 1').fetchone()['id'])

def payment_row(txid):
    return dict(c.execute('SELECT * FROM payment_transactions WHERE id=?',(txid,)).fetchone())
def reward_row(txid):
    r=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(txid,)).fetchone()
    return dict(r) if r else None
def source_rows(table, pk):
    return [dict(r) for r in c.execute("SELECT * FROM integration_source_change_queue WHERE source_table=? AND source_pk=? ORDER BY id",(table,str(pk))).fetchall()]
def events_for(txid):
    rows=c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' ORDER BY id").fetchall()
    out=[]
    for r in rows:
        e=json.loads(r['envelope_json'])
        if e['payload'].get('event_data',{}).get('payment_transaction_id')==txid:
            out.append(e)
    return out
def event_types(txid):
    return [e['payload']['event_type'] for e in events_for(txid)]

# 1) successful -> full refund
tx_ref=app.record_payment(c,S,plan_id,100000,'PKR','successful',provider='stripe'); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
rr_before=reward_row(tx_ref)
direct_id=rr_before['id']; direct_amt=rr_before['reward_amount_minor']; upstream_amt=rr_before['override_reward_amount_minor']
changed=app.refund_payment_transaction(c,tx_ref,100000,'terminal state test refund')
ok('successful payment -> full refund allowed',changed is True)
pr=payment_row(tx_ref); rr=reward_row(tx_ref)
ok('refund produces coherent authoritative tuple',
   pr['status']=='refunded' and int(pr['refund_amount_minor'])==100000 and pr['refund_status']=='refunded')
ok('refund reverses existing direct/upstream rewards without identity/amount mutation',
   rr['id']==direct_id and int(rr['reward_amount_minor'])==int(direct_amt) and int(rr['override_reward_amount_minor'])==int(upstream_amt)
   and rr['status']=='reversed' and rr['override_status']=='reversed')
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
ok('coherent full refund projects PAYMENT_REFUNDED',event_types(tx_ref).count('PAYMENT_REFUNDED')==1)

# 3) refund -> reversal rejected and leaves all authoritative/source state unchanged.
before_payment=payment_row(tx_ref); before_reward=reward_row(tx_ref)
before_pq=source_rows('payment_transactions',tx_ref); before_rq=source_rows('referral_rewards',direct_id)
try:
    app.reverse_payment_transaction(c,tx_ref,'illegal refund to reversal')
    blocked=False
except ValueError as exc:
    blocked='unsupported payment transition' in str(exc)
ok('refund -> reversal attempt rejected',blocked)
ok('refund -> reversal leaves payment row unchanged',payment_row(tx_ref)==before_payment)
ok('refund -> reversal leaves reward ledger unchanged',reward_row(tx_ref)==before_reward)
ok('refund -> reversal leaves source-change state unchanged',
   source_rows('payment_transactions',tx_ref)==before_pq and source_rows('referral_rewards',direct_id)==before_rq)

# 9) exact full refund repeat is idempotent no-op.
before_payment=payment_row(tx_ref); before_reward=reward_row(tx_ref)
before_pq=source_rows('payment_transactions',tx_ref); before_rq=source_rows('referral_rewards',direct_id)
repeat=app.refund_payment_transaction(c,tx_ref,100000,'same terminal operation')
ok('identical full refund repeat is idempotent',repeat is False)
ok('idempotent refund repeat changes no authoritative/source state',
   payment_row(tx_ref)==before_payment and reward_row(tx_ref)==before_reward
   and source_rows('payment_transactions',tx_ref)==before_pq and source_rows('referral_rewards',direct_id)==before_rq)

# 2) successful -> reversal
tx_rev=app.record_payment(c,S,plan_id,50000,'PKR','successful',provider='manual'); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
rr_rev_before=reward_row(tx_rev); rev_id=rr_rev_before['id']; rev_direct_amt=rr_rev_before['reward_amount_minor']; rev_up_amt=rr_rev_before['override_reward_amount_minor']
changed=app.reverse_payment_transaction(c,tx_rev,'terminal state test reversal')
ok('successful payment -> reversal allowed',changed is True)
pr=payment_row(tx_rev); rr=reward_row(tx_rev)
ok('reversal produces coherent authoritative tuple',
   pr['status']=='reversed' and int(pr['refund_amount_minor'] or 0)==0 and pr['refund_status']=='reversed')
ok('reversal preserves reward identities/amounts while reversing eligibility',
   rr['id']==rev_id and int(rr['reward_amount_minor'])==int(rev_direct_amt) and int(rr['override_reward_amount_minor'])==int(rev_up_amt)
   and rr['status']=='reversed' and rr['override_status']=='reversed')
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
ok('coherent reversal projects PAYMENT_REVERSED',event_types(tx_rev).count('PAYMENT_REVERSED')==1)

# 4) reversal -> refund rejected
before_payment=payment_row(tx_rev); before_reward=reward_row(tx_rev)
before_pq=source_rows('payment_transactions',tx_rev); before_rq=source_rows('referral_rewards',rev_id)
try:
    app.refund_payment_transaction(c,tx_rev,50000,'illegal reversal to refund')
    blocked=False
except ValueError as exc:
    blocked='unsupported payment transition' in str(exc)
ok('reversal -> refund attempt rejected',blocked)
ok('reversal -> refund leaves all authoritative/source state unchanged',
   payment_row(tx_rev)==before_payment and reward_row(tx_rev)==before_reward
   and source_rows('payment_transactions',tx_rev)==before_pq and source_rows('referral_rewards',rev_id)==before_rq)

# 10) exact reversal repeat idempotent
before_payment=payment_row(tx_rev); before_reward=reward_row(tx_rev)
before_pq=source_rows('payment_transactions',tx_rev); before_rq=source_rows('referral_rewards',rev_id)
repeat=app.reverse_payment_transaction(c,tx_rev,'same reversal')
ok('identical reversal repeat is idempotent',repeat is False)
ok('idempotent reversal repeat changes no authoritative/source state',
   payment_row(tx_rev)==before_payment and reward_row(tx_rev)==before_reward
   and source_rows('payment_transactions',tx_rev)==before_pq and source_rows('referral_rewards',rev_id)==before_rq)

# 5/6) failed payment cannot be refunded or reversed.
tx_fail=app.record_payment(c,S,plan_id,40000,'PKR','failed',provider='manual'); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
base_payment=payment_row(tx_fail); base_sources=source_rows('payment_transactions',tx_fail)
try:
    app.refund_payment_transaction(c,tx_fail,40000,'illegal failed refund')
    fail_refund_block=False
except ValueError as exc:
    fail_refund_block='unsupported payment transition' in str(exc)
ok('failed payment -> refund rejected',fail_refund_block)
ok('failed refund attempt leaves payment/source state unchanged',
   payment_row(tx_fail)==base_payment and source_rows('payment_transactions',tx_fail)==base_sources)
try:
    app.reverse_payment_transaction(c,tx_fail,'illegal failed reversal')
    fail_reverse_block=False
except ValueError as exc:
    fail_reverse_block='unsupported payment transition' in str(exc)
ok('failed payment -> reversal rejected',fail_reverse_block)
ok('failed reversal attempt leaves payment/source state unchanged',
   payment_row(tx_fail)==base_payment and source_rows('payment_transactions',tx_fail)==base_sources)

# 7) partial refunds still fail closed.
tx_partial=app.record_payment(c,S,plan_id,60000,'PKR','successful',provider='manual'); c.commit()
base_payment=payment_row(tx_partial); base_reward=reward_row(tx_partial)
partial_sources=source_rows('payment_transactions',tx_partial)
try:
    app.refund_payment_transaction(c,tx_partial,30000,'partial refund attack')
    partial_block=False
except ValueError as exc:
    partial_block='partial refund reward policy is not governed' in str(exc)
ok('partial refund remains rejected',partial_block)
ok('partial refund changes no payment/reward/source state',
   payment_row(tx_partial)==base_payment and reward_row(tx_partial)==base_reward and source_rows('payment_transactions',tx_partial)==partial_sources)

# 8) raw contradictory terminal tuple never produces an outbound event and remains pending.
tx_bad=app.record_payment(c,S,plan_id,80000,'PKR','successful',provider='manual'); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
before_count=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
c.execute("UPDATE payment_transactions SET status='reversed',refund_amount_minor=80000,refund_status='reversed' WHERE id=?",(tx_bad,)); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
after_count=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
types=event_types(tx_bad)
pending=c.execute("SELECT COUNT(*) n FROM integration_source_change_queue WHERE source_table='payment_transactions' AND source_pk=? AND projected_at=''",(str(tx_bad),)).fetchone()['n']
ok('raw contradictory terminal tuple emits no terminal Growth event',
   after_count==before_count and 'PAYMENT_REVERSED' not in types and 'PAYMENT_REFUNDED' not in types)
ok('raw contradictory terminal source change remains pending',pending>=1)

# Additional tuple attack: refunded with wrong amount must remain pending/no event.
tx_bad2=app.record_payment(c,S,plan_id,70000,'PKR','successful',provider='manual'); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
before_count=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
c.execute("UPDATE payment_transactions SET status='refunded',refund_amount_minor=35000,refund_status='refunded' WHERE id=?",(tx_bad2,)); c.commit()
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
after_count=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
pending2=c.execute("SELECT COUNT(*) n FROM integration_source_change_queue WHERE source_table='payment_transactions' AND source_pk=? AND projected_at=''",(str(tx_bad2),)).fetchone()['n']
ok('unsupported partial-refund raw tuple emits no outbound event and remains pending',after_count==before_count and pending2>=1)

# 11) terminal operations have not changed referral attribution or reward IDs/amounts.
attr=c.execute('SELECT * FROM referral_attributions WHERE user_id=?',(S,)).fetchone()
ok('terminal transitions preserve referral attribution',attr is not None and attr['referrer_id']==B)
ok('terminal transitions preserve direct/upstream reward IDs and amounts',
   reward_row(tx_ref)['id']==direct_id and reward_row(tx_ref)['reward_amount_minor']==direct_amt and reward_row(tx_ref)['override_reward_amount_minor']==upstream_amt
   and reward_row(tx_rev)['id']==rev_id and reward_row(tx_rev)['reward_amount_minor']==rev_direct_amt and reward_row(tx_rev)['override_reward_amount_minor']==rev_up_amt)

# Producer replay/idempotency: repeated synchronisation adds no events for coherent terminal rows.
count_before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
integ.sync_growth_outbox(c,'6.5.10'); c.commit()
count_after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
# Pending contradictory rows stay pending, so they are rechecked but must not create events.
ok('repeated producer synchronization is idempotent for coherent and blocked terminal rows',count_after==count_before)

ok('database integrity ok',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
ok('foreign keys clean',len(c.execute('PRAGMA foreign_key_check').fetchall())==0)
print(json.dumps({
  'status':'PASS','checks':len(checks),'confirmed_total':0,'P0':0,'P1':0,
  'payment':'PASS','referral':'PASS','terminal_ordering':'PASS','producer_replay':'PASS',
  'privacy':'PRESERVED_FROM_V6_5_9','growth_v0_14_3_receiver_replay':'PENDING_CENTRAL_CONNECTED_QUALIFICATION',
  'integrity':'ok','foreign_key_violations':0,'check_names':checks
},indent=2))
c.close()
try: os.remove(dbpath)
except OSError: pass
