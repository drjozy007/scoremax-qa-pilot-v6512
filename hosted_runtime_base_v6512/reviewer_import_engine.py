"""Guided large-import orchestration for ScoreMax Academic Reviewer Workspace.

V6.2.8.1 accepts broad CSV/JSON/Excel conventions and the governed Power House
academic-review workbook structure. It stores a private preview, preserves source
worksheet/row lineage, and atomically splits confirmed imports into review batches
of up to 100 without writing to the live ScoreMax question bank.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import re
import secrets
import sqlite3
from datetime import datetime
from typing import Any, Mapping, Sequence

import reviewer_workspace_engine as reviewer_workspace

MAX_IMPORT_ITEMS = 10_000
BATCH_SIZE = 100
CANONICAL_FIELDS = (
    'external_question_id','chapter','topic','question_type','question_text','stimulus_context','options_text',
    'option_a','option_b','option_c','option_d','correct_answer','explanation','mastery_level','priority',
    'review_requirement','reviewer2_required','calibration_expected_decision'
)
REQUIRED_FIELDS = ('question_text','correct_answer_or_rubric')
FIELD_LABELS = {
    'external_question_id':'Question ID','chapter':'Chapter','topic':'Topic','question_type':'Question type',
    'question_text':'Question','stimulus_context':'Stimulus / context','options_text':'Statements / options',
    'option_a':'Option A','option_b':'Option B','option_c':'Option C','option_d':'Option D',
    'correct_answer':'Correct answer / key','explanation':'Explanation / marking rubric','mastery_level':'Mastery level',
    'priority':'Review priority','review_requirement':'Review requirement','reviewer2_required':'Reviewer 2 required',
    'calibration_expected_decision':'Calibration expected decision (optional)'
}
ALIASES = {
    'external_question_id':(
        'question id','question_id','id','item id','item_id','qid','question code','permutation question id'
    ),
    'chapter':('chapter','unit','chapter name'),
    'topic':('topic','subtopic','sub-topic','lesson','concept'),
    'question_type':('question type','question_type','item type','family type'),
    'question_text':(
        'question','question text','question_text','stem','prompt','item','content','question / task','question/task','question task'
    ),
    'stimulus_context':(
        'stimulus','context','stimulus / context','stimulus/context','scenario','stimulus / statements / matching content'
    ),
    'options_text':(
        'statements / options','statements/options','statements and options','options / statements','options/statements',
        'options','stimulus / statements / matching content'
    ),
    'option_a':('a','option a','option_a','choice a','answer a'),
    'option_b':('b','option b','option_b','choice b','answer b'),
    'option_c':('c','option c','option_c','choice c','answer c'),
    'option_d':('d','option d','option_d','choice d','answer d'),
    'correct_answer':(
        'answer','correct answer','correct_answer','answer key','key','correct option','key answer','key_answer'
    ),
    'explanation':(
        'explanation','rationale','feedback','answer explanation','reason','explanation / marking rubric',
        'explanation/marking rubric','marking rubric','rubric'
    ),
    'mastery_level':('mastery level','mastery_level','level','difficulty level','mastery'),
    'priority':('priority','review priority'),
    'review_requirement':('review requirement','review_requirement','review scope'),
    'reviewer2_required':('reviewer 2 required','reviewer2 required','reviewer_2_required','dual required'),
    'calibration_expected_decision':('calibration expected decision','calibration_expected_decision')
}
POWER_HOUSE_V3_HEADERS = {
    'question / task','key answer','explanation / marking rubric','statements / options','review requirement'
}


def _text(value: Any) -> str:
    return '' if value is None else str(value).strip()


def _norm_header(value: Any) -> str:
    text=_text(value).casefold().replace('_',' ').replace('-',' ')
    text=re.sub(r'\s*/\s*',' / ',text)
    return re.sub(r'\s+',' ',text).strip()


def _truthy(value: Any) -> bool:
    return _text(value).casefold() in {'1','yes','true','required','y'}


def init_schema(c) -> None:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS reviewer_imports(
      id INTEGER PRIMARY KEY,import_code TEXT UNIQUE NOT NULL,title TEXT NOT NULL,chapter TEXT,topic TEXT,
      source_filename TEXT,source_checksum TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PREVIEW',
      total_rows INTEGER NOT NULL DEFAULT 0,valid_rows INTEGER NOT NULL DEFAULT 0,invalid_rows INTEGER NOT NULL DEFAULT 0,
      mapping_json TEXT DEFAULT '{}',rows_json TEXT NOT NULL DEFAULT '[]',error_rows_json TEXT DEFAULT '[]',
      batch_count INTEGER NOT NULL DEFAULT 0,created_by INTEGER,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      confirmed_at TEXT);
    CREATE INDEX IF NOT EXISTS idx_reviewer_imports_created ON reviewer_imports(created_by,created_at);
    ''')
    columns={r['name'] for r in c.execute('PRAGMA table_info(reviewer_batches)').fetchall()}
    for name,definition in {
        'import_id':'INTEGER','batch_number':'INTEGER DEFAULT 1','batch_count':'INTEGER DEFAULT 1',
        'source_sheet':'TEXT DEFAULT \'\'','source_part_number':'INTEGER DEFAULT 1','source_part_count':'INTEGER DEFAULT 1'
    }.items():
        if name not in columns:
            c.execute(f'ALTER TABLE reviewer_batches ADD COLUMN {name} {definition}')
    columns={r['name'] for r in c.execute('PRAGMA table_info(reviewer_assignments)').fetchall()}
    if 'assignment_group_code' not in columns:
        c.execute('ALTER TABLE reviewer_assignments ADD COLUMN assignment_group_code TEXT')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reviewer_batches_import ON reviewer_batches(import_id,batch_number)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reviewer_batches_source_sheet ON reviewer_batches(import_id,source_sheet,source_part_number)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reviewer_assignments_group ON reviewer_assignments(reviewer_user_id,assignment_group_code,status)')


def headers(rows: Sequence[Mapping[str,Any]]) -> list[str]:
    out=[]
    for row in rows[:100]:
        for key in row.keys():
            key=_text(key)
            if key and not key.startswith('__') and key not in out:
                out.append(key)
    return out


def sheet_counts(rows: Sequence[Mapping[str,Any]]) -> list[dict]:
    counts: OrderedDict[str,int]=OrderedDict()
    for row in rows:
        name=_text(row.get('__source_sheet')) or 'Imported questions'
        counts[name]=counts.get(name,0)+1
    return [{'sheet':name,'rows':count} for name,count in counts.items()]


def detect_profile(column_names: Sequence[str], rows: Sequence[Mapping[str,Any]]|None=None) -> str:
    normalized={_norm_header(x) for x in column_names}
    if POWER_HOUSE_V3_HEADERS <= normalized:
        return 'POWER_HOUSE_ACADEMIC_REVIEW_V3'
    names={_text(x.get('__source_sheet')) for x in (rows or []) if _text(x.get('__source_sheet'))}
    if {'Batch 1 Review','Batch 2 Review','Batch 3 Review'} <= names:
        return 'POWER_HOUSE_ACADEMIC_REVIEW_V3'
    return 'GUIDED_GENERIC'


def suggest_mapping(column_names: Sequence[str]) -> dict[str,str]:
    normalized={_norm_header(x):x for x in column_names}
    result={}
    for canonical,aliases in ALIASES.items():
        for alias in aliases:
            if _norm_header(alias) in normalized:
                result[canonical]=normalized[_norm_header(alias)]
                break
    return result


def preview_import(c, rows: Sequence[Mapping[str,Any]], *, title: str, filename: str, chapter: str,
                   topic: str, created_by: int) -> dict:
    if not rows:
        raise ValueError('No question-bearing worksheet or question rows were detected in the uploaded file.')
    if len(rows)>MAX_IMPORT_ITEMS:
        raise ValueError(f'One guided import may contain up to {MAX_IMPORT_ITEMS:,} questions.')
    serial=[{_text(k):v for k,v in dict(row).items()} for row in rows]
    columns=headers(serial)
    mapping=suggest_mapping(columns)
    payload=json.dumps(serial,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':'))
    digest=hashlib.sha256(payload.encode('utf-8')).hexdigest()
    import_code='RVI-'+secrets.token_hex(5).upper()
    cur=c.execute('''INSERT INTO reviewer_imports(import_code,title,chapter,topic,source_filename,source_checksum,status,
      total_rows,mapping_json,rows_json,created_by) VALUES(?,?,?,?,?,?,'PREVIEW',?,?,?,?)''',
      (import_code,_text(title) or 'Academic Review Import',_text(chapter),_text(topic),_text(filename),digest,
       len(serial),json.dumps(mapping),payload,created_by))
    c.commit()
    return {
        'id':cur.lastrowid,'import_code':import_code,'columns':columns,'mapping':mapping,'total_rows':len(serial),
        'profile':detect_profile(columns,serial),'sheets':sheet_counts(serial)
    }


def get_preview(c, import_id: int, created_by: int|None=None):
    if created_by is None:
        return c.execute('SELECT * FROM reviewer_imports WHERE id=?',(import_id,)).fetchone()
    return c.execute('SELECT * FROM reviewer_imports WHERE id=? AND created_by=?',(import_id,created_by)).fetchone()


def _parse_letter_options(value: Any) -> list[dict]:
    text=_text(value)
    if not text:
        return []
    lines=text.replace('\r\n','\n').replace('\r','\n').split('\n')
    options=[]
    current=None
    for raw_line in lines:
        line=raw_line.strip()
        if not line:
            continue
        match=re.match(r'^(?:option\s+)?([A-F])[\.:\)]\s*(.+)$',line,re.I)
        if match:
            if current:
                options.append(current)
            current={'id':match.group(1).upper(),'text':match.group(2).strip()}
            continue
        if current and not re.match(r'^(statements?|options?|tier\s+\d+|tier\s+\d+\s+reasons?|left items?|right options?)\s*:?$',line,re.I):
            current['text']=(current['text']+' '+line).strip()
    if current:
        options.append(current)
    ids=[x['id'] for x in options]
    return options if len(options)>=2 and len(ids)==len(set(ids)) else []


def _review_content(value: Any, parsed_options: Sequence[Mapping[str,Any]]) -> str:
    text=_text(value)
    if not text:
        return ''
    lowered=text.casefold()
    if any(marker in lowered for marker in ('tier 2','left items','right options')):
        return text
    parts=re.split(r'(?im)^\s*options?\s*:\s*$',text,maxsplit=1)
    if len(parts)==2:
        prefix=re.sub(r'(?im)^\s*statements?\s*:\s*$','',parts[0]).strip()
        return prefix
    return '' if parsed_options else text


def normalize_guided(row: Mapping[str,Any], mapping: Mapping[str,str], index: int, *, default_chapter: str='', default_topic: str='') -> dict:
    def value(field,default=''):
        column=_text(mapping.get(field))
        return row.get(column,default) if column else default

    qtext=_text(value('question_text'))
    qtype=_text(value('question_type'))
    explanation=_text(value('explanation'))
    answer=_text(value('correct_answer'))
    answer_from_rubric=False
    if not answer and explanation:
        # Constructed-response workbooks commonly use the marking-rubric column as the complete configured answer.
        answer=explanation
        answer_from_rubric=True
    if not qtext or not answer:
        missing=[]
        if not qtext:
            missing.append('question')
        if not answer:
            missing.append('correct answer or marking rubric')
        raise ValueError('Missing '+' and '.join(missing))

    options=[]
    for letter in ('a','b','c','d'):
        text=_text(value(f'option_{letter}'))
        if text:
            options.append({'id':letter.upper(),'text':text})
    combined=_text(value('options_text'))
    if not options:
        options=_parse_letter_options(combined)
    review_content=_review_content(combined,options)

    external=_text(value('external_question_id')) or f'REVIEW-{index:06d}'
    mastery=_text(value('mastery_level')) or 'Not supplied'
    calibration=_text(value('calibration_expected_decision')).upper()
    if calibration and calibration not in reviewer_workspace.DECISIONS:
        raise ValueError('Invalid calibration decision')
    requirement=_text(value('review_requirement'))
    reviewer2_raw=_text(value('reviewer2_required'))
    reviewer2_required=_truthy(reviewer2_raw) or 'DUAL_REVIEW_REQUIRED' in requirement.upper()
    source_sheet=_text(row.get('__source_sheet'))
    source_row=int(row.get('__source_row') or index)
    source_order=int(row.get('__source_sheet_order') or 0)

    return {
      'external_question_id':external,'chapter':_text(value('chapter')) or _text(default_chapter),
      'topic':_text(value('topic')) or _text(default_topic),'question_type':qtype,'question_text':qtext,
      'stimulus_context':_text(value('stimulus_context')),'review_content':review_content,'options':options,
      'correct_answer':answer,'explanation':explanation or ('Marking rubric used as the configured answer.' if answer_from_rubric else 'Explanation not supplied in the import. Reviewer should assess whether one is required.'),
      'mastery_level':mastery,'priority':_text(value('priority')),'review_requirement':requirement,
      'reviewer2_required':1 if reviewer2_required else 0,'calibration_expected_decision':calibration,
      'source_sheet':source_sheet,'source_row':source_row,'source_sheet_order':source_order,'display_order':index,
    }


def validate_preview(rowset: Sequence[Mapping[str,Any]], mapping: Mapping[str,str], *, chapter: str='', topic: str='') -> tuple[list[dict],list[dict]]:
    normalized=[]
    errors=[]
    seen={}
    for index,row in enumerate(rowset,1):
        try:
            q=normalize_guided(row,mapping,index,default_chapter=chapter,default_topic=topic)
            key=q['external_question_id'].casefold()
            if key in seen:
                q['external_question_id']=f"{q['external_question_id']}-{index}"
            seen[q['external_question_id'].casefold()]=index
            normalized.append(q)
        except ValueError as exc:
            errors.append({
                'row':int(row.get('__source_row') or index),'sheet':_text(row.get('__source_sheet')),
                'reason':str(exc)
            })
    normalized.sort(key=lambda q:(int(q.get('source_sheet_order') or 0),int(q.get('source_row') or 0),int(q.get('display_order') or 0)))
    return normalized,errors


def _source_groups(normalized: Sequence[Mapping[str,Any]]) -> OrderedDict[str,list[dict]]:
    groups: OrderedDict[str,list[dict]]=OrderedDict()
    for q in normalized:
        source=_text(q.get('source_sheet')) or 'Imported questions'
        groups.setdefault(source,[]).append(dict(q))
    return groups


def confirm_import(c, import_id: int, mapping: Mapping[str,str], *, actor_user_id: int) -> dict:
    row=get_preview(c,import_id,actor_user_id)
    if not row or row['status']!='PREVIEW':
        raise ValueError('That import preview is no longer available.')
    raw_rows=json.loads(row['rows_json'] or '[]')
    normalized,errors=validate_preview(raw_rows,mapping,chapter=row['chapter'] or '',topic=row['topic'] or '')
    if not normalized:
        raise ValueError('No valid questions were detected. Choose the Question column and either a Correct answer or Explanation / marking rubric column.')

    groups=_source_groups(normalized)
    batch_count=sum((len(items)+BATCH_SIZE-1)//BATCH_SIZE for items in groups.values())
    created=[]
    global_batch_index=0
    try:
        c.execute('BEGIN IMMEDIATE')
        for source_sheet,items in groups.items():
            source_part_count=(len(items)+BATCH_SIZE-1)//BATCH_SIZE
            for source_part,start in enumerate(range(0,len(items),BATCH_SIZE),1):
                global_batch_index+=1
                chunk=items[start:start+BATCH_SIZE]
                batch_title=_text(row['title'])
                if len(groups)>1:
                    batch_title=f'{batch_title} · {source_sheet} · Part {source_part} of {source_part_count}'
                elif batch_count>1:
                    batch_title=f'{batch_title} · Batch {global_batch_index} of {batch_count}'
                payload={
                    'import_code':row['import_code'],'batch_number':global_batch_index,'source_sheet':source_sheet,
                    'source_part':source_part,'questions':chunk
                }
                digest=reviewer_workspace.checksum(payload)
                if c.execute('SELECT id FROM reviewer_batches WHERE source_checksum=?',(digest,)).fetchone():
                    raise ValueError('This confirmed import has already been created.')
                batch_code='RVB-'+secrets.token_hex(5).upper()
                cur=c.execute('''INSERT INTO reviewer_batches(batch_code,title,chapter,topic,source_filename,source_checksum,status,
                  question_count,created_by,import_id,batch_number,batch_count,source_sheet,source_part_number,source_part_count)
                  VALUES(?,?,?,?,?,?,'READY',?,?,?,?,?,?,?,?)''',
                  (batch_code,batch_title,row['chapter'] or '',row['topic'] or '',row['source_filename'] or '',digest,len(chunk),
                   actor_user_id,import_id,global_batch_index,batch_count,source_sheet,source_part,source_part_count))
                batch_id=cur.lastrowid
                for pos,q in enumerate(chunk,1):
                    snapshot=reviewer_workspace.checksum({k:v for k,v in q.items() if k not in {'display_order','source_sheet_order'}})
                    c.execute('''INSERT INTO reviewer_questions(batch_id,external_question_id,display_order,chapter,topic,question_text,
                      stimulus_context,review_content,options_json,correct_answer,explanation,mastery_level,question_type,review_priority,
                      review_requirement,reviewer2_required,source_sheet,source_row,calibration_expected_decision,snapshot_checksum)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (batch_id,q['external_question_id'],pos,q['chapter'],q['topic'],q['question_text'],q['stimulus_context'],
                       q['review_content'],json.dumps(q['options'],ensure_ascii=False),q['correct_answer'],q['explanation'],
                       q['mastery_level'],q['question_type'],q['priority'],q['review_requirement'],q['reviewer2_required'],
                       q['source_sheet'],q['source_row'],q['calibration_expected_decision'],snapshot))
                created.append({
                    'batch_id':batch_id,'batch_code':batch_code,'count':len(chunk),'batch_number':global_batch_index,
                    'source_sheet':source_sheet,'source_part_number':source_part,'source_part_count':source_part_count
                })
        c.execute('''UPDATE reviewer_imports SET status='CONFIRMED',valid_rows=?,invalid_rows=?,mapping_json=?,error_rows_json=?,
          batch_count=?,confirmed_at=? WHERE id=?''',
          (len(normalized),len(errors),json.dumps(dict(mapping)),json.dumps(errors),batch_count,
           datetime.now().isoformat(timespec='seconds'),import_id))
        c.execute('INSERT INTO reviewer_audit_events(actor_user_id,event_type,metadata_json) VALUES(?,?,?)',
                  (actor_user_id,'REVIEW_LARGE_IMPORT_CONFIRMED',json.dumps({
                      'import_id':import_id,'valid_rows':len(normalized),'invalid_rows':len(errors),'batch_count':batch_count,
                      'source_sheets':[{'sheet':name,'rows':len(items)} for name,items in groups.items()]
                  })))
        c.commit()
        return {
            'import_id':import_id,'valid_rows':len(normalized),'invalid_rows':len(errors),
            'batch_count':batch_count,'batches':created,'source_sheets':[{'sheet':name,'rows':len(items)} for name,items in groups.items()]
        }
    except sqlite3.IntegrityError as exc:
        c.rollback()
        raise ValueError('The import could not be completed because duplicate review data was detected.') from exc
    except Exception:
        c.rollback()
        raise


def demo_rows(count: int=24) -> list[dict]:
    count=max(5,min(100,count))
    rows=[]
    for i in range(1,count+1):
        rows.append({
          'Question ID':f'DEMO-{i:03d}','Chapter':'Reviewer Demo','Topic':'Academic checking',
          'Question':f'Demo question {i}: Which statement best represents careful academic review?',
          'A':'Accept every item immediately','B':'Check the answer, explanation and mastery suitability',
          'C':'Skip the explanation','D':'Approve from the spreadsheet title alone','Correct Answer':'B',
          'Explanation':'A reviewer should independently check the configured answer, explanation and proposed mastery level.',
          'Mastery Level':'Foundation' if i%2 else 'Exam Ready'
        })
    return rows
