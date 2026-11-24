/* UK11 PREVIEW-ONLY preference continuity.
 * Session tab storage is not account persistence, authorisation or an authentication system.
 * Never persist answers, marks, child identity, postcode or mastery here. */
(function(){
'use strict';
if(typeof state==='undefined'||typeof SCHOOLS==='undefined'||typeof render!=='function')return;
const key='scoremax.uk11.preview.selectedSchools.v1';
const allowed=new Set(SCHOOLS.filter(s=>s.school_id&&!String(s.school_id).endsWith('-route')).map(s=>s.school_id));
function read(){
 try{
  const raw=sessionStorage.getItem(key);
  if(!raw)return [];
  const data=JSON.parse(raw);
  return Array.isArray(data)?data.filter(id=>typeof id==='string'&&allowed.has(id)).slice(0,30):[];
 }catch(_){return []}
}
function save(){
 try{sessionStorage.setItem(key,JSON.stringify([...state.selected].filter(id=>allowed.has(id)).slice(0,30)))}catch(_){}
}
const stored=read();
if(stored.length){
 // This preview has no real signed-in identity. Stored IDs are tab-local, never trusted entitlements.
 state.selected=new Set(stored);
 render();
}
document.addEventListener('click',ev=>{
 const button=ev.target.closest('button[data-act]');
 if(!button)return;
 const action=button.getAttribute('data-act')||'';
 if(action.startsWith('toggle:')){
  // The original handler is registered earlier and updates state synchronously.
  save();
 }
});
window.addEventListener('pagehide',save);
})();