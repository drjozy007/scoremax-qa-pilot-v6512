"""Blank response-component browser test over isolated HTTP; synthetic input only."""
import json,os,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from jinja2 import Environment,FileSystemLoader,select_autoescape
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]/'ux_vnext_overlay'
saved=''
env=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html']))


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/static/structured_practice.js':
            data=(ROOT/'static/structured_practice.js').read_bytes();kind='application/javascript'
        else:
            component=env.get_template('_structured_practice.html').render(structured_saved=saved,url_for=lambda *a,**k:'/static/'+k['filename'])
            data=('<!doctype html><title>Isolated qualification</title><form method="post">'+component+
                  '<button type="submit">Save</button><button type="submit" name="action" value="clear">Clear answer</button></form>').encode();kind='text/html'
        self.send_response(200);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(data)
    def do_POST(self):
        global saved
        form=parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode(),keep_blank_values=True)
        saved='' if form.get('action')==['clear'] else form.get('answer',[''])[0]
        self.send_response(303);self.send_header('Location','/');self.end_headers()


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE') or None,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':844})
            base=f'http://127.0.0.1:{server.server_port}'
            page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base) else route.abort())
            page.goto(base);page.get_by_label('Subject',exact=True).wait_for()
            assert page.locator('input').evaluate_all('(xs)=>xs.every(x=>x.value==="")');checks.append('no_prefilled_answers')
            page.get_by_label('Subject',exact=True).fill('synthetic sample')
            page.get_by_label('Relation',exact=True).fill('occupies')
            page.get_by_label('Object',exact=True).fill('available space')
            page.get_by_role('button',name='Add equation',exact=True).click()
            page.get_by_label('Equation',exact=True).fill('X=YZ')
            page.get_by_role('button',name='Add value and unit',exact=True).click()
            page.get_by_label('Value',exact=True).fill('12');page.get_by_label('Unit',exact=True).fill('m')
            page.get_by_label('Working',exact=True).fill('6+6')
            page.get_by_role('button',name='Save',exact=True).click();page.wait_for_load_state('networkidle')
            payload=json.loads(saved)
            assert payload['assertions']==[{'subject':'synthetic sample','relation':'occupies','object':'available space'}]
            assert payload['equations']==['X=YZ'] and payload['values']==[{'value':'12','unit':'m','working':'6+6'}]
            checks.append('native_serialization_roundtrip')
            assert page.get_by_label('Subject',exact=True).input_value()=='synthetic sample'
            assert page.get_by_label('Equation',exact=True).input_value()=='X=YZ';checks.append('saved_work_restored')
            page.get_by_role('button',name='Add statement',exact=True).click()
            page.get_by_label('Subject',exact=True).nth(1).fill('unfinished')
            page.get_by_role('button',name='Save',exact=True).click()
            assert 'Complete all three fields' in page.get_by_role('status').inner_text();checks.append('malformed_row_guidance')
            page.get_by_role('button',name='Clear answer',exact=True).click();page.wait_for_load_state('networkidle')
            assert saved=='' and page.get_by_label('Subject',exact=True).input_value()=='';checks.append('clear_incomplete_response')
            assert page.locator('select').count()==0;checks.append('no_answer_choices')
            print(json.dumps({'passed':True,'checks':checks,'browser_version':browser.version,'external_requests_allowed':False}))
            browser.close()
    finally:server.shutdown()

if __name__=='__main__':main()
