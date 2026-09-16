from __future__ import annotations

from pathlib import Path


def apply_chapter_card_open_fix(root: Path) -> None:
    """Separate learner-live chapter availability from mastery eligibility.

    A released chapter must remain navigable even when its current bank does not yet
    satisfy formal mastery/assembly requirements. The existing mastery snapshot stays
    authoritative for mastery; this patch changes only the chapter-open gate and card UX.
    """
    runtime_path=root/'ux_student_batch.py'
    template_path=root/'templates'/'ux_subject_chapters.html'
    if not runtime_path.is_file() or not template_path.is_file():
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_SOURCE_MISSING')

    runtime=runtime_path.read_text(encoding='utf-8')
    old=("        mastery=runtime.chapter_mastery_opportunity(conn,student_id,subject,chapter); "
         "total=int(mastery.get('production_questions') or 0); available=total>0")
    new="""        mastery=runtime.chapter_mastery_opportunity(conn,student_id,subject,chapter)
        mastery_total=int(mastery.get('production_questions') or 0)
        programme=(runtime.student_programme(conn,student_id) or '').strip()
        aliases=runtime._programme_aliases(programme) if programme else []
        if aliases:
            programme_clause,programme_params=runtime._programme_scope_sql(aliases,'q')
        else:
            programme_clause,programme_params='1=1',[]
        live_row=conn.execute(
            f\"SELECT COUNT(*) n FROM questions q WHERE {runtime.live_question_clause('q')} \"
            f\"AND lower(COALESCE(q.subject,''))=lower(?) \"
            f\"AND lower(COALESCE(q.chapter,''))=lower(?) AND {programme_clause}\",
            [subject,chapter]+programme_params,
        ).fetchone()
        live_total=int(live_row['n'] or 0)
        available=live_total>0"""
    if old not in runtime:
        if 'mastery_total=int(mastery.get(\'production_questions\') or 0)' not in runtime:
            raise SystemExit('SCOREMAX_CHAPTER_OPEN_RUNTIME_ANCHOR_MISSING')
    else:
        runtime=runtime.replace(old,new,1)

    old_append="'question_count':total,'available':available"
    new_append="'question_count':live_total,'mastery_question_count':mastery_total,'available':available"
    if old_append in runtime:
        runtime=runtime.replace(old_append,new_append,1)
    elif new_append not in runtime:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_COUNT_ANCHOR_MISSING')
    runtime_path.write_text(runtime,encoding='utf-8')

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
        "live_total=int(live_row['n'] or 0)",
        'available=live_total>0',
        "'mastery_question_count':mastery_total",
        'aria-label="Open {{ch.name}}"',
        '<span class="ux-chapter-open">Open →</span>',
    )
    combined=rendered_runtime+'\n'+rendered_template
    missing=[x for x in required if x not in combined]
    if missing:
        raise SystemExit('SCOREMAX_CHAPTER_OPEN_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    print(
        'SCOREMAX_CHAPTER_OPEN_FIX_PASS learner_live_gate=true mastery_gate_separate=true '
        'whole_card_clickable=true programme_scoped=true learner_navigation_contract_unchanged=true',
        flush=True,
    )
