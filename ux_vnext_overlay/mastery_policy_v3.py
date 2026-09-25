"""Scoped, transparent policy and coverage helpers for the existing mastery engine."""

def policy_score(value,default=50):
    import math
    if value is None or value=='':value=default
    if isinstance(value,bool):raise ValueError('Policy score must be an integer from 0 to 100')
    try:
        number=float(value)
        if not math.isfinite(number) or number!=int(number) or not 0<=number<=100:raise ValueError()
        return int(number)
    except (TypeError,ValueError,OverflowError):
        raise ValueError('Policy score must be an integer from 0 to 100')


def effective_mastery_requirements(base_policy,assembly_policy=None):
    import math
    if not base_policy:return {}
    base=dict(base_policy);assembly=dict(assembly_policy or {})
    standard=policy_score(assembly.get('mastery_standard_score'))
    delta=(standard-50)/50.0
    def number(key,default):
        value=base.get(key)
        return float(default if value is None or value=='' else value)
    # 50 is an actual neutral point, including expressly configured zero shares.
    return {'level':base.get('mastery_level') or base.get('level',''),
      'min_accuracy':round(max(0,min(100,number('min_accuracy',70)+5*delta)),2),
      'min_questions':max(5,int(math.ceil(number('min_questions',10)*(1+.25*delta)))),
      'min_forms':max(1,int(number('min_forms',1))+(1 if delta>=.55 else -1 if delta<=-.75 else 0)),
      'target_band_pct':round(max(0,min(1,number('target_band_pct',.25)+.15*delta)),3),
      'unseen_family_pct':round(max(0,min(1,number('unseen_family_pct',.6)+.2*delta)),3),
      'min_breadth_pct':round(max(0,min(1,number('min_breadth_pct',0)+.1*delta)),3),
      'verification_days':max(1,int(round(number('verification_days',90)*(1-.25*delta)))),
      'mastery_standard_score':standard,'base_mastery_policy_id':base.get('id'),
      'assembly_policy_id':assembly.get('id'),'assembly_policy_version':assembly.get('policy_version','1')}


def normalise_policy_scope(scope_type,scope_key,blueprint=None):
    scope_type=str(scope_type or '').strip().lower();key=str(scope_key or '').strip()
    if scope_type not in ('global','programme','subject','chapter','blueprint','framework_version','assessment_type'):
        raise ValueError('Choose a valid policy scope')
    if scope_type=='global':
        if key:raise ValueError('Global policy scope must have no key')
        return scope_type,''
    bp=dict(blueprint or {})
    if scope_type in ('blueprint','framework_version'):
        value=bp.get('id' if scope_type=='blueprint' else 'framework_version_id') or key
        if not str(value).isdigit() or int(value)<=0:raise ValueError('A governed blueprint or framework version is required')
        return scope_type,str(int(value))
    if not key or len(key)>300:raise ValueError('A non-empty bounded scope key is required')
    parts=[x.strip() for x in key.split('|')]
    if any(not x for x in parts):raise ValueError('Scope components cannot be empty')
    allowed={'programme':(1,),'subject':(1,2),'chapter':(1,3),'assessment_type':(1,)}
    if len(parts) not in allowed[scope_type]:raise ValueError('Use programme|subject or programme|subject|chapter')
    if scope_type=='programme' or len(parts)>1:parts[0]=canonical_programme(parts[0])
    if scope_type=='assessment_type' and parts[0] not in ('mastery','practice','standard','mock','recovery','diagnostic','exam'):
        raise ValueError('Unknown assessment type')
    return scope_type,'|'.join(parts)


