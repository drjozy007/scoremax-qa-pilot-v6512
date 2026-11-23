/* ScoreMax UK 11+ candidate school directory, 23 Nov 2026.
   School presence is NOT proof of admission, consortium membership or current-cycle test.
   Mapping is conservative and deliberately preserves pending/alternate routes. */
(function(){
'use strict';
if(typeof SCHOOLS==='undefined'||typeof ROUTES==='undefined'||typeof state==='undefined') return;
const entryYear=2028;
const official={
 CSSE:'https://csse.org.uk/storage/2026/03/CSSE-Information-Guide-2027-Entry.pdf',
 BUCKS:'https://www.buckinghamshire.gov.uk/schools-libraries-and-parks/school-admissions-and-appeals/guides-and-policies/guide-to-grammar-schools-and-the-secondary-school-transfer-test-11-plus/',
 SLOUGH:'https://www.herschel.slough.sch.uk/year-7-admissions-2028/',
 SUTTON:'https://www.sutton.gov.uk/schools-and-learning/school-admissions/apply-start-secondary-school/secondary-school-tests-assessments-and-supplementary-forms',
 WMGS:'https://www.birmingham.gov.uk/info/20119/school_admissions/584/grammar_schools_in_birmingham/',
 KENT:'https://www.kent.gov.uk/education-and-children/schools/school-places/kent-test',
 SEAG:'https://seagni.co.uk/'
};
function canonical(s){return String(s||'').toLowerCase().normalize('NFKD').replace(/[’‘]/g,"'").replace(/\bst[.]?\b/g,'saint').replace(/[^a-z0-9]+/g,' ').trim()}
function slug(s){return canonical(s).replaceAll(' ','-')}
function addRoute(r){if(!ROUTES.some(x=>x.route_id===r.route_id)) ROUTES.push(r)}
addRoute({route_id:'SLOUGH28',name:'Slough Consortium 11+ (2028 entry)',group:'Four Slough grammar schools',subjects:['English','Maths','Verbal Reasoning','Non-Verbal Reasoning'],format:'Two mixed-subject papers (provider Quest Assessments)',evidence_cycle:2028,source_url:official.SLOUGH,evidence_status:'OFFICIAL_2028',entry_2028:'OFFICIAL_REFERENCE',notes:'Consortium test does not guarantee admission; check each school’s individual policy',provider:'Quest Assessments'});
addRoute({route_id:'SUTTON27',name:'Sutton Selective Eligibility Test (2027 reference)',group:'Sutton six-school shared SET',subjects:['English','Maths'],format:'First-stage selective eligibility; additional school-specific stages may be necessary',evidence_cycle:2027,source_url:official.SUTTON,evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:'Qualifying at stage one is not a school offer; stage-two tests differ',provider:'School consortium'});
addRoute({route_id:'WMGS27',name:'West Midlands Grammar Schools entrance test (2026 reference)',group:'Birmingham and participating West Midlands schools',subjects:['English','Maths','Verbal Reasoning','Non-Verbal Reasoning'],format:'Consortium entrance examination; exact cycle and subject mix require confirmation',evidence_cycle:2027,source_url:official.WMGS,evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:'2028 school policies, provider and exact paper structure pending',provider:'Check cycle'});
addRoute({route_id:'GLOS28',name:'Gloucestershire Grammar Schools 11+ (2028 entry)',group:'Seven Gloucestershire grammar schools',subjects:['English','Maths'],format:'FSCE Adventure, Beacon and cross-curricular Compass papers; present ScoreMax subjects do not cover the entire Compass paper',evidence_cycle:2028,source_url:'https://www.gloucestershire.gov.uk/schooladmissions/grammar-schools/',evidence_status:'OFFICIAL_2028',entry_2028:'OFFICIAL_REFERENCE',notes:'FSCE cross-curricular Compass tests wider subjects than the four current ScoreMax areas. Must not claim complete exam preparation.',provider:'Future Stories Community Enterprise (FSCE)'});
addRoute({route_id:'BEXLEY27',name:'Bexley Selection Test (2027 entry reference)',group:'Four Bexley grammar schools',subjects:['English','Maths','Verbal Reasoning','Non-Verbal Reasoning'],format:'Two timed multiple-choice booklets testing verbal ability, numerical and non-verbal reasoning',evidence_cycle:2027,source_url:'https://www.bexley.gov.uk/services/schools-and-education/selection-tests/about-test',evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:'Distinct from Kent and Medway Tests; passing alone does not guarantee an offer',provider:'Quest Assessments'});
addRoute({route_id:'MEDWAY27',name:'Medway Test (2027 entry reference)',group:'Six Medway grammar schools',subjects:['English','Maths'],format:'Three papers: English, Mathematics and Reasoning; precise reasoning subskills require verification',evidence_cycle:2027,source_url:'https://www.medway.gov.uk/medwaytest',evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:'Reasoning paper not fully mapped to approved ScoreMax subject subskills; Chatham Grammar also accepts Kent Test as an alternative',provider:'GL Assessment'});
addRoute({route_id:'WIRRAL27',name:'Wirral non-Catholic grammar school assessment (2027 entry reference)',group:'Four Wirral non-Catholic grammar schools',subjects:['Maths','Verbal Reasoning','Non-Verbal Reasoning'],format:'Two Quest papers: verbal reasoning, mathematics and non-verbal reasoning',evidence_cycle:2027,source_url:'https://www.wirral.gov.uk/schools-and-learning/school-admissions/step-by-step/apply-secondary-school-place/assessment-grammar',evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:"St Anselm's College and Upton Hall use separate school assessments",provider:'Quest Assessments'});
addRoute({route_id:'REDBRIDGE27',name:'Redbridge 11+ (2027 entry reference)',group:'Ilford and Woodford County High Schools',subjects:['English','Maths','Verbal Reasoning','Non-Verbal Reasoning'],format:'English and verbal reasoning; mathematics and non-verbal reasoning',evidence_cycle:2027,source_url:'https://www.redbridge.gov.uk/11plus',evidence_status:'OFFICIAL_2027_REFERENCE_ONLY',entry_2028:'NOT_VERIFIED',notes:'Catchment and school admissions criteria must be confirmed',provider:'GL Assessment'});
const buckinghamshireRoute=route('BUCKS');if(buckinghamshireRoute) buckinghamshireRoute.provider='GL Assessment';
const csseRoute=route('CSSE');if(csseRoute) csseRoute.provider='CSSE consortium';
const csse=new Set(['colchester county high school for girls','colchester royal grammar school','king edward vi grammar school','shoeburyness high school','southend high school for boys','southend high school for girls','st bernard s high school','st thomas more high school for boys','westcliff high school for boys','westcliff high school for girls'].map(canonical));
const sutton=new Set(['greenshaw high school','nonsuch high school for girls','sutton grammar school','wallington county grammar school','wallington high school for girls',"wilson's school"].map(canonical));
const wMgs=new Set(['bishop vesey s grammar school','king edward vi handsworth grammar school for boys','king edward vi aston school','king edward vi camp hill school for boys','king edward vi camp hill school for girls','king edward vi five ways school','king edward vi handsworth school for girls','sutton coldfield grammar school for girls','alcester grammar school','ashlawn school','haberdashers adams','king edward vi school','lawrence sheriff school','newport girls high school','queen mary s grammar school','queen mary s high school','rugby high school','stratford girls grammar school','wolverhampton girls high school'].map(canonical));
const excludedKent=new Set(['dover grammar school for boys','dover grammar school for girls','the harvey grammar school','the folkestone school for girls','cranbrook school'].map(canonical));
const additions=[
 {school_name:'Greenshaw High School',town:'Sutton',area:'Sutton',nation:'England',school_type:'partially_selective'},
 {school_name:'Ashlawn School',town:'Rugby',area:'Warwickshire',nation:'England',school_type:'partially_selective'}
];
const candidates=[...(window.UK11_ENGLAND_SCHOOLS||[]),...(window.UK11_NI_SCHOOLS||[]),...additions];
let inserted=0,merged=0;
for(const c of candidates){
 const same=SCHOOLS.find(x=>x.school_id&&!String(x.school_id).endsWith('-route')&&canonical(x.school_name)===canonical(c.school_name)&&((x.area&&x.area===c.area&&(!x.town||x.town===c.town))||(!x.area&&x.route_id==='CSSE'&&(c.area==='Essex'||c.area==='Southend-on-Sea'))));
 if(same){same.area=c.area;same.town=c.town;same.nation=c.nation;same.school_type=c.school_type;same.identity_source=c.identity_source||'Directory candidate; confirm official school identity';merged++;continue}
 const id='catalogue-'+slug(c.nation+'-'+c.area+'-'+c.town+'-'+c.school_name);
 SCHOOLS.push({...c,school_id:id,route_id:null,route_ids:[],identity_status:c.identity_status||'DIRECTORY_CANDIDATE_CONFIRM_OFFICIAL',routing_status:'SCHOOL_ROUTE_UNVERIFIED',admissions_cycle:entryYear});
 inserted++;
}
function setRoute(s,r,confidence,evidence,cycle,notes) {
 if(!s||!r)return;
 if(!Array.isArray(s.route_ids))s.route_ids=[];
 if(!s.route_ids.includes(r))s.route_ids.push(r);
 s.route_id=s.route_ids[0];
 s.routing_status=confidence;
 s.membership_evidence=evidence||null;
 s.evidence_cycle=cycle||null;
 s.routing_notes=notes||'Test applicability does not establish admission eligibility.';
}
for(const s of SCHOOLS){
 if(String(s.school_id).endsWith('-route'))continue;
 const name=canonical(s.school_name),area=s.area||'';
 if(csse.has(name)&&(area==='Essex'||area==='Southend-on-Sea'||!area)){
   setRoute(s,'CSSE','PRIOR_CYCLE_OFFICIAL',official.CSSE,2027,'CSSE 2027 entry documented; 2028 participation and policy need rechecking.');
 }else if(area==='Buckinghamshire'){
   setRoute(s,'BUCKS','PRIOR_CYCLE_OFFICIAL',official.BUCKS,2027,'13-school Bucks transfer route; 2028 school policy not verified.');
 }else if(area==='Slough'){
   setRoute(s,'SLOUGH28','CURRENT_CYCLE_OFFICIAL',official.SLOUGH,2028,'2028 Slough consortium and Quest contract confirmed; individual entry criteria still apply.');
 }else if(sutton.has(name)){
   setRoute(s,'SUTTON27','PRIOR_CYCLE_OFFICIAL',official.SUTTON,2027,'First-stage SET only; separate second-stage examinations may apply for grammar schools.');
 }else if(wMgs.has(name)){
   setRoute(s,'WMGS27','PRIOR_CYCLE_OFFICIAL',official.WMGS,2027,'Historical shared-test membership; current 2028 requirements need confirmation.');
 }else if(area==='Gloucestershire'){
   setRoute(s,'GLOS28','CURRENT_CYCLE_OFFICIAL','https://www.gloucestershire.gov.uk/schooladmissions/grammar-schools/',2028,'Gloucestershire seven-school FSCE 2028 test confirmed. Cross-curricular Compass paper is not fully covered by the present ScoreMax subjects.');
 }else if(area==='Bexley'){
   setRoute(s,'BEXLEY27','PRIOR_CYCLE_OFFICIAL','https://www.bexley.gov.uk/services/schools-and-education/selection-tests/about-test',2027,'Bexley four-school shared test; 2028 format and rules pending review.');
 }else if(area==='Medway'){
   setRoute(s,'MEDWAY27','PRIOR_CYCLE_OFFICIAL','https://www.medway.gov.uk/medwaytest',2027,'Medway Test; exact reasoning subskills and 2028 arrangements remain to be verified.');
   if(name===canonical('Chatham Grammar')){s.alternate_route_ids=['KENT'];s.route_requirement='OR';s.routing_notes='Chatham Grammar accepts Medway Test OR Kent Test in the published reference. Confirm 2028 arrangements; this is not a requirement to sit both.';}
 }else if(area==='Wirral'&& ![canonical("St Anselm's College"),canonical('Upton Hall School FCJ')].includes(name)){
   setRoute(s,'WIRRAL27','PRIOR_CYCLE_OFFICIAL','https://www.wirral.gov.uk/schools-and-learning/school-admissions/secondary-education-information-parents',2027,'Wirral council-run non-Catholic assessment; 2028 confirmation pending.');
 }else if(area==='Wirral'){
   s.routing_status='MULTI_OR_ALTERNATIVE_TEST_REVIEW';s.routing_notes='This Catholic grammar school runs its own assessment, not the council-administered four-school Wirral test. 2028 details not confirmed.';
 }else if(area==='Redbridge'){
   setRoute(s,'REDBRIDGE27','PRIOR_CYCLE_OFFICIAL','https://www.redbridge.gov.uk/11plus',2027,'Redbridge GL Assessment 2027-entry reference. Catchment restrictions and 2028 rules need verification.');
 }else if(area==='Kent'&&!excludedKent.has(name)){
   s.suggested_route_id='KENT';s.routing_status='REGIONAL_CANDIDATE';s.membership_evidence=official.KENT;s.evidence_cycle=2027;s.routing_notes='Kent Test is a regional suggestion only; no exam is auto-assigned until the school’s 2028 route is confirmed.';
 }else if(area==='Kent'&&excludedKent.has(name)){
   s.routing_status='MULTI_OR_ALTERNATIVE_TEST_REVIEW';
   s.routing_notes='Potential Kent Test plus alternative/school-specific assessment. Do not auto-assign until individual 2028 policy reviewed.';
 }else if(area==='Northern Ireland'){
   s.routing_status='SEAG_MEMBERSHIP_UNVERIFIED';
   s.routing_notes='SEAG is a shared NI assessment route, but this school’s membership and 2028 admission requirements are not yet evidenced.';
 }
 if(!s.routing_status)s.routing_status='SCHOOL_ROUTE_UNVERIFIED';
 if(!s.admissions_cycle)s.admissions_cycle=entryYear;
}
for(const s of SCHOOLS){if(s.route_id==='CSSE'&&!s.nation&&!String(s.school_id).endsWith('-route')){s.nation='England';s.area='Southend-on-Sea';s.town='Southend-on-Sea';s.identity_source=official.CSSE;s.identity_status='CSSE_2027_MEMBER';}}
const evidenceLabel=s=>{
 const x=s.routing_status||'SCHOOL_ROUTE_UNVERIFIED';
 if(x==='CURRENT_CYCLE_OFFICIAL')return '2028 route evidenced';
 if(x==='PRIOR_CYCLE_OFFICIAL')return 'Prior entry-cycle reference';
 if(x==='REGIONAL_CANDIDATE')return 'Regional route — verify school';
 if(x==='MULTI_OR_ALTERNATIVE_TEST_REVIEW')return 'Alternative tests possible';
 if(x==='SEAG_MEMBERSHIP_UNVERIFIED')return 'SEAG school membership pending';
 return 'School/test mapping pending';
};
const e=escapeHtml;
const originalRender=render;
const pageCount=36;
state.schoolArea='all';
state.schoolNation='all';
state.schoolPage=1;
const areas=()=>[...new Set(SCHOOLS.filter(s=>!String(s.school_id).endsWith('-route')).map(s=>s.area).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
schools=function(){
 const list=SCHOOLS.filter(s=>{
   if(String(s.school_id).endsWith('-route'))return false;
   if(state.schoolNation!=='all'&&s.nation!==state.schoolNation)return false;
   if(state.schoolArea!=='all'&&s.area!==state.schoolArea)return false;
   const term=state.search.toLowerCase().trim();
   const routeText=route(s.route_id)?.name||'';
   return !term||[s.school_name,s.area,s.town,routeText].some(v=>String(v||'').toLowerCase().includes(term));
 });
 const maxPage=Math.max(1,Math.ceil(list.length/pageCount));
 state.schoolPage=Math.max(1,Math.min(state.schoolPage,maxPage));
 const shown=list.slice((state.schoolPage-1)*pageCount,state.schoolPage*pageCount);
 const selected=chosenSchools().filter(s=>!String(s.school_id).endsWith('-route'));
 const routes=chosenRoutes();
 const pending=selected.filter(s=>!s.route_id||!['CURRENT_CYCLE_OFFICIAL','PRIOR_CYCLE_OFFICIAL'].includes(s.routing_status));
 const nationOptions=['all','England','Northern Ireland'].map(n=>'<option value="'+e(n)+'"'+(state.schoolNation===n?' selected':'')+'>'+e(n==='all'?'All nations':n)+'</option>').join('');
 const areaOptions=['all',...areas()].map(a=>'<option value="'+e(a)+'"'+(state.schoolArea===a?' selected':'')+'>'+e(a==='all'?'All areas':a)+'</option>').join('');
 return '<h1 class="title">Choose your target schools</h1>'+
 '<p class="text-sm muted">Select one school or several. Their identified assessment routes are automatically combined—one shared test and one subject group are shown only once. Route references do not prove eligibility or 2028 membership.</p>'+
 '<div class="toolbar"><label class="sr-only" for="schoolSearch">Search by school, town, county or test</label><input id="schoolSearch" class="search" type="search" value="'+e(state.search)+'" placeholder="Search school, town, county or exam" autocomplete="off">'+
 '<label for="catalogueNation" class="sr-only">Nation</label><select id="catalogueNation" class="search" style="max-width:170px" aria-label="Filter by nation">'+nationOptions+'</select>'+
 '<label for="catalogueArea" class="sr-only">Area</label><select id="catalogueArea" class="search" style="max-width:220px" aria-label="Filter by local authority">'+areaOptions+'</select>'+
 '<span class="kicker">'+list.length+' matches · '+selected.length+' selected</span></div>'+
 '<div class="grid2"><div class="card"><h3>School catalogue <span class="hint">· candidate directory</span></h3>'+
 '<p class="hint">Some school identities, names and test mappings still require official confirmation. Use the source link where available.</p>'+
 (shown.length?shown.map(s=>{
   const active=state.selected.has(s.school_id),r=route(s.route_id)||route(s.suggested_route_id),link=s.membership_evidence;
   const b=active?'✓ Selected':'+ Select';
   return '<div class="route-row"><div class="info"><strong>'+e(s.school_name)+'</strong><p>'+e([s.town,s.area,s.nation].filter(Boolean).join(' · '))+'</p>'+
   '<div class="chips"><span class="chip'+(s.routing_status==='CURRENT_CYCLE_OFFICIAL'?'':' warn')+'">'+e(evidenceLabel(s))+'</span>'+
   (r?'<span class="chip">'+e(r.name)+'</span>':'')+'</div>'+
   (s.routing_notes?'<p class="hint">'+e(s.routing_notes)+'</p>':'')+(s.alternate_route_ids?.length?'<p class="hint">Alternative assessment route (not an extra required exam): '+e(s.alternate_route_ids.map(id=>route(id)?.name||id).join(' OR '))+'</p>':'')+
   (s.school_website_verified&&s.school_website?'<p class="hint"><a href="'+e(s.school_website)+'" target="_blank" rel="noopener noreferrer">Official school website</a></p>':'')+
    (link?'<p class="hint"><a href="'+e(link)+'" target="_blank" rel="noopener noreferrer">Official route reference</a></p>':'')+
   '</div><button type="button" class="mini'+(active?' selected':'')+'" data-act="toggle:'+e(s.school_id)+'" aria-pressed="'+active+'">'+b+'</button></div>';
 }).join(''):'<div class="empty">No schools match these filters. Try a different area or search.</div>')+
 '<div class="toolbar"><button type="button" class="mini" data-act="school-prev"'+(state.schoolPage<=1?' disabled':'')+'>Previous</button>'+
 '<span class="kicker">Page '+state.schoolPage+' of '+maxPage+'</span>'+
 '<button type="button" class="mini" data-act="school-next"'+(state.schoolPage>=maxPage?' disabled':'')+'>Next</button></div></div>'+
 '<div><div class="card"><h3>My selected schools</h3>'+
 (selected.length?selected.map(s=>'<div class="route-row"><div class="info"><strong>'+e(s.school_name)+'</strong><p class="hint">'+e(evidenceLabel(s))+'</p></div>'+
 '<button type="button" class="mini" data-act="toggle:'+e(s.school_id)+'" aria-label="Remove '+e(s.school_name)+'">Remove</button></div>').join(''):'<div class="empty">Start by adding one or more schools.</div>')+
 '<div class="actions" style="margin-top:17px">'+btn('View my combined plan','view:plan')+'</div></div>'+
 '<div class="card" style="margin-top:13px"><h3>Automatically matched tests</h3>'+
 (routes.length?routes.map(r=>'<div class="route-row"><div class="info"><strong>'+e(r.name)+'</strong><p class="hint">Provider: '+e(r.provider||'Check admission authority')+'</p><p class="hint">Evidence reference: '+e(r.evidence_cycle||'unknown')+' · '+(r.evidence_cycle===entryYear?'2028 evidence cited':'2028 confirmation pending')+'</p>'+chips(r.subjects)+
 (r.source_url?'<p class="hint"><a href="'+e(r.source_url)+'" target="_blank" rel="noopener noreferrer">Check admissions authority</a></p>':'')+
 '</div></div>').join(''):'<div class="empty">No evidenced or regional candidate test matches are available for your chosen schools yet.</div>')+
 '<h3>Relevant subject coverage</h3>'+ (activeSubjects().length?chips(activeSubjects()):'<p class="hint">Subjects require verified school/test requirements.</p>')+
 (pending.length?'<p class="note">'+pending.length+' selected school(s) require additional admissions verification. Do not rely on this preview for registration or eligibility.</p>':'')+
 '<p class="hint">Multiple schools sharing the same test create only one study route here. Application eligibility remains school-specific.</p></div></div></div>';
};
document.addEventListener('input',function(ev){
 if(ev.target.id!=='schoolSearch')return;
 const v=ev.target.value;state.search=v;state.schoolPage=1;
});
document.addEventListener('change',function(ev){
 if(ev.target.id==='catalogueNation'){state.schoolNation=ev.target.value;state.schoolArea='all';state.schoolPage=1;render();}
 if(ev.target.id==='catalogueArea'){state.schoolArea=ev.target.value;state.schoolPage=1;render();}
});
document.addEventListener('click',function(ev){
 const b=ev.target.closest('button[data-act]');if(!b)return;
 const a=b.getAttribute('data-act');
 if(a==='school-prev'){state.schoolPage--;render();}
 if(a==='school-next'){state.schoolPage++;render();}
});
window.UK11_CATALOGUE_STATS={candidateSchools:SCHOOLS.filter(s=>!String(s.school_id).endsWith('-route')).length,newRecords:inserted,mergedRecords:merged,nations:2};
render();
})();