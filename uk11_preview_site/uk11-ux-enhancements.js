/* ScoreMax UK 11+ — incremental static UX enhancement.
 * Extends the accepted preview without changing academic data, backend or Pakistan production.
 * Everything here is a non-persistent presentation demonstration. */
(function () {
  'use strict';
  if (typeof state === 'undefined' || typeof MASTERY_LEVELS === 'undefined' ||
      typeof render !== 'function' || !document.getElementById('page')) return;

  const original = { render: render, home: home, parents: parents };
  const e = escapeHtml;
  const stageColours = ['#4b70c9','#138776','#7159b6','#a46b3a','#9b4aaa','#284a9c'];
  const toolViews = {
    study: 'plan', weak: 'recovery', subjects: 'practice', mocks: 'mocks',
    progress: 'insights', spark: 'spark', capsules: 'capsules',
    challenges: 'challenges', knowledge: 'knowledge', writing: 'writing',
    support: 'teacher', parents: 'parents', community: ''
  };
  const extendedPages = {
    plan: planPage, recovery: recoveryPage, insights: insightsPage,
    spark: sparkPage, capsules: capsulesPage, knowledge: knowledgePage,
    challenges: challengesPage, writing: writingPage, teacher: teacherPage,
    onboarding: onboardingPage
  };
  state.level = '';  // No level is selected as if achieved on first visit.
  state.onboard = new Set();
  state.writingDraft = '';

  function status(label, concept) {
    return '<span class="demo-status' + (concept ? ' concept' : '') +
      '">' + e(label) + '</span>';
  }
  function intro(title, description, label) {
    return '<header class="tool-header"><div><h1>' + e(title) + '</h1><p>' +
      e(description) + '</p></div>' + status(label || 'Static UX preview') + '</header>';
  }
  function actionCard(title, desc, label, act) {
    return '<div class="card action-card"><div><h3>' + e(title) + '</h3><p>' +
      e(desc) + '</p></div><div class="actions">' +
      btn(label, act, 'secondary small') + '</div></div>';
  }
  function evidenceNote() {
    return '<p class="note">No scores, skill diagnoses, mastery achievements, admission eligibility or learning history have been generated. This static demonstration does not store student data or connect to marking.</p>';
  }
  function masterySummary(audience) {
    return '<section class="mastery-status-card" aria-label="Learner mastery status">' +
      '<div><span class="eyebrow">' + (audience === 'parent' ? 'FAMILY LEARNING OVERVIEW' : 'YOUR LEARNING JOURNEY') +
      '</span><h2>Current: Not Yet Established · Next goal: Foundation</h2>' +
      '<p>Choose your school or test routes, explore the relevant subjects, then complete independently assessed work once the qualified ScoreMax service is connected. Sample answers do not count towards mastery.</p></div>' +
      '<div class="actions">' + btn('Choose schools', 'view:schools', 'secondary small') +
      btn('Explore practice', 'view:practice', 'secondary small') + '</div></section>';
  }
  masteryShowcase = function(audience) { return masterySummary(audience); };

  function masteryDockHTML() {
    const selected = MASTERY_LEVELS.find(function(l){ return l.n === state.level; });
    let items = MASTERY_LEVELS.map(function(level, index) {
      return '<button type="button" class="mastery-step' +
        (state.level === level.n ? ' active' : '') + '" style="--tier:' + stageColours[index] +
        '" data-act="level:' + e(level.n) + '" aria-pressed="' + (state.level === level.n) +
        '" aria-label="Explore ' + e(level.n) + ' level. Not an achieved level.">' +
        '<small>LEVEL ' + e(level.num) + '</small><strong>' + e(level.n) +
        '</strong><span>' + e(level.scope) + '</span></button>';
    }).join('');
    return '<div class="mastery-dock-head"><div><span class="eyebrow">THE SCOREMAX DIFFERENCE</span>' +
      '<h2>Foundation → Exam Ready → Advanced → Distinction → Expert → Elite</h2>' +
      '<p>Explore the six stages. A highlighted card is an explanation, not an award.</p></div>' +
      '<div class="mastery-state">Current learner status<strong>Not Yet Established</strong></div></div>' +
      '<div class="mastery-steps" aria-label="Six mastery level explanations">' + items + '</div>' +
      '<div class="mastery-next"><div><strong>Next goal: Foundation.</strong> ' +
      'Learning action: choose the right test routes and explore appropriate practice. ' +
      'Independent qualified evidence will be required to establish a level.</div>' +
      btn('Choose school or test', 'view:schools', 'mini') + '</div>' +
      (selected ? '<div class="mastery-info" aria-live="polite"><strong>About ' +
        e(selected.n) + ': ' + e(selected.short) + '</strong><p>' + e(selected.detail) +
        '</p></div>' : '') +
      '<div class="mastery-caption">Foundation–Distinction: topic/chapter progression · ' +
      'Expert: subject-wide · Elite: broad/full-exam achievement. None is awarded in this demo.</div>';
  }
  function installChrome() {
    const routeStrip = document.querySelector('.programme-rail');
    if (routeStrip && !document.getElementById('masteryDock')) {
      const el = document.createElement('section');
      el.id = 'masteryDock';
      el.className = 'mastery-dock';
      el.setAttribute('aria-label', 'Six ScoreMax mastery levels and current learner status');
      routeStrip.insertAdjacentElement('afterend', el);
    }
    if (!document.querySelector('.skip-link')) {
      const skip = document.createElement('a');
      skip.className = 'skip-link';
      skip.href = '#page';
      skip.textContent = 'Skip to main content';
      document.body.insertAdjacentElement('afterbegin', skip);
    }
    document.getElementById('page').setAttribute('tabindex','-1');
    document.getElementById('page').setAttribute('aria-live','off');
    document.querySelector('.programme-rail')?.setAttribute('role','group');
  }
  function syncChrome() {
    const dock = document.getElementById('masteryDock');
    if (dock) dock.innerHTML = masteryDockHTML();
    const rname = ROUTES.find(function(r){ return r.name === state.search; })?.route_id || '';
    document.querySelectorAll('.programme-link').forEach(function(item) {
      const id = item.getAttribute('data-act').slice('route:'.length);
      const active = id === rname;
      item.classList.toggle('active',active);
      item.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll('.role button').forEach(function(button) {
      const selected = button.id === (state.role === 'parent' ? 'parentRole' : 'studentRole');
      button.setAttribute('aria-pressed', String(selected));
    });
  }
  nav = function() {
    const views = [
      ['home','⌂','Home'], ['schools','⌕','Schools & tests'],
      ['plan','◷','My study plan'], ['practice','◈','Practice'],
      ['mocks','▤','Exam centre'], ['features','✦','Explore ScoreMax']
    ];
    const extras = ['features','recovery','insights','spark','capsules',
      'knowledge','challenges','writing','teacher','onboarding'];
    document.getElementById('nav').innerHTML = views.map(function(item) {
      const id = item[0], glyph = item[1], label = item[2];
      const current = id === 'home' ? (state.view === 'home' || state.view === 'parents') :
        id === 'features' ? extras.includes(state.view) : state.view === id;
      return '<button type="button" class="nav-btn' + (current ? ' active' : '') +
        '" data-act="view:' + id + '" aria-label="' + e(label) +
        '" aria-current="' + (current ? 'page' : 'false') +
        '"><span class="glyph" aria-hidden="true">' + glyph +
        '</span><span class="label">' + e(label) + '</span></button>';
    }).join('');
    document.getElementById('studentRole').classList.toggle('active', state.role === 'student');
    document.getElementById('parentRole').classList.toggle('active', state.role === 'parent');
  };
  featureShowcase = function() {
    const selected = FEATURE_AREAS.find(function(f){ return f.id === state.feature; });
    const cards = FEATURE_AREAS.map(function(f){
      const target = toolViews[f.id];
      return '<button class="feature-card' + (state.feature === f.id ? ' active' : '') +
        '" type="button" data-act="feature:' + e(f.id) + '" aria-pressed="' +
        (state.feature === f.id) + '"><span class="feature-symbol" aria-hidden="true">' +
        f.icon + '</span><strong>' + e(f.title) + '</strong><span>' +
        e(f.summary) + '</span>' + status(target ? 'View available' : 'Concept only', !target) +
        '</button>';
    }).join('');
    let detail = '';
    if (selected) {
      const target = toolViews[selected.id];
      detail = '<div class="feature-detail" aria-live="polite"><strong>' + e(selected.title) +
        '</strong><p>' + e(selected.detail) + '</p><p class="hint">' +
        (target ? 'This opens a navigable static experience. Live learning integration is not active.' :
          'This feature is not implemented in the UK static preview.') +
        '</p><div class="actions">' +
        (target ? btn('Open ' + selected.title, 'view:' + target, 'secondary small') : '') +
        '</div></div>';
    }
    return '<section class="feature-space" aria-labelledby="featuresTitle">' +
      heading('Explore the full ScoreMax experience', 'UK navigation previews extend the existing feature map; none is an operational learning service.') +
      '<div class="feature-grid">' + cards + '</div>' + detail +
      '<div class="panel-block">' + btn('Getting started guide', 'view:onboarding','secondary small') +
      ' ' + btn('Teacher & classroom preview', 'view:teacher','secondary small') + '</div></section>';
  };
  parents = function() {
    return original.parents() +
      heading('Next actions for families','Preview the learner plan and understand what the evidence can—and cannot—show.') +
      '<div class="grid2">' +
      actionCard('Combined learning plan','Shared subject areas from selected routes, without pretending to know strengths or weaknesses.','View plan','view:plan') +
      actionCard('Insights and support','An honest unassessed state until qualified marking exists.','View insights','view:insights') +
      '</div>';
  };
  home = function() {
    return state.role === 'parent' ? parents() : original.home();
  };

  function planPage() {
    const rs = chosenRoutes(), ss = activeSubjects();
    const selectedHtml = rs.length ? rs.map(function(r) {
      return '<div class="route-row"><div class="info"><strong>' + e(r.name) +
        '</strong><p>' + e(r.format) + '</p>' + chips(r.subjects) +
        '</div></div>';
    }).join('') : '<div class="empty">No targets selected yet. Choose one or more schools or tests before building a route-aware plan.</div>';
    const subjects = ss.map(function(s){
      return '<div class="card action-card"><div><h3>' + e(s) +
        '</h3><p>Relevant to your current selection or available as general sample practice.</p></div>' +
        btn('Try examples', 'start:' + s, 'secondary small') + '</div>';
    }).join('');
    return intro('My study plan','Your chosen routes become one deduplicated subject overview. A truly personalised plan must wait for qualified diagnostic evidence.','Route-aware UI preview') +
      '<div class="journey-grid">' +
      [['01','Choose destinations',rs.length ? rs.length + ' example examination pathways selected.' : 'Pick one or more target schools or tests.'],
       ['02','Establish a starting point','Learner status: Not Yet Established. No diagnostic results exist.'],
       ['03','Build skill and confidence','Use learning capsules and sample practice as exploratory activities.'],
       ['04','Independently verify mastery','Qualified assessment and evidence are not connected in this static preview.']
      ].map(function(step){
        return '<div class="journey-card"><span class="step-number">STEP ' + step[0] +
          '</span><h3>' + e(step[1]) + '</h3><p>' + e(step[2]) + '</p></div>';
      }).join('') + '</div>' +
      heading('Your selected examination routes','Demonstration relationships—not a school eligibility decision.',btn('Manage school choices','view:schools','secondary small')) +
      '<div class="card">' + selectedHtml + '</div>' +
      heading('Combined subjects','One subject area is shown once even if several chosen routes share it.') +
      '<div class="grid2">' + (subjects || '<div class="empty">No school-specific subject mapping has been confirmed for this selection yet. Check the school/test register before preparing an admissions-specific plan.</div>') + '</div>' + evidenceNote();
  }
  function recoveryPage() {
    return intro('Weak-area recovery','A future recovery journey will connect verified mistakes to short explanations and fresh independent evidence. There are no diagnosed weak areas in this preview.','Workflow preview') +
      '<div class="journey-grid">' +
      [['01','Identify a genuine gap','Qualifying response and marking evidence required.'],
       ['02','Understand the method','Open a learning capsule or guided explanation.'],
       ['03','Practise again','Use new, meaningful questions instead of cosmetic repeats.'],
       ['04','Confirm recovery','Independent assessment updates mastery only after qualification.']
      ].map(function(s){return '<div class="journey-card"><span class="step-number">' + s[0] +
        '</span><h3>' + e(s[1]) + '</h3><p>' + e(s[2]) + '</p></div>';}).join('') +
      '</div><div class="panel-block">' +
      actionCard('Start with a short practice preview','You can explore sample items without receiving a score or a weak-area diagnosis.','Explore practice','view:practice') +
      '</div>' + evidenceNote();
  }
  function insightsPage() {
    return intro('Learning insights','See the metrics families and learners will eventually use, without fabricated baselines, marks or admissions estimates.','Unassessed state') +
      '<div class="stats"><div class="stat"><strong style="font-size:17px">Not Yet Established</strong><small>Mastery status</small></div>' +
      '<div class="stat"><strong>—</strong><small>Eligible independent assessments</small></div>' +
      '<div class="stat"><strong>—</strong><small>Verified mock results</small></div></div>' +
      heading('What happens next','Mastery requires original, appropriately evidenced work. Demo responses are excluded.') +
      '<div class="grid2">' +
      actionCard('Choose the route and subjects','School selections determine which study areas to explore.','Manage targets','view:schools') +
      actionCard('Explore an unmarked question','Practice answers are shown only during the session and do not qualify as achievement.','Try practice','view:practice') +
      '</div>' + evidenceNote();
  }
  function sparkPage() {
    return intro('Daily Spark','A small starting point for today: pick an area and explore a short unmarked practice set. No artificial streak, reward or score is created.','Activity preview') +
      '<div class="hero"><div><span class="eyebrow">A LITTLE LEARNING, OFTEN</span><h1>One small step today.</h1>' +
      '<p>Choose a subject. In the connected platform, Daily Spark can become a short age-appropriate routine, separate from independently verified mastery.</p>' +
      btn('Choose a subject','view:practice','secondary') +
      '</div><div class="hero-visual"><div class="orbit"><div>✷</div></div></div></div>' +
      heading('Explore a sample','No day count, points or progress are stored.') + subjectTiles();
  }
  function capsulesPage() {
    return intro('Learning capsules','The right explanation at the right moment. This preview shows subject entry points, not approved curriculum lessons.','Content awaiting approval') +
      '<div class="feature-catalogue">' + activeSubjects().map(function(s){
        return '<div class="card"><span class="eyebrow">LEARNING CAPSULE</span><h3>' +
          e(s) + '</h3><p>Short topic explanations and worked examples will be visible here after academic approval and accessible-content review.</p>' +
          status('Not yet connected',true) + btn('Try sample practice','start:' + s,'secondary small') +
          '</div>';
      }).join('') + '</div>' + evidenceNote();
  }
  function safeSourceLink(r) {
    const u = typeof r.source_url === 'string' && /^https:\/\/[a-z0-9.-]+\//i.test(r.source_url) ? r.source_url : '';
    return u ? '<a href="' + e(u) + '" target="_blank" rel="noopener noreferrer">Visit published source</a>' : 'Source link unavailable';
  }
  function knowledgePage() {
    return intro('Knowledge Hub','Find route reference links and discover how ScoreMax explains the learning journey. Always check current-cycle official information with each admissions authority.','Reference links only') +
      heading('Examination route references','Links come from the existing demonstration source register; they have not been re-verified for every intake.') +
      '<div class="grid2">' + ROUTES.map(function(r){
        return '<div class="card"><strong>' + e(r.name) + '</strong><p class="text-sm muted">' +
          e(r.format) + '</p><p class="route-source">Reference cycle: ' + e(r.evidence_cycle) +
          ' · Subsequent intake eligibility and requirements: unverified</p>' +
          safeSourceLink(r) + '</div>';
      }).join('') + '</div>' +
      heading('How learning levels work','Achievement requires qualified independent evidence, not repeated cosmetic practice.') +
      actionCard('Understand the six levels','Read what Foundation through Elite means and return to school routing.','Review levels','view:home');
  }
  function challengesPage() {
    return intro('Challenges','Explore harder-looking sample tasks when you feel ready. This static preview records no rankings, streaks, prizes or mastery evidence.','Unmarked examples') +
      '<div class="card"><strong>Choose your challenge area</strong><p class="text-sm muted">These buttons reuse the same demonstration question player; they do not represent a newly approved challenge bank.</p></div>' +
      '<div class="panel-block">' + subjectTiles() + '</div>' + evidenceNote();
  }
  function writingPage() {
    return intro('Written practice','Use this space to try explaining your reasoning in words. It is a temporary note in this browser session, not a submitted answer.','Unmarked writing space') +
      '<div class="card"><label class="form-label" for="writingDraft">Your explanation or working</label>' +
      '<p class="text-sm muted">For example, describe the steps you tried in a sample question. Avoid entering personal information.</p>' +
      '<textarea id="writingDraft" class="writing-field" rows="7" maxlength="4000" placeholder="Type your working or explanation here...">' +
      e(state.writingDraft) + '</textarea><div class="qbottom"><span class="hint">Not saved to a server, scored, reviewed or used for mastery.</span>' +
      btn('Clear my text','draft-clear','secondary small') + '</div></div>' +
      '<div class="panel-block">' + actionCard('Explore sample questions','Written and multi-part assessment needs independently verified rubrics and native marking before activation.','Go to practice','view:practice') +
      '</div>' + evidenceNote();
  }
  function teacherPage() {
    const parts = [
      ['Class overview','Future role-based classroom lists and access controls; no real classes or student profiles are connected.'],
      ['Assignments & group plans','Planned use of canonical questions and school routes, without duplicating academic content.'],
      ['Safeguarding & access','Child data minimisation, role separation and accessibility need runtime verification before launch.']
    ];
    return intro('Teacher & classroom','Keep the wider ScoreMax classroom workflow, adapted to UK 11+. This is a concept interface, not a functioning class account.','Concept only') +
      '<div class="feature-catalogue">' + parts.map(function(p){return '<div class="card"><h3>' +
        e(p[0]) + '</h3><p>' + e(p[1]) + '</p>' + status('Integration pending',true) +
        '</div>';}).join('') + '</div><div class="panel-block">' +
      actionCard('Family-facing preview','Review how parent information avoids invented outcomes and test eligibility.','Open parent space','view:parents') +
      '</div>' + evidenceNote();
  }
  function onboardingPage() {
    const steps = [
      ['targets','Choose school or test routes','view:schools'],
      ['subjects','Explore relevant subjects','view:practice'],
      ['family','Review family overview','view:parents'],
      ['mastery','Understand what evidence can establish a level','view:insights']
    ];
    return intro('Getting started','Explore the key parts of ScoreMax UK 11+. These are optional preview checkboxes, not account setup or student achievement.','Session-only guide') +
      '<div class="card">' + steps.map(function(s){
        const on = state.onboard.has(s[0]);
        return '<div class="checkpoint"><button type="button" class="mini' + (on?' selected':'') +
          '" data-act="onboard:' + s[0] + '" aria-pressed="' + on +
          '">' + (on?'✓ Viewed':'Mark viewed') + '</button><div class="info"><strong>' +
          e(s[1]) + '</strong><p class="text-sm muted">Optional demo navigation step.</p></div>' +
          btn('Open','view:' + s[2].slice('view:'.length),'secondary small') +
          '</div>';
      }).join('') + '</div><p class="hint">Checklist state exists only in this open page; it is not saved or linked to a child account.</p>';
  }

  render = function() {
    if (Object.prototype.hasOwnProperty.call(extendedPages,state.view)) {
      nav();
      document.getElementById('page').innerHTML = extendedPages[state.view]();
      if (state.view === 'writing') {
        document.getElementById('writingDraft')?.addEventListener('input',function(ev){
          state.writingDraft = ev.target.value;
        });
      }
    } else {
      original.render();
    }
    syncChrome();
  };
  installChrome();
  document.addEventListener('click',function(ev) {
    const b = ev.target.closest('button[data-act]');
    if (!b) return;
    const act = b.getAttribute('data-act');
    if (act.startsWith('onboard:')) {
      const name = act.slice('onboard:'.length);
      if (state.onboard.has(name)) state.onboard.delete(name);
      else state.onboard.add(name);
      render();
      document.querySelector('button[data-act="' + act + '"]')?.focus();
      return;
    }
    if (act === 'draft-clear') {
      state.writingDraft = '';
      render();
      document.getElementById('writingDraft')?.focus();
      return;
    }
    if (act.startsWith('view:') || act.startsWith('route:') ||
        act.startsWith('mock:') || act.startsWith('start:')) {
      document.getElementById('page')?.focus({preventScroll:true});
    } else if (act.startsWith('level:') || act.startsWith('answer:') ||
               act.startsWith('feature:') || act.startsWith('toggle:')) {
      const same = Array.from(document.querySelectorAll('button[data-act]')).find(function(node){
        return node.getAttribute('data-act') === act;
      });
      same?.focus({preventScroll:true});
    }
  });
  render();
})();