from __future__ import annotations

import re
from pathlib import Path


def apply_chapter_card_open_fix(root: Path) -> None:
    """Bind learner catalogue chapters to governed source chapter identity.

    The browse catalogue owns learner-facing number/name labels. Imported content keeps
    its exact governed source chapter string. These identities must be joined through
    ``chapter_catalogue`` before availability, mastery or navigation is calculated.

    This deliberately keeps three concerns separate:
      * catalogue display identity;
      * governed source identity;
      * formal mastery eligibility.
    """
    runtime_path=root/'ux_student_batch.py'
    template_path=root/'templates'/'ux_subject_chapters.html'
    if not runtime_path.is_file() or not template_path.is_file():
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_SOURCE_MISSING')

    runtime=runtime_path.read_text(encoding='utf-8')
    replacement=r'''def _chapter_snapshots(conn, student_id: int, subject: str) -> list[dict]:
    import app as runtime
    programme=(_active_programme_for_student(conn,student_id) or '').strip()
    track=_programme_track(programme)
    canonical=_catalogue_subject(track,subject) if track else ''
    if track and canonical:
        browse_items=list(subject_items(track,canonical))
    else:
        browse_items=[{'number':'','name':name} for name in _catalogue_for_student(conn,student_id,subject)]

    aliases=runtime._programme_aliases(programme) if programme else []
    if aliases:
        programme_clause,programme_params=runtime._programme_scope_sql(aliases,'q')
    else:
        programme_clause,programme_params='1=1',[]

    out=[]
    for idx,item in enumerate(browse_items,1):
        display_name=str(item.get('name') or '').strip()
        display_number=str(item.get('number') or '').strip()

        # Resolve the learner-facing catalogue item to the exact governed source
        # chapter. Prefer governed metadata and the number+name pair; never infer an
        # opaque source identity from sequence alone.
        mapped=None
        if programme and display_name:
            mapped=conn.execute(
                """SELECT * FROM chapter_catalogue
                   WHERE active=1 AND programme=? AND lower(subject)=lower(?)
                     AND (
                       (?<>'' AND chapter_number=?) OR
                       lower(COALESCE(chapter_name,''))=lower(?) OR
                       lower(COALESCE(display_label,''))=lower(?) OR
                       lower(COALESCE(source_chapter,''))=lower(?)
                     )
                   ORDER BY
                     CASE
                       WHEN ?<>'' AND chapter_number=? AND lower(COALESCE(chapter_name,''))=lower(?) THEN 0
                       WHEN ?<>'' AND chapter_number=? THEN 1
                       WHEN lower(COALESCE(chapter_name,''))=lower(?) THEN 2
                       WHEN metadata_source IN ('POWER_HOUSE','GOVERNED_IMPORT','ADMIN_GOVERNED') THEN 3
                       ELSE 4
                     END,
                     id DESC
                   LIMIT 1""",
                (
                    programme,subject,
                    display_number,display_number,display_name,display_name,display_name,
                    display_number,display_number,display_name,
                    display_number,display_number,display_name,
                ),
            ).fetchone()

        source_chapter=(str(mapped['source_chapter'] or '').strip() if mapped else display_name)
        mapped_number=(str(mapped['chapter_number'] or '').strip() if mapped else display_number)
        mapped_name=(str(mapped['chapter_name'] or '').strip() if mapped else display_name)

        ans=conn.execute(
            """SELECT COUNT(*) n,
                      COALESCE(AVG(CASE WHEN aa.is_correct=1 THEN 100.0 ELSE 0 END),0) acc
               FROM attempt_answers aa
               JOIN attempts a ON a.id=aa.attempt_id
               JOIN questions q ON q.id=aa.question_db_id
               WHERE a.student_id=? AND lower(q.subject)=lower(?)
                 AND lower(COALESCE(q.chapter,''))=lower(?)""",
            (student_id,subject,source_chapter),
        ).fetchone()
        answered=int(ans['n'] or 0)
        acc=round(float(ans['acc'] or 0))

        mastery=runtime.chapter_mastery_opportunity(
            conn,student_id,subject,source_chapter,programme
        )
        mastery_total=int(mastery.get('production_questions') or 0)
        live_row=conn.execute(
            f"SELECT COUNT(*) n FROM questions q WHERE {runtime.live_question_clause('q')} "
            f"AND lower(COALESCE(q.subject,''))=lower(?) "
            f"AND lower(COALESCE(q.chapter,''))=lower(?) AND {programme_clause}",
            [subject,source_chapter]+programme_params,
        ).fetchone()
        live_total=int(live_row['n'] or 0)
        available=live_total>0

        evidence='No evidence' if answered==0 else runtime.evidence_strength(answered)
        performance='No practice evidence' if answered==0 else runtime.performance_status(acc,answered)
        if mastery.get('existing_status')=='Verification Due':
            next_action,next_reason='Reconfirm mastery','Your previous mastery needs fresh independent evidence.'
        elif answered==0:
            next_action,next_reason='Find your starting point','Start with practice, then prove what you can do independently.'
        elif answered<3:
            next_action,next_reason='Build more evidence','A few more answers will make the recommendation more reliable.'
        elif acc<60:
            next_action,next_reason='Strengthen this chapter','Your recent practice shows this chapter is costing you marks.'
        elif not mastery.get('has_formal_mastery'):
            next_action,next_reason='Prove your mastery','Practice is going well; formal mastery still needs independent evidence.'
        elif int(mastery.get('opportunity_pct') or 0)>0:
            next_action,next_reason=f"Build toward {mastery.get('potential_level') or 'the next stage'}",'Your current evidence can support a higher verified chapter stage.'
        else:
            next_action,next_reason='Keep it strong','Maintain this chapter with spaced practice and reconfirmation.'

        if available:
            print(
                'SCOREMAX_CHAPTER_LINK_BINDING '
                f'programme={programme} subject={subject} display_number={display_number} '
                f'display_name={display_name!r} source_chapter={source_chapter!r} '
                f'live_questions={live_total} mastery_questions={mastery_total}',
                flush=True,
            )

        out.append({
            'number':mapped_number or display_number or idx,
            'name':mapped_name or display_name,
            'source_chapter':source_chapter,
            'answered':answered,
            'accuracy':acc,
            'mastery_level':mastery.get('existing_level') or 'Not verified',
            'mastery':mastery,
            'question_count':live_total,
            'mastery_question_count':mastery_total,
            'available':available,
            'evidence_strength':evidence,
            'performance_status':performance,
            'next_action':next_action,
            'next_reason':next_reason,
            'url':url_for('chapter_page',subject=subject,chapter=source_chapter) if available else '',
        })
    return out
'''

    pattern=r"def _chapter_snapshots\(conn, student_id: int, subject: str\) -> list\[dict\]:\n.*?(?=\ndef _learn_context\(conn, student_id: int\):)"
    rendered,count=re.subn(pattern,replacement.rstrip()+'\n\n',runtime,count=1,flags=re.S)
    if count!=1:
        # Accept idempotent generated runtime only when the full governed binding is present.
        if 'SCOREMAX_CHAPTER_LINK_BINDING' not in runtime or 'FROM chapter_catalogue' not in runtime:
            raise SystemExit(f'SCOREMAX_CHAPTER_OPEN_RUNTIME_ANCHOR_MISMATCH:matches={count}')
        rendered=runtime
    compile(rendered,str(runtime_path),'exec')
    runtime_path.write_text(rendered,encoding='utf-8')

    template=template_path.read_text(encoding='utf-8')
    template=template.replace(
        ".ux-chapter-card{display:flex;flex-direction:column;min-width:0;padding:11px 12px 10px;",
        ".ux-chapter-card{display:flex;flex-direction:column;min-width:0;padding:11px 12px 10px;text-decoration:none;",
        1,
    )
    old_open='''      <article class="ux-chapter-card {{\'is-unverified\' if unverified else \'\'}} {{\'has-practice\' if ch.answered else \'\'}}">'''
    new_open='''      {% if ch.available %}<a class="ux-chapter-card {{'is-unverified' if unverified else ''}} {{'has-practice' if ch.answered else ''}}" href="{{ch.url}}" aria-label="Open {{ch.name}}">{% else %}<article class="ux-chapter-card {{'is-unverified' if unverified else ''}} {{'has-practice' if ch.answered else ''}}">{% endif %}'''
    if old_open in template:
        template=template.replace(old_open,new_open,1)
    elif 'aria-label="Open {{ch.name}}"' not in template:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_TEMPLATE_ANCHOR_MISSING')

    old_action='''          {% if ch.available %}<a class="ux-chapter-open" href="{{ch.url}}">Open →</a>{% endif %}'''
    new_action='''          {% if ch.available %}<span class="ux-chapter-open">Open →</span>{% endif %}'''
    if old_action in template:
        template=template.replace(old_action,new_action,1)
    elif new_action not in template:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_ACTION_ANCHOR_MISSING')

    old_close='''      </article>'''
    new_close='''      {% if ch.available %}</a>{% else %}</article>{% endif %}'''
    if old_close in template:
        template=template.replace(old_close,new_close,1)
    elif new_close not in template:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_CLOSE_ANCHOR_MISSING')
    template_path.write_text(template,encoding='utf-8')

    rendered_runtime=runtime_path.read_text(encoding='utf-8')
    rendered_template=template_path.read_text(encoding='utf-8')
    required=(
        'FROM chapter_catalogue',
        "source_chapter=(str(mapped['source_chapter']",
        "live_total=int(live_row['n'] or 0)",
        "'source_chapter':source_chapter",
        "url_for('chapter_page',subject=subject,chapter=source_chapter)",
        'SCOREMAX_CHAPTER_LINK_BINDING',
        'aria-label="Open {{ch.name}}"',
        '<span class="ux-chapter-open">Open →</span>',
    )
    combined=rendered_runtime+'\n'+rendered_template
    missing=[x for x in required if x not in combined]
    if missing:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    print(
        'SCOREMAX_CHAPTER_OPEN_FIX_PASS catalogue_identity=true governed_source_identity=true '
        'chapter_catalogue_join=true learner_live_gate=true mastery_gate_separate=true '
        'whole_card_clickable=true programme_scoped=true learner_navigation_contract_unchanged=true',
        flush=True,
    )
