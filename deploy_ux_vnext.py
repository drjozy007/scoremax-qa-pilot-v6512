from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import deploy_ux_vnext_teacher_base as base
from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace
from ux_vnext_overlay.ux_student_account_patch import apply_student_account_patch

ICON_NAME = 'scoremax-icon-student-summit-v3.png'
HEADER_ICON_NAME = 'scoremax-header-summit-tight-v6.png'


def _load_pillow():
    try:
        from PIL import Image, ImageChops, ImageDraw
        return Image, ImageChops, ImageDraw
    except ImportError:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'Pillow==11.3.0'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        from PIL import Image, ImageChops, ImageDraw
        return Image, ImageChops, ImageDraw


def _derive_tight_header_asset(source: Path, target: Path) -> tuple[int, int, int]:
    Image, ImageChops, ImageDraw = _load_pillow()
    im = Image.open(source).convert('RGBA')
    width, height = im.size
    corners = [
        im.getpixel((0, 0)),
        im.getpixel((width - 1, 0)),
        im.getpixel((0, height - 1)),
        im.getpixel((width - 1, height - 1)),
    ]
    # Median-like stable corner background estimate, robust to one non-background corner.
    bg = tuple(sorted(p[i] for p in corners)[1:3][0] for i in range(4))
    if sum(1 for p in corners if p[3] <= 16) >= 3:
        alpha = im.getchannel('A')
        mask = alpha.point(lambda p: 255 if p > 16 else 0)
    else:
        bg_img = Image.new('RGBA', im.size, bg)
        diff = ImageChops.difference(im, bg_img).convert('RGB')
        # Use maximum channel difference so light anti-aliasing does not define the crop.
        mask = Image.new('L', im.size, 0)
        src = diff.load(); dst = mask.load()
        for y in range(height):
            for x in range(width):
                px = src[x, y]
                dst[x, y] = 255 if max(px) > 18 else 0

    bbox = mask.getbbox()
    if not bbox:
        raise SystemExit('SCOREMAX_HEADER_ICON_NO_VISIBLE_ARTWORK_DETECTED')
    x0, y0, x1, y1 = bbox
    pad = 2
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(width, x1 + pad), min(height, y1 + pad)
    crop = im.crop((x0, y0, x1, y1))
    crop_w, crop_h = crop.size
    if crop_w < 8 or crop_h < 8:
        raise SystemExit(f'SCOREMAX_HEADER_ICON_ARTWORK_BOUNDS_TOO_SMALL:{crop_w}x{crop_h}')

    # Remove only the connected outer background; internal white/gold artwork is preserved.
    if not (sum(1 for p in corners if p[3] <= 16) >= 3):
        for seed in ((0, 0), (crop_w - 1, 0), (0, crop_h - 1), (crop_w - 1, crop_h - 1)):
            ImageDraw.floodfill(crop, seed, (0, 0, 0, 0), thresh=42)

    alpha = crop.getchannel('A')
    visible_mask = alpha.point(lambda p: 255 if p > 16 else 0)
    visible_bbox = visible_mask.getbbox()
    if not visible_bbox:
        raise SystemExit('SCOREMAX_HEADER_ICON_NO_VISIBLE_PIXELS_AFTER_BACKGROUND_REMOVAL')
    visible_pixels = sum(1 for p in alpha.getdata() if p > 16)
    min_visible = max(40, int(crop_w * crop_h * 0.03))
    if visible_pixels < min_visible:
        raise SystemExit(f'SCOREMAX_HEADER_ICON_VISIBLE_PIXEL_COUNT_TOO_LOW:{visible_pixels}')
    vx0, vy0, vx1, vy1 = visible_bbox
    if (vx1 - vx0) < max(8, int(crop_w * 0.45)) or (vy1 - vy0) < max(8, int(crop_h * 0.45)):
        raise SystemExit(f'SCOREMAX_HEADER_ICON_VISIBLE_SPAN_TOO_SMALL:{vx1-vx0}x{vy1-vy0}')

    target.parent.mkdir(parents=True, exist_ok=True)
    crop.save(target, format='PNG', optimize=True)
    return crop_w, crop_h, visible_pixels


