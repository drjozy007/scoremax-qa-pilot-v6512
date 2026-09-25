from __future__ import annotations

import base64
import json
import os
import textwrap
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AGENT=os.environ['SEMANTIC_QA_AGENT_ID'].strip()
MODEL=os.environ.get('SEMANTIC_QA_MODEL','gemma3:4b').strip()
OLLAMA=os.environ.get('SEMANTIC_QA_OLLAMA_BASE','http://127.0.0.1:11434').rstrip('/')
PROMPTS=Path(os.environ.get('SEMANTIC_QA_PROMPT_FILE','config/semantic_qa_agent_prompts_v2.json'))
OUT=Path(os.environ.get('SEMANTIC_QA_DIAGNOSTIC_DIR','/tmp/semantic-qa-diagnostic'))
OUT.mkdir(parents=True,exist_ok=True)

@dataclass(frozen=True)
class Case:
    case_id:str
    expected:str
    severity:str
    category:str
    lines:tuple[str,...]


def student_cases():
    clean=[
      ('S-C01','Which molecule carries hereditary information in most organisms?','A. DNA','B. ATP','C. Glucose','D. Lipid'),
      ('S-C02','In a monohybrid cross Aa × Aa, what fraction of offspring is expected to be aa?','A. 1/4','B. 1/2','C. 3/4','D. 1'),
      ('S-C03','Which structure contains chromosomes in a typical eukaryotic cell?','A. Nucleus','B. Ribosome','C. Cell wall','D. Vacuole'),
      ('S-C04','Which allele combination is heterozygous?','A. AA','B. Aa','C. aa','D. A only'),
      ('S-C05','Crossing over normally occurs during which stage of meiosis?','A. Prophase I','B. Metaphase II','C. Anaphase II','D. Cytokinesis'),
      ('S-C06','Which term describes one gene influencing several phenotypic traits?','A. Pleiotropy','B. Codominance','C. Linkage','D. Segregation'),
      ('S-C07','Which blood group genotype can produce phenotype O in the ABO system?','A. ii','B. IAIA','C. IAIB','D. IBIB'),
      ('S-C08','If P(A)=1/2 and P(B)=1/2 for independent events, what is P(A and B)?','A. 1/4','B. 1/2','C. 1','D. 2'),
      ('S-C09','Which process produces gametes with half the chromosome number?','A. Meiosis','B. Mitosis','C. Translation','D. Replication'),
      ('S-C10','A recessive phenotype appears only when no dominant allele is present. Which genotype shows it?','A. aa','B. AA','C. Aa','D. A_'),
    ]
    out=[Case(cid,'CLEAN','NONE','CLEAN',tuple([q,*opts,'Submission status: answer submitted.'])) for cid,q,*opts in clean]
    defects=[
      Case('S-D01','DEFECT','MAJOR','MISSING_CONTEXT',('Which process does this describe?','A. Replication','B. Transcription','C. Translation','D. Meiosis','No description or stimulus is shown.')),
      Case('S-D02','DEFECT','MAJOR','MULTIPLE_DEFENSIBLE_ANSWERS',('Which molecule can store genetic information?','A. DNA','B. RNA','C. Glucose','D. Triglyceride')),
      Case('S-D03','DEFECT','MAJOR','DUPLICATE_OPTIONS',('Which molecule is a nucleic acid?','A. DNA','B. RNA','C. RNA','D. Glycogen')),
      Case('S-D04','DEFECT','MAJOR','LEARNER_FACING_INTERNAL_LANGUAGE',('R2 HOLD — reviewer must rectify this item before release.','Which allele is dominant?','A. A','B. a','C. Both are always dominant','D. Neither')),
      Case('S-D05','DEFECT','MAJOR','MISSING_OPTION',('Which genotype is homozygous recessive?','A. AA','B. Aa','D. aa','Select one option.')),
      Case('S-D06','DEFECT','CRITICAL','WRONG_MARKING',('What is 3/4 × 3/4?','A. 9/16','B. 6/8','C. 3/8','D. 1/16','Selected response: A. 9/16','Platform feedback: Incorrect.')),
      Case('S-D07','DEFECT','MAJOR','FEEDBACK_CONTRADICTION',('Which molecule carries hereditary information in most organisms?','A. DNA','B. RNA','C. ATP','D. Glucose','Selected response: B. RNA','Platform feedback: Correct. DNA carries hereditary information in most organisms.')),
      Case('S-D08','DEFECT','MAJOR','MALFORMED_INTERACTION',('Select ALL statements that are true.','○ A. DNA contains nucleotides.','○ B. Genes are made of DNA.','○ C. Ribosomes are chromosomes.','○ D. Meiosis forms gametes.','Only one radio-button choice can be selected.')),
      Case('S-D09','DEFECT','MAJOR','MISSING_REPRESENTATION',('According to the pedigree shown above, which individual is affected?','A. I-1','B. I-2','C. II-1','D. II-2','No pedigree is visible on the page.')),
      Case('S-D10','DEFECT','MAJOR','TRUNCATED_TASK',('A heterozygous parent is crossed with a recessive parent. The expected offspring ratio is','A. 1:1','B. 3:1','The remaining options and end of the question are not visible.')),
    ]
    return out+defects


