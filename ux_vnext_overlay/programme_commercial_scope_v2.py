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
            WHERE v.local_question_db_id=q.id AND r.local_status='ACTIVE' AND lower(trim(r.programme_id)) IN ({slots}))))
          ORDER BY q.subject""",aliases+aliases+aliases).fetchall()
    return [r['subject'] for r in rows]
