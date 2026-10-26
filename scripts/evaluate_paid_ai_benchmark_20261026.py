"""Evaluate only independently approved references; engineering fixtures cannot qualify grades."""
import argparse,hashlib,json,math
from pathlib import Path
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def evaluate(reference,predictions):
    approval=reference.get('independent_reference_approval') or {}
    if (approval.get('status')!='APPROVED' or not approval.get('approving_authority')
            or not approval.get('receipt_reference') or not approval.get('approved_manifest_sha256')):
        raise ValueError('INDEPENDENT_REFERENCE_MARK_APPROVAL_PENDING')
    cases=reference.get('cases') or []
    manifest=[{k:r[k] for k in ('case_id','question_id','question_version_id','question_checksum_sha256','rubric_sha256','reference_marks')} for r in cases]
    if hashlib.sha256(canonical(manifest).encode()).hexdigest()!=approval['approved_manifest_sha256']:
        raise ValueError('APPROVED_REFERENCE_MANIFEST_HASH_MISMATCH')
    refs={r['case_id']:r for r in cases}
    if not refs or len(refs)!=len(cases) or any(r['reference_marks'] is None for r in cases):
        raise ValueError('COMPLETE_APPROVED_REFERENCE_MARKS_REQUIRED')
    groups={}
    seen=set()
    for p in predictions:
        key=(p['model'],p['case_id'])
        if key in seen:raise ValueError('DUPLICATE_MODEL_CASE_PREDICTION')
        seen.add(key);r=refs.get(p['case_id'])
        if not r or any(p.get(k)!=r[k] for k in ('question_id','question_version_id','question_checksum_sha256','rubric_sha256')):
            raise ValueError('PREDICTION_GOVERNED_LINEAGE_MISMATCH')
        bucket=groups.setdefault(p['model'],{'case_count':0,'exact_marks':0,'absolute_error_sum':0.0,'overmarks':0,'errors':0,'measured_usd':0.0})
        bucket['case_count']+=1
        if p.get('error'):bucket['errors']+=1;continue
        actual=float(p['awarded_marks']);expected=float(r['reference_marks']);cost=float(p['measured_usd'])
        if not all(math.isfinite(x) and x>=0 for x in (actual,expected,cost)):raise ValueError('INVALID_BENCHMARK_VALUE')
        bucket['exact_marks']+=actual==expected;bucket['absolute_error_sum']+=abs(actual-expected)
        bucket['overmarks']+=actual>expected;bucket['measured_usd']+=cost
    for bucket in groups.values():
        if bucket['case_count']!=len(refs):raise ValueError('ALL_APPROVED_CASES_REQUIRED_PER_MODEL')
        successful=bucket['case_count']-bucket['errors']
        bucket['mean_absolute_mark_error']=bucket['absolute_error_sum']/successful if successful else None
    return {'independent_reference_approval':'APPROVED','models':groups,'automatic_official_grade_or_mastery_authority':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference');p.add_argument('predictions');p.add_argument('output');a=p.parse_args()
    result=evaluate(json.loads(Path(a.reference).read_text()),json.loads(Path(a.predictions).read_text()))
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
