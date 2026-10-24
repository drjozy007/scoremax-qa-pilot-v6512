"""AST/hash checks only: never import the Flask application or run a build."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
dump=lambda node:ast.dump(node,include_attributes=False)
read=lambda name:(HERE/name).read_text(encoding='utf-8')
app_before=ast.parse(read('app.baseline.py'));app_after=ast.parse(read('app.py'))
def function(module,name):
    matches=[n for n in module.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    assert len(matches)==1,name
    return matches[0]
old=function(app_before,'_pilot_backup');new=function(app_after,'_pilot_backup')
assert dump(old.args)==dump(new.args)
old_if=[n for n in old.body if isinstance(n,ast.If)]
new_if=[n for n in new.body if isinstance(n,ast.If)]
assert len(old_if)==len(new_if)==1
assert dump(old_if[0].test)==dump(new_if[0].test)
# Remove only the successful-artifact digest branch, then compare every caller
# commit, receipt, return key, native helper call and all other app AST nodes.
old_if[0].body=[ast.Pass()];new_if[0].body=[ast.Pass()]
assert dump(app_before)==dump(app_after)
raw_new=function(ast.parse(read('app.py')),'_pilot_backup')
assert not any(isinstance(n,ast.Attribute) and n.attr=='read_bytes' for n in ast.walk(raw_new))
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read'
           and len(n.args)==1 and isinstance(n.args[0],ast.BinOp)
           and ast.literal_eval(ast.Expression(n.args[0].left))==1024
           and ast.literal_eval(ast.Expression(n.args[0].right))==1024 for n in ast.walk(raw_new))

engine_before=ast.parse(read('pilot_readiness_engine.baseline.py'))
engine_after=ast.parse(read('pilot_readiness_engine.py'))
before_funcs={n.name:n for n in engine_before.body if isinstance(n,ast.FunctionDef)}
after_funcs={n.name:n for n in engine_after.body if isinstance(n,ast.FunctionDef)}
assert set(after_funcs)-set(before_funcs)=={'_native_backup_semantics','_native_backup_free_space'}
assert not set(before_funcs)-set(after_funcs)
for name,body in before_funcs.items():
    if name!='sqlite_backup':assert dump(body)==dump(after_funcs[name]),name
assert dump(before_funcs['sqlite_backup'].args)==dump(after_funcs['sqlite_backup'].args)
assert dump(before_funcs['sqlite_backup'].returns)==dump(after_funcs['sqlite_backup'].returns)
old_constants=[n for n in engine_before.body if isinstance(n,(ast.Assign,ast.AnnAssign))]
new_constants=[n for n in engine_after.body if isinstance(n,(ast.Assign,ast.AnnAssign)) and not (
    isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_NATIVE_BACKUP_SLACK_BYTES' for t in n.targets))]
assert [dump(n) for n in old_constants]==[dump(n) for n in new_constants]

deploy_before=read('deploy_ux_vnext.accepted630.source.py')
assert hashlib.sha1(b'blob '+str(len(deploy_before.encode())).encode()+b'\0'+deploy_before.encode()).hexdigest()=='e311d3f73f6d62428e607c26ae4c93474d551739'
anchor='    apply_native_manifest_pull(ROOT)\n'
hook="    from scripts.apply_scoremax_native_backup_delta_20261024 import apply as apply_native_backup_delta\n    print('SCOREMAX_NATIVE_BACKUP_DELTA', apply_native_backup_delta(ROOT), flush=True)\n"
assert deploy_before.count(anchor)==1
deploy_after=deploy_before.replace(anchor,anchor+hook,1)
hook_patch=''.join(difflib.unified_diff(deploy_before.splitlines(keepends=True),deploy_after.splitlines(keepends=True),fromfile='a/deploy_ux_vnext.py',tofile='b/deploy_ux_vnext.py'))
assert read('deploy_ux_vnext_native_backup_hook.patch')==hook_patch
parsed_before=ast.parse(deploy_before);parsed_after=ast.parse(deploy_after)
after_main=function(parsed_after,'main')
assert isinstance(after_main.body[-2],ast.ImportFrom) and after_main.body[-2].module=='scripts.apply_scoremax_native_backup_delta_20261024'
assert isinstance(after_main.body[-1],ast.Expr)
del after_main.body[-2:]
assert dump(parsed_before)==dump(parsed_after)

pins={name:sha((HERE/name).read_bytes()) for name in ('app.py','pilot_readiness_engine.py','backup_capacity_v1.py')}
assert pins['backup_capacity_v1.py']=='ebb95b113285ae6dd8d3e27eb0c0f537f70eecabd5c728dcae48ef986f4308a3'
manifest=json.loads(read('runtime_capture_manifest_630.json'))
tree=lambda items:sha(json.dumps(items,sort_keys=True,separators=(',',':')).encode())
assert len(manifest)==259 and tree(manifest)=='28aeb812a0ed269840ff73ea45f6864cf78138e57f98ab6c1c69093161ba6279'
derived={**manifest,**pins}
for name in ('app.py','pilot_readiness_engine.py'):
    baseline=name.replace('.py','.baseline.py')
    delta=''.join(difflib.unified_diff(read(baseline).splitlines(keepends=True),read(name).splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
    (HERE/(name+'.patch')).write_text(delta,encoding='utf-8',newline='\n')
result={
 'passed':True,'scope':'AST and source hashes only; no application import/build/test replay',
 'app_all_other_AST_unchanged':True,'backup_receipt_return_commit_and_failure_gates_unchanged':True,
 'engine_other_functions_and_constants_unchanged':True,'native_signature_and_return_annotation_unchanged':True,
 'existing_deploy_checks_preserved_AST':True,'hook_after_final_native_manifest_overlay':True,
 'baseline_runtime_files':259,'candidate_runtime_files':len(derived),
 'baseline_runtime_tree_sha256':tree(manifest),'candidate_runtime_tree_sha256':tree(derived),
 'candidate_sha256':pins,
 'deploy_hook_baseline_git_blob':'e311d3f73f6d62428e607c26ae4c93474d551739',
 'deploy_hook_baseline_sha256':sha(deploy_before.encode()),
 'installer_sha256':sha((HERE/'apply_scoremax_native_backup_delta_20261024.py').read_bytes()),
 'production_access':False,'services_started':0,'historical_suites_replayed':0,
}
(HERE/'NATIVE_BACKUP_SOURCE_CHECK_RESULT_20261024.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,sort_keys=True))
