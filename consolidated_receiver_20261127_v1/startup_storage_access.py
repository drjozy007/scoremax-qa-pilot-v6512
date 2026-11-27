"""Temporary startup access during this coordinated cutover; no database writes."""
from pathlib import Path
import hashlib,http.server,json,os,shutil,sqlite3,threading
EXPECTED_SERVICE='srv-daj5fbm7bikc73aq2gdg'
def required_capacity(database):
 c=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
 try:
  c.execute('PRAGMA query_only=ON');size=int(c.execute('PRAGMA page_size').fetchone()[0])*int(c.execute('PRAGMA page_count').fetchone()[0])
 finally:c.close()
 return max(database.stat().st_size,size)*2+536870912+4194304
class Unavailable(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'ScoreMax startup held by native backup capacity guard.\n'
  self.send_response(503);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
def wait_for_native_capacity():
 if os.environ.get('RENDER_SERVICE_ID')!=EXPECTED_SERVICE:raise RuntimeError('EXACT_EXISTING_SERVICE_REQUIRED')
 database=Path('/data/scoremax/state/scoremax.db');required=required_capacity(database)
 # Keep operational shell access available; no learner content or DB writer starts.
 server=http.server.ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','10000'))),Unavailable)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 print('SCOREMAX_CUTOVER_STORAGE_ACCESS_ONLY '+json.dumps({'http':503,'free':shutil.disk_usage('/data').free,'required':required,'native_guard_bypassed':False,'application_started':False}),flush=True)
 for root in ('/data/scoremax/backup','/data/scoremax/intake','/data/scoremax/state'):
  p=Path(root)
  print('SCOREMAX_CUTOVER_INVENTORY '+json.dumps({'root':root,'files':[{'path':str(x),'bytes':x.stat().st_size}for x in p.iterdir()if x.is_file()and not x.is_symlink()]}),flush=True)
 while shutil.disk_usage('/data').free<required_capacity(database):threading.Event().wait(5)
 print('SCOREMAX_CUTOVER_CAPACITY_AVAILABLE_NATIVE_GUARD_REQUIRED',flush=True)
 return server,thread
