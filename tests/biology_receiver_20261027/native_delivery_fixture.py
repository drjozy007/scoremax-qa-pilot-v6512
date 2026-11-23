"""Reusable actual native Flask/HMAC/SQLite fixture. No real academic authority."""
from copy import deepcopy
import hashlib,json,os,socket,sys
from pathlib import Path

class NativeDeliveryFixture:
    def __init__(self,runtime_path,state_directory,*,retain_idle_between_requests=False):
        self.runtime_path=Path(runtime_path).resolve()
        self.state_directory=Path(state_directory).resolve()
        self.state_directory.mkdir(parents=True,exist_ok=True)
        if (self.state_directory/'native.db').exists():
            raise ValueError('Fresh disposable fixture directory required')
        for key in tuple(os.environ):
            if key.startswith(('SCOREMAX_','POWER_HOUSE_','GROWTH_ENGINE_')):os.environ.pop(key)
        os.environ.update(SCOREMAX_ENV='local',SCOREMAX_DB=str(self.state_directory/'native.db'),
            SCOREMAX_SECRET='software-withdrawal-only-secret-20261122',
            SCOREMAX_STAGING_SESSION_SECRET='software-withdrawal-only-secret-20261122',
            SCOREMAX_SEND_EMAIL_VERIFICATION='0',POWER_HOUSE_TO_SCOREMAX_TOKEN='software-ph-token',
            POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET='software-ph-hmac',SCOREMAX_SMTP_HOST='invalid.test')
        def denied(*args,**kwargs):raise RuntimeError('QUALIFICATION_NETWORK_DISABLED')
        socket.socket.connect=denied;socket.socket.connect_ex=denied
        if 'app' in sys.modules:raise RuntimeError('Use a fresh interpreter per native runtime fixture')
        sys.path.insert(0,str(self.runtime_path))
        import app as native
        self.native=native;self.integration=native.integration_v1
        native.app.config['TESTING']=True
        if not retain_idle_between_requests:
            @native.app.teardown_appcontext
            def close_owned_qualification_idle(error=None):
                helper=sys.modules.get('navigation_request_connections_v1')
                if helper is not None and hasattr(helper,'clear_idle'):
                    helper.clear_idle()

    def seal(self, envelope):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        envelope['payload_checksum_sha256'] = integration.payload_checksum(envelope['payload'])
        return envelope

    def content(self, label):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        env = json.loads((RUNTIME / 'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json').read_text())
        rel = env['payload']['release']
        q = deepcopy(env['payload']['questions'][0])
        now = integration.utcnow()
        rel.update(release_id='software-release::' + label, release_version='1', generated_at=now, effective_at=now, question_count=1, stimulus_count=0)
        q.update(question_id='opaque::question/' + label, question_version_id='opaque::version/' + label, question_version_number=1, supersedes_question_version_id=None)
        q['question_checksum_sha256'] = integration._object_checksum(q, 'question_checksum_sha256')
        env['payload'].update(questions=[q], stimuli=[])
        env.update(message_id='software-content::' + label, idempotency_key='software-content::' + label, occurred_at=now, sent_at=now)
        return self.seal(env)

    def withdrawal(self, label, q, fingerprint=None, *, target=None):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        now = integration.utcnow()
        item = {'item_public_id': 'software-item::' + label, 'withdrawal_queue_id': 'software-queue::' + label, 'question_public_id': q['question_id'], 'question_version_fingerprint': q['question_version_id'] if fingerprint is None else fingerprint, 'hold_id': 'software-hold::' + label, 'defect_code': 'SOFTWARE_WITHDRAWAL_CONTROL', 'reason': 'Disposable native stop control, not a real academic decision.', 'requested_action': 'STOP_FUTURE_DELIVERY_PRESERVE_HISTORICAL_ATTEMPTS', 'historical_attempts_must_be_preserved': True}
        if target is not None:item['delivery_targets']=[dict(target)] if isinstance(target,dict) else [dict(t) for t in target]
        item['item_sha256'] = hashlib.sha256(integration.canonical_json(item).encode()).hexdigest()
        payload = {'export_public_id': 'software-export::' + label, 'population_sha256': hashlib.sha256(integration.canonical_json([{key:item[key] for key in ('item_public_id','question_public_id','item_sha256')}]).encode()).hexdigest(), 'items': [item], 'release_authority_conferred': False}
        return self.seal({'message_id': 'software-withdraw::' + label, 'contract_name': 'PH_SM_QUESTION_WITHDRAWAL_V1', 'contract_version': '1', 'schema_version': '1.1.0' if target is not None else '1.0.0', 'source_system': 'POWER_HOUSE', 'destination_system': 'SCOREMAX', 'occurred_at': now, 'sent_at': now, 'correlation_id': 'software-correlation::' + label, 'idempotency_key': 'software-withdraw::' + label, 'producer_version': 'SOFTWARE_FIXTURE_ONLY', 'retry_of_message_id': None, 'data_classification': 'INTERNAL', 'payload': payload})

    def signed_post(self, path, envelope, *, expected_statuses=(200,202)):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        sent = integration.utcnow()
        checksum = envelope['payload_checksum_sha256']
        headers = {'Authorization': 'Bearer software-ph-token', 'X-Message-Id': envelope['message_id'], 'X-Sent-At': sent, 'X-Content-SHA256': checksum, 'X-Signature': 'hmac-sha256=' + integration.signature('POST', path, envelope['message_id'], sent, checksum, 'software-ph-hmac')}
        with native.app.test_client() as client:
            response = client.post(path, data=integration.canonical_json(envelope), headers=headers, content_type='application/json')
            assert response.status_code in expected_statuses, (response.status_code, response.get_json())
            return (response.status_code, response.get_json())

    def send_content(self, env):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        return self.signed_post('/api/integration/v1/power-house/content-releases', env)

    def send_stop(self, env):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        return self.signed_post('/api/integration/v1/power-house/question-withdrawals', env)

    def activate(self, env):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        rel = env['payload']['release']
        c = native.db()
        try:
            result = integration.authorize_product_activation(c, rel['release_id'], rel['release_version'], rel['package_checksum_sha256'], 'SOFTWARE_FIXTURE_ONLY', 'Disposable activation, no production authority.')
            c.commit()
            return result
        finally:
            c.close()

    def active(self, q):
        native = self.native
        integration = self.integration
        RUNTIME = self.runtime_path
        c = native.db()
        try:
            row = c.execute('SELECT id,active,status FROM questions WHERE ph_question_id=?', (q['question_id'],)).fetchone()
            return dict(row) if row else None
        finally:
            c.close()

    def exact_target(self,envelope):
        release=envelope['payload']['release'];question=envelope['payload']['questions'][0]
        return {**{key:release[key] for key in ('release_id','release_version','package_checksum_sha256',
            'market_id','programme_id','subject_id','chapter_id')},
            'question_version_id':question['question_version_id'],
            'question_checksum_sha256':question['question_checksum_sha256']}

    def learner(self,label,programme='FSc Part 1'):
        c=self.native.db()
        try:
            cur=c.execute('''INSERT INTO users(role,full_name,username,academic_level,active_programme,
              account_status,session_version,email_verified) VALUES('student',?,?,?,?, 'active',0,1)''',
              ('Software learner '+label,'software-'+label,programme,programme))
            c.commit();return cur.lastrowid
        finally:c.close()

    def session_for(self,learner_id,envelope,*,mode='practice'):
        question=envelope['payload']['questions'][0];release=envelope['payload']['release']
        c=self.native.db()
        try:
            q=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(question['question_id'],)).fetchone()
            programme=self.integration.question_contracts.programme_for_release(release['programme_id'],
                self.integration.canonical_json(question['curriculum']))
            session=self.native.create_assessment_session(c,learner_id,mode,None,[q['id']],{
                'programme':programme,'subject':q['subject'],'chapters':q['chapter'],
                'scope':'chapter','level':q['level'],'assessment_kind':'standard'})
            self.native.save_assessment(c,session,answers={str(q['id']):str(question['content']['marking']['key'])})
            c.commit();return session,q['id'],programme
        finally:c.close()

    def submit(self,learner_id,session_id,*,expected_statuses=(302,)):
        with self.native.app.test_client() as client:
            with client.session_transaction() as browser:
                browser.update(user_id=learner_id,role='student',session_version=0,
                    full_name='Software learner',_csrf_token='software-fixture-csrf')
            response=client.post('/test/session/'+str(session_id)+'/submit',
                data={'_csrf_token':'software-fixture-csrf'})
            assert response.status_code in expected_statuses,(response.status_code,response.data[:500])
            return response.status_code,response.headers.get('Location')
