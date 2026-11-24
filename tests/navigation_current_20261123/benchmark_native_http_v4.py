"""Bounded native Gunicorn HTTP evidence; no production traffic or authority cache.

Extends the existing PR55/56 harness rather than bypassing its <=50 guard.
Every scheduled request is retained. Local resource/time budgets are operational
bounds, not newly invented product SLOs. Primary HTTP timings are unprofiled.
"""
from __future__ import annotations
import argparse,asyncio,base64,hashlib,importlib.metadata,importlib.util,json,math,os
from pathlib import Path
import signal,sqlite3,statistics,subprocess,sys,threading,time,uuid
import psutil

ROOT=Path(__file__).resolve().parents[2]
PROTECTED=('users','questions','question_families','attempts','attempt_answers',
 'assessment_sessions','mastery_records','mastery_form_results','mastery_history',
 'integration_ph_question_version_store','integration_ph_release_question_membership',
 'integration_ph_content_releases','integration_ph_product_activation_authorizations',
 'ph_bridge_staged_withdrawal_exclusions_v6611e','integration_outbox','integration_receipts')


def fingerprint(database):
    result={}
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=5) as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in PROTECTED:
            if table not in tables:continue
            digest=hashlib.sha256();n=0
            for row in c.execute('SELECT * FROM "'+table+'" ORDER BY rowid'):
                values=[['bytes',base64.b64encode(x).decode()] if isinstance(x,bytes)
                        else [type(x).__name__,x] for x in row]
                digest.update(json.dumps(values,separators=(',',':'),ensure_ascii=False).encode()+b'\n');n+=1
            result[table]={'rows':n,'sha256':digest.hexdigest()}
        result['integrity_check']=c.execute('PRAGMA quick_check').fetchone()[0]
        result['foreign_key_violations']=len(c.execute('PRAGMA foreign_key_check').fetchall())
    return result


def files(database):
    return {suffix or 'database':Path(str(database)+suffix).stat().st_size
            if Path(str(database)+suffix).exists() else 0 for suffix in ('','-wal','-shm','-journal')}


def quantiles(values):
    if not values:return {'count':0,'median_ms':None,'p95_ms':None,'p99_ms':None,'max_ms':None}
    v=sorted(values)
    return {'count':len(v),'median_ms':statistics.median(v),
        'p95_ms':v[math.ceil(.95*len(v))-1],'p99_ms':v[math.ceil(.99*len(v))-1],'max_ms':v[-1]}


class Resources:
    def __init__(self,pid,database):
        self.pid=pid;self.database=database;self.stop=threading.Event();self.samples=[]
        self.thread=threading.Thread(target=self.collect,daemon=True)
    def collect(self):
        while not self.stop.is_set():
            total={'rss':0,'cpu_seconds':0,'threads':0,'fds':0,'io_read_bytes':0,'io_write_bytes':0}
            try:processes=[psutil.Process(self.pid)]+psutil.Process(self.pid).children(recursive=True)
            except psutil.Error:processes=[]
            for p in processes:
                try:
                    total['rss']+=p.memory_info().rss;cpu=p.cpu_times()
                    total['cpu_seconds']+=cpu.user+cpu.system;total['threads']+=p.num_threads()
                    total['fds']+=p.num_fds() if hasattr(p,'num_fds') else 0
                    io=p.io_counters();total['io_read_bytes']+=io.read_bytes;total['io_write_bytes']+=io.write_bytes
                except (psutil.Error,AttributeError):pass
            total.update(at_ns=time.monotonic_ns(),database_files=files(self.database))
            self.samples.append(total);self.stop.wait(.25)
    def start(self):self.thread.start()
    def finish(self):
        self.stop.set();self.thread.join(timeout=2)
        if not self.samples:return {'samples':[]}
        a,b=self.samples[0],self.samples[-1]
        return {'sample_interval_seconds':.25,'sample_count':len(self.samples),
            'peak_server_rss_sum_bytes':max(s['rss'] for s in self.samples),
            'server_cpu_seconds_delta':max(0,b['cpu_seconds']-a['cpu_seconds']),
            'peak_server_threads':max(s['threads'] for s in self.samples),
            'peak_server_open_fds':max(s['fds'] for s in self.samples),
            'server_io_read_bytes_delta':max(0,b['io_read_bytes']-a['io_read_bytes']),
            'server_io_write_bytes_delta':max(0,b['io_write_bytes']-a['io_write_bytes']),
            'start_files':a['database_files'],'end_files':b['database_files'],
            'peak_wal_bytes':max(s['database_files']['-wal'] for s in self.samples),
            'rss_note':'Sum of master/worker RSS includes shared pages; not unique physical memory.'}


