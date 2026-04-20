#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
CONFIG_FILE = HOME / '.anisub_config.json'
WORK_DIR = HOME / 'anisub_work'
FONTS_DIR = HOME / 'anisub_fonts'
WORK_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)

FONTS = {
    '1': {
        'name': 'SolaimanLipi',
        'family': 'SolaimanLipi',
        'file': 'SolaimanLipi.ttf',
        'url': 'https://raw.githubusercontent.com/shiftenterdev/bangla-font/master/SolaimanLipi.ttf',
    },
    '2': {
        'name': 'Kalpurush',
        'family': 'Kalpurush',
        'file': 'kalpurush.ttf',
        'url': 'https://raw.githubusercontent.com/hmoazzem/bangla-fonts/master/kalpurush.ttf',
    },
    '3': {
        'name': 'Hind Siliguri',
        'family': 'Hind Siliguri',
        'file': 'HindSiliguri-Regular.ttf',
        'url': 'https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-Regular.ttf',
    },
    '4': {
        'name': 'Tiro Bangla',
        'family': 'Tiro Bangla',
        'file': 'TiroBangla-Regular.ttf',
        'url': 'https://github.com/google/fonts/raw/main/ofl/tirobangla/TiroBangla-Regular.ttf',
    },
}

COLORS = {
    '1': ('White', '&H00FFFFFF'),
    '2': ('Warm White', '&H00F2F7FF'),
    '3': ('Netflix Yellow', '&H0000F8FF'),
    '4': ('Cyan', '&H00FFFF00'),
}

POSITIONS = {
    '1': ('Bottom', 2),
    '2': ('Middle', 5),
    '3': ('Top', 8),
}

SIZES = {
    '1': ('Normal', 0.085),
    '2': ('Large', 0.105),
    '3': ('XL', 0.125),
    '4': ('XXL', 0.145),
}

STYLE_PRESETS = {
    '1': {
        'name': 'Screenshot Boxed',
        'description': 'Black background box like your screenshot. Default recommendation.',
        'font_key': '1',
        'color_key': '1',
        'position_key': '1',
        'size_key': '1',
        'bold': True,
        'italic': False,
        'border_style': 3,
        'outline': 1,
        'shadow': 0,
        'back_colour': '&H50000000',
        'outline_colour': '&H00000000',
        'spacing': 0,
        'margin_lr_ratio': 0.06,
        'margin_v_ratio': 0.05,
        'blur': 0,
    },
    '2': {
        'name': 'Netflix Clean',
        'description': 'No black box. White text with strong dark outline/shadow.',
        'font_key': '3',
        'color_key': '1',
        'position_key': '1',
        'size_key': '2',
        'bold': True,
        'italic': False,
        'border_style': 1,
        'outline': 3.2,
        'shadow': 1.2,
        'back_colour': '&H00000000',
        'outline_colour': '&H00000000',
        'spacing': 0.2,
        'margin_lr_ratio': 0.07,
        'margin_v_ratio': 0.055,
        'blur': 0,
    },
    '3': {
        'name': 'Big Mobile Box',
        'description': 'Extra large boxed subtitle for mobile reels/shorts.',
        'font_key': '2',
        'color_key': '1',
        'position_key': '1',
        'size_key': '4',
        'bold': True,
        'italic': False,
        'border_style': 3,
        'outline': 1,
        'shadow': 0,
        'back_colour': '&H42000000',
        'outline_colour': '&H00000000',
        'spacing': 0,
        'margin_lr_ratio': 0.05,
        'margin_v_ratio': 0.05,
        'blur': 0,
    },
}

def B(t): return '\033[1m' + str(t) + '\033[0m'
def G(t): return '\033[32m' + str(t) + '\033[0m'
def Y(t): return '\033[33m' + str(t) + '\033[0m'
def R(t): return '\033[31m' + str(t) + '\033[0m'
def C(t): return '\033[36m' + str(t) + '\033[0m'
def DIM(t): return '\033[2m' + str(t) + '\033[0m'
def hr(): print(DIM('--' * 24))

def ok(m): print(G('  [OK] ' + m))
def warn(m): print(Y('  [!!] ' + m))
def err(m): print(R('  [XX] ' + m))
def info(m): print(DIM('       ' + m))
def step(n, m): print('\n' + B(C('[' + str(n) + ']')) + ' ' + B(m))

