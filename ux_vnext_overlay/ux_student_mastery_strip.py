from __future__ import annotations

from flask import session


def _mastery_strip_patch() -> str:
    return r'''<style id="ux-student-mastery-strip-style">
/* Student mastery deliberately reuses the public landing progression-card contract. */
.ux-student-mastery-strip{max-width:1200px!important;margin:0 auto!important;padding:26px 28px 30px!important;background:transparent!important;border:0!important;box-shadow:none!important}
.ux-student-mastery-strip .ux-section-head{max-width:none!important;margin:0 0 18px!important;text-align:left!important;display:flex!important;align-items:flex-end!important;justify-content:space-between!important;gap:18px!important}
.ux-student-mastery-strip .ux-section-head>div{min-width:0}.ux-student-mastery-strip .ux-kicker{color:#2F7F7D!important;margin:0 0 7px!important}
.ux-student-mastery-strip .ux-section-head h2{font-size:clamp(1.35rem,2.6vw,2.05rem)!important;line-height:1.08!important;letter-spacing:-.035em!important;margin:0!important;color:#0f172a!important}
.ux-student-mastery-strip .ux-section-head h2 span{color:#2F7F7D!important}.ux-student-mastery-strip .ux-mastery-context{margin:6px 0 0!important;color:#64748b!important;font-size:.86rem!important;line-height:1.45!important}
.ux-student-mastery-status{display:inline-flex;align-items:center;gap:7px;min-height:32px;padding:7px 11px;border:1px solid #b9e1df;border-radius:999px;background:#E8F6F5;color:#236765;font-size:.7rem;font-weight:900;white-space:nowrap}
/* Restore the exact landing-box geometry even though the student shell has compact .ux-progress-top rules. */
.ux-student-mastery-strip .ux-levels{display:grid!important;grid-template-columns:repeat(6,1fr)!important;gap:10px!important}
.ux-student-mastery-strip .ux-level{position:relative!important;padding:18px 14px!important;border:1px solid #e2e8f0!important;border-radius:20px!important;background:#fff!important;min-height:116px!important;display:flex!important;gap:12px!important;align-items:flex-start!important;transition:.2s ease!important;color:inherit!important}
.ux-student-mastery-strip .ux-level:hover{transform:translateY(-4px)!important;box-shadow:0 18px 40px rgba(15,23,42,.08)!important}
.ux-student-mastery-strip .ux-level>span{font-size:.72rem!important;font-weight:900!important;color:#64748b!important}.ux-student-mastery-strip .ux-level strong{display:block!important;color:#0f172a!important;font-size:1rem!important}.ux-student-mastery-strip .ux-level small{display:block!important;color:#64748b!important;margin-top:7px!important;line-height:1.35!important;font-size:inherit!important}
.ux-student-mastery-strip .ux-level.level-1{border-top:4px solid #94a3b8!important}.ux-student-mastery-strip .ux-level.level-2{border-top:4px solid #38bdf8!important}.ux-student-mastery-strip .ux-level.level-3{border-top:4px solid #2563eb!important}.ux-student-mastery-strip .ux-level.level-4{border-top:4px solid #7c3aed!important}.ux-student-mastery-strip .ux-level.level-5{border-top:4px solid #db2777!important}.ux-student-mastery-strip .ux-level.level-6{border-top:4px solid #f59e0b!important;background:linear-gradient(180deg,#fffdf5,#fff)!important}
.ux-student-mastery-strip .ux-level.ux-mastery-reached{background:#f8fbfb!important}.ux-student-mastery-strip .ux-level.ux-mastery-reached strong{color:#315d5b!important}
.ux-student-mastery-strip .ux-level.ux-mastery-current{border-color:#3FA6A3!important;box-shadow:0 0 0 3px rgba(63,166,163,.14),0 15px 34px rgba(47,127,125,.13)!important;transform:translateY(-2px)!important}.ux-student-mastery-strip .ux-level.ux-mastery-current:after{content:'YOU';position:absolute;right:9px;top:9px;padding:3px 6px;border-radius:999px;background:#2F7F7D;color:#fff;font-size:.52rem;font-weight:950;letter-spacing:.08em}.ux-student-mastery-strip .ux-level.ux-mastery-current strong{color:#236765!important;padding-right:28px}
/* The retired legacy mastery hero must never coexist with the landing-style strip. */
body.ux-mastery-strip-active .mastery-hero-card{display:none!important}
@media(max-width:980px){.ux-student-mastery-strip .ux-levels{grid-template-columns:repeat(3,1fr)!important}}
@media(max-width:640px){.ux-student-mastery-strip{padding:20px 18px 24px!important}.ux-student-mastery-strip .ux-section-head{align-items:flex-start!important;flex-direction:column!important;gap:10px!important}.ux-student-mastery-strip .ux-levels{grid-template-columns:1fr 1fr!important;gap:10px!important}.ux-student-mastery-strip .ux-level{min-height:102px!important}}
</style>
<script id="ux-student-mastery-strip-script">(function(){
const levels=[
  ['Foundation','Build understanding'],['Exam Ready','Use it correctly'],['Advanced','Handle harder questions'],
  ['Distinction','Reduce mistakes'],['Expert','Perform under pressure'],['Elite','Prove consistency']
];
function normalise(text){const s=(text||'').replace(/YOU/gi,'').replace(/\s+/g,' ').trim().toLowerCase();for(const item of levels){if(s.includes(item[0].toLowerCase()))return item[0];}return '';}
function authoritativeStage(old){if(!old)return '';const current=old.querySelector('.mastery-step.current');let stage=normalise(current&&current.textContent);if(stage)return stage;const pill=old.querySelector('.mastery-status-pill');stage=normalise(pill&&pill.textContent);if(stage)return stage;const marked=old.querySelector('[aria-current="step"],[data-current="true"]');return normalise(marked&&marked.textContent);}
function makeLevel(item,i,currentIndex){const a=document.createElement('article');a.className='ux-level level-'+(i+1);if(currentIndex>=0&&i<currentIndex)a.classList.add('ux-mastery-reached');if(i===currentIndex){a.classList.add('ux-mastery-current');a.setAttribute('aria-current','step');}a.innerHTML='<span>'+String(i+1).padStart(2,'0')+'</span><div><strong>'+item[0]+'</strong><small>'+item[1]+'</small></div>';return a;}
function render(stage){let section=document.getElementById('uxStudentMasteryStrip');const idx=levels.findIndex(x=>x[0]===stage);if(!section){section=document.createElement('section');section.id='uxStudentMasteryStrip';section.className='ux-progress-section ux-student-mastery-strip';section.setAttribute('aria-labelledby','uxStudentMasteryTitle');const context=document.querySelector('.student-context-stack');if(context)context.insertAdjacentElement('afterend',section);else{const main=document.querySelector('main,.student-home-v2');if(main)main.insertBefore(section,main.firstChild);else document.body.prepend(section);}}
section.innerHTML='';const head=document.createElement('div');head.className='ux-section-head';const left=document.createElement('div');left.innerHTML='<p class="ux-kicker">YOUR MASTERY</p><h2 id="uxStudentMasteryTitle">'+(idx>=0?'Current stage: <span>'+levels[idx][0]+'</span>':'Mastery not yet established')+'</h2><p class="ux-mastery-context">'+(idx>=0?'Your current position is highlighted below. Keep building evidence to move forward.':'Complete a short diagnostic so ScoreMax can establish your starting stage.')+'</p>';const status=document.createElement('span');status.className='ux-student-mastery-status';status.textContent=idx>=0?levels[idx][0]+' · current':'Diagnostic needed';head.append(left,status);const grid=document.createElement('div');grid.className='ux-levels';grid.setAttribute('aria-label','Six ScoreMax mastery stages');levels.forEach((item,i)=>grid.appendChild(makeLevel(item,i,idx)));section.append(head,grid);document.body.classList.add('ux-mastery-strip-active');}
function cleanLegacy(old){if(!old)return;const parent=old.parentElement;old.remove();if(parent&&parent.classList.contains('home-priority-grid')){parent.classList.add('ux-single-priority');if(!parent.querySelector(':scope > *'))parent.remove();}}
function apply(){const old=document.querySelector('.mastery-hero-card');if(!old){return !!document.getElementById('uxStudentMasteryStrip');}const stage=authoritativeStage(old);render(stage);cleanLegacy(old);return true;}
function boot(){apply();[80,250,700,1400].forEach(ms=>setTimeout(apply,ms));const obs=new MutationObserver(function(){const old=document.querySelector('.mastery-hero-card');if(old){const stage=authoritativeStage(old);render(stage);cleanLegacy(old);}});obs.observe(document.body,{childList:true,subtree:true});setTimeout(()=>obs.disconnect(),5000);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();</script>'''


def install_student_mastery_strip(app) -> None:
    if getattr(app,'_ux_student_mastery_strip_installed',False):
        return

    @app.after_request
    def _ux_student_mastery_strip_response(response):
        if not response.is_sequence or 'text/html' not in (response.content_type or '').lower():
            return response
        if session.get('role')!='student' or not session.get('user_id'):
            return response
        html=response.get_data(as_text=True)
        # Only home/dashboard HTML containing the legacy authoritative mastery widget is transformed.
        if 'mastery-hero-card' not in html or 'ux-student-mastery-strip-style' in html:
            return response
        patch=_mastery_strip_patch()
        html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
        response.set_data(html); response.content_length=len(response.get_data())
        return response

    app._ux_student_mastery_strip_installed=True
