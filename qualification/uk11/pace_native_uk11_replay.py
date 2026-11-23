"""Pace only disposable UK11 native replay assertions; never change rate limits."""
from pathlib import Path
p=Path('qualification/uk11/native_intake_explanation_qualification.py')
s=p.read_text()
a='        replay_submit=client.post('
b="        response=client.get(f'/uk11/result/{aid}/question/{qid}/explain',base_url=BASE_URL)"
assert s.count(a)==1 and s.count(b)==1,'NATIVE_REPLAY_PACING_ANCHOR_DRIFT'
s=s.replace(a,"        import time\n        time.sleep(1.3)  # respect live-style student rate limiter\n"+a)
s=s.replace(b,"        time.sleep(1.3)  # allow the rate window to recover\n"+b)
p.write_text(s)
