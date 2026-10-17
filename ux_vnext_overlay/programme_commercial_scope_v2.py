"""Build-time donor for the existing commercial coverage subject lookup."""

def programme_subjects(c, programme):
    from question_contract_engine import programme_aliases
    aliases=sorted({str(v).strip().casefold() for v in programme_aliases(programme) if str(v).strip()})
    if not aliases: return []
    slots=','.join('?' for _ in aliases)
    columns={r['name'] for r in c.execute('PRAGMA table_info(questions)')}
    tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    native={'integration_ph_question_version_store','integration_ph_release_question_membership','integration_ph_content_releases'}
    if 'ph_projection_owner' not in columns or not native.issubset(tables):
        rows=c.execute(f"SELECT DISTINCT subject FROM questions WHERE COALESCE(subject,'')<>'' AND (lower(COALESCE(programme,'')) IN ({slots}) OR lower(COALESCE(qualification,'')) IN ({slots})) ORDER BY subject",aliases+aliases).fetchall()
    else:
        rows=c.execute(f"""SELECT DISTINCT q.subject FROM questions q WHERE COALESCE(q.subject,'')<>'' AND (
          (COALESCE(q.ph_projection_owner,'')<>'POWER_HOUSE' AND
            (lower(COALESCE(q.programme,'')) IN ({slots}) OR lower(COALESCE(q.qualification,'')) IN ({slots})))
          OR (q.ph_projection_owner='POWER_HOUSE' AND EXISTS (
            SELECT 1 FROM integration_ph_question_version_store v
            JOIN integration_ph_release_question_membership m ON m.question_id=v.question_id AND m.question_version_id=v.question_version_id
            JOIN integration_ph_content_releases r ON r.release_id=m.release_id AND r.release_version=m.release_version
            WHERE v.local_question_db_id=q.id AND v.question_id=q.ph_question_id
              AND v.question_version_id=q.ph_question_version_id AND v.question_checksum_sha256=q.ph_question_checksum_sha256
              AND r.local_status='ACTIVE' AND lower(scoremax_release_programme(r.programme_id,v.curriculum_json)) IN ({slots})
              AND EXISTS(SELECT 1 FROM integration_ph_product_activation_authorizations a
                WHERE a.release_id=r.release_id AND a.release_version=r.release_version
                  AND a.package_checksum_sha256=r.package_checksum_sha256 AND a.activation_status IN ('AUTHORIZED','ACTIVATED'))
              AND NOT EXISTS(SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
                WHERE e.release_id=m.release_id AND e.release_version=m.release_version
                  AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id))))
          ORDER BY q.subject""",aliases+aliases+aliases).fetchall()
    return [r['subject'] for r in rows]