def fmt_time(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f'{h}h {m}m {s}s'
    if m:
        return f'{m}m {s}s'
    return f'{s}s'

def ask(prompt, default=None):
    hint = (' ' + DIM('[' + str(default) + ']')) if default not in (None, '') else ''
    try:
        v = input(C('?') + ' ' + prompt + hint + ': ').strip()
    except EOFError:
        print()
        sys.exit(0)
    return v if v else default

def choose(title, opts, default='1'):
    print('\n' + B(title))
    for k, v in opts.items():
        if isinstance(v, tuple):
            label = v[0]
            desc = ''
        else:
            label = v['name']
            desc = v.get('description', '')
        marker = G('>') if k == default else ' '
        line = f'  {marker} {k}) {label}'
        if desc:
            line += ' ' + DIM('- ' + desc)
        print(line)
    try:
        v = input(C('?') + f' Choice [{default}]: ').strip() or default
    except EOFError:
        print()
        sys.exit(0)
    return v if v in opts else default

def load_cfg():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

def save_cfg(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    ok('Config saved')

def setup_telegram(cfg):
    hr()
    print(B('Telegram Setup') + DIM(' (once only)'))
    print(DIM('  my.telegram.org -> API Development Tools'))
    cfg['tg_api_id'] = ask('API ID', cfg.get('tg_api_id'))
    cfg['tg_api_hash'] = ask('API Hash', cfg.get('tg_api_hash'))
    cfg['tg_bot_token'] = ask('Bot Token', cfg.get('tg_bot_token'))
    print(DIM('  @channel_username or -100xxxxxxxxxx'))
    cfg['tg_chat_id'] = ask('Chat ID', cfg.get('tg_chat_id'))
    save_cfg(cfg)
    return cfg

def download_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def ensure_font(font_key):
    meta = FONTS[font_key]
    path = FONTS_DIR / meta['file']
    if path.exists() and path.stat().st_size > 10000:
        ok('Font ready: ' + meta['name'])
        return str(path)
    print('  Downloading ' + meta['name'] + '...')
    try:
        data = download_bytes(meta['url'], timeout=60)
        path.write_bytes(data)
        if path.stat().st_size <= 10000:
            raise RuntimeError('font download invalid')
        ok('Font saved: ' + str(path))
        return str(path)
    except Exception as e:
        warn('Font download failed: ' + str(e))
        return ''

def vtt_to_srt(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = []
    idx = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line == 'WEBVTT' or line.startswith(('NOTE', 'Kind:', 'Language:')):
            i += 1
            continue
        if '-->' in line:
            out.append(str(idx))
            out.append(line.replace('.', ','))
            i += 1
            buf = []
            while i < len(lines) and lines[i].strip():
                clean = re.sub(r'<[^>]+>', '', lines[i]).strip()
                if clean:
                    buf.append(clean)
                i += 1
            out.append('\n'.join(buf))
            out.append('')
            idx += 1
        else:
            i += 1
    return '\n'.join(out)

def load_subtitle(sub_input, work_dir):
    if sub_input.startswith('http'):
        info('Downloading subtitle...')
        text = download_bytes(sub_input, timeout=60).decode('utf-8', errors='replace')
    else:
        p = Path(sub_input.strip())
        if not p.exists():
            raise FileNotFoundError('Subtitle not found: ' + sub_input)
        text = p.read_text(encoding='utf-8', errors='replace')
    stripped = text.lstrip()
    if stripped.startswith('[Script Info]') or sub_input.lower().endswith('.ass'):
        out = work_dir / 'input.ass'
        out.write_text(text, encoding='utf-8')
        ok('ASS subtitle loaded')
        return str(out), 'ass'
    if stripped.startswith('WEBVTT') or sub_input.lower().endswith('.vtt'):
        info('VTT -> SRT')
        text = vtt_to_srt(text)
    out = work_dir / 'input.srt'
    out.write_text(text, encoding='utf-8')
    count = sum(1 for line in text.splitlines() if '-->' in line)
    ok(f'SRT loaded ({count} entries)')
    return str(out), 'srt'

def strip_html_tags(text):
    return re.sub(r'<[^>]+>', '', text)

def strip_ass_overrides(text):
    tmp = text.replace(r'\N', '<<<LB>>>').replace(r'\n', '<<<LB>>>')
    tmp = re.sub(r'\{[^{}]*\}', '', tmp)
    tmp = re.sub(r'\\h', ' ', tmp)
    tmp = re.sub(r'\\[Nn]', '<<<LB>>>', tmp)
    tmp = tmp.replace('<<<LB>>>', r'\N')
    return tmp.strip()

def esc_filter(p):
    return p.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'").replace(',', '\\,')

def ffprobe_json(url, referer=''):
    headers_val = 'Accept: */*\r\n'
    if referer:
        headers_val += 'Referer: ' + referer + '\r\nOrigin: ' + referer + '\r\n'
    cmd = [
        'ffprobe', '-v', 'error',
        '-user_agent', 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
        '-headers', headers_val,
        '-print_format', 'json',
        '-show_streams', '-show_format', url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None

def resolve_video_url(url):
    ytdlp = shutil.which('yt-dlp')
    if not ytdlp:
        warn('yt-dlp not installed')
        return url
    info('yt-dlp দিয়ে real URL বের করছে...')
    try:
        r = subprocess.run(
            [ytdlp, '--get-url', '-f', 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best', url],
            capture_output=True, text=True, timeout=60
        )
        lines = [x.strip() for x in r.stdout.splitlines() if x.strip().startswith('http')]
        if lines:
            ok('yt-dlp resolved')
            return lines[0]
    except Exception as e:
        warn('yt-dlp error: ' + str(e))
    return url

def get_video_meta(video_url, referer=''):
    meta = ffprobe_json(video_url, referer)
    if not meta:
        video_url = resolve_video_url(video_url)
        meta = ffprobe_json(video_url, referer)
    if not meta:
        return video_url, {'width': 1280, 'height': 720, 'duration': None}
    vstream = None
    for s in meta.get('streams', []):
        if s.get('codec_type') == 'video':
            vstream = s
            break
    width = int(vstream.get('width', 1280)) if vstream else 1280
    height = int(vstream.get('height', 720)) if vstream else 720
    duration = None
    try:
        duration = float(meta.get('format', {}).get('duration'))
    except Exception:
        duration = None
    return video_url, {'width': width, 'height': height, 'duration': duration}

def to_ass_time(ts):
    ts = ts.strip().replace(',', '.')
    if re.fullmatch(r'\d+:\d+:\d+(?:\.\d+)?', ts):
        h, m, s = ts.split(':')
        sec = float(s)
        cs = int(round((sec - int(sec)) * 100))
        return f'{int(h)}:{int(m):02d}:{int(sec):02d}.{cs:02d}'
    return ts

def calc_font_size(size_ratio, play_h):
    return max(44, int(round(play_h * size_ratio)))

def calc_margin_v(position_key, play_h, preset):
    base = max(24, int(round(play_h * preset['margin_v_ratio'])))
    if position_key == '1':
        return base
    if position_key == '2':
        return max(80, int(round(play_h * 0.16)))
    return base

def build_header(play_w, play_h, font_family, font_size, primary_colour, align, margin_v, bold, italic, preset):
    bf = -1 if bold else 0
    itf = -1 if italic else 0
    margin_lr = max(40, int(round(play_w * preset['margin_lr_ratio'])))
    return (
        '[Script Info]\n'
        'Title: AniSub Fixed\n'
        'ScriptType: v4.00+\n'
        f'PlayResX: {play_w}\n'
        f'PlayResY: {play_h}\n'
        'ScaledBorderAndShadow: yes\n'
        'WrapStyle: 2\n'
        'YCbCr Matrix: TV.709\n\n'
        '[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        f'Style: Default,{font_family},{font_size},{primary_colour},&H0000FFFF,{preset["outline_colour"]},{preset["back_colour"]},{bf},{itf},0,0,100,100,{preset["spacing"]},0,{preset["border_style"]},{preset["outline"]},{preset["shadow"]},{align},{margin_lr},{margin_lr},{margin_v},1\n\n'
        '[Events]\n'
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    )

def apply_line_fx(text, preset):
    if preset.get('blur', 0):
        return '{\\blur' + str(preset['blur']) + '}' + text
    return text

def srt_to_ass(srt_path, ass_path, style_cfg):
    text = Path(srt_path).read_text(encoding='utf-8', errors='replace')
    blocks = re.split(r'\n\s*\n', text.strip())
    dialogues = []
    for block in blocks:
        lines = [x.rstrip() for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        if re.fullmatch(r'\d+', lines[0]):
            lines = lines[1:]
        if not lines or '-->' not in lines[0]:
            continue
        start, end = [x.strip() for x in lines[0].split('-->', 1)]
        body = '\n'.join(lines[1:])
        body = strip_html_tags(body).replace('\r', '')
        body = body.replace('\n', r'\N').strip()
        body = apply_line_fx(body, style_cfg['preset'])
        dialogues.append((to_ass_time(start), to_ass_time(end), body))
    header = build_header(**style_cfg['header'])
    body = '\n'.join(f'Dialogue: 0,{s},{e},Default,,0,0,0,,{t}' for s, e, t in dialogues)
    Path(ass_path).write_text(header + body + '\n', encoding='utf-8')
    ok('ASS ready - ' + str(len(dialogues)) + ' lines')

def restyle_ass(src_ass_path, ass_path, style_cfg):
    text = Path(src_ass_path).read_text(encoding='utf-8', errors='replace')
    dialogues = []
    for line in text.splitlines():
        if not line.startswith('Dialogue:'):
            continue
        payload = line.split(':', 1)[1].lstrip()
        parts = payload.split(',', 9)
        if len(parts) < 10:
            continue
        start = parts[1].strip()
        end = parts[2].strip()
        txt = parts[9].strip()
        txt = strip_ass_overrides(txt)
        if not txt:
            continue
        txt = apply_line_fx(txt, style_cfg['preset'])
        dialogues.append((start, end, txt))
    if not dialogues:
        raise RuntimeError('Could not parse dialogue lines from ASS')
    header = build_header(**style_cfg['header'])
    body = '\n'.join(f'Dialogue: 0,{s},{e},Default,,0,0,0,,{t}' for s, e, t in dialogues)
    Path(ass_path).write_text(header + body + '\n', encoding='utf-8')
    ok('ASS restyled - ' + str(len(dialogues)) + ' lines')

def parse_time_from_ffmpeg(line):
    m = re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

def run_ffmpeg(cmd, duration=None):
    start = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
    last = 0
    for line in p.stderr:
        line = line.rstrip()
        if not line:
            continue
        if 'time=' in line and duration and time.time() - last > 1.2:
            cur = parse_time_from_ffmpeg(line)
            if cur is not None:
                pct = min(99, int(cur / duration * 100))
                bar = '#' * (pct // 5) + '.' * (20 - pct // 5)
                print('\r  [' + bar + '] ' + str(pct) + '%  elapsed=' + fmt_time(time.time() - start) + '   ', end='', flush=True)
                last = time.time()
        elif any(x in line.lower() for x in ['error', 'failed', 'invalid', 'no such']):
            print('\n  ' + R(line))
    p.wait()
    print()
    return p.returncode, time.time() - start

def upload_telegram(file_path, title, caption, cfg):
    try:
        from pyrogram import Client
    except ImportError:
        err('Install first: pip install pyrogram tgcrypto')
        return None
    chat_id = cfg['tg_chat_id']
    try:
        chat_id = int(chat_id)
    except Exception:
        pass
    info('Uploading ' + str(round(os.path.getsize(file_path) / 1048576, 1)) + ' MB...')
    t0 = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    last = [0]
    async def _do():
        async with Client('anisub_bot', api_id=int(cfg['tg_api_id']), api_hash=cfg['tg_api_hash'], bot_token=cfg['tg_bot_token'], in_memory=True) as app:
            def _prog(cur, total):
                if total and time.time() - last[0] > 1.5:
                    pct = int(cur / total * 100)
                    bar = '#' * (pct // 5) + '.' * (20 - pct // 5)
                    print('\r  [' + bar + '] ' + str(pct) + '%  ' + str(cur // 1048576) + '/' + str(total // 1048576) + 'MB', end='', flush=True)
                    last[0] = time.time()
            cap = ('**' + title + '**\n\n' + caption).strip() if caption else '**' + title + '**'
            msg = await app.send_video(chat_id=chat_id, video=file_path, caption=cap, supports_streaming=True, progress=_prog)
            print()
            return msg.link, time.time() - t0
    try:
        return loop.run_until_complete(_do())
    finally:
        loop.close()

def main():
    print(B(C('\n  AniSub CLI - Hard Fixed\n')))
    cfg = load_cfg()
    if not all(cfg.get(k) for k in ['tg_api_id', 'tg_api_hash', 'tg_bot_token', 'tg_chat_id']):
        warn('Telegram config not set')
        cfg = setup_telegram(cfg)
    else:
        hr()
        print(B('Telegram: ') + DIM(str(cfg.get('tg_chat_id'))))

    hr()
    step(1, 'Video & Subtitle')
    video_url = ask('Video URL (direct mp4/m3u8)')
    if not video_url:
        err('Video URL required')
        sys.exit(1)
    referer = ask('Referer (site homepage URL)', '')
    sub_input = ask('Subtitle path or URL (.srt/.vtt/.ass)')
    if not sub_input:
        err('Subtitle required')
        sys.exit(1)

    step(2, 'Probe video')
    video_url, meta = get_video_meta(video_url, referer)
    play_w = int(meta['width'] or 1280)
    play_h = int(meta['height'] or 720)
    duration = meta.get('duration')
    ok(f'Video size: {play_w}x{play_h}')
    if duration:
        info('Duration: ' + fmt_time(duration))

    step(3, 'Subtitle Style')
    preset_key = choose('Style preset', STYLE_PRESETS, '1')
    preset = STYLE_PRESETS[preset_key]
    use_defaults = ask('Use preset defaults? (y/n)', 'y').lower() == 'y'
    if use_defaults:
        font_key = preset['font_key']
        color_key = preset['color_key']
        position_key = preset['position_key']
        size_key = preset['size_key']
        bold = preset['bold']
        italic = preset['italic']
    else:
        font_key = choose('Font', FONTS, preset['font_key'])
        color_key = choose('Color', COLORS, preset['color_key'])
        position_key = choose('Position', POSITIONS, preset['position_key'])
        size_key = choose('Size', SIZES, preset['size_key'])
        bold = ask('Bold? (y/n)', 'y' if preset['bold'] else 'n').lower() == 'y'
        italic = ask('Italic? (y/n)', 'y' if preset['italic'] else 'n').lower() == 'y'

    font_meta = FONTS[font_key]
    color_hex = COLORS[color_key][1]
    align = POSITIONS[position_key][1]
    font_size = calc_font_size(SIZES[size_key][1], play_h)
    margin_v = calc_margin_v(position_key, play_h, preset)

    hr()
    info('Preset   : ' + preset['name'])
    info('Font     : ' + font_meta['name'])
    info('Color    : ' + COLORS[color_key][0])
    info('FontSize : ' + str(font_size))
    info('Position : ' + POSITIONS[position_key][0])

    step(4, 'Post Info')
    title = ask('Title', 'AniSub')
    caption = ask('Caption (optional)', '') or ''

    job_id = str(int(time.time()))
    work_dir = WORK_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    ass_path = str(work_dir / 'subtitle.ass')
    out_path = str(work_dir / 'output.mp4')

    step(5, 'Font')
    font_path = ensure_font(font_key)
    if not font_path:
        warn('Font missing. Rendering may fallback to system font.')

    step(6, 'Load subtitle')
    sub_path, sub_fmt = load_subtitle(sub_input, work_dir)

    style_cfg = {
        'preset': preset,
        'header': {
            'play_w': play_w,
            'play_h': play_h,
            'font_family': font_meta['family'],
            'font_size': font_size,
            'primary_colour': color_hex,
            'align': align,
            'margin_v': margin_v,
            'bold': bold,
            'italic': italic,
            'preset': preset,
        }
    }

    step(7, 'Build styled ASS')
    if sub_fmt == 'srt':
        srt_to_ass(sub_path, ass_path, style_cfg)
    else:
        restyle_ass(sub_path, ass_path, style_cfg)

    step(8, 'Render with FFmpeg')
    vf = "ass='" + esc_filter(ass_path) + "':fontsdir='" + esc_filter(str(FONTS_DIR)) + "'"
    headers_val = 'Accept: */*\r\n'
    if referer:
        headers_val += 'Referer: ' + referer + '\r\nOrigin: ' + referer + '\r\n'
    cmd = [
        'ffmpeg', '-y',
        '-user_agent', 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
        '-headers', headers_val,
        '-i', video_url,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        out_path,
    ]
    rc, render_time = run_ffmpeg(cmd, duration)
    if rc != 0 or not os.path.exists(out_path):
        err('FFmpeg render failed')
        shutil.rmtree(work_dir, ignore_errors=True)
        sys.exit(1)
    ok('Rendered: ' + str(round(os.path.getsize(out_path) / 1048576, 1)) + ' MB')
    ok('Render time: ' + fmt_time(render_time))

    step(9, 'Telegram upload')
    result = upload_telegram(out_path, title, caption, cfg)
    link = result[0] if result else None
    upload_time = result[1] if result else 0
    shutil.rmtree(work_dir, ignore_errors=True)
    info('Temp cleaned')

    hr()
    print(B('⏱ সময়ের হিসাব'))
    print(DIM('  Render : ') + G(fmt_time(render_time)))
    print(DIM('  Upload : ') + G(fmt_time(upload_time)))
    if link:
        print('\n' + G(B('Done! ')) + link)
    else:
        warn('Upload finished কিনা Telegram এ check করো')
    hr()

if __name__ == '__main__':
    main()