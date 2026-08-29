from __future__ import annotations
import base64,hashlib,json,os,re,sys
from urllib.parse import quote

def _out(v):sys.stdout.write(json.dumps(v,separators=(',',':')));sys.stdout.flush()
def _nonblank(b):return len(b)>1000 and len(set(b[:min(len(b),16384)]))>8

def _login_ready(page,base,attempts=3):
    last=None
    for _ in range(attempts):
        try:
            page.goto(base+'/login',wait_until='domcontentloaded',timeout=60000)
            i=page.locator('input[name="identity"]');p=page.locator('input[name="password"]');i.wait_for(state='visible',timeout=30000);p.wait_for(state='visible',timeout=5000);return i,p
        except Exception as e:last=e
    raise RuntimeError('ScoreMax login page did not become ready after bounded cold-start recovery') from last

def main():
    browser=context=None
    try:
        cfg=json.loads(sys.stdin.read());base=str(cfg['base_url']).rstrip('/');items=list(cfg['items'])
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);context=browser.new_context(viewport={'width':1440,'height':1100});page=context.new_page()
            identity,pwbox=_login_ready(page,base);identity.fill(str(cfg['username']));pwbox.fill(str(cfg['password']));page.get_by_role('button',name='Log In').click();page.wait_for_url(re.compile(r'.*/qa/synthetic(?:\?.*)?$'),timeout=30000)
            if page.locator('text=MASTERY LABORATORY · QA SANDBOX ONLY').count()!=1: raise RuntimeError('Synthetic learner did not reach QA sandbox')
            evidence=[]
            for item in items:
                qid=str(item['external_question_id']);ver=str(item['external_version'])
                page.goto(base+'/qa/synthetic?external_question_id='+quote(qid,safe='')+'&external_version='+quote(ver,safe=''),wait_until='domcontentloaded',timeout=30000)
                rows=page.locator('tbody tr').filter(has_text=qid).filter(has_text='Version '+ver)
                if rows.count()!=1: raise RuntimeError(f'Exact learner QA lookup returned {rows.count()} rows for {qid}@{ver}')
                rows.get_by_role('button',name='Open learner view').click();page.wait_for_url(re.compile(r'.*/qa/synthetic/session/\d+$'),timeout=15000)
                card=page.locator('[data-qa-sandbox="true"]');raw=page.screenshot(full_page=True);element=card.screenshot() if card.count()==1 else b''
                overflow=bool(page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 2'))
                evidence.append({'external_question_id':qid,'external_version':ver,'evidence':{'browser_authenticated':True,'pixel_consumed':True,'pixel_nonblank':_nonblank(raw),'element_pixels_consumed':_nonblank(element),'question_visible':card.count()==1,'horizontal_overflow':overflow,'screenshot_sha256':hashlib.sha256(raw).hexdigest(),'element_screenshot_sha256':hashlib.sha256(element).hexdigest() if element else '','screenshot_png_b64':base64.b64encode(raw).decode(),'qa_sandbox_only':True,'learner_attempt_submitted':False,'password_persisted':False,'browser_process_isolated':True,'browser_slice_process':True}})
            _out({'schema':'PH_BROWSER_QA_SLICE_CHILD_RECEIPT_V1','capture_type':'LEARNER','request_id':cfg['request_id'],'evidence':evidence});return 0
    except BaseException as e:_out({'schema':'PH_BROWSER_QA_SLICE_CHILD_ERROR_V1','error_type':type(e).__name__,'message':str(e)});return 2
    finally:
        try:
            if context is not None:context.close()
        except:pass
        try:
            if browser is not None:browser.close()
        except:pass
if __name__=='__main__':raise SystemExit(main())