def reviewer_cases():
    clean=[
      Case('R-C01','CLEAN','NONE','CLEAN',('Question: Which molecule carries hereditary information in most organisms?','A. DNA  B. ATP  C. Glucose  D. Lipid','Displayed key: A','Rubric: DNA is the principal hereditary material in most organisms.','Interaction: single-select')),
      Case('R-C02','CLEAN','NONE','CLEAN',('Question: Aa × Aa. What fraction is expected to be aa?','A. 1/4  B. 1/2  C. 3/4  D. 1','Displayed key: A','Rubric: Aa × Aa gives aa in 1 of 4 equally likely genotype outcomes.','Interaction: single-select')),
      Case('R-C03','CLEAN','NONE','CLEAN',('Question: Which stage normally includes crossing over?','A. Prophase I  B. Metaphase II  C. Anaphase II  D. Cytokinesis','Displayed key: A','Rubric: Homologous chromosomes exchange segments during prophase I.','Interaction: single-select')),
      Case('R-C04','CLEAN','NONE','CLEAN',('Question: Which term means one gene influences several traits?','A. Pleiotropy  B. Linkage  C. Segregation  D. Dominance','Displayed key: A','Rubric: Pleiotropy is one gene affecting multiple phenotypic traits.','Interaction: single-select')),
      Case('R-C05','CLEAN','NONE','CLEAN',('Question: Which genotype produces ABO phenotype O?','A. ii  B. IAIA  C. IAIB  D. IBIB','Displayed key: A','Rubric: Phenotype O requires two recessive i alleles.','Interaction: single-select')),
      Case('R-C06','CLEAN','NONE','CLEAN',('Question: Independent events each have probability 1/2. What is their joint probability?','A. 1/4  B. 1/2  C. 1  D. 2','Displayed key: A','Rubric: Multiply independent probabilities: 1/2 × 1/2 = 1/4.','Interaction: single-select')),
      Case('R-C07','CLEAN','NONE','CLEAN',('Question: Which process halves chromosome number to form gametes?','A. Meiosis  B. Mitosis  C. Translation  D. Replication','Displayed key: A','Rubric: Meiosis is the reduction division that forms haploid gametes.','Interaction: single-select')),
      Case('R-C08','CLEAN','NONE','CLEAN',('Question: Which genotype is heterozygous?','A. AA  B. Aa  C. aa  D. A only','Displayed key: B','Rubric: Aa contains two different alleles.','Interaction: single-select')),
      Case('R-C09','CLEAN','NONE','CLEAN',('Question: A recessive phenotype appears when no dominant allele is present. Which genotype shows it?','A. aa  B. AA  C. Aa  D. A_','Displayed key: A','Rubric: Homozygous recessive aa expresses the recessive phenotype.','Interaction: single-select')),
      Case('R-C10','CLEAN','NONE','CLEAN',('Question: Which cell structure normally contains chromosomes?','A. Nucleus  B. Ribosome  C. Cell wall  D. Lysosome','Displayed key: A','Rubric: Eukaryotic chromosomes are housed in the nucleus.','Interaction: single-select')),
    ]
    defects=[
      Case('R-D01','DEFECT','CRITICAL','WRONG_KEY',('Question: Which molecule carries hereditary information in most organisms?','A. DNA  B. RNA  C. ATP  D. Glucose','Displayed key: B','Rubric: DNA is the principal hereditary material in most organisms.','Interaction: single-select')),
      Case('R-D02','DEFECT','MAJOR','KEY_RUBRIC_CONTRADICTION',('Question: Which genotype is heterozygous?','A. AA  B. Aa  C. aa  D. A only','Displayed key: B','Rubric: AA contains two different alleles and is heterozygous.','Interaction: single-select')),
      Case('R-D03','DEFECT','MAJOR','MULTIPLE_DEFENSIBLE_ANSWERS',('Question: Which molecule can store genetic information?','A. DNA  B. RNA  C. Glucose  D. Lipid','Displayed key: A','Rubric: DNA can store genetic information.','Interaction: single-select')),
      Case('R-D04','DEFECT','MAJOR','MISSING_CONTEXT',('Question: According to the table above, which cross gives the highest recombinant frequency?','A. Cross 1  B. Cross 2  C. Cross 3  D. Cross 4','Displayed key: C','Rubric: Cross 3 has the highest value.','No table is visible.')),
      Case('R-D05','DEFECT','MAJOR','DUPLICATE_OPTIONS',('Question: Which molecule is a nucleic acid?','A. DNA  B. RNA  C. RNA  D. Glycogen','Displayed key: B','Rubric: RNA is a nucleic acid.','Interaction: single-select')),
      Case('R-D06','DEFECT','CRITICAL','CARDINALITY_KEY_MISMATCH',('Question: Select ALL true statements.','A. DNA contains nucleotides.  B. Genes are made of DNA.  C. Ribosomes are chromosomes.  D. Meiosis forms gametes.','Displayed key: B','Rubric: A, B and D are true.','Interaction: single-select')),
      Case('R-D07','DEFECT','MAJOR','RUBRIC_WRONG_TASK',('Question: What fraction of Aa × Aa offspring is expected to be aa?','A. 1/4  B. 1/2  C. 3/4  D. 1','Displayed key: A','Rubric: Crossing over occurs during prophase I of meiosis.','Interaction: single-select')),
      Case('R-D08','DEFECT','MAJOR','INSUFFICIENT_NUMERICAL_CONTEXT',('Question: Calculate the recombination frequency from the data provided.','A. 12%  B. 25%  C. 40%  D. 50%','Displayed key: B','Rubric: recombinants ÷ total × 100 = 25%.','No recombinant or total counts are shown.')),
      Case('R-D09','DEFECT','CRITICAL','RESPONSE_CONTRACT_MISMATCH',('Question: Which TWO statements are correct?','A. I and II  B. I and III  C. II and IV  D. III and IV','Displayed key: A,C','Rubric: I and II is the correct combination.','Interaction: single-select')),
      Case('R-D10','DEFECT','MAJOR','REVIEWER_LANGUAGE_LEAK_IN_STEM',('Learner-facing question text begins: REVIEWER NOTE — accept B if uncertain.','Question: Which genotype is heterozygous?','A. AA  B. Aa  C. aa  D. A only','Displayed key: B','Rubric: Aa is heterozygous.')),
    ]
    return clean+defects