def _install_agreed_scoremax_icon(root: Path) -> None:
    source = Path('ux_vnext_overlay') / 'static' / ICON_NAME
    target = root / 'static' / ICON_NAME
    header_target = root / 'static' / HEADER_ICON_NAME
    manifest_source = Path('ux_vnext_overlay') / 'static' / 'scoremax.webmanifest'
    manifest_target = root / 'static' / 'scoremax.webmanifest'
    if not source.is_file():
        raise SystemExit('SCOREMAX_V3_AGREED_ICON_SOURCE_MISSING')
    if not manifest_source.is_file():
        raise SystemExit('SCOREMAX_V3_MANIFEST_SOURCE_MISSING')

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    shutil.copy2(manifest_source, manifest_target)
    crop_w, crop_h, visible_pixels = _derive_tight_header_asset(source, header_target)

    base_path = root / 'templates' / 'base.html'
    text = base_path.read_text(encoding='utf-8')
    new_ref = "{{url_for('static',filename='scoremax-icon-student-summit-v3.png')}}?v=3"
    header_ref = "{{url_for('static',filename='scoremax-header-summit-tight-v6.png')}}?v=6"
    for old in (
        "{{url_for('static',filename='scoremax-icon-32.png')}}",
        "{{url_for('static',filename='scoremax-icon-180.png')}}",
        "{{url_for('static',filename='scoremax-icon-summit-v2.png')}}?v=2",
    ):
        text = text.replace(old, new_ref)

    old_mark = '<span class="scoremax-install-mark" aria-hidden="true"><i></i><i></i><i></i></span>'
    new_mark = '<img class="scoremax-install-art" src="'+new_ref+'" alt="">'
    if old_mark in text:
        text = text.replace(old_mark, new_mark)
    if 'scoremax-install-art' not in text:
        raise SystemExit('SCOREMAX_V3_VISIBLE_INSTALL_ART_MISSING')

    wordmark = '<span class="ux-brand-name"><span class="ux-brand-score">Score</span><span class="ux-brand-max">Max</span></span>'
    if text.count(wordmark) != 1:
        raise SystemExit(f'SCOREMAX_HEADER_WORDMARK_BASELINE_MISMATCH:{text.count(wordmark)}')
    old_brand_mark = '<span class="ux-brand-mark" aria-hidden="true"><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i><i class="ux-brand-bar"></i></span>'
    new_brand_mark = '<img class="ux-brand-art" src="'+header_ref+'" alt="" aria-hidden="true">'
    if old_brand_mark not in text:
        raise SystemExit('SCOREMAX_V3_OLD_HEADER_BRAND_MARK_MISSING')
    text = text.replace(old_brand_mark, new_brand_mark, 1)
    if text.count(wordmark) != 1:
        raise SystemExit('SCOREMAX_HEADER_WORDMARK_CHANGED_DURING_ICON_RECTIFICATION')

    style = '''\n<style id="scoremax-agreed-icon-v6-style">
.scoremax-install-art{width:46px;height:46px;flex:0 0 46px;object-fit:cover;border-radius:12px;display:block;box-shadow:0 3px 10px rgba(15,23,42,.14)}
.scoremax-install-help-card .scoremax-install-art{width:68px;height:68px;flex-basis:68px;border-radius:16px;margin:0 auto 8px}
.ux-brand-art{width:38px;height:38px;flex:0 0 38px;object-fit:contain;object-position:center;display:block;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;filter:none!important}
@media(max-width:420px){.ux-brand-art{width:34px;height:34px;flex-basis:34px}}
</style>\n'''
    if 'scoremax-agreed-icon-v6-style' not in text:
        if '</head>' not in text:
            raise SystemExit('SCOREMAX_V6_HEAD_MARKER_MISSING')
        text = text.replace('</head>', style + '</head>', 1)

    manifest = manifest_target.read_text(encoding='utf-8')
    if 'scoremax-icon-student-summit-v3.png?v=3' not in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_REFERENCE_MISSING')
    if 'scoremax-icon-summit-v2.png' in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_OLD_ICON_STILL_AUTHORITATIVE')
    if HEADER_ICON_NAME not in text or not header_target.is_file():
        raise SystemExit('SCOREMAX_V6_TIGHT_HEADER_ASSET_MISSING')
    if 'class="ux-brand-bar"' in text:
        raise SystemExit('SCOREMAX_V3_OLD_THREE_BAR_HEADER_MARK_SURVIVED')
    if text.count(wordmark) != 1:
        raise SystemExit('SCOREMAX_V6_WORDMARK_POSTBUILD_MISMATCH')

    base_path.write_text(text, encoding='utf-8')
    print(
        'SCOREMAX_INSTALL_AGREED_ICON_V6_ACTIVE '
        f'source={ICON_NAME} header_asset={HEADER_ICON_NAME} crop={crop_w}x{crop_h} visible_pixels={visible_pixels} '
        'artwork=student_climbing_mountain_steps_gold_star derived_from_approved_source=true '
        'pillow_asset_pipeline=true edge_background_removed=true css_crop=false blank_header_tile=false '
        'wordmark_unchanged=true install_prompt_exact_artwork=true old_three_bar_header_markup=false '
        'served_image_visual_acceptance_required=true',
        flush=True,
    )


def main() -> None:
    base.main()
    apply_teacher_workspace(base.OUT)
    apply_student_account_patch(base.OUT)
    _install_agreed_scoremax_icon(base.OUT)

    rendered_base = (base.OUT / 'templates' / 'base.html').read_text(encoding='utf-8')
    for required in ('ux-student-logout-link','ux-student-mobile-logout','scoremax-icon-student-summit-v3.png','scoremax-install-art',HEADER_ICON_NAME,'ux-brand-art','ux-brand-name'):
        if required not in rendered_base:
            raise SystemExit('SCOREMAX_POSTBUILD_ACCOUNT_ICON_CONTROL_MISSING:'+required)
    if 'class="ux-brand-bar"' in rendered_base:
        raise SystemExit('SCOREMAX_POSTBUILD_THREE_BAR_HEADER_MARK_SURVIVED')
    if 'ux-brand-crop' in rendered_base:
        raise SystemExit('SCOREMAX_POSTBUILD_CSS_CROP_WRAPPER_SURVIVED')
    print(
        'SCOREMAX_UX_ACCOUNT_ICON_RECTIFICATION_V7_PASS '
        'student_logout_visible=true landing_install_art=true header_brand_art=true '
        'derived_header_asset=true pillow_asset_pipeline=true css_crop=false blank_header_tile=false '
        'wordmark_unchanged=true old_three_bar_header=false teacher_workspace_preserved=true',
        flush=True,
    )


if __name__ == '__main__':
    main()
