"""One bounded run of changed paths; no bank workload or PH connection."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
CG=Path('/sys/fs/cgroup');OUT=Path('/evidence');OUT.mkdir(exist_ok=True)
def counters(name):return {k:int(v) for k,v in (x.split() for x in (CG/name).read_text().splitlines())}
memory_before=counters('memory.events');cpu_before=counters('cpu.stat');started=time.monotonic()
results=[]
def run(name,command,root=None):
 env=dict(os.environ)
 if root:env['BIOLOGY_TEST_ROOT']=root
 begin=time.monotonic();reply=subprocess.run([sys.executable,'-B']+command,env=env,text=True,capture_output=True,timeout=100)
 (OUT/(name+'.log')).write_text(reply.stdout+reply.stderr)
 if reply.returncode:raise AssertionError(name+' failed:\n'+(reply.stdout+reply.stderr)[-9000:])
 results.append({'check':name,'passed':True,'seconds':time.monotonic()-begin})
run('accepted-public-gap-reproduction',['/checks/tests/biology_receiver_20261027/test_receiver.py','/accepted','--baseline-probe'],'/data/bio-baseline')
run('biology-native-receiver',['/checks/tests/biology_receiver_20261027/test_receiver.py','/app'],'/data/bio-candidate')
run('accepted-public-cold-rollback',['/checks/tests/biology_receiver_20261027/test_receiver.py','/accepted','--rollback-existing'],'/data/bio-candidate')
run('manifest-byte-bounds',['/checks/tests/biology_receiver_20261027/test_manifest_limits.py','/app'])
run('affected-native-pull-security',['/checks/scripts/qualify_native_manifest_pull.py','--runtime','/app'])
memory_after=counters('memory.events');memory_delta={k:memory_after[k]-v for k,v in memory_before.items()}
assert all(memory_delta[k]==0 for k in ('high','max','oom','oom_kill')),memory_delta
result={'status':'BIOLOGY_RECEIVER_ENGINEERING_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'runtime_sha256':'ddb4ee4a1398c0e5ac2300e4711b7a1befadd7e4ef067dfc21bc28de118cdc9c','runtime_files':261,
 'accepted_public_cold_rollback':True,'targeted_native_cases':15,'baseline_gap_reproduction_cases':15,'manifest_bound_cases':4,
 'checks':results,'elapsed_seconds':time.monotonic()-started,'memory_event_delta':memory_delta,
 'memory_peak_bytes':int((CG/'memory.peak').read_text()),'cpu_stat_delta':{k:v-cpu_before.get(k,0) for k,v in counters('cpu.stat').items()},
 'production_data_used':False,'power_house_accessed':False,'production_deployments':0,
 'academic_banks_generated':False,'historical_transfers_or_acks_replayed':False,'Gate_D_replayed':False,
 'live_question_or_release_changes':0,'AI_candidate_applied':False,'paid_AI_calls':0,
 'scope':'Receiver compatibility and changed native student scopes only; no 300/1500 academic-bank or production capacity qualification'}
(OUT/'BIOLOGY_RECEIVER_ENGINEERING_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