def font(size=27,bold=False):
    path='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    try:return ImageFont.truetype(path,size)
    except Exception:return ImageFont.load_default()


def render_batch(cases,batch_no):
    W,H=1700,2300
    img=Image.new('RGB',(W,H),'white')
    draw=ImageDraw.Draw(img)
    title=font(31,True);body=font(25,False);small=font(20,False)
    panel_h=H//5
    for idx,case in enumerate(cases):
        y0=idx*panel_h
        draw.rectangle((20,y0+15,W-20,y0+panel_h-15),outline='black',width=3)
        draw.text((45,y0+32),f'Case {case.case_id}',fill='black',font=title)
        y=y0+84
        for raw in case.lines:
            for line in textwrap.wrap(str(raw),width=98) or ['']:
                draw.text((55,y),line,fill='black',font=body)
                y+=32
        draw.text((55,y0+panel_h-48),'Judge this visible item independently.',fill='black',font=small)
    path=OUT/f'{AGENT}_batch_{batch_no}.png';img.save(path);return path


def call_model(prompt,image,cases):
    raw=base64.b64encode(Path(image).read_bytes()).decode()
    ids=[c.case_id for c in cases]
    user=(
      'The image contains exactly five separate numbered QA panels. Evaluate every panel independently using only visible content. '
      'Return JSON only in this exact shape: {"results":[{"case_id":"...","decision":"ACCEPT|FLAG|UNCERTAIN","confidence":0.0,"category":"short"}]}. '
      'Return exactly one result for each of these case IDs and no others: '+', '.join(ids)+'. '
      'Do not provide reasoning outside JSON and do not infer hidden keys or missing material.'
    )
    payload={'model':MODEL,'stream':False,'format':'json','options':{'temperature':0,'seed':int.from_bytes(AGENT.encode(),'little')%2147483647,'num_predict':700},'messages':[{'role':'system','content':prompt},{'role':'user','content':user,'images':[raw]}]}
    req=urllib.request.Request(OLLAMA+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    started=time.time()
    with urllib.request.urlopen(req,timeout=900) as r:data=json.loads(r.read())
    elapsed=round(time.time()-started,3)
    content=str((data.get('message') or {}).get('content') or '').strip()
    parsed=json.loads(content)
    results=parsed.get('results')
    if not isinstance(results,list):raise RuntimeError('model output missing results list')
    return results,elapsed,content


def main():
    prompts=json.loads(PROMPTS.read_text(encoding='utf-8'))['agents']
    if AGENT not in prompts:raise RuntimeError('unknown agent')
    prompt=str(prompts[AGENT]['prompt'])
    cases=student_cases() if AGENT.startswith('STUDENT_') else reviewer_cases()
    predictions={};timings=[]
    for batch_no,start in enumerate(range(0,len(cases),5),1):
        batch=cases[start:start+5];image=render_batch(batch,batch_no)
        results,elapsed,content=call_model(prompt,image,batch);timings.append(elapsed)
        expected_ids={c.case_id for c in batch};seen=set()
        for row in results:
            cid=str(row.get('case_id') or '')
            if cid not in expected_ids or cid in seen:raise RuntimeError(f'invalid/duplicate case id {cid}')
            decision=str(row.get('decision') or '').upper();confidence=float(row.get('confidence') or 0)
            if decision not in {'ACCEPT','FLAG','UNCERTAIN'} or not 0<=confidence<=1:raise RuntimeError(f'invalid prediction {row}')
            predictions[cid]={'decision':decision,'confidence':confidence,'category':str(row.get('category') or '')}
            seen.add(cid)
        if seen!=expected_ids:raise RuntimeError(f'partial batch coverage {seen} != {expected_ids}')
        print('SEMANTIC_QA_DIAGNOSTIC_BATCH '+json.dumps({'agent':AGENT,'batch':batch_no,'case_ids':sorted(seen),'elapsed_seconds':elapsed},sort_keys=True),flush=True)
    if set(predictions)!={c.case_id for c in cases}:raise RuntimeError('partial diagnostic population')
    clean=[c for c in cases if c.expected=='CLEAN'];defects=[c for c in cases if c.expected=='DEFECT'];critical=[c for c in defects if c.severity=='CRITICAL']
    tp=[c for c in defects if predictions[c.case_id]['decision']=='FLAG']
    fp=[c for c in clean if predictions[c.case_id]['decision']=='FLAG']
    critical_misses=[c for c in critical if predictions[c.case_id]['decision']!='FLAG']
    uncertain=[c for c in cases if predictions[c.case_id]['decision']=='UNCERTAIN']
    high_fn=[c for c in defects if predictions[c.case_id]['decision']=='ACCEPT' and predictions[c.case_id]['confidence']>=.90]
    result={
      'schema':'PH_SEMANTIC_QA_20Q_VISUAL_DIAGNOSTIC_V2','agent':AGENT,'model':MODEL,'cases':len(cases),'clean':len(clean),'defects':len(defects),'critical':len(critical),
      'defect_recall':round(len(tp)/len(defects),4),'clean_false_positive_rate':round(len(fp)/len(clean),4),'critical_misses':len(critical_misses),'uncertain':len(uncertain),'high_confidence_false_negatives':len(high_fn),
      'missed_defects':[c.case_id for c in defects if c not in tp],'false_positives':[c.case_id for c in fp],'critical_miss_ids':[c.case_id for c in critical_misses],'uncertain_ids':[c.case_id for c in uncertain],
      'total_inference_seconds':round(sum(timings),3),'predictions':predictions,'release_authority':False,'qualification_conferred':False
    }
    print('SEMANTIC_QA_20Q_VISUAL_DIAGNOSTIC_FINAL '+json.dumps(result,sort_keys=True),flush=True)
    Path(OUT/f'{AGENT}_result.json').write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8')

if __name__=='__main__':main()
