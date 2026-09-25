from __future__ import annotations

from hashlib import sha256

from scripts import run_semantic_qa_seeded_visual_diagnostic_v2 as base

_STUDENT_CLEAN_ATTEMPTS={
    "S-C01":"Selected response: A. DNA",
    "S-C02":"Selected response: A. 1/4",
    "S-C03":"Selected response: A. Nucleus",
    "S-C04":"Selected response: B. Aa",
    "S-C05":"Selected response: A. Prophase I",
    "S-C06":"Selected response: A. Pleiotropy",
    "S-C07":"Selected response: A. ii",
    "S-C08":"Selected response: A. 1/4",
    "S-C09":"Selected response: A. Meiosis",
    "S-C10":"Selected response: A. aa",
}


def _student_complete_evidence(rows):
    out=[]
    for case in rows:
        attempt=_STUDENT_CLEAN_ATTEMPTS.get(case.case_id)
        if not attempt:
            out.append(case);continue
        lines=tuple(x for x in case.lines if not str(x).startswith("Submission status:"))+(attempt,"Platform feedback: Correct.")
        out.append(base.Case(case.case_id,case.expected,case.severity,case.category,lines))
    return out


def _opaque(case):
    token=sha256(("PH-QA-DIAG-V2.1|"+case.case_id).encode()).hexdigest()[:12].upper()
    return base.Case("QAX-"+token,case.expected,case.severity,case.category,case.lines)


def _mixed(rows):
    clean=sorted((_opaque(x) for x in rows if x.expected=="CLEAN"),key=lambda x:x.case_id)
    defect=sorted((_opaque(x) for x in rows if x.expected=="DEFECT"),key=lambda x:x.case_id)
    if len(clean)!=10 or len(defect)!=10:
        raise RuntimeError("diagnostic must contain exactly 10 clean and 10 defect controls")
    out=[]
    for c,d in zip(clean,defect):
        # Deterministically vary which member of each pair appears first without exposing gold state.
        if int(sha256((c.case_id+d.case_id).encode()).hexdigest()[-1],16)%2:
            out.extend((d,c))
        else:
            out.extend((c,d))
    if len({x.case_id for x in out})!=20:
        raise RuntimeError("opaque diagnostic IDs are not unique")
    # Every rendered 5-panel batch must mix clean and defective controls.
    for start in range(0,20,5):
        states={x.expected for x in out[start:start+5]}
        if states!={"CLEAN","DEFECT"}:
            raise RuntimeError("diagnostic batch leaked population class by clustering")
    return out


_original_student=base.student_cases
_original_reviewer=base.reviewer_cases
base.student_cases=lambda:_mixed(_student_complete_evidence(_original_student()))
base.reviewer_cases=lambda:_mixed(_original_reviewer())

if __name__=="__main__":
    base.main()
