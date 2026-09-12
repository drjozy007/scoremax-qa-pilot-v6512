from __future__ import annotations

import ast
import shutil
from pathlib import Path


def _extract_template(source_path: Path) -> str:
    tree=ast.parse(source_path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign):
            if any(isinstance(t,ast.Name) and t.id=='TEMPLATE' for t in node.targets):
                value=ast.literal_eval(node.value)
                if not isinstance(value,str):
                    raise SystemExit('UX_INTEREST_ADMIN_TEMPLATE_NOT_STRING')
                return value
    raise SystemExit('UX_INTEREST_ADMIN_TEMPLATE_MISSING')


def apply_interest_admin(root: Path) -> None:
    source=Path('ux_vnext_overlay')/'ux_interest_admin.py'
    if not source.is_file():
        raise SystemExit('UX_INTEREST_ADMIN_SOURCE_MISSING')
    runtime_module=root/'ux_interest_admin.py'
    shutil.copy2(source,runtime_module)
    template=root/'templates'/'admin_interest_demand.html'
    template.write_text(_extract_template(source),encoding='utf-8')

    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    marker='from ux_interest_admin import install_interest_admin\ninstall_interest_admin(app)'
    if marker not in text:
        anchor="\nif __name__=='__main__':\n"
        if anchor not in text:
            raise SystemExit('UX_INTEREST_ADMIN_APP_INSTALL_ANCHOR_MISSING')
        text=text.replace(anchor,'\n'+marker+'\n'+anchor,1)
        app_path.write_text(text,encoding='utf-8')
    rendered=app_path.read_text(encoding='utf-8')
    if marker not in rendered:
        raise SystemExit('UX_INTEREST_ADMIN_INSTALL_CONTROL_MISSING')
    if not template.is_file() or 'Interest & Demand' not in template.read_text(encoding='utf-8'):
        raise SystemExit('UX_INTEREST_ADMIN_TEMPLATE_CONTROL_MISSING')
    print('SCOREMAX_UX_INTEREST_ADMIN_BUILD_PASS runtime_module=true template=true installer=true',flush=True)
