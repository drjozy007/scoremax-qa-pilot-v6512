"""Wire the invitation boundary into the existing assembled production target."""
from pathlib import Path
import shutil


def apply(root):
    root = Path(root)
    production = root / 'scoremax_production.py'
    text = production.read_text(encoding='utf-8')
    old = 'import app as scoremax\nscoremax.init()'
    new = ('import app as scoremax\n'
           'from invite_only_pilot_runtime import install as install_invite_only_pilot\n'
           'install_invite_only_pilot(scoremax.app, scoremax.db)\n'
           'scoremax.init()')
    if 'install_invite_only_pilot(scoremax.app, scoremax.db)' not in text:
        if text.count(old) != 1:
            raise RuntimeError('INVITE_ONLY_PILOT_PRODUCTION_ANCHOR_MISMATCH')
        text = text.replace(old, new, 1)
    source = Path(__file__).with_name('invite_only_pilot_runtime.py')
    template = root / 'templates' / 'ux_subject_chapters.html'
    chapters = template.read_text(encoding='utf-8')
    unavailable = ('{% if not ch.available %}\n'
                   '              <span class="state">Coming soon</span>'
                   '<span class="dot">·</span>No released questions\n'
                   '            {% elif not ch.answered %}')
    if unavailable not in chapters:
        if chapters.count('{% if not ch.answered %}') != 1:
            raise RuntimeError('INVITE_ONLY_PILOT_CHAPTER_ANCHOR_MISMATCH')
        chapters = chapters.replace('{% if not ch.answered %}', unavailable, 1)
    compile(text, str(production), 'exec')
    shutil.copyfile(source, root / source.name)
    production.write_text(text, encoding='utf-8')
    template.write_text(chapters, encoding='utf-8')
    return {'installed': True, 'native_release_and_role_checks_preserved': True}
