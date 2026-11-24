/* UK11 postcode discovery enhancement — preview-only.
   Sends only a validated outward postcode (e.g. ST4), never a full home postcode.
   Approximate distances use locality centroids rather than individual school locations.
   Not an admissions-eligibility or catchment-area tool. */
(function(){
'use strict';
if(typeof schools!=='function'||typeof SCHOOLS==='undefined'||typeof state==='undefined')return;
const verifiedSchools=[
 {name:'aylesbury grammar school',area:'Buckinghamshire',urn:'136884',site:'https://www.ags.bucks.sch.uk/'},
 {name:'aylesbury high school',area:'Buckinghamshire',urn:'136846',site:'https://www.ahs.bucks.sch.uk/'},
 {name:'sutton grammar school',area:'Sutton',urn:'136787',site:'https://www.suttongrammar.sutton.sch.uk/'},
 {name:"queen elizabeth's school",area:'Barnet',urn:'136290',site:'https://www.qebarnet.co.uk/'}
];
const normalizeName=v=>String(v||'').toLowerCase().replace(/[’‘]/g,"'").replace(/\s+/g,' ').trim();
for(const s of SCHOOLS){
 const m=verifiedSchools.find(x=>normalizeName(s.school_name)===x.name&&s.area===x.area);
 if(!m)continue;
 s.official_urn=m.urn;
 s.identity_status='GIAS_IDENTITY_VERIFIED';
 s.identity_source='https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/'+m.urn;
 s.school_website=m.site;
 s.school_website_verified=true;
 s.school_website_verified_on='2026-11-24';
 s.school_website_source=s.identity_source;
}
const previousSchools=schools;
const centres=window.UK11_LOCALITY_CENTRES||{};
const esc=typeof escapeHtml==='function'?escapeHtml:(x=>String(x));
const postcode=/^[A-Z]{1,2}[0-9][0-9A-Z]?$/i;
let requested='',result=null,error='';
function radians(n){return n*Math.PI/180}
function miles(a,b){
 const dlat=radians(b.lat-a.lat),dlon=radians(b.lon-a.lon);
 const h=Math.sin(dlat/2)**2+Math.cos(radians(a.lat))*Math.cos(radians(b.lat))*Math.sin(dlon/2)**2;
 return 3958.7613*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h));
}
function coords(s){
 const direct=centres[[s.nation,s.area,s.town].join('|')];
 const local=centres[[s.nation,s.area,s.area].join('|')];
 return direct||local||null;
}
function safeUrl(url){
 try{const u=new URL(url);return u.protocol==='https:'?u.href:null}catch(e){return null}
}
function link(s){
 // A route/admissions page is not represented as the school's own website.
 const url=s.school_website_verified===true?safeUrl(s.school_website):null;
 if(url)return '<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">School website (verified)</a>';
 const admission=safeUrl(s.membership_evidence);
 return admission?'<a target="_blank" rel="noopener noreferrer" href="'+esc(admission)+'">Official admissions information</a>':
   '<span class="hint">School website not yet verified</span>';
}
function nearby(){
 if(!result)return '';
 const items=SCHOOLS.filter(s=>!String(s.school_id).endsWith('-route'))
  .map(s=>({school:s,position:coords(s)})).filter(x=>x.position)
  .map(x=>({...x,distance:miles(result,x.position)}))
  .sort((a,b)=>a.distance-b.distance||a.school.school_name.localeCompare(b.school.school_name));
 const count=items.length;
 const shown=items.slice(0,24);
 return '<section class="card" aria-label="Approximate schools near postcode"><h3>Schools around '+esc(requested)+'</h3>'+
 '<p class="hint">Showing '+shown.length+' of '+count+' mapped locality candidates, ordered by approximate straight-line distance between the postcode district centre and the school town/locality centre. These are NOT school-to-home distances, travel times, catchments or admissions eligibility.</p>'+
 (shown.length?'<div class="uk11-nearby-list">'+shown.map(({school:s,distance,position})=>
 '<div class="route-row"><div class="info"><strong>'+esc(s.school_name)+'</strong>'+
 '<p class="hint">'+esc([s.town,s.area,s.nation].filter(Boolean).join(' · '))+' · ≈'+distance.toFixed(1)+' miles (locality estimate)</p>'+
 '<p class="hint">'+link(s)+'</p>'+
 '<p class="hint">'+(s.routing_status==='CURRENT_CYCLE_OFFICIAL'?'Route evidenced for the indicated cycle': 'Exam route / 2028 entry still requires official verification')+'</p>'+
 '</div><button type="button" class="mini'+(state.selected.has(s.school_id)?' selected':'')+'" data-act="toggle:'+esc(s.school_id)+'" aria-pressed="'+state.selected.has(s.school_id)+'">'+(state.selected.has(s.school_id)?'✓ Selected':'+ Select')+'</button></div>'
 ).join('')+'</div>':'<p>No locality coordinates available for the school catalogue.</p>')+'</section>';
}
schools=function(){
 const html=previousSchools();
 return '<section class="card uk11-postcode-search" aria-label="Find nearby 11+ schools"><h3>Find 11+ schools near a postcode district</h3>'+
 '<p class="hint">Enter only the first part of a UK postcode, for example ST4, B15 or HP20. Do not enter a full home postcode. Only the district is sent to a public postcode lookup service; no address is saved by this preview.</p>'+
 '<div class="toolbar"><label class="sr-only" for="uk11Outcode">Postcode district</label>'+
 '<input class="search" id="uk11Outcode" type="text" maxlength="4" spellcheck="false" autocapitalize="characters" autocomplete="off" placeholder="e.g. ST4" value="'+esc(requested)+'">'+
 '<button type="button" class="mini" data-act="uk11-nearby-search">Find nearby schools</button>'+
 (result?'<button type="button" class="mini" data-act="uk11-nearby-clear">Clear</button>':'')+'</div>'+
 (error?'<p class="note" role="status">'+esc(error)+'</p>':'')+
 '<p class="hint">Directory candidates include schools whose current 11+ route and eligibility are not yet verified. Search is discovery, not an admissions recommendation.</p></section>'+
 nearby()+html;
};
async function lookup(){
 const input=document.getElementById('uk11Outcode');
 const typed=(input?.value||'').trim().toUpperCase().replace(/\s+/g,'');
 requested=typed;
 if(!postcode.test(typed)){
   result=null;error='Use an outward postcode only, such as ST4. Full postcodes and addresses are not accepted.';render();return;
 }
 error='Checking district location…';result=null;render();
 try{
   const response=await fetch('https://api.postcodes.io/outcodes/'+encodeURIComponent(typed),{method:'GET',cache:'no-store',referrerPolicy:'no-referrer'});
   if(!response.ok)throw new Error('Postcode district not found');
   const data=await response.json();
   if(requested!==typed)return;
   const a=data?.result;
   if(!a||!Number.isFinite(a.latitude)||!Number.isFinite(a.longitude))throw new Error('No reliable district centre found');
   result={lat:a.latitude,lon:a.longitude};error='';
 }catch(e){if(requested!==typed)return;result=null;error='This district could not be located. Check the outward postcode or try again later.'}
 render();
}
document.addEventListener('click',ev=>{
 const button=ev.target.closest('button[data-act]');if(!button)return;
 const action=button.getAttribute('data-act');
 if(action==='uk11-nearby-search'){ev.preventDefault();lookup()}
 if(action==='uk11-nearby-clear'){requested='';result=null;error='';render()}
});
document.addEventListener('keydown',ev=>{
 if(ev.target?.id==='uk11Outcode'&&ev.key==='Enter'){ev.preventDefault();lookup()}
});
})();