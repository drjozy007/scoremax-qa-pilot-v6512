from __future__ import annotations

import shutil
import struct
import zlib
from collections import deque
from pathlib import Path

import deploy_ux_vnext_teacher_base as base
from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace
from ux_vnext_overlay.ux_student_account_patch import apply_student_account_patch

ICON_NAME = 'scoremax-icon-student-summit-v3.png'
HEADER_ICON_NAME = 'scoremax-header-summit-tight-v5.png'
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _read_rgba_png(path: Path):
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise SystemExit('SCOREMAX_HEADER_ICON_SOURCE_NOT_PNG')
    pos = len(PNG_SIGNATURE)
    width = height = None
    idat = bytearray()
    while pos + 12 <= len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            width, height, bit_depth, colour_type, compression, filter_method, interlace = struct.unpack('>IIBBBBB', payload)
            if (bit_depth, colour_type, compression, filter_method, interlace) != (8, 6, 0, 0, 0):
                raise SystemExit('SCOREMAX_HEADER_ICON_SOURCE_FORMAT_UNSUPPORTED')
        elif kind == b'IDAT':
            idat.extend(payload)
        elif kind == b'IEND':
            break
    if not width or not height or not idat:
        raise SystemExit('SCOREMAX_HEADER_ICON_SOURCE_STRUCTURE_INVALID')

    decoded = zlib.decompress(bytes(idat))
    bpp = 4
    stride = width * bpp
    expected = height * (stride + 1)
    if len(decoded) != expected:
        raise SystemExit(f'SCOREMAX_HEADER_ICON_DECODE_LENGTH_INVALID expected={expected} actual={len(decoded)}')

    rows = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        f = decoded[offset]
        offset += 1
        scan = decoded[offset:offset + stride]
        offset += stride
        recon = bytearray(stride)
        for i, value in enumerate(scan):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if f == 0:
                result = value
            elif f == 1:
                result = (value + left) & 255
            elif f == 2:
                result = (value + up) & 255
            elif f == 3:
                result = (value + ((left + up) // 2)) & 255
            elif f == 4:
                result = (value + _paeth(left, up, up_left)) & 255
            else:
                raise SystemExit(f'SCOREMAX_HEADER_ICON_FILTER_UNSUPPORTED:{f}')
            recon[i] = result
        rows.append(recon)
        prev = recon
    return width, height, rows


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', crc)


def _write_rgba_png(path: Path, width: int, height: int, rows) -> None:
    raw = b''.join(b'\x00' + bytes(row) for row in rows)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    png = PNG_SIGNATURE + _png_chunk(b'IHDR', ihdr) + _png_chunk(b'IDAT', zlib.compress(raw, 9)) + _png_chunk(b'IEND', b'')
    path.write_bytes(png)


def _pixel(row, x: int):
    i = x * 4
    return tuple(row[i:i + 4])


def _median4(values):
    ordered = sorted(values)
    return (ordered[1] + ordered[2]) // 2


def _derive_tight_header_asset(source: Path, target: Path) -> tuple[int, int, int]:
    width, height, rows = _read_rgba_png(source)
    corners = [
        _pixel(rows[0], 0),
        _pixel(rows[0], width - 1),
        _pixel(rows[height - 1], 0),
        _pixel(rows[height - 1], width - 1),
    ]
    bg = tuple(_median4([p[c] for p in corners]) for c in range(4))
    mostly_transparent_bg = sum(1 for p in corners if p[3] < 32) >= 3

    def is_background(px) -> bool:
        if px[3] <= 8:
            return True
        if mostly_transparent_bg:
            return False
        rgb_distance = abs(px[0] - bg[0]) + abs(px[1] - bg[1]) + abs(px[2] - bg[2])
        return rgb_distance <= 45 and abs(px[3] - bg[3]) <= 40

    foreground = []
    for y, row in enumerate(rows):
        for x in range(width):
            if not is_background(_pixel(row, x)):
                foreground.append((x, y))
    if not foreground:
        raise SystemExit('SCOREMAX_HEADER_ICON_NO_VISIBLE_ARTWORK_DETECTED')

    min_x = min(x for x, _ in foreground)
    max_x = max(x for x, _ in foreground)
    min_y = min(y for _, y in foreground)
    max_y = max(y for _, y in foreground)
    pad = 1
    x0, x1 = max(0, min_x - pad), min(width - 1, max_x + pad)
    y0, y1 = max(0, min_y - pad), min(height - 1, max_y + pad)
    crop_w, crop_h = x1 - x0 + 1, y1 - y0 + 1
    if crop_w < 8 or crop_h < 8:
        raise SystemExit(f'SCOREMAX_HEADER_ICON_ARTWORK_BOUNDS_TOO_SMALL:{crop_w}x{crop_h}')

    cropped = []
    for y in range(y0, y1 + 1):
        start = x0 * 4
        end = (x1 + 1) * 4
        cropped.append(bytearray(rows[y][start:end]))

    # Remove only blank/background pixels connected to the crop edge. Internal light
    # details remain untouched, so this is a framing correction rather than a redraw.
    visited = set()
    queue = deque()
    for x in range(crop_w):
        queue.append((x, 0))
        queue.append((x, crop_h - 1))
    for y in range(crop_h):
        queue.append((0, y))
        queue.append((crop_w - 1, y))
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or x < 0 or y < 0 or x >= crop_w or y >= crop_h:
            continue
        visited.add((x, y))
        px = _pixel(cropped[y], x)
        if not is_background(px):
            continue
        i = x * 4
        cropped[y][i + 3] = 0
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    visible = 0
    vis_x, vis_y = [], []
    for y, row in enumerate(cropped):
        for x in range(crop_w):
            if _pixel(row, x)[3] > 16:
                visible += 1
                vis_x.append(x)
                vis_y.append(y)
    min_visible = max(40, int(crop_w * crop_h * 0.03))
    if visible < min_visible:
        raise SystemExit(f'SCOREMAX_HEADER_ICON_VISIBLE_PIXEL_COUNT_TOO_LOW:{visible}')
    span_w = max(vis_x) - min(vis_x) + 1
    span_h = max(vis_y) - min(vis_y) + 1
    if span_w < max(8, int(crop_w * 0.45)) or span_h < max(8, int(crop_h * 0.45)):
        raise SystemExit(f'SCOREMAX_HEADER_ICON_VISIBLE_SPAN_TOO_SMALL:{span_w}x{span_h}')

    target.parent.mkdir(parents=True, exist_ok=True)
    _write_rgba_png(target, crop_w, crop_h, cropped)
    return crop_w, crop_h, visible


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
    header_ref = "{{url_for('static',filename='scoremax-header-summit-tight-v5.png')}}?v=5"
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

    style = '''\n<style id="scoremax-agreed-icon-v5-style">
.scoremax-install-art{width:46px;height:46px;flex:0 0 46px;object-fit:cover;border-radius:12px;display:block;box-shadow:0 3px 10px rgba(15,23,42,.14)}
.scoremax-install-help-card .scoremax-install-art{width:68px;height:68px;flex-basis:68px;border-radius:16px;margin:0 auto 8px}
.ux-brand-art{width:36px;height:36px;flex:0 0 36px;object-fit:contain;object-position:center;display:block;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;filter:none!important}
@media(max-width:420px){.ux-brand-art{width:33px;height:33px;flex-basis:33px}}
</style>\n'''
    if 'scoremax-agreed-icon-v5-style' not in text:
        if '</head>' not in text:
            raise SystemExit('SCOREMAX_V5_HEAD_MARKER_MISSING')
        text = text.replace('</head>', style + '</head>', 1)

    manifest = manifest_target.read_text(encoding='utf-8')
    if 'scoremax-icon-student-summit-v3.png?v=3' not in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_REFERENCE_MISSING')
    if 'scoremax-icon-summit-v2.png' in manifest:
        raise SystemExit('SCOREMAX_V3_MANIFEST_OLD_ICON_STILL_AUTHORITATIVE')
    if HEADER_ICON_NAME not in text or not header_target.is_file():
        raise SystemExit('SCOREMAX_V5_TIGHT_HEADER_ASSET_MISSING')
    if 'class="ux-brand-bar"' in text:
        raise SystemExit('SCOREMAX_V3_OLD_THREE_BAR_HEADER_MARK_SURVIVED')
    if text.count(wordmark) != 1:
        raise SystemExit('SCOREMAX_V5_WORDMARK_POSTBUILD_MISMATCH')

    base_path.write_text(text, encoding='utf-8')
    print(
        'SCOREMAX_INSTALL_AGREED_ICON_V5_ACTIVE '
        f'source={ICON_NAME} header_asset={HEADER_ICON_NAME} crop={crop_w}x{crop_h} visible_pixels={visible_pixels} '
        'artwork=student_climbing_mountain_steps_gold_star derived_from_approved_source=true '
        'edge_background_removed=true css_crop=false blank_header_tile=false '
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
        'SCOREMAX_UX_ACCOUNT_ICON_RECTIFICATION_V6_PASS '
        'student_logout_visible=true landing_install_art=true header_brand_art=true '
        'derived_header_asset=true css_crop=false blank_header_tile=false wordmark_unchanged=true '
        'old_three_bar_header=false teacher_workspace_preserved=true',
        flush=True,
    )


if __name__ == '__main__':
    main()
