from pathlib import Path
import hashlib
EARLY="    # The existing MDCAT catalogue supplies presentation labels only.\n    # Keep the immutable destination key for routing, pins and results.\n    if canonical_programme(programme)=='MDCAT':\n        from ux_catalogue_data import subject_items\n        parts=str(source_chapter or '').split('::')\n        if len(parts)==4 and parts[0]=='MDCAT' and parts[1].replace('_',' ').casefold()==str(subject).casefold() and parts[2]=='UNIT' and parts[3].isdigit():\n            number=str(int(parts[3]))\n            item=next((x for x in subject_items('mdcat',str(subject).title()) if str(x['number']).lstrip('0')==number),None)\n            if item:\n                return {'chapter':str(source_chapter),'chapter_number':number,'chapter_name':item['name'],\n                  'display_label':f\"Unit {number} — {item['name']}\",'chapter_kind':'Unit',\n                  'identity_status':'RESOLVED','metadata_source':'EXISTING_GOVERNED_MDCAT_CATALOGUE'}\n"
FORMAT="\n\n@app.template_filter('learner_answer')\ndef learner_answer(value):\n    \"\"\"Present the saved structured response, without changing marking or storage.\"\"\"\n    text=str(value or '').strip()\n    if not text:return 'No answer'\n    if not text.startswith('{') or len(text)>10000:return text\n    try:data=json.loads(text)\n    except (ValueError,TypeError):return text\n    if not isinstance(data,dict) or data.get('version')!='PH-STRUCTURED-PRACTICE-1':return text\n    parts=[]\n    for claim in data.get('assertions',[]) if isinstance(data.get('assertions'),list) else []:\n        if isinstance(claim,dict):\n            words=[claim.get(key,'') for key in ('subject','relation','object')]\n            if all(isinstance(word,str) for word in words):\n                sentence=' '.join(word.strip() for word in words if word.strip())\n                if sentence:parts.append(sentence)\n    for equation in data.get('equations',[]) if isinstance(data.get('equations'),list) else []:\n        if isinstance(equation,str) and equation.strip():parts.append(equation.strip())\n    for quantity in data.get('values',[]) if isinstance(data.get('values'),list) else []:\n        if isinstance(quantity,dict):\n            value=quantity.get('value','');unit=quantity.get('unit','')\n            if isinstance(value,(str,int,float)) and not isinstance(value,bool) and isinstance(unit,str):\n                shown=f'{value} {unit}'.strip()\n                if shown:parts.append(shown)\n            working=quantity.get('working','')\n            if isinstance(working,str) and working.strip():parts.append('Working: '+working.strip())\n    return '; '.join(parts) or 'No answer'\n"

def apply(root):
    root=Path(root)
    app=root/'app.py';source=app.read_text(encoding='utf8')
    assert 'def learner_answer(' not in source,'DISPLAY_DELTA_ALREADY_PRESENT'
    needle='    programme=str(programme or \'\').strip(); subject=str(subject or \'\').strip(); source=str(source_chapter or \'\').strip()'
    start=source.index('def chapter_identity(');end=source.index('\ndef canonical_family_key(',start)
    block=source[start:end];assert block.count(needle)==1,'CHAPTER_IDENTITY_ANCHOR_MISMATCH'
    source=source[:start]+block.replace(needle,EARLY+needle,1)+source[end:]+FORMAT
    compile(source,str(app),'exec');app.write_text(source,encoding='utf8',newline='\n')
    result=root/'templates/result.html';text=result.read_text(encoding='utf8')
    old="{{d.selected_answer or 'No answer'}}";assert text.count(old)==3
    text=text.replace(old,"{{d.selected_answer|learner_answer}}");result.write_text(text,encoding='utf8',newline='\n')
    chapter=root/'templates/chapter_page.html';text=chapter.read_text(encoding='utf8')
    assert 'CHAPTER {{chapter.chapter_number}}' in text
    text=text.replace('CHAPTER {{chapter.chapter_number}}',"{{(chapter.chapter_kind or 'Chapter')|upper}} {{chapter.chapter_number}}")
    text=text.replace('Practise chapter',"Practise {{(chapter.chapter_kind or 'Chapter')|lower}}")
    chapter.write_text(text,encoding='utf8',newline='\n')
    setup=root/'templates/test_setup.html';text=setup.read_text(encoding='utf8')
    text=text.replace('<label>Chapter<select',"<label>{{'Unit' if prefill.programme=='MDCAT' else 'Chapter'}}<select")
    text=text.replace('>One chapter</option>',">{{'One unit' if prefill.programme=='MDCAT' else 'One chapter'}}</option>")
    text=text.replace('>Several chapters</option>',">{{'Several units' if prefill.programme=='MDCAT' else 'Several chapters'}}</option>")
    setup.write_text(text,encoding='utf8',newline='\n')
    return {'runtime_files_changed':['app.py','templates/result.html','templates/chapter_page.html','templates/test_setup.html'],'question_or_marking_or_membership_mutations':0}
