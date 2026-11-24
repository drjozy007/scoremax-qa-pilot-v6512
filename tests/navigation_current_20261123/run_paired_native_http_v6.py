"""Sequential paired disposable HTTP trial orchestration; preserves every result."""
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
 p=argparse.ArgumentParser();p.add_argument('seed',type=Path);p.add_argument('output_directory',type=Path)
 p.add_argument('--fixture',required=True);p.add_argument('--order',default='ABBA,BAAB')
 p.add_argument('--levels',default='1,10,50');p.add_argument('--timeout',default='45')
 p.add_argument('--operations',type=int,default=0);p.add_argument('--routes',default='learn,subject')
 p.add_argument('--server-one-cpu',action='store_true')
 p.add_argument('--reference-runtime',type=Path,required=True);p.add_argument('--candidate-runtime',type=Path,required=True)
 p.add_argument('--workers',type=int,default=1);p.add_argument('--threads',type=int,default=4)
 a=p.parse_args();seed=a.seed.resolve();out=a.output_directory.resolve()
 if not seed.is_relative_to(ROOT) or not out.is_relative_to(ROOT):raise RuntimeError('OWNED_DISPOSABLE_PATHS_REQUIRED')
 if out.exists():raise RuntimeError('NEW_EVIDENCE_DIRECTORY_REQUIRED')
 if Path(str(seed)+'-wal').exists() and Path(str(seed)+'-wal').stat().st_size:
  raise RuntimeError('SEED_HAS_UNCHECKPOINTED_WAL_USE_SQLITE_BACKUP_API')
 out.mkdir(parents=True);manifest={'version':'SCOREMAX-NATIVE-HTTP-EXECUTION-5','fixture':a.fixture,'seed_sha256':hashlib.sha256(seed.read_bytes()).hexdigest(),
  'order':a.order,'levels':a.levels,'trials':[],'production_actions':False,'capacity_acceptance':'PENDING_INDEPENDENT_EVALUATION'}
 routes={'learn':'/student/learn-vnext','subject':'/student/subject/Biology',
  'chapter':'/student/chapter?subject=Biology&chapter=Synthetic%20Chapter%201',
  'catalogue':'/student/catalogue/year11/Biology'}
 for block,order in enumerate(a.order.split(',')):
  for index,letter in enumerate(order):
   if letter not in 'AB':raise RuntimeError('ORDER_REQUIRES_AB_VARIANTS')
   variant='reference_runtime' if letter=='A' else 'candidate_runtime'
   runtime=a.reference_runtime.resolve() if letter=='A' else a.candidate_runtime.resolve()
   if not runtime.is_relative_to(ROOT):raise RuntimeError('OWNED_RUNTIME_REQUIRED')
   for route in a.routes.split(','):
    label=f'{block}-{index}-{letter}-{route}';state=out/label/'state';state.mkdir(parents=True)
    db=state/'measure.db';shutil.copy2(seed,db)
    assert hashlib.sha256(db.read_bytes()).hexdigest()==manifest['seed_sha256']
    output=out/(label+'.json');log=out/(label+'.log')
    command=[sys.executable,'-B',str(ROOT/'tests/navigation_current_20261123/benchmark_native_http_v4.py'),
     str(runtime),str(db),str(output),'--variant',variant,'--fixture',a.fixture,
     '--levels',a.levels,'--timeout',a.timeout,'--trial-label',label,
     '--route',routes[route],'--operations',str(a.operations),'--port','18861','--workers',str(a.workers),'--threads',str(a.threads)]
    if a.server_one_cpu:command.append('--server-one-cpu')
    started=time.monotonic()
    with log.open('w',encoding='utf-8') as stream:
     result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    entry={'label':label,'variant':variant,'route':routes[route],'returncode':result.returncode,
     'wall_seconds':time.monotonic()-started,'result':str(output),'log':str(log)}
    if output.exists():
     raw=json.loads(output.read_text());entry['conditions']=[{'level':c['level'],
      'successful_p95_ms':c['successful_nav_latency']['p95_ms'],'errors':c['errors'],
      'timeout_censoring':c['timeout_censoring'],'successful_throughput':c['successful_responses_per_second']}
      for c in raw['conditions']]
     entry['protected_rows_unchanged_after_warmup']=raw.get('protected_rows_unchanged_after_warmup')
    manifest['trials'].append(entry)
    (out/'execution_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(entry,sort_keys=True),flush=True)
    # Only trial DB copies are removed. Raw events, value hashes, logs and seed
    # stay available; no runtime DB is placed in a release package.
    for suffix in ('','-wal','-shm','-journal'):Path(str(db)+suffix).unlink(missing_ok=True)


if __name__=='__main__':main()