async def workload(port,route,cookies,level,operations,timeout,condition):
    start=time.monotonic_ns();go=asyncio.Event();events=[]
    async def actor(index):
        await go.wait()
        # Closed-loop requests are sequential per distinct learner. Burst mode
        # is operations==level; larger counts supply repeated allowed GETs.
        for ordinal in range(index,operations,level):
            scheduled=time.monotonic_ns();writer=None
            event=dict(condition,scheduled_ns=scheduled,start_ns=scheduled,
                request_ordinal=ordinal,learner_actor=index,cohort='ALLOWED_NAVIGATION',
                event_id=condition['run_id']+':'+str(ordinal),
                status_code=None,bytes=0,outcome='not_started')
            try:
                async with asyncio.timeout(timeout):
                    reader,writer=await asyncio.open_connection('127.0.0.1',port,limit=1024*1024)
                    writer.write(('GET '+route+' HTTP/1.1\r\nHost: localhost\r\nCookie: '+cookies[index]+
                        '\r\nAccept: text/html\r\nConnection: close\r\n\r\n').encode())
                    await writer.drain();header=await reader.readuntil(b'\r\n\r\n')
                    status=int(header.split(b' ',2)[1]);payload=await reader.read()
                    event.update(status_code=status,bytes=len(payload),
                        body_sha256=hashlib.sha256(payload).hexdigest(),
                        outcome='success' if status==200 and len(payload)>=1000 else 'http_error')
            except TimeoutError:event.update(outcome='timeout')
            except Exception as exc:event.update(outcome='transport_error',error_type=type(exc).__name__)
            finally:
                if writer is not None:writer.close()
                event['end_ns']=time.monotonic_ns()
                event['duration_ms']=(event['end_ns']-event['scheduled_ns'])/1e6
                events.append(event)
    tasks=[asyncio.create_task(actor(i)) for i in range(level)]
    go.set();await asyncio.gather(*tasks)
    return events,(time.monotonic_ns()-start)/1e9


