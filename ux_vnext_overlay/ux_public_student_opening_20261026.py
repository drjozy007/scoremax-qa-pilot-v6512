"""Extend the accepted learner runtime's existing invitation boundary."""
from pathlib import Path
import hashlib
import shutil

BASE_APP = '6a0888979310d721cde59119b349ea446229074f8a8d576521866c9f8b661484'
def apply(root):
    root=Path(root)
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf8')
    if hashlib.sha256(app_path.read_bytes()).hexdigest()!=BASE_APP:
        raise RuntimeError('PUBLIC_OPENING_ACCEPTED_APP_BASE_MISMATCH')
    old="            temp_username='pending-'+secrets.token_urlsafe(10).lower()"
    new=("            registration_admission=app.extensions.get('scoremax_registration_admission')\n"
         "            if registration_admission is not None:\n"
         "                admission_response=registration_admission(c,role)\n"
         "                if admission_response is not None:\n"
         "                    c.rollback()\n"
         "                    return admission_response\n"+old)
    if text.count(old)!=1:raise RuntimeError('PUBLIC_OPENING_NATIVE_REGISTRATION_ANCHOR_MISMATCH')
    text=text.replace(old,new,1)
    compile(text,str(app_path),'exec')
    module=Path(__file__).parent/'public_opening_20261026'/'invite_only_pilot_runtime.py'
    compile(module.read_text(encoding='utf8'),str(module),'exec')
    app_path.write_text(text,encoding='utf8',newline='\n')
    shutil.copyfile(module,root/'invite_only_pilot_runtime.py')
    return {'native_registration_atomic_admission_hook':True,'existing_invitation_gate_extended':True,'marking_or_release_rules_changed':False}