def policy_matches_context(policy,context):
    p=dict(policy);ctx=dict(context)
    try:kind,key=normalise_policy_scope(p.get('scope_type'),p.get('scope_key'))
    except ValueError:return False
    if kind=='global':return True
    if kind=='programme':return canonical_programme(ctx.get('programme')).casefold()==key.casefold()
    if kind=='assessment_type':return str(ctx.get('assessment_type') or '').casefold()==key.casefold()
    if kind in ('blueprint','framework_version'):
        field='blueprint_id' if kind=='blueprint' else 'framework_version_id'
        return str(ctx.get(field) or '')==key
    parts=key.split('|')
    field='subject' if kind=='subject' else 'chapter'
    if len(parts)==1:return str(ctx.get(field) or '').casefold()==key.casefold()
    expected='|'.join([canonical_programme(ctx.get('programme')),str(ctx.get('subject') or '')]+([str(ctx.get('chapter') or '')] if kind=='chapter' else []))
    return expected.casefold()==key.casefold()


def mastery_record_policy_context(c,record):
    r=dict(record)
    result={'programme':canonical_programme(r.get('programme')),'subject':r.get('subject') or '',
            'chapter':r.get('chapter') or '', 'assessment_type':'mastery','blueprint_id':None,'framework_version_id':None}
    evidence=c.execute("""SELECT a.assessment_blueprint_id,ab.framework_version_id
      FROM mastery_form_results mf JOIN attempts a ON a.id=mf.attempt_id
      LEFT JOIN assessment_blueprints ab ON ab.id=a.assessment_blueprint_id
      WHERE mf.student_id=? AND mf.scope_type=? AND mf.scope_key=? AND mf.passed=1
      ORDER BY mf.id DESC LIMIT 1""",(r['student_id'],r['scope_type'],r['scope_key'])).fetchone()
    if evidence:result.update(blueprint_id=evidence['assessment_blueprint_id'],framework_version_id=evidence['framework_version_id'])
    return result


def _stricter_mastery(before,after):
    higher=('min_accuracy','min_questions','min_forms','target_band_pct','unseen_family_pct','min_breadth_pct')
    return any(float(after.get(k,0))>float(before.get(k,0)) for k in higher) or float(after.get('verification_days',90))<float(before.get('verification_days',90))


def simulate_policy_impact(c,blueprint=None,mastery_standard_score=50,scope_type=None,scope_key=''):
    bp=dict(blueprint or {})
    if scope_type is None:scope_type='blueprint' if bp else 'global';scope_key=str(bp.get('id') or '')
    kind,key=normalise_policy_scope(scope_type,scope_key,bp)
    proposal={'scope_type':kind,'scope_key':key}
    fake={'id':None,'policy_version':'PREVIEW','mastery_standard_score':policy_score(mastery_standard_score)}
    rows=c.execute("""SELECT mf.*,a.assessment_blueprint_id,ab.framework_version_id,s.meta_json session_meta,
      a.marking_status attempt_marking_status,a.mastery_evidence_eligible attempt_eligible
      FROM mastery_form_results mf
      LEFT JOIN attempts a ON a.id=mf.attempt_id
      LEFT JOIN assessment_sessions s ON s.id=mf.assessment_session_id
      LEFT JOIN assessment_blueprints ab ON ab.id=a.assessment_blueprint_id
      WHERE mf.demo_only=0 ORDER BY mf.id""").fetchall()
    groups={}
    for row in rows:
        ctx={'programme':row['programme'],'subject':row['subject'],'chapter':row['chapter'],'assessment_type':'mastery',
             'blueprint_id':row['assessment_blueprint_id'],'framework_version_id':row['framework_version_id']}
        if not policy_matches_context(proposal,ctx):continue
        groups.setdefault(row['target_level'],[]).append(row)
    output=[]
    for level,evidence in groups.items():
        base=mastery_policy(c,level)
        if not base:continue
        req=effective_mastery_requirements(base,fake);proposed=assessable=0
        for row in evidence:
            meta=safe_json(row['session_meta'],{})
            # Historical forms lacking explicit breadth/complexity measurements cannot
            # establish a numeric new-standard pass probability. Report unknown, not 0.
            ratio=meta.get('mastery_breadth_ratio');target=meta.get('mastery_target_band_ratio')
            if ratio is None or target is None or row['attempt_marking_status']!='FINAL' or row['attempt_eligible']!=1:continue
            assessable+=1
            meets=(float(row['score'])>=req['min_accuracy'] and row['question_count']>=req['min_questions']
              and float(ratio)>=req['min_breadth_pct'] and float(target)>=req['target_band_pct']
              and bool(meta.get('mastery_mandatory_covered')) and row['unseen_family_ratio']>=req['unseen_family_pct'])
            proposed+=int(meets)
        output.append({'level':level,'observed_forms':len(evidence),'assessable_forms':assessable,'unassessable_forms':len(evidence)-assessable,
          'current_form_pass_rate':round(100*sum(int(r['passed']) for r in evidence)/len(evidence),1),
          'estimated_proposed_form_pass_rate':round(100*proposed/assessable,1) if assessable else None,
          'proposed_min_accuracy':req['min_accuracy'],'proposed_min_questions':req['min_questions'],
          'proposed_unseen_family_pct':req['unseen_family_pct']})
    count=sum(len(v) for v in groups.values());assessable=sum(r['assessable_forms'] for r in output)
    return {'observed_forms':count,'assessable_forms':assessable,'unassessable_forms':count-assessable,'levels':output,
      'scope_type':kind,'scope_key':key,'confidence':'Descriptive only — not calibrated prediction',
      'external_percentile_claim':False,'note':'Form-level replay only. Missing historical fields are unknown; no student records are changed.'}


