from __future__ import annotations
import json
from pathlib import Path

MARKER='SM-PH-CONTENT-INCIDENT-V1-SCHEMA-1.1.0-20260916'
INCIDENT='SM_PH_CONTENT_INCIDENT_V1'


def _replace_once(path:Path,old:str,new:str)->None:
    text=path.read_text(encoding='utf-8'); n=text.count(old)
    if n!=1: raise SystemExit(f'EMERGENCY_CONTRACT_PATCH_ANCHOR_MISMATCH path={path} count={n}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')


def apply_emergency_return_contract(root:Path)->None:
    integration=root/'scoremax_integration_v1.py'
    bridge=root/'scoremax_ph_bridge_v6611d.py'
    base=root/'integration_contracts'
    old_schema_path=base/(INCIDENT+'.schema.json')
    if not old_schema_path.is_file(): raise SystemExit('EMERGENCY_INCIDENT_V1_SCHEMA_MISSING')
    old_schema=json.loads(old_schema_path.read_text(encoding='utf-8'))
    schema=json.loads(json.dumps(old_schema))
    schema['properties']['schema_version']={'const':'1.1.0'}
    qprop=schema['properties']['payload']['properties']['question']
    native=json.loads(json.dumps(qprop))
    emergency={
      'type':'object','additionalProperties':False,
      'required':['identity_mode','source_question_id','power_house_public_id','power_house_source_row','batch_code','transport_sha256','selection_ledger_sha256','source_prompt_pack_id','rendered_question_sha256'],
      'properties':{
        'identity_mode':{'const':'EMERGENCY_DIRECT_GOVERNED'},
        'source_question_id':{'type':'string','minLength':1,'maxLength':256},
        'power_house_public_id':{'type':'string','minLength':1,'maxLength':256},
        'power_house_source_row':{'type':'string','minLength':1,'maxLength':128},
        'batch_code':{'type':'string','minLength':1,'maxLength':128},
        'transport_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
        'selection_ledger_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
        'source_prompt_pack_id':{'type':'string','maxLength':256},
        'rendered_question_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
      }
    }
    schema['properties']['payload']['properties']['question']={'oneOf':[native,emergency]}
    target_dir=base/'v1_1_0'; target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/(INCIDENT+'.schema.json')
    target.write_text(json.dumps(schema,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

    old="""    if contract in {'PH_SM_APPROVED_CONTENT_V1','PH_SM_APPROVED_CONTENT_MANIFEST_V1','PH_SM_APPROVED_CONTENT_PACKAGE_V1'} and sv in {'1.1.0','1.2.0'}:
        return base/('v1_1_0' if sv=='1.1.0' else 'v1_2_0')/(contract+'.schema.json')
"""
    new="""    if contract in {'PH_SM_APPROVED_CONTENT_V1','PH_SM_APPROVED_CONTENT_MANIFEST_V1','PH_SM_APPROVED_CONTENT_PACKAGE_V1'} and sv in {'1.1.0','1.2.0'}:
        return base/('v1_1_0' if sv=='1.1.0' else 'v1_2_0')/(contract+'.schema.json')
    if contract=='SM_PH_CONTENT_INCIDENT_V1' and sv=='1.1.0':
        return base/'v1_1_0'/(contract+'.schema.json')
"""
    _replace_once(integration,old,new)
    old="""    supported={'1.0.0','1.1.0','1.2.0'} if contract=='PH_SM_APPROVED_CONTENT_V1' else {'1.0.0'}
"""
    new="""    supported=({'1.0.0','1.1.0','1.2.0'} if contract=='PH_SM_APPROVED_CONTENT_V1' else ({'1.0.0','1.1.0'} if contract=='SM_PH_CONTENT_INCIDENT_V1' else {'1.0.0'}))
"""
    _replace_once(integration,old,new)
    old="""    env={'message_id':msg,'contract_name':contract,'contract_version':'1','schema_version':SCHEMA_VERSION,'source_system':'SCOREMAX','destination_system':destination,
"""
    new="""    schema_version='1.1.0' if contract=='SM_PH_CONTENT_INCIDENT_V1' else SCHEMA_VERSION
    env={'message_id':msg,'contract_name':contract,'contract_version':'1','schema_version':schema_version,'source_system':'SCOREMAX','destination_system':destination,
"""
    _replace_once(integration,old,new)

    # Native payload stays byte-shape compatible with incident schema 1.0.0; identity_mode is emergency-only.
    native_line="          'identity_mode':'NATIVE_POWER_HOUSE_RELEASE',\n"
    text=bridge.read_text(encoding='utf-8')
    if text.count(native_line)!=1: raise SystemExit('EMERGENCY_NATIVE_PAYLOAD_COMPAT_ANCHOR_MISMATCH')
    bridge.write_text(text.replace(native_line,'',1),encoding='utf-8')

    # Prove the frozen 1.0.0 schema bytes remain untouched.
    frozen=json.loads(old_schema_path.read_text(encoding='utf-8'))
    if frozen.get('properties',{}).get('schema_version',{}).get('const')!='1.0.0': raise SystemExit('EMERGENCY_INCIDENT_V1_FROZEN_SCHEMA_CHANGED')
    if json.loads(target.read_text(encoding='utf-8'))['properties']['schema_version']['const']!='1.1.0': raise SystemExit('EMERGENCY_INCIDENT_V11_SCHEMA_WRITE_FAILED')
    print(f'{MARKER} PASS frozen_1_0_0=true incident_1_1_0=true native_shape_preserved=true emergency_shape_closed=true',flush=True)
