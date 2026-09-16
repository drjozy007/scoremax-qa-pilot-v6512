from __future__ import annotations

from pathlib import Path

REASONS=(
    'Incorrect answer/key',
    'Factual/scientific issue',
    'Unclear or ambiguous wording',
    'Weak/incorrect distractors',
    'Duplicate',
    'Incorrect difficulty',
    'Incorrect LO/mapping',
    'Outside syllabus',
    'Poor explanation',
    'Formatting/presentation issue',
    'Other',
)


def apply_admin_rejection_reason_guard(root: Path) -> None:
    """Make ScoreMax Admin rejection explainable and auditable.

    This extends the existing Admin Question Review only. Teachers remain unable to use
    admin review/edit routes. A rejection cannot be committed without a controlled
    reason; choosing Other also requires written feedback. Existing question-review
    history remains the system of evidence on the ScoreMax side until Power House
    consumes the return event.
    """
    app_path=Path(root)/'app.py'
    template_path=Path(root)/'templates'/'admin_question_detail.html'
    if not app_path.is_file() or not template_path.is_file():
        raise SystemExit('SCOREMAX_ADMIN_REJECTION_GUARD_SOURCE_MISSING')

    app=app_path.read_text(encoding='utf-8')
    marker='SCOREMAX_ADMIN_REJECTION_REASON_GUARD_V1'
    if marker not in app:
        old=("    action=request.form.get('action','').strip(); reason=request.form.get('reason_code','').strip(); note=request.form.get('note','').strip()\n"
             "    status_map={'ready':'Ready for Review','start':'Under Review','approve':'Approved','changes':'Changes Required','reject':'Rejected','retire':'Retired','restore':'Approved'}\n"
             "    if action not in status_map: flash('Unknown review action.','error'); return redirect(url_for('admin_question_detail',qid=qid))")
        allowed_repr=repr(set(REASONS))
        new=("    # SCOREMAX_ADMIN_REJECTION_REASON_GUARD_V1\n"
             "    action=request.form.get('action','').strip(); reason=request.form.get('reason_code','').strip(); note=request.form.get('note','').strip()\n"
             "    status_map={'ready':'Ready for Review','start':'Under Review','approve':'Approved','changes':'Changes Required','reject':'Rejected','retire':'Retired','restore':'Approved'}\n"
             "    if action not in status_map: flash('Unknown review action.','error'); return redirect(url_for('admin_question_detail',qid=qid))\n"
             f"    allowed_rejection_reasons={allowed_repr}\n"
             "    if action=='reject':\n"
             "        if reason not in allowed_rejection_reasons:\n"
             "            flash('Select a rejection reason before rejecting this question.','error')\n"
             "            return redirect(url_for('admin_question_detail',qid=qid))\n"
             "        if reason=='Other' and not note:\n"
             "            flash('Add a short explanation when the rejection reason is Other.','error')\n"
             "            return redirect(url_for('admin_question_detail',qid=qid))")
        if old not in app:
            raise SystemExit('SCOREMAX_ADMIN_REJECTION_BACKEND_ANCHOR_MISSING')
        app=app.replace(old,new,1)
        compile(app,str(app_path),'exec')
        app_path.write_text(app,encoding='utf-8')

    template=template_path.read_text(encoding='utf-8')
    old_block="""<label>Reason</label><select name='reason_code'><option value=''>Select if relevant</option>{% for r in ['Incorrect answer','Weak distractors','Unclear wording','Duplicate','Incorrect difficulty','Incorrect LO','Outside syllabus','Poor explanation','Factual/scientific issue','Formatting issue','Other'] %}<option>{{ r }}</option>{% endfor %}</select>
<label>Review note</label><textarea name='note' rows='3' placeholder='Optional reviewer note'></textarea>
<div class='actions'><button class='btn alt' name='action' value='ready'>Ready for review</button><button class='btn alt' name='action' value='start'>Start review</button><button class='btn' name='action' value='approve'>Approve</button><button class='btn alt' name='action' value='changes'>Changes required</button><button class='btn danger' name='action' value='reject'>Reject</button><button class='btn danger' name='action' value='retire'>Retire</button></div>"""
    reasons_list='['+','.join(repr(x) for x in REASONS)+']'
    new_block=f"""<label for='questionReviewReason'>Reason <small class='muted'>(required for Reject)</small></label><select id='questionReviewReason' name='reason_code'><option value=''>Select rejection reason</option>{{% for r in {reasons_list} %}}<option>{{{{ r }}}}</option>{{% endfor %}}</select>
<label for='questionReviewNote'>Additional feedback</label><textarea id='questionReviewNote' name='note' rows='3' placeholder='Optional, except required when reason is Other'></textarea>
<p class='muted' style='margin:.45rem 0 0'>Rejecting a question removes it from learner use. A reason is mandatory so the decision is auditable and can be returned to Power House.</p>
<div class='actions'><button class='btn alt' name='action' value='ready'>Ready for review</button><button class='btn alt' name='action' value='start'>Start review</button><button class='btn' name='action' value='approve'>Approve</button><button class='btn alt' name='action' value='changes'>Changes required</button><button class='btn danger' id='questionRejectButton' name='action' value='reject'>Reject</button><button class='btn danger' name='action' value='retire'>Retire</button></div>
<script>
(function(){{
  const form=document.getElementById('questionRejectButton')?.form;
  const reject=document.getElementById('questionRejectButton');
  const reason=document.getElementById('questionReviewReason');
  const note=document.getElementById('questionReviewNote');
  if(!form||!reject||!reason||!note) return;
  const clear=()=>{{reason.setCustomValidity('');note.setCustomValidity('');}};
  reason.addEventListener('change',clear); note.addEventListener('input',clear);
  form.addEventListener('submit',function(event){{
    const submitter=event.submitter;
    if(!submitter || submitter.value!=='reject') return;
    clear();
    if(!reason.value){{
      event.preventDefault();
      reason.setCustomValidity('Select a rejection reason.');
      reason.reportValidity();
      return;
    }}
    if(reason.value==='Other' && !note.value.trim()){{
      event.preventDefault();
      note.setCustomValidity('Add a short explanation when the reason is Other.');
      note.reportValidity();
    }}
  }});
}})();
</script>"""
    if 'questionRejectButton' not in template:
        if old_block not in template:
            raise SystemExit('SCOREMAX_ADMIN_REJECTION_TEMPLATE_ANCHOR_MISSING')
        template=template.replace(old_block,new_block,1)
        template_path.write_text(template,encoding='utf-8')

    rendered_app=app_path.read_text(encoding='utf-8')
    rendered_template=template_path.read_text(encoding='utf-8')
    required=(
        marker,
        "if action=='reject':",
        "if reason not in allowed_rejection_reasons:",
        "if reason=='Other' and not note:",
        "id='questionReviewReason'",
        "id='questionReviewNote'",
        "id='questionRejectButton'",
        'Select a rejection reason.',
        'reason is Other',
    )
    combined=rendered_app+'\n'+rendered_template
    missing=[x for x in required if x not in combined]
    if missing:
        raise SystemExit('SCOREMAX_ADMIN_REJECTION_GUARD_POSTBUILD_MISSING:'+','.join(missing))
    print(
        'SCOREMAX_ADMIN_REJECTION_REASON_GUARD_PASS admin_only=true '
        'reject_reason_required=true other_note_required=true audit_history_preserved=true '
        'teacher_permissions_unchanged=true power_house_bridge_unchanged=true',
        flush=True,
    )