def admin_create_assessment_policy():
    if not require('admin'):return redirect(url_for('login'))
    c=db()
    try:
        rigor=policy_score(request.form.get('rigor_score'));standard=policy_score(request.form.get('mastery_standard_score'))
        raw=request.form.get('blueprint_id') or ''
        if raw and (not raw.isdigit() or int(raw)<=0):raise ValueError('Invalid blueprint')
        blueprint_id=int(raw) if raw else None
        bp=blueprint_joined(c,blueprint_id) if blueprint_id else None
        if blueprint_id and not bp:raise ValueError('Unknown blueprint')
        kind,key=normalise_policy_scope(request.form.get('scope_type','global'),request.form.get('scope_key',''),bp)
        if kind=='blueprint' and not bp:
            bp=blueprint_joined(c,int(key));blueprint_id=int(key)
            if not bp:raise ValueError('Unknown blueprint')
        if kind=='framework_version' and not c.execute('SELECT 1 FROM assessment_framework_versions WHERE id=?',(int(key),)).fetchone():raise ValueError('Unknown framework version')
        reason=request.form.get('reason','').strip()
        if not reason:raise ValueError('A reason is required')
        version=request.form.get('policy_version','').strip() or datetime.now().strftime('%Y.%m.%d.%H%M%S.%f')
        if len(version)>100:raise ValueError('Policy version is too long')
        sqlite_mutation.begin_immediate(c)
        if c.execute("SELECT 1 FROM assessment_assembly_policies WHERE scope_type=? AND lower(scope_key)=lower(?) AND policy_version=?",(kind,key,version)).fetchone():raise ValueError('That scope/version already exists')
        prior=c.execute("SELECT * FROM assessment_assembly_policies WHERE status='ACTIVE' AND scope_type=? AND lower(scope_key)=lower(?) ORDER BY id DESC LIMIT 1",(kind,key)).fetchone()
        preview={'historical_simulation':simulate_policy_impact(c,bp,standard,kind,key),'historical_mastery_is_not_rewritten':True,'material_tightening_action':'Verification Due'}
        if bp:
            current=blueprint_bank_sufficiency(c,bp['id'])
            preview.update(blueprint=bp['powerhouse_blueprint_id'],current_bank_ready=bool(current and current['ready']),
              current_mix=current['target_difficulty_mix'] if current else {},proposed_mix=rigor_mix(rigor,safe_json(bp['difficulty_distribution_json'],{})))
        code=request.form.get('policy_code','').strip() or 'SMX-POLICY-'+secrets.token_hex(8)
        selection={'unseen_family_ratio':round(.50+.004*rigor,2),'duplicate_family_limit':1,
          'target_difficulty_mix':preview.get('proposed_mix') or rigor_mix(rigor),
          'cognitive_demand_bias':'higher' if rigor>=65 else 'accessible' if rigor<=35 else 'balanced'}
        evidence=safe_json(prior['evidence_config_json'],{}) if prior else {}
        evidence.update(mastery_standard_score=standard,historical_results_immutable=True,policy_tightening_action='Verification Due',academic_approval_required=True)
        cur=c.execute("""INSERT INTO assessment_assembly_policies(policy_code,policy_version,scope_type,scope_key,framework_version_id,blueprint_id,
          name,rigor_score,mastery_standard_score,selection_config_json,evidence_config_json,status,created_by,reason,preview_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?,?)""",(code,version,kind,key,
          int(key) if kind=='framework_version' else bp['framework_version_id'] if bp else None,blueprint_id,
          request.form.get('name','').strip() or f'Rigor Policy {version}',rigor,standard,json.dumps(selection),json.dumps(evidence),session['user_id'],reason,json.dumps(preview)))
        record_policy_audit(c,cur.lastrowid,'CREATED','','DRAFT',reason,preview,session['user_id'])
        c.commit();flash('Policy saved as DRAFT. Review its scoped impact before activation.','success')
    except (ValueError,TypeError,sqlite3.IntegrityError) as exc:
        c.rollback();flash(str(exc) if isinstance(exc,ValueError) else 'Invalid or duplicate policy.','error')
        return redirect(url_for('admin_mastery_rigor'))
    finally:c.close()
    return redirect(url_for('admin_mastery_rigor'))


