"""Eligibility of signed Power House projections for formal independent mastery.

This gate does not grant academic authority or alter ordinary practice, coverage,
accuracy thresholds, question tiers, or native ScoreMax inventory.
"""
import math

POLICY = 'SM-PH-FORMAL-INDEPENDENT-EVIDENCE-1'
DEPENDENT_TYPES = frozenset({
    'VARIANT', 'TRUE_VARIANT', 'SCAFFOLD', 'RECOVERY', 'RECONFIRMATION',
    'DEPENDENT', 'SHARED_STIMULUS_DEPENDENT',
})


def eligible_for_formal_mastery(row):
    """Keep native eligibility; PH evidence needs an independent role and weight."""
    try:
        q = dict(row)
    except (TypeError, ValueError):
        return False
    markers = ('ph_question_id', 'ph_question_version_id',
               'ph_question_checksum_sha256', 'ph_release_id',
               'ph_evidence_role', 'ph_dependency_type')
    ph_owned = (any(str(q.get(k) or '').strip() for k in markers)
                or str(q.get('ph_projection_owner') or '').strip().upper() == 'POWER_HOUSE'
                or str(q.get('source_type') or '').strip().casefold().startswith('power house'))
    if not ph_owned:
        return True
    role = str(q.get('ph_evidence_role') or '').strip().upper()
    dependency = str(q.get('ph_dependency_type') or '').strip().upper()
    if role != 'INDEPENDENT' or dependency in DEPENDENT_TYPES:
        return False
    weight = q.get('ph_independent_mastery_weight')
    if isinstance(weight, bool):
        return False
    try:
        weight = float(weight)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(weight) and weight > 0


def question_ids_have_formal_evidence(conn, question_ids):
    """One bounded lookup of internal question keys for a completed formal form."""
    if (not isinstance(question_ids, (list, tuple)) or not question_ids
            or any(isinstance(x, bool) or not isinstance(x, (int, str)) for x in question_ids)):
        return False
    marks = ','.join('?' for _ in question_ids)
    rows = conn.execute('SELECT * FROM questions WHERE id IN (' + marks + ')',
                        tuple(question_ids)).fetchall()
    return len(rows) == len(question_ids) and all(eligible_for_formal_mastery(q) for q in rows)
