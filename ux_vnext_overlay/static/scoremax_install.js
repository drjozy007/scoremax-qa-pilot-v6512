(() => {
  'use strict';
  const INSTALLED_KEY='scoremax-app-installed-v1';
  let deferredPrompt=null;
  const nudge=document.getElementById('scoremaxInstallNudge');
  const button=document.getElementById('scoremaxInstallButton');
  const help=document.getElementById('scoremaxInstallHelp');
  const steps=document.getElementById('scoremaxInstallSteps');
  const done=document.getElementById('scoremaxInstallDone');
  const close=document.getElementById('scoremaxInstallClose');

  if(!nudge || !button) return;

  const standalone=()=>window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone===true;
  const installedFlag=()=>{try{return localStorage.getItem(INSTALLED_KEY)==='1'}catch(_){return false}};
  const hideAll=()=>{nudge.hidden=true;if(help)help.hidden=true};
  const markInstalled=()=>{try{localStorage.setItem(INSTALLED_KEY,'1')}catch(_){} hideAll()};

  if(standalone()){markInstalled();return;}
  if(installedFlag()){hideAll();return;}

  const ua=navigator.userAgent||'';
  const isIOS=/iPad|iPhone|iPod/.test(ua) || (navigator.platform==='MacIntel' && navigator.maxTouchPoints>1);
  const isMac=/Macintosh|Mac OS X/.test(ua) && !isIOS;
  const isSafari=/Safari/.test(ua) && !/Chrome|CriOS|Edg|EdgiOS|OPR|Firefox|FxiOS/.test(ua);
  const isChromium=/Chrome|Chromium|CriOS|Edg|EdgiOS/.test(ua);

  const showHelp=(kind)=>{
    if(!help||!steps)return;
    steps.innerHTML='';
    let items=[];
    if(kind==='ios'){
      items=['Tap the Share button in your browser.','Choose “Add to Home Screen”.','Tap “Add”.'];
    }else if(kind==='mac-safari'){
      items=['Use Safari’s Share button or File menu.','Choose “Add to Dock”.','Click “Add”.'];
    }else if(kind==='chromium-menu'){
      items=['Open the browser menu.','Choose “Install ScoreMax”, “Install app”, or “Add to Home screen”.','Confirm the install.'];
    }else{
      items=['Open ScoreMax in Chrome or Edge on Windows/Android, or Safari on Apple devices.','Use the browser’s Install / Add to Home Screen option.'];
    }
    items.forEach(t=>{const li=document.createElement('li');li.textContent=t;steps.appendChild(li)});
    help.hidden=false;
    help.querySelector('button')?.focus();
  };

  window.addEventListener('beforeinstallprompt',(event)=>{
    event.preventDefault();
    deferredPrompt=event;
    nudge.hidden=false;
  });

  window.addEventListener('appinstalled',()=>{
    deferredPrompt=null;
    markInstalled();
  });

  button.addEventListener('click',async()=>{
    if(standalone()){markInstalled();return;}
    if(deferredPrompt){
      const promptEvent=deferredPrompt;
      deferredPrompt=null;
      try{
        await promptEvent.prompt();
        const choice=await promptEvent.userChoice;
        if(choice && choice.outcome==='accepted') markInstalled();
      }catch(_){
        showHelp('chromium-menu');
      }
      return;
    }
    if(isIOS){showHelp('ios');return;}
    if(isMac && isSafari){showHelp('mac-safari');return;}
    if(isChromium){showHelp('chromium-menu');return;}
    showHelp('other');
  });

  done?.addEventListener('click',markInstalled);
  close?.addEventListener('click',()=>{if(help)help.hidden=true});
  help?.addEventListener('click',(e)=>{if(e.target===help)help.hidden=true});
  document.addEventListener('keydown',(e)=>{if(e.key==='Escape'&&help&&!help.hidden)help.hidden=true});

  nudge.hidden=false;
})();
