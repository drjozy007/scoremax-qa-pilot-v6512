from __future__ import annotations
from pathlib import Path

MARKER='SM-PH-EMERGENCY-RETURN-DISPATCH-20260916-1'


def _replace_once(path:Path,old:str,new:str)->None:
    s=path.read_text(encoding='utf-8'); n=s.count(old)
    if n!=1: raise SystemExit(f'EMERGENCY_DISPATCH_PATCH_ANCHOR_MISMATCH path={path} count={n}')
    path.write_text(s.replace(old,new,1),encoding='utf-8')


def apply_emergency_return_dispatch(root:Path)->None:
    p=root/'scoremax_integration_v1.py'
    old="""def _dispatch_target(contract):
    if contract in {'SM_PH_DELIVERY_EVIDENCE_V1','SM_PH_CONTENT_REQUIREMENT_V1'}:
        base=os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL','').rstrip('/'); path='/api/integration/v1/scoremax/delivery-evidence' if contract=='SM_PH_DELIVERY_EVIDENCE_V1' else '/api/integration/v1/scoremax/content-requirements'; direction='SCOREMAX_TO_POWER_HOUSE'
    elif contract=='SM_GE_PRODUCT_EVENT_V1':
"""
    new="""def _dispatch_target(contract):
    if contract in {'SM_PH_DELIVERY_EVIDENCE_V1','SM_PH_CONTENT_REQUIREMENT_V1','SM_PH_CONTENT_INCIDENT_V1'}:
        base=os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL','').rstrip('/')
        paths={
          'SM_PH_DELIVERY_EVIDENCE_V1':'/api/integration/v1/scoremax/delivery-evidence',
          'SM_PH_CONTENT_REQUIREMENT_V1':'/api/integration/v1/scoremax/content-requirements',
          'SM_PH_CONTENT_INCIDENT_V1':'/api/integration/v1/scoremax/content-incidents',
        }
        path=paths[contract]; direction='SCOREMAX_TO_POWER_HOUSE'
    elif contract=='SM_GE_PRODUCT_EVENT_V1':
"""
    _replace_once(p,old,new)

    old="""      'SM_PH_DELIVERY_EVIDENCE_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_PH_CONTENT_REQUIREMENT_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_GE_PRODUCT_EVENT_V1':'SCOREMAX_TO_GROWTH_ENGINE_CREDENTIAL_EXPIRES_AT',
"""
    new="""      'SM_PH_DELIVERY_EVIDENCE_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_PH_CONTENT_REQUIREMENT_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_PH_CONTENT_INCIDENT_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_GE_PRODUCT_EVENT_V1':'SCOREMAX_TO_GROWTH_ENGINE_CREDENTIAL_EXPIRES_AT',
"""
    _replace_once(p,old,new)

    old="""        ('SCOREMAX -> POWER_HOUSE','SM_PH_DELIVERY_EVIDENCE_V1','OUTBOUND'),
        ('SCOREMAX -> POWER_HOUSE','SM_PH_CONTENT_REQUIREMENT_V1','OUTBOUND'),
        ('SCOREMAX -> GROWTH_ENGINE','SM_GE_PRODUCT_EVENT_V1','OUTBOUND'),
"""
    new="""        ('SCOREMAX -> POWER_HOUSE','SM_PH_DELIVERY_EVIDENCE_V1','OUTBOUND'),
        ('SCOREMAX -> POWER_HOUSE','SM_PH_CONTENT_REQUIREMENT_V1','OUTBOUND'),
        ('SCOREMAX -> POWER_HOUSE','SM_PH_CONTENT_INCIDENT_V1','OUTBOUND'),
        ('SCOREMAX -> GROWTH_ENGINE','SM_GE_PRODUCT_EVENT_V1','OUTBOUND'),
"""
    _replace_once(p,old,new)

    old="""            'local_schema_version':RECTIFIED_SCHEMA_VERSION if contract=='PH_SM_APPROVED_CONTENT_V1' else SCHEMA_VERSION,
"""
    new="""            'local_schema_version':('1.1.0' if contract=='SM_PH_CONTENT_INCIDENT_V1' else (RECTIFIED_SCHEMA_VERSION if contract=='PH_SM_APPROVED_CONTENT_V1' else SCHEMA_VERSION)),
"""
    _replace_once(p,old,new)

    print(f'{MARKER} PASS existing_dispatcher_extended=true incident_path=/api/integration/v1/scoremax/content-incidents credentials=SCOREMAX_TO_POWER_HOUSE health_observable=true',flush=True)
