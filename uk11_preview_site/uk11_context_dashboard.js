/* ScoreMax UK 11+ / school-aware student landing, 23 Nov 2026.
 * Presentation adapter on the isolated static preview; no login, data persistence,
 * academic approval, admissions decision, native scoring or mastery update.
 * Always derive subject visibility from selected school -> evidenced route.
 */
(function () {
  'use strict';
  if (typeof state === 'undefined' || typeof SCHOOLS === 'undefined' ||
      typeof ROUTES === 'undefined' || typeof chosenSchools !== 'function' ||
      typeof render !== 'function' || typeof home !== 'function') return;

  const old = {
    render: render, home: home, parents: parents, practice: practice,
    mocks: mocks, nav: nav, subjectTiles: subjectTiles, schools: schools
  };
  const e = escapeHtml;
  const validStatuses = new Set(['CURRENT_CYCLE_OFFICIAL','PRIOR_CYCLE_OFFICIAL']);
  const firstRouteLabels = document.querySelector('.programme-rail')?.innerHTML || '';
  const featureSubjects = FEATURE_AREAS.find(f => f.id === 'subjects');
  const defaultFeatureSummary = featureSubjects ? featureSubjects.summary : '';
  const knownViews = new Set(['home','schools','plan','practice','mocks','features','parents','question',
    'recovery','insights','spark','capsules','knowledge','challenges','writing','teacher','onboarding']);

  function deriveContext() {
    const schools = chosenSchools().filter(s => !String(s.school_id || '').endsWith('-route'));
    const routeIds = [];
    const pending = [];
    const provisional = [];
    for (const s of schools) {
      if (!validStatuses.has(s.routing_status)) {
        pending.push(s);
        continue;
      }
      if (s.routing_status !== 'CURRENT_CYCLE_OFFICIAL') provisional.push(s);
      const ids = Array.isArray(s.route_ids) ? s.route_ids : (s.route_id ? [s.route_id] : []);
      for (const id of ids) {
        if (ROUTES.some(r => r.route_id === id) && !routeIds.includes(id)) routeIds.push(id);
      }
      if (!ids.length) pending.push(s);
    }
    const routes = routeIds.map(id => ROUTES.find(r => r.route_id === id)).filter(Boolean);
    const subjects = SUBJECTS.filter(subject => routes.some(r =>
      Array.isArray(r.subjects) && r.subjects.includes(subject)));
    const perSubject = subjects.map(subject => ({
      name: subject,
      routes: routes.filter(r => r.subjects.includes(subject)),
      sampleCount: QUESTIONS.filter(q => q.subject === subject).length
    }));
    return { schools, pending, provisional, routes, subjects, perSubject,
      selected: schools.length > 0,
      hasMapped: routes.length > 0,
      uniqueTests: routes.length };
  }

  function softTag(text, extra='') {
    return '<span class="context-tag' + (extra ? ' ' + extra : '') + '">' + e(text) + '</span>';
  }
  function schoolNameList(items, max=3) {
    return items.slice(0,max).map(x=>e(x.school_name)).join(' · ') +
      (items.length > max ? ' · +' + (items.length-max) + ' more' : '');
  }
  function scopeAlert(ctx) {
    if (!ctx.pending.length && !ctx.provisional.length) return '';
    return '<div class="context-caution" role="status">' +
      (ctx.pending.length ? '<strong>' + ctx.pending.length + ' school' +
        (ctx.pending.length>1?'s have':' has') + ' no verified test mapping for this intake.</strong> ' +
        'Their exam subjects have not been added. ' : '') +
      (ctx.provisional.length ? '<strong>Previous-cycle reference:</strong> ' +
        ctx.provisional.length + ' school' + (ctx.provisional.length>1?'s use':' uses') +
        ' a historical test mapping. Confirm 2028 admission requirements before relying on it. ' : '') +
      'Admission eligibility is assessed separately by each school.</div>';
  }
  function programmeItems(ctx) {
    const strip = document.querySelector('.programme-rail');
    if (!strip) return;
    if (!ctx.selected) { if (strip.innerHTML !== firstRouteLabels) strip.innerHTML=firstRouteLabels; return; }
    strip.innerHTML =
      '<span class="programme-label">MY SELECTED TESTS</span>' +
      (ctx.routes.length ? ctx.routes.map(r => '<span class="context-route">' +
        e(r.name) + (r.evidence_cycle === 2028 ? '' : ' · check 2028') +
        '</span>').join('') :
        '<span class="context-route unverified">No confirmed test mapping</span>') +
      '<button class="context-change" type="button" data-act="view:schools">Edit schools</button>';
  }
  function contextNav() {
    const ctx = deriveContext();
    const items = [
      ['home','⌂','My home'], ['schools','⌕','My schools'],
      ['plan','◷','Study plan']
    ];
    if (!ctx.selected || ctx.subjects.length) items.push(['practice','◈','Subject practice']);
    if (!ctx.selected || ctx.routes.length) items.push(['mocks','▤','Exam centre']);
    items.push(['features','✦','Explore ScoreMax']);
    const extraViews = ['recovery','insights','spark','capsules','knowledge',
      'challenges','writing','teacher','onboarding'];
    const navEl = document.getElementById('nav');
    if (navEl) navEl.innerHTML = items.map(([id,glyph,label])=>{
      const active = id === 'home' ? (state.view==='home'||state.view==='parents') :
        id === 'features' ? (state.view==='features'||extraViews.includes(state.view)) :
        state.view===id;
      return '<button type="button" class="nav-btn'+(active?' active':'')+
        '" data-act="view:'+id+'" aria-label="'+e(label)+
        '" aria-current="'+(active?'page':'false')+'">'+
        '<span class="glyph" aria-hidden="true">'+glyph+'</span>'+
        '<span class="label">'+e(label)+'</span></button>';
    }).join('');
    document.getElementById('studentRole')?.classList.toggle('active',state.role==='student');
    document.getElementById('parentRole')?.classList.toggle('active',state.role==='parent');
  }
  function subjectsHTML(ctx) {
    if (!ctx.selected) return old.subjectTiles();
    if (!ctx.perSubject.length) return '<div class="context-empty" role="status">' +
      '<strong>Subject requirements pending verification</strong><p>The chosen school' +
      (ctx.schools.length>1?'s do':' does') +
      ' not yet have an accepted test-to-subject mapping for the selected entry year. ' +
      'ScoreMax will not display unrelated subjects as if they were required.</p>' +
      btn('Review my schools','view:schools','secondary small')+'</div>';
    return '<div class="context-subject-grid">' + ctx.perSubject.map(item =>
      '<article class="context-subject"><div class="context-subject-icon" aria-hidden="true">' +
      e(SYMBOLS[item.name] || '✧') + '</div><div class="context-subject-body"><h3>'+
      e(item.name)+'</h3><p>Required by ' + item.routes.length +
      ' selected test ' + (item.routes.length===1?'route':'routes') + '</p>'+
      '<div class="context-source-chips">' + item.routes.map(r =>
        softTag(r.name + (r.evidence_cycle===2028?'':' · reference'),'quiet')).join('')+
      '</div><p class="context-foot">Sample practice: '+item.sampleCount+
      ' unmarked demonstration item'+(item.sampleCount===1?'':'s')+'.</p></div>'+
      '<button type="button" class="secondary small" data-act="start:'+e(item.name)+
      '"'+(item.sampleCount===0?' disabled':'')+'>'+
      (item.sampleCount?'Try sample practice':'Examples unavailable')+'</button></article>'
    ).join('')+'</div>';
  }
  function routeCards(ctx) {
    if (!ctx.routes.length) return '';
    return '<div class="context-test-grid">' + ctx.routes.map(r =>
      '<article class="context-test"><div class="context-test-top"><span class="eyebrow">TEST PATHWAY</span>'+
      softTag(r.evidence_cycle===2028?'2028-entry source':'Earlier-cycle reference',
        r.evidence_cycle===2028?'':'warn')+'</div>'+
      '<h3>'+e(r.name)+'</h3><p class="text-sm muted">'+e(r.format || 'Format verification pending')+'</p>'+
      chips(r.subjects || [])+
      (r.notes ? '<p class="context-foot">'+e(r.notes)+'</p>' : '')+
      '<div class="actions">'+btn('Preview exam format','mock:'+e(r.route_id),'secondary small')+
      '</div></article>'
    ).join('')+'</div>';
  }
  function schoolAwareHome() {
    const ctx = deriveContext();
    if (!ctx.selected) return old.home();
    if (state.role==='parent') return parents();
    return masteryShowcase('student') +
      '<header class="context-hero"><div><span class="eyebrow">YOUR SCHOOL-SPECIFIC LEARNING SPACE</span>'+
      '<h1>Welcome to your 11+ preparation</h1>'+
      '<p class="context-subtitle">Your preview is tailored to '+
      e(ctx.schools.length===1?'your chosen school':'your chosen schools')+
      '. This is the page a learner would see <strong>after sign-in</strong>; there is no account login in this static preview.</p>'+
      '<div class="context-selected">'+softTag(ctx.schools.length + ' school' +
      (ctx.schools.length===1?'':'s')+' selected')+
      softTag(ctx.uniqueTests+' mapped test'+(ctx.uniqueTests===1?'':'s'))+
      softTag(ctx.subjects.length+' relevant subject'+(ctx.subjects.length===1?'':'s'))+
      '</div><p class="context-schoolnames">'+schoolNameList(ctx.schools)+'</p>'+
      '<div class="actions">'+btn('Change my schools','view:schools','secondary small')+
      btn('My study plan','view:plan','secondary small')+'</div></div>'+
      '<div class="context-hero-visual" aria-hidden="true">✦</div></header>'+
      scopeAlert(ctx) +
      heading('Your subjects',
        ctx.hasMapped?'Only subjects associated with mapped tests for your selected schools.':
          'Your selected schools do not yet have confirmed subject requirements.')+
      subjectsHTML(ctx)+
      (ctx.hasMapped?heading('Your test pathways',
        'Shared tests appear only once when several schools use the same route.')+routeCards(ctx):'')+
      heading('Your next steps','ScoreMax does not invent progress, marks or admissions predictions.')+
      '<div class="grid2">'+
      '<div class="card"><strong>Current mastery: Not Yet Established</strong>'+
      '<p class="text-sm muted">Next goal: Foundation. Independent eligible evidence is required to establish progress.</p>'+
      btn('Explore learning plan','view:plan','secondary small')+'</div>'+
      '<div class="card"><strong>Full ScoreMax support</strong>'+
      '<p class="text-sm muted">Weak-area recovery, Daily Spark, learning capsules, Knowledge Hub and challenges remain part of your learning experience.</p>'+
      btn('Explore learning tools','view:features','secondary small')+'</div></div>'+
      '<p class="context-disclaimer">Static UX preview only. No learner account, saved choices, native marking or genuine mastery assessments are connected. Subject/test references require admission-cycle verification.</p>';
  }
  function schoolAwarePractice() {
    const ctx=deriveContext();
    if (!ctx.selected) return old.practice();
    return '<header class="tool-header"><div><h1>Practice for your chosen schools</h1>'+
      '<p>Only the mapped subject areas appear below. Your selected schools determine the options; sample questions are not graded.</p>'+
      '</div>'+softTag('Unmarked demonstration')+'</header>'+
      scopeAlert(ctx)+subjectsHTML(ctx)+
      (ctx.subjects.length?heading('Preparation guidance','Your subject coverage is shared across selected test routes, not duplicated school by school.')+
      '<div class="card"><strong>Foundation first</strong><p class="text-sm muted">Explore practice and return to the study plan. No sample response updates independent mastery.</p>'+
      btn('Open study plan','view:plan','secondary small')+'</div>':'') +
      '<p class="context-disclaimer">Demonstration questions may not match a provider’s actual paper; official test format, timing and marking must be independently qualified.</p>';
  }
  function schoolAwareMocks() {
    const ctx=deriveContext();
    if (!ctx.selected) return old.mocks();
    if (!ctx.routes.length) return '<h1 class="title">Your exam centre</h1>'+
      scopeAlert(ctx)+'<div class="context-empty"><strong>Test route pending</strong>'+
      '<p>We cannot show school-specific mock examinations until your chosen school’s test route is verified.</p>'+
      btn('Review schools','view:schools','secondary small')+'</div>';
    return '<header class="tool-header"><div><h1>Your exam centre</h1>'+
      '<p>Only test routes linked to your selected schools appear. These are unmarked layout demonstrations, not live timed papers.</p></div>'+
      softTag(ctx.routes.length+' matched test'+(ctx.routes.length===1?'':'s'))+
      '</header>'+scopeAlert(ctx)+routeCards(ctx)+
      '<p class="context-disclaimer">Each test’s timing, format, accessibility and official scoring remain subject to source verification. No admission estimate is produced.</p>';
  }
  function schoolAwareParents() {
    const ctx=deriveContext();
    if (!ctx.selected) return old.parents();
    return masteryShowcase('parent')+
      '<header class="tool-header"><div><h1>Family learning overview</h1>'+
      '<p>Selected schools: '+schoolNameList(ctx.schools,5)+
      '. The preparation areas below are derived from mapped tests only.</p></div>'+
      softTag('No learner assessment recorded')+'</header>'+
      scopeAlert(ctx)+
      '<div class="stats"><div class="stat"><strong>'+ctx.schools.length+
      '</strong><small>Selected schools</small></div><div class="stat"><strong>'+
      ctx.uniqueTests+'</strong><small>Mapped tests</small></div>'+
      '<div class="stat"><strong>'+ctx.subjects.length+
      '</strong><small>Mapped subjects</small></div></div>'+
      heading('Subjects relevant to your school choices','Unverified schools cannot generate presumed requirements.')+
      subjectsHTML(ctx)+
      '<div class="grid2 context-parent-actions">'+
      '<div class="card"><strong>Mastery and progress</strong><p class="text-sm muted">Current: Not Yet Established. Next goal: Foundation. No verified results or admission predictions exist.</p>'+
      btn('Learning insights','view:insights','secondary small')+'</div>'+
      '<div class="card"><strong>School choices and plan</strong><p class="text-sm muted">Change schools or review a combined study plan with no duplicated test subjects.</p>'+
      btn('Change school selection','view:schools','secondary small')+'</div></div>';
  }

  const originalSchools = schools;
  schools = function () {
    let html=originalSchools();
    const oldButton=btn('View my combined plan','view:plan');
    if (deriveContext().selected && html.includes(oldButton)) {
      html=html.replace(oldButton,
        btn('Open my student home','view:home')+' '+oldButton);
    }
    return html;
  };
  subjectTiles = function () { return subjectsHTML(deriveContext()); };
  home = schoolAwareHome;
  practice = schoolAwarePractice;
  mocks = schoolAwareMocks;
  parents = schoolAwareParents;
  nav = contextNav;

  const previousRender = render;
  render = function () {
    const ctx = deriveContext();
    if (ctx.selected && ctx.subjects.length && !ctx.subjects.includes(state.subject)) {
      state.subject=ctx.subjects[0];
    }
    // School selection changed during a question session: do not display
    // an out-of-scope quiz left from the previous school selection.
    if (state.view==='question' && ctx.selected &&
        (state.mode==='mock' ? !ctx.routes.some(r =>
          r.subjects.includes(state.subject)) : !ctx.subjects.includes(state.subject))) {
      state.view='home';state.quiz=[];state.responses={};state.completed=false;
    }
    if (featureSubjects) {
      featureSubjects.summary = !ctx.selected ? defaultFeatureSummary :
        ctx.subjects.length ? 'Your mapped subjects: '+ctx.subjects.join(', ')+'.' :
        'Your school’s subject requirements await verification.';
    }
    previousRender();
    programmeItems(ctx);
  };

  // Block stale/demo test or subject controls after a school change. This is
  // display guard only: true authorisation must be enforced server-side.
  document.addEventListener('click',function(ev){
    const button=ev.target.closest('button[data-act]');
    if(!button)return;
    const a=button.getAttribute('data-act');
    if(!a)return;
    const ctx=deriveContext();
    if(!ctx.selected)return;
    if(a.startsWith('start:') && !ctx.subjects.includes(a.slice(6))){
      ev.stopImmediatePropagation();ev.preventDefault();return;
    }
    if(a.startsWith('mock:') && !ctx.routes.some(r=>r.route_id===a.slice(5))){
      ev.stopImmediatePropagation();ev.preventDefault();return;
    }
  },true);

  // This extension stays within current in-memory client state.
  // Authentication and persisted school-scoped entitlements belong to Chat 3.
  render();
})();