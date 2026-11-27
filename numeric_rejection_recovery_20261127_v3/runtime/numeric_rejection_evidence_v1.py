"""Evidence for the existing atomic rejected-content receipt; no admission writes."""
import hashlib,json,re
CODE='NUMERICAL_REJECTED_BEFORE_ADMISSION'
SCHEMA='SM-EXACT-NUMERICAL-NO-ADMISSION-1'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def rejection_evidence(conn,release,questions,errors):
    # Caller already owns BEGIN IMMEDIATE and native inbound idempotency claim.
    if not conn.in_transaction:raise ValueError('NATIVE_REJECTION_TRANSACTION_REQUIRED')
    bad=set()
    for error in errors:
        match=re.fullmatch(r'payload\.questions\[([0-9]+)\]\.content(?:\.marking(?:\.key)?)?',str(error.get('path')or''))
        if error.get('code') not in {'NUMERIC_KEY_REQUIRED','NUMERIC_TOLERANCE','QUESTION_RESPONSE_CONTRACT'} or not match:return None
        index=int(match[1])
        if index>=len(questions) or (questions[index].get('content')or{}).get('marking',{}).get('key_type')!='NUMERIC':return None
        bad.add(index)
    if not bad:return None
    rid=release.get('release_id');version=release.get('release_version');package=release.get('package_checksum_sha256')
    if not all(isinstance(x,str) and x for x in (rid,version,package)) or not re.fullmatch('[0-9a-f]{64}',package):return None
    if conn.execute('SELECT 1 FROM integration_ph_content_releases WHERE release_id=? AND release_version=? LIMIT 1',(rid,version)).fetchone():return None
    if conn.execute('SELECT 1 FROM questions WHERE active=1 AND ph_release_checksum_sha256=? LIMIT 1',(package,)).fetchone():return None
    members=[{k:q.get(k)for k in ('question_id','question_version_id','question_checksum_sha256')}for q in questions]
    if len({q['question_id']for q in members})!=len(members):return None
    body={'schema':SCHEMA,'release_id':rid,'release_version':version,'package_checksum_sha256':package,
        'receiver_release_absent':True,'receiver_active_failed_members':0,
        'member_identity_sha256':digest(sorted(members,key=lambda q:q['question_id'])),
        'failed_numeric_members':[members[i]for i in sorted(bad)]}
    return {'code':CODE,'path':'payload.release','message':json.dumps(body,sort_keys=True,separators=(',',':')),'retryable':False}