def main():
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('database',type=Path)
    p.add_argument('output',type=Path);p.add_argument('--variant',required=True);p.add_argument('--fixture',required=True)
    p.add_argument('--route',default='/student/learn-vnext');p.add_argument('--programme',default='FSc Part 1')
    p.add_argument('--levels',default='1,10,50');p.add_argument('--operations',type=int,default=0)
    p.add_argument('--trials',type=int,default=1);p.add_argument('--timeout',type=float,default=45)
    p.add_argument('--port',type=int,default=18861);p.add_argument('--workers',type=int,default=1);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--trial-label',default='A1');p.add_argument('--server-one-cpu',action='store_true');a=p.parse_args()
    runtime=a.runtime.resolve();database=a.database.resolve();a.output=a.output.resolve()
    if not database.is_relative_to(ROOT) or database.is_symlink() or not database.is_file():
        raise RuntimeError('CONTINUATION_OWNED_DISPOSABLE_DATABASE_REQUIRED')
    if not runtime.is_relative_to(ROOT) or not (runtime/'scoremax_production.py').is_file():
        raise RuntimeError('CONTINUATION_NATIVE_RUNTIME_REQUIRED')
    levels=[int(x) for x in a.levels.split(',')]
    if min(levels)<1 or max(levels)>1000 or not (1<=a.workers<=2) or not (1<=a.threads<=4) or not (1<=a.timeout<=120) or a.operations>2000:
        raise RuntimeError('DECLARED_LOCAL_RESOURCE_BUDGET_EXCEEDED')
    dependencies=ROOT/'dependencies_v1'
    host_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None
    if a.server_one_cpu and (not host_affinity or not hasattr(os,'sched_setaffinity')):
        raise RuntimeError('ONE_CPU_SERVER_AFFINITY_NOT_AVAILABLE')
    server_affinity=host_affinity[:1] if a.server_one_cpu else host_affinity
    def resource_file(path):
        try:return Path(path).read_text(encoding='utf-8').strip()
        except OSError:return None
    sys.path.insert(0,str(dependencies))
    old=ROOT/'tests/navigation_perf_20261114/benchmark_gunicorn_http.py'
    spec=importlib.util.spec_from_file_location('native_http_original',old)
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    env=prior.make_environment(database);env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']=str(dependencies)+os.pathsep+str(runtime)
    os.environ.update({k:v for k,v in env.items() if k.startswith('SCOREMAX_')})
    pre_start=fingerprint(database);sys.path.insert(0,str(runtime))
    import scoremax_production
    app=scoremax_production.application
    serializer=app.session_interface.get_signing_serializer(app)
    with sqlite3.connect(database) as conn:
        students=conn.execute("SELECT id,COALESCE(session_version,0) FROM users WHERE system_user_id LIKE 'SYN-STUDENT-%' ORDER BY id LIMIT ?",(max(levels),)).fetchall()
    if len(students)<max(levels):raise RuntimeError('DISTINCT_LEARNER_FIXTURE_TOO_SMALL')
    cookies=[app.config.get('SESSION_COOKIE_NAME','session')+'='+serializer.dumps(
        {'user_id':uid,'role':'student','session_version':int(ver),'_csrf_token':'synthetic'}) for uid,ver in students]
    state=database.parent.parent;config=state/'gunicorn_qualification_config.py';ready=state/'worker_ready.txt'
    ready.unlink(missing_ok=True)
    config.write_text('def post_worker_init(worker):\n    with open('+repr(str(ready))+
        ", 'a', encoding='utf-8') as stream:\n        stream.write(str(worker.pid)+'\\n')\n",encoding='utf-8')
    report={'version':'SCOREMAX-NATIVE-HTTP-CONTINUATION-3','variant':a.variant,'fixture':a.fixture,
        'runtime':str(runtime),'database':str(database),'trial_label':a.trial_label,
        'workers':a.workers,'threads_per_worker':a.threads,'client_timeout_seconds':a.timeout,
        'mode':'single_wave_compatibility' if not a.operations else 'sequential_per_learner_closed_loop',
        'versions':{k:importlib.metadata.version(k) for k in ('Flask','Werkzeug','gunicorn')},
        'sqlite_version':sqlite3.sqlite_version,'pre_startup_fingerprint':pre_start,
        'invocation_id':uuid.uuid4().hex,
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'resource_environment':{'host_cpu_count':os.cpu_count(),'load_generator_affinity':host_affinity,
            'declared_server_affinity':server_affinity,'server_one_cpu_requested':a.server_one_cpu,
            'cgroup_cpu_max':resource_file('/sys/fs/cgroup/cpu.max'),
            'cgroup_memory_max':resource_file('/sys/fs/cgroup/memory.max'),
            'python':sys.version,'production_render_equivalence':False,
            'production_reference':'1CPU/2GiB/5GB disk, Python3.13.5; local stack differs.'},
        'conditions':[],'request_events':[],'runs':[],'production_render_capacity_qualified':False,
        'official_ai_scoring_enabled':False,'schema_changes':False,'production_actions':False}
    def save():
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    log_path=state/'gunicorn.log';started=time.monotonic()
    with log_path.open('w',encoding='utf-8') as log:
        command=[sys.executable,'-B','-m','gunicorn','scoremax_production:application',
            '--config',str(config),'--workers',str(a.workers),'--threads',str(a.threads),'--bind',f'127.0.0.1:{a.port}',
            '--timeout','120','--backlog','2048','--access-logfile','-','--error-logfile','-']
        affinity_hook=(lambda:os.sched_setaffinity(0,set(server_affinity))) if a.server_one_cpu else None
        proc=subprocess.Popen(command,cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,
            start_new_session=True,preexec_fn=affinity_hook)
        try:
            prior.wait_until_ready(proc,a.port);prior.wait_until_all_workers_initialised(proc,ready,a.workers)
            server_processes=[psutil.Process(proc.pid)]+psutil.Process(proc.pid).children(recursive=True)
            report['resource_environment']['observed_server_affinities']=[p.cpu_affinity() for p in server_processes]
            if a.server_one_cpu and any(set(p.cpu_affinity())!=set(server_affinity) for p in server_processes):
                raise RuntimeError('ONE_CPU_SERVER_AFFINITY_NOT_APPLIED')
            report['startup_seconds']=time.monotonic()-started
            # Read routes are warmed equally before timing; cold startup is kept separately.
            prior.request_once(a.port,a.route,cookies[0])
            report['post_startup_fingerprint']=fingerprint(database)
            for trial in range(a.trials):
                for level in levels:
                    condition={'variant':a.variant,'fixture':a.fixture,'route':a.route,
                        'programme':a.programme,'level':level,'trial':a.trial_label+':'+str(trial),
                        'invocation_id':report['invocation_id'],'workers':a.workers,'threads_per_worker':a.threads,
                        'server_affinity':server_affinity,'timeout_seconds':a.timeout}
                    condition['run_id']=hashlib.sha256(json.dumps(condition,sort_keys=True).encode()).hexdigest()[:24]
                    sampler=Resources(proc.pid,database);sampler.start()
                    run_start_ns=time.monotonic_ns()
                    events,wall=asyncio.run(workload(a.port,a.route,cookies,level,max(level,a.operations),a.timeout,condition))
                    run_end_ns=time.monotonic_ns()
                    resource=sampler.finish();outcomes={}
                    for event in events:outcomes[event['outcome']]=outcomes.get(event['outcome'],0)+1
                    successful=[e['duration_ms'] for e in events if e['outcome']=='success']
                    summary=dict(condition,scheduled=len(events),wall_seconds=wall,outcomes=outcomes,
                        all_outcomes_latency=quantiles([e['duration_ms'] for e in events]),
                        successful_nav_latency=quantiles(successful),
                        achieved_responses_per_second=len(events)/wall,
                        successful_responses_per_second=len(successful)/wall,
                        errors=len(events)-len(successful),resource=resource,
                        stable_tail_sample_minimum_met=len(successful)>=200,
                        timeout_censoring=any(e['outcome']=='timeout' for e in events))
                    report['conditions'].append(summary);report['request_events'].extend(events)
                    report['runs'].append({'run_id':condition['run_id'],'start_ns':run_start_ns,'end_ns':run_end_ns})
                    save()
                    print(json.dumps(summary,sort_keys=True),flush=True)
        finally:
            os.killpg(proc.pid,signal.SIGTERM) if proc.poll() is None else None
            try:proc.wait(timeout=12)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
            report['server_exit_code']=proc.returncode
            report['after_workload_fingerprint']=fingerprint(database)
            report['protected_rows_unchanged_after_warmup']=(report.get('post_startup_fingerprint')==report['after_workload_fingerprint'])
            report['final_database_files']=files(database)
            report['local_free_disk_bytes']=psutil.disk_usage(str(database.parent)).free
            report['sql_statement_latencies']='Separate diagnostic profile logs; no timing instrumentation in primary HTTP run.'
            report['writes_marking_ack_backup_mixed_load']='NOT_EXERCISED_BY_THIS_READ_ONLY_DRIVER'
            save()


if __name__=='__main__':main()