def admin_activate_assessment_policy(policy_id):
    if not require('admin'):return redirect(url_for('login'))
    c=db()
    try:
        sqlite_mutation.begin_immediate(c)
        p=c.execute('SELECT * FROM assessment_assembly_policies WHERE id=?',(policy_id,)).fetchone()
        if not p:abort(404)
        if p['status']!='DRAFT':raise ValueError('Only a draft policy can be activated')
        kind,key=normalise_policy_scope(p['scope_type'],p['scope_key'])
        policy_score(p['rigor_score']);policy_score(p['mastery_standard_score'])
        reason=request.form.get('reason','').strip()
        if not reason:raise ValueError('An activation reason is required')
        candidates=[]
        for record in mastery_policy_candidates(c,policy=p):
            ctx=mastery_record_policy_context(c,record)
            if not policy_matches_context(p,ctx):continue
            base=mastery_policy(c,record['mastery_level'])
            if not base:continue
            prior=active_assembly_policy(c,**ctx)
            candidates.append((record,ctx,effective_mastery_requirements(base,prior)))
        c.execute("UPDATE assessment_assembly_policies SET status='SUPERSEDED',superseded_at=CURRENT_TIMESTAMP WHERE status='ACTIVE' AND scope_type=? AND lower(scope_key)=lower(?) AND id<>?",(kind,key,policy_id))
        c.execute("UPDATE assessment_assembly_policies SET status='ACTIVE',approved_by=?,approved_at=CURRENT_TIMESTAMP,reason=? WHERE id=?",(session['user_id'],reason,policy_id))
        changed=[]
        for record,ctx,before in candidates:
            effective=active_assembly_policy(c,**ctx)
            after=effective_mastery_requirements(mastery_policy(c,record['mastery_level']),effective)
            if not _stricter_mastery(before,after):continue
            record_mastery_history(c,record,'policy_tightened',new_status='Verification Due',note=reason,
              metadata={'policy_id':policy_id,'previous_requirements':before,'new_requirements':after})
            c.execute("UPDATE mastery_records SET status='Verification Due',verification_due_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(record['id'],))
            changed.append(record['id'])
        record_policy_audit(c,policy_id,'ACTIVATED','DRAFT','ACTIVE',reason,
          {'scope_type':kind,'scope_key':key,'reverification_count':len(changed),'historical_results_immutable':True},session['user_id'])
        c.commit();flash(f'Policy activated. {len(changed)} in-scope mastery records require verification. Historical results are unchanged.','success')
    except (ValueError,TypeError) as exc:
        c.rollback();flash(str(exc),'error');return redirect(url_for('admin_mastery_rigor'))
    finally:c.close()
    return redirect(url_for('admin_mastery_rigor'))


def mastery_coverage_contract(c,programme,subject='',chapter='',scope_type='chapter'):
    """Consume an explicit frozen curriculum register, never the available item pool.

    Stored within the existing versioned policy evidence JSON. It must reference an
    approved original source and approved universal knowledge nodes. This function
    does not create, infer, import or confer PH authority on such a register.
    """
    programme=canonical_programme(programme);matches=[]
    for policy in c.execute("SELECT evidence_config_json FROM assessment_assembly_policies WHERE status='ACTIVE'").fetchall():
        document=safe_json(policy['evidence_config_json'],{})
        if not isinstance(document,dict):raise ValueError('Invalid policy evidence document')
        configs=document.get('curriculum_coverage_contracts',[])
        if not isinstance(configs,list):raise ValueError('Invalid curriculum coverage register list')
        for cfg in configs:
            if not isinstance(cfg,dict):continue
            if canonical_programme(cfg.get('programme'))!=programme:continue
            if cfg.get('scope_type')!=scope_type or str(cfg.get('subject') or '')!=subject or str(cfg.get('chapter') or '')!=chapter:continue
            matches.append(cfg)
    unique={integration_v1.canonical_json(x) for x in matches}
    if len(unique)!=1:raise ValueError('A unique approved curriculum coverage register is required; question inventory cannot substitute for syllabus coverage.')
    cfg=json.loads(next(iter(unique)))
    if cfg.get('schema')!='SM-CURRICULUM-COVERAGE-1' or cfg.get('complete') is not True or cfg.get('authority')!='POWER_HOUSE':raise ValueError('Coverage register is incomplete or ungoverned')
    if not isinstance(cfg.get('source_id'),str) or not cfg['source_id'] or not isinstance(cfg.get('curriculum_version'),str) or not re.fullmatch(r'[a-fA-F0-9]{64}',str(cfg.get('source_checksum_sha256') or '')):
        raise ValueError('Coverage source identity/version/checksum is incomplete')
    source=c.execute('SELECT * FROM universal_source_documents WHERE source_id=?',(cfg.get('source_id',''),)).fetchone()
    if not source or source['status'] not in ('APPROVED','VERIFIED','RELEASED') or source['version']!=cfg.get('curriculum_version') or source['file_hash']!=cfg.get('source_checksum_sha256'):
        raise ValueError('Coverage source/version/checksum cannot be verified')
    ids=cfg.get('required_node_ids');mandatory=cfg.get('mandatory_node_ids',[])
    if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Invalid curriculum node population')
    if not isinstance(mandatory,list) or any(not isinstance(x,str) for x in mandatory) or len(set(mandatory))!=len(mandatory) or not set(mandatory)<=set(ids):raise ValueError('Mandatory nodes are not contained in the curriculum')
    lookup={r['knowledge_node_id']:dict(r) for r in c.execute('SELECT * FROM universal_knowledge_nodes WHERE source_id=? AND version=?',(cfg['source_id'],cfg['curriculum_version'])).fetchall()}
    for nid in ids:
        node=lookup.get(nid,{})
        if node.get('status') not in ('APPROVED','RELEASED') or node.get('environment')!='LIVE' or node.get('exam_mastery_eligible')!=1 or canonical_programme(node.get('programme'))!=programme:
            raise ValueError('Curriculum node is missing, inactive or outside the programme')
        if subject and node.get('subject')!=subject:raise ValueError('Curriculum node belongs to another subject')
        if chapter and node.get('chapter')!=chapter:raise ValueError('Curriculum node belongs to another chapter')
    cfg['required_node_ids']=sorted(ids);cfg['mandatory_node_ids']=sorted(mandatory)
    cfg['checksum_sha256']=hashlib.sha256(integration_v1.canonical_json(cfg).encode()).hexdigest()
    return cfg


def question_coverage_nodes(row):
    q=dict(row)
    vals=safe_json(q.get('ph_knowledge_node_ids_json'),[])
    # Exact academic IDs only. Family IDs, question IDs and display topic strings
    # are not curriculum nodes and may never become a coverage denominator.
    return {x for x in vals if isinstance(x,str) and x.strip()} if isinstance(vals,list) else set()


def mastery_evidence_band_levels(target_level):
    """Map learner mastery targets onto the governed Power House item-level evidence bands.

    Power House questions are classified only as Foundation, Exam Ready, Advanced or
    Distinction. ScoreMax Expert (subject) and Elite (programme) are aggregate learner
    achievements, not new question labels. They therefore consume high-tier Advanced /
    Distinction evidence without inventing Expert/Elite item metadata.
    """
    target=str(target_level or '').strip()
    if target in ('Expert','Elite'):
        return {'Advanced','Distinction'}
    if target in ('Foundation','Exam Ready','Advanced','Distinction'):
        return {target}
    return set()


def attach_mastery_coverage(c,chosen,meta):
    if meta.get('mastery_demo_only'):return chosen,meta
    cfg=mastery_coverage_contract(c,meta['programme'],meta.get('subject',''),meta.get('chapters',''),meta['mastery_scope_type'])
    required=set(cfg['required_node_ids']);covered=set()
    for q in chosen:covered.update(question_coverage_nodes(q)&required)
    ratio=len(covered)/len(required)
    mandatory=set(cfg['mandatory_node_ids'])<=covered
    threshold=float(meta['mastery_effective_policy'].get('min_breadth_pct',0))
    if ratio+1e-12<threshold or not mandatory:
        raise ValueError(f'The mastery form covers {len(covered)}/{len(required)} required curriculum nodes; its governed breadth/mandatory-node rule is not met.')
    target=meta['mastery_target_level'];band=mastery_evidence_band_levels(target)
    if not band:raise ValueError('Unknown mastery evidence band')
    target_ratio=sum((q['level'] or 'Foundation') in band for q in chosen)/len(chosen)
    meta.update(mastery_breadth_ok=True,mastery_breadth_ratio=ratio,mastery_breadth_required_pct=threshold,
      mastery_breadth_unit='governed curriculum knowledge node',mastery_breadth_covered=len(covered),mastery_breadth_required=len(required),
      mastery_mandatory_covered=mandatory,mastery_coverage_snapshot=cfg,mastery_target_band_ratio=target_ratio,
      mastery_evidence_band_levels=sorted(band))
    meta['mastery_effective_policy']=dict(meta['mastery_effective_policy'],coverage_contract_checksum=cfg['checksum_sha256'])
    return chosen,meta


def ensure_mastery_launch_policy_v1(c):
    """Apply the launch mastery baseline exactly once, with an auditable migration.

    This changes future evidence requirements only. Historical attempts are immutable;
    any existing verified record affected by a stricter baseline becomes Verification
    Due through the existing governance path rather than being silently downgraded.
    """
    marker='SCOREMAX_MASTERY_LAUNCH_POLICY_V1'
    c.execute("""CREATE TABLE IF NOT EXISTS mastery_policy_change_audit_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mastery_level TEXT NOT NULL,
      actor_user_id INTEGER,
      previous_json TEXT NOT NULL DEFAULT '{}',
      new_json TEXT NOT NULL DEFAULT '{}',
      reason TEXT NOT NULL DEFAULT '',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    if c.execute("SELECT 1 FROM mastery_policy_change_audit_v1 WHERE reason=? LIMIT 1",(marker,)).fetchone():
        return False
    rules=[
      ('Foundation',1,10,70.0,120,None,0.20,0.50,0.50),
      ('Exam Ready',1,20,80.0,90,None,0.25,0.50,0.70),
      ('Advanced',2,15,88.0,75,None,0.30,0.60,0.80),
      ('Distinction',2,20,94.0,60,None,0.35,0.65,0.90),
      ('Expert',2,25,95.0,45,None,0.40,0.70,0.95),
      ('Elite',3,30,97.0,30,None,0.45,0.75,1.00),
    ]
    for level,min_forms,min_questions,min_accuracy,verification_days,external_percentile,target_band,unseen,breadth in rules:
        row=c.execute("SELECT * FROM mastery_policies WHERE mastery_level=?",(level,)).fetchone()
        if not row:raise ValueError(f'Missing mastery policy: {level}')
        before=dict(row)
        c.execute("""UPDATE mastery_policies SET min_forms=?,min_questions=?,min_accuracy=?,
          verification_days=?,external_percentile_target=?,target_band_pct=?,
          unseen_family_pct=?,min_breadth_pct=?,updated_at=CURRENT_TIMESTAMP
          WHERE mastery_level=?""",(min_forms,min_questions,min_accuracy,verification_days,
          external_percentile,target_band,unseen,breadth,level))
        after=dict(c.execute("SELECT * FROM mastery_policies WHERE mastery_level=?",(level,)).fetchone())
        c.execute("""INSERT INTO mastery_policy_change_audit_v1(
          mastery_level,actor_user_id,previous_json,new_json,reason)
          VALUES(?,NULL,?,?,?)""",(level,json.dumps(before,sort_keys=True,default=str),
          json.dumps(after,sort_keys=True,default=str),marker))
        mark_baseline_changes_for_verification(c,level,before,marker)
    return True


def validate_mastery_policy_values(values):
    import math
    rules={'min_forms':(1,100,True),'min_questions':(5,10000,True),'min_accuracy':(0,100,False),
      'verification_days':(1,3650,True),'target_band_pct':(0,1,False),'unseen_family_pct':(0,1,False),
      'min_breadth_pct':(0,1,False),'external_percentile_target':(0,100,False)}
    out={}
    for name,(lo,hi,integer) in rules.items():
        value=values.get(name)
        if name=='external_percentile_target' and value in (None,''):
            out[name]=None;continue
        if value in (None,'') or isinstance(value,bool):raise ValueError(f'{name} is required')
        try:number=float(value)
        except (ValueError,TypeError):raise ValueError(f'Invalid {name}')
        if not math.isfinite(number) or not lo<=number<=hi or (integer and number!=int(number)):
            raise ValueError(f'{name} must be a finite number between {lo} and {hi}')
        out[name]=int(number) if integer else number
    return out


def select_mastery_coverage_questions(pool,count,target,target_fraction,unseen_fraction,previous,coverage,rigor):
    """Bounded deterministic greedy assembly; reject unsatisfied constraints, never relax.

    This extends the native form assembler. It is not a claim of complete set-cover
    optimisation: a fragmented bank may require more eligible questions or a blueprint.
    """
    import math
    required=set(coverage['required_node_ids']);mandatory=set(coverage['mandatory_node_ids'])
    band=mastery_evidence_band_levels(target)
    if not band:raise ValueError('Unknown mastery evidence band')
    threshold=float(coverage.get('min_breadth_pct',0))
    needed=int(math.ceil(len(required)*threshold-1e-12))
    target_needed=int(math.ceil(count*target_fraction-1e-12))
    unseen_needed=int(math.ceil(count*unseen_fraction-1e-12))
    freq={node:sum(node in question_coverage_nodes(q) for q in pool) for node in required}
    difficulty_order=({'Difficult':0,'Moderate':1,'Easy':2} if rigor>=65 else
      {'Easy':0,'Moderate':1,'Difficult':2} if rigor<=35 else {'Moderate':0,'Difficult':1,'Easy':2})
    def family(q):return str(q['family_id'] or f"Q-{q['id']}")
    chosen=[];families=set();covered=set()
    for _ in range(count):
        slots=count-len(chosen)
        t_need=max(0,target_needed-sum((q['level'] or 'Foundation') in band for q in chosen))
        u_need=max(0,unseen_needed-sum(family(q) not in previous for q in chosen))
        candidates=[q for q in pool if family(q) not in families
          and (t_need<slots or (q['level'] or 'Foundation') in band) and (u_need<slots or family(q) not in previous)]
        if not candidates:break
        missing=mandatory-covered
        def rank(q):
            gain=question_coverage_nodes(q)&required-covered
            urgent=missing&gain
            return (bool(urgent),sum(1/max(1,freq[n]) for n in urgent),
              len(gain) if len(covered)<needed else 0,
              int(t_need>0 and (q['level'] or 'Foundation') in band)+int(u_need>0 and family(q) not in previous),
              -difficulty_order.get(normalize_difficulty(q['difficulty'] or q['level']),1),-int(q['id']))
        q=max(candidates,key=rank)
        chosen.append(q);families.add(family(q));covered.update(question_coverage_nodes(q)&required)
    if len(chosen)<count or len(covered)<needed or not mandatory<=covered:
        raise ValueError('The independent question bank cannot meet the frozen curriculum coverage requirement with this form size.')
    if sum((q['level'] or 'Foundation') in band for q in chosen)<target_needed or sum(family(q) not in previous for q in chosen)<unseen_needed:
        raise ValueError('The independent question bank cannot meet the target-level and unseen-evidence requirements.')
    return chosen


def mastery_policy_candidates(c,policy=None,level=''):
    """Narrow candidate scans by the actual policy scope before resolving precedence."""
    clauses=["status IN ('Verified','Elite Candidate')"];params=[]
    if level:clauses.append('mastery_level=?');params.append(level)
    if policy:
        kind,key=normalise_policy_scope(policy['scope_type'],policy['scope_key'])
        if kind=='programme':
            clauses.append('lower(programme)=lower(?)');params.append(key)
        elif kind in ('subject','chapter'):
            parts=key.split('|')
            fields=(['subject' if kind=='subject' else 'chapter'] if len(parts)==1 else
                    ['programme','subject'] if kind=='subject' else ['programme','subject','chapter'])
            for field,value in zip(fields,parts):clauses.append(f'lower({field})=lower(?)');params.append(value)
    return c.execute('SELECT * FROM mastery_records WHERE '+' AND '.join(clauses)+' ORDER BY id',params).fetchall()


def mark_baseline_changes_for_verification(c,level,before_policy,reason):
    changed=0
    for record in mastery_policy_candidates(c,level=level):
        ctx=mastery_record_policy_context(c,record);assembly=active_assembly_policy(c,**ctx)
        before=effective_mastery_requirements(before_policy,assembly)
        after=effective_mastery_requirements(mastery_policy(c,level),assembly)
        if not _stricter_mastery(before,after):continue
        record_mastery_history(c,record,'baseline_policy_tightened',new_status='Verification Due',note=reason,
          metadata={'previous_requirements':before,'new_requirements':after})
        c.execute("UPDATE mastery_records SET status='Verification Due',verification_due_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(record['id'],))
        changed+=1
    return changed
