"""Outils communs : configuration, dossiers, ffmpeg/ffprobe, images, polices."""
import json, os, re, shutil, subprocess, sys, threading, time, unicodedata

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_WIN = os.name == 'nt'

SUB = {
    'inbox': '00_inbox', 'refs': '01_references', 'clips': '02_clips',
    'projects': '03_projects', 'reels': '04_reels', 'pub': '05_publication',
    'reports': '06_rapports', 'assets': '_assets', 'index': '_index',
}

DEFAULT_CONFIG = {
    'factory_root': 'D:/ReelFactory' if IS_WIN else os.path.expanduser('~/ReelFactory'),
    'rush_roots': ['D:/RUSH'] if IS_WIN else [],
    'video_ext': ['.mp4', '.mov', '.mxf', '.m4v', '.avi', '.mts'],
    'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe',
    'canvas': [1080, 1920],
    'also_landscape_when_ref_landscape': True,
    'loudness_lufs': -14.0, 'true_peak_db': -1.0,
    'x264': {'crf': 18, 'preset': 'slow', 'maxrate': '20M', 'bufsize': '40M'},
    'preview_max_mb': 28,
    'download_pause_s': [4, 9],
}

_CFG = None


def load_config(path=None):
    """Charge config.json (RF_CONFIG, ./config.json, <factory>/config.json, kit/config.json)."""
    global _CFG
    if _CFG is not None and path is None:
        return _CFG
    cands = [path, os.environ.get('RF_CONFIG'), os.path.join(os.getcwd(), 'config.json'),
             os.path.join(KIT, 'config.json'), os.path.join(os.path.dirname(KIT), 'config.json'),
             'D:/ReelFactory/config.json' if IS_WIN else None]
    cfg = dict(DEFAULT_CONFIG)
    for c in cands:
        if c and os.path.isfile(c):
            with open(c, encoding='utf-8') as f:
                cfg.update(json.load(f))
            cfg['_config_path'] = c
            break
    if os.environ.get('RF_ROOT'):
        cfg['factory_root'] = os.environ['RF_ROOT']
    _CFG = cfg
    return cfg


def root(*parts):
    return os.path.join(load_config()['factory_root'], *parts)


def d(key, *parts):
    """Chemin d'un sous-dossier standard de l'usine (cree si besoin)."""
    p = root(SUB[key], *parts)
    os.makedirs(p if not os.path.splitext(p)[1] else os.path.dirname(p), exist_ok=True)
    return p


def ensure_tree():
    for k in SUB:
        os.makedirs(root(SUB[k]), exist_ok=True)
    for s in ('fonts', 'sfx', 'overlays', 'luts'):
        os.makedirs(root(SUB['assets'], s), exist_ok=True)


def slug(s, n=40):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s[:n] or 'x'


def jload(p, default=None):
    if not os.path.isfile(p):
        return default
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def jsave(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = p + '.tmp%d' % os.getpid()
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    for _ in range(20):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            time.sleep(0.2)
    os.replace(tmp, p)


class FileLock:
    """Verrou simple par fichier (plusieurs agents peuvent ecrire le meme JSON)."""
    def __init__(self, path, timeout=60):
        self.p = path + '.lock'; self.timeout = timeout
    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() - t0 > self.timeout:
                    try: os.remove(self.p)
                    except OSError: pass
                time.sleep(0.1)
    def __exit__(self, *a):
        os.close(self.fd)
        try: os.remove(self.p)
        except OSError: pass


# ---------------------------------------------------------------- ffmpeg

def ff():
    return load_config()['ffmpeg']


def ffp():
    return load_config()['ffprobe']


def run(cmd, check=True, capture=False, text=True, timeout=None, quiet=True):
    """Lance une commande (liste). Leve RuntimeError avec la fin de stderr si echec."""
    cmd = [str(c) for c in cmd]
    if cmd[0] in ('ffmpeg', ff()) and quiet and '-loglevel' not in cmd:
        cmd = [cmd[0], '-hide_banner', '-loglevel', 'error', '-nostdin'] + cmd[1:]
    p = subprocess.run(cmd, capture_output=True, text=text, timeout=timeout,
                       encoding='utf-8' if text else None, errors='replace' if text else None)
    if check and p.returncode != 0:
        err = (p.stderr or '')[-2500:] if text else p.stderr[-2500:].decode('utf-8', 'replace')
        raise RuntimeError('Commande echouee (%d): %s\n%s' % (p.returncode, ' '.join(cmd[:12]), err))
    return p if capture else p.returncode


def ffmpeg(*args, **kw):
    return run([ff(), '-y'] + list(args), **kw)


def probe(path):
    """Infos video : w,h (apres rotation), fps, dur, audio, codec, taille."""
    p = run([ffp(), '-v', 'error', '-show_entries',
             'format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels:stream_side_data=rotation:stream_tags=rotate',
             '-of', 'json', path], capture=True)
    j = json.loads(p.stdout or '{}')
    v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), None)
    a = next((s for s in j.get('streams', []) if s.get('codec_type') == 'audio'), None)
    fmt = j.get('format', {})
    out = {'path': path, 'dur': float(fmt.get('duration') or 0), 'size': int(fmt.get('size') or 0),
           'bitrate': int(fmt.get('bit_rate') or 0), 'audio': a is not None,
           'audio_rate': int(a.get('sample_rate', 0)) if a else 0,
           'audio_ch': int(a.get('channels', 0)) if a else 0}
    if v:
        w, h = int(v.get('width', 0)), int(v.get('height', 0))
        rot = 0
        for sd in v.get('side_data_list', []) or []:
            if 'rotation' in sd:
                rot = int(float(sd['rotation']))
        if 'rotate' in (v.get('tags') or {}):
            rot = int(v['tags']['rotate'])
        if abs(rot) % 180 == 90:
            w, h = h, w
        out.update(w=w, h=h, rotation=rot, vcodec=v.get('codec_name'),
                   fps=_rate(v.get('avg_frame_rate')) or _rate(v.get('r_frame_rate')))
    else:
        out.update(w=0, h=0, rotation=0, vcodec=None, fps=0)
    return out


def _rate(r):
    try:
        a, b = str(r).split('/')
        return float(a) / float(b) if float(b) else 0.0
    except Exception:
        try: return float(r)
        except Exception: return 0.0


def frame_at(path, t, w=480, vf=None):
    """Une image PIL a l'instant t (seek rapide)."""
    from PIL import Image
    import io
    filt = (vf + ',' if vf else '') + 'scale=%d:-2' % w
    p = subprocess.run([ff(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', '%.3f' % max(0, t), '-i', path,
                        '-frames:v', '1', '-vf', filt, '-f', 'image2pipe', '-vcodec', 'png', '-'],
                       capture_output=True)
    if not p.stdout:
        return None
    return Image.open(io.BytesIO(p.stdout)).convert('RGB')


def iter_frames(path, w, h, fps=None, ss=None, t=None, keyframes_only=False, vf=None, pix='rgb24', with_pts=False):
    """Generateur de frames numpy (h,w,3) via un pipe ffmpeg (streaming, memoire constante).
    with_pts=True -> renvoie (pts, frame)."""
    import numpy as np
    cmd = [ff(), '-hide_banner', '-nostdin']
    cmd += ['-loglevel', 'info' if with_pts else 'error']
    if keyframes_only:
        cmd += ['-skip_frame', 'nokey']
    if ss is not None:
        cmd += ['-ss', '%.3f' % ss]
    if t is not None:
        cmd += ['-t', '%.3f' % t]
    cmd += ['-i', path, '-an']
    filt = []
    if vf: filt.append(vf)
    if fps: filt.append('fps=%s' % fps)
    filt.append('scale=%d:%d' % (w, h))
    if with_pts: filt.append('showinfo')
    cmd += ['-vf', ','.join(filt)]
    if keyframes_only: cmd += ['-fps_mode', 'passthrough']
    cmd += ['-f', 'rawvideo', '-pix_fmt', pix, '-']
    ch = 1 if pix == 'gray' else 3
    size = w * h * ch
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pts = []
    def _err():
        for line in proc.stderr:
            if with_pts:
                m = re.search(rb'pts_time:\s*([0-9.]+)', line)
                if m: pts.append(float(m.group(1)))
    th = threading.Thread(target=_err, daemon=True); th.start()
    i = 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if not buf or len(buf) < size:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(h, w, ch) if ch == 3 else np.frombuffer(buf, np.uint8).reshape(h, w)
            if with_pts:
                for _ in range(200):
                    if len(pts) > i: break
                    time.sleep(0.005)
                yield (pts[i] if i < len(pts) else None), fr
            else:
                yield fr
            i += 1
    finally:
        try: proc.stdout.close()
        except Exception: pass
        proc.wait()


def extract_wav(src, dst, rate=48000, ch=2, ss=None, t=None):
    args = []
    if ss: args += ['-ss', '%.3f' % ss]
    if t: args += ['-t', '%.3f' % t]
    ffmpeg(*args, '-i', src, '-vn', '-ac', ch, '-ar', rate, '-c:a', 'pcm_s16le', dst)
    return dst


def read_audio(path, rate=48000, ch=2):
    """Audio -> numpy float32 (n, ch)."""
    import numpy as np
    p = subprocess.run([ff(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-i', path, '-vn', '-ac', str(ch),
                        '-ar', str(rate), '-f', 'f32le', '-'], capture_output=True)
    a = np.frombuffer(p.stdout, np.float32)
    return a.reshape(-1, ch).copy()


def write_wav(path, a, rate=48000):
    import numpy as np, wave
    a = np.clip(a, -1, 1)
    if a.ndim == 1: a = a[:, None]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((a * 32767).astype('<i2').tobytes())
    return path


def loudness(path):
    """Mesure EBU R128 : I (LUFS), LRA, TP (dBTP)."""
    p = subprocess.run([ff(), '-hide_banner', '-nostdin', '-i', path, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    s = p.stderr
    tail = s[s.rfind('Summary:'):] if 'Summary:' in s else s
    def g(pat):
        m = re.search(pat, tail)
        return float(m.group(1)) if m else None
    return {'I': g(r'I:\s*(-?[0-9.]+|-inf) LUFS'), 'LRA': g(r'LRA:\s*([0-9.]+) LU'),
            'TP': g(r'Peak:\s*(-?[0-9.]+|-inf) dBFS')}


# ---------------------------------------------------------------- images

def font_label(size=22):
    from PIL import ImageFont
    for c in [os.path.join(root(SUB['assets'], 'fonts'), 'Inter-Bold.ttf'), 'C:/Windows/Fonts/arialbd.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']:
        if os.path.isfile(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def sheet(tiles, labels=None, cols=6, out=None, tile_w=320, quality=85, title=None):
    """Planche contact avec etiquettes (PIL, pas de drawtext : evite le crash fontconfig sous Windows)."""
    from PIL import Image, ImageDraw
    tiles = [t for t in tiles if t is not None]
    if not tiles:
        return None
    th = int(round(tiles[0].height * tile_w / tiles[0].width))
    rows = (len(tiles) + cols - 1) // cols
    top = 40 if title else 0
    sh = Image.new('RGB', (cols * tile_w, rows * th + top), (16, 16, 16))
    d = ImageDraw.Draw(sh); f = font_label(max(14, tile_w // 15))
    if title:
        d.text((8, 8), title, font=font_label(24), fill=(255, 220, 0))
    for k, t in enumerate(tiles):
        x, y = (k % cols) * tile_w, (k // cols) * th + top
        sh.paste(t.resize((tile_w, th)), (x, y))
        if labels and k < len(labels) and labels[k]:
            lab = str(labels[k]); tw = d.textlength(lab, font=f)
            d.rectangle([x, y, x + tw + 8, y + f.size + 8], fill=(0, 0, 0))
            d.text((x + 4, y + 3), lab, font=f, fill=(255, 230, 0))
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        sh.save(out, quality=quality)
    return sh


def img_stats(im):
    """Statistiques couleur d'une image PIL/numpy : luminance, saturation, chaleur, teintes."""
    import numpy as np
    a = np.asarray(im.convert('RGB') if hasattr(im, 'convert') else im).reshape(-1, 3).astype(np.float32)
    L = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = a.max(1), a.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    lo, hi = np.percentile(L, 25), np.percentile(L, 90)
    sh = a[L <= lo].mean(0) if (L <= lo).any() else a.mean(0)
    hl = a[L >= hi].mean(0) if (L >= hi).any() else a.mean(0)
    return {'luma': round(float(L.mean()) / 255, 4), 'sat': round(float(sat.mean()), 4),
            'warmth': round(float((a[:, 0] - a[:, 2]).mean()) / 255, 4),
            'contrast': round(float(np.percentile(L, 95) - np.percentile(L, 5)) / 255, 4),
            'mean_rgb': [round(float(x), 1) for x in a.mean(0)],
            'std_rgb': [round(float(x), 1) for x in a.std(0)],
            'shadow_rgb': [round(float(x), 1) for x in sh], 'high_rgb': [round(float(x), 1) for x in hl]}


# ---------------------------------------------------------------- polices
# Cle -> candidats (fichier, axes variables). Les polices OFL sont telechargees par install.py
FONT_DB = {
    'didone':        [('C:/Windows/Fonts/BOD_R.TTF', None), ('BodoniModa[opsz,wght].ttf', {'Weight': 500, 'Optical size': 24}), ('LibreBodoni[wght].ttf', {'Weight': 400}), ('DejaVuSerif.ttf', None)],
    'didone_bold':   [('C:/Windows/Fonts/BOD_B.TTF', None), ('BodoniModa[opsz,wght].ttf', {'Weight': 800, 'Optical size': 24}), ('DejaVuSerif-Bold.ttf', None)],
    'didone_italic': [('C:/Windows/Fonts/BOD_I.TTF', None), ('BodoniModa-Italic[opsz,wght].ttf', {'Weight': 500, 'Optical size': 24}), ('DejaVuSerif-Italic.ttf', None)],
    'garamond':      [('C:/Windows/Fonts/GARA.TTF', None), ('EBGaramond[wght].ttf', {'Weight': 400}), ('CormorantGaramond[wght].ttf', {'Weight': 500}), ('DejaVuSerif.ttf', None)],
    'garamond_italic': [('C:/Windows/Fonts/GARAIT.TTF', None), ('EBGaramond-Italic[wght].ttf', {'Weight': 400}), ('DejaVuSerif-Italic.ttf', None)],
    'garamond_bold': [('C:/Windows/Fonts/GARABD.TTF', None), ('EBGaramond[wght].ttf', {'Weight': 700}), ('DejaVuSerif-Bold.ttf', None)],
    'impact':        [('C:/Windows/Fonts/impact.ttf', None), ('Anton-Regular.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'anton':         [('Anton-Regular.ttf', None), ('C:/Windows/Fonts/impact.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'bebas':         [('BebasNeue-Regular.ttf', None), ('LeagueGothic[wdth].ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'league_gothic': [('LeagueGothic[wdth].ttf', None), ('BebasNeue-Regular.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'archivo_black': [('ArchivoBlack-Regular.ttf', None), ('C:/Windows/Fonts/ariblk.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'poppins_bold':  [('Poppins-Bold.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'poppins_xbold': [('Poppins-ExtraBold.ttf', None), ('Poppins-Bold.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'poppins_semibold': [('Poppins-SemiBold.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'poppins_bolditalic': [('Poppins-BoldItalic.ttf', None), ('DejaVuSans-BoldOblique.ttf', None)],
    'montserrat_black': [('Montserrat[wght].ttf', {'Weight': 900}), ('DejaVuSans-Bold.ttf', None)],
    'montserrat_bold': [('Montserrat[wght].ttf', {'Weight': 700}), ('DejaVuSans-Bold.ttf', None)],
    'inter_bold':    [('Inter[opsz,wght].ttf', {'Weight': 700}), ('C:/Windows/Fonts/arialbd.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'inter':         [('Inter[opsz,wght].ttf', {'Weight': 450}), ('C:/Windows/Fonts/arial.ttf', None), ('DejaVuSans.ttf', None)],
    'oswald_bold':   [('Oswald[wght].ttf', {'Weight': 700}), ('DejaVuSans-Bold.ttf', None)],
    'instrument':    [('InstrumentSerif-Regular.ttf', None), ('DejaVuSerif.ttf', None)],
    'instrument_italic': [('InstrumentSerif-Italic.ttf', None), ('DejaVuSerif-Italic.ttf', None)],
    'playfair':      [('PlayfairDisplay[wght].ttf', {'Weight': 500}), ('DejaVuSerif.ttf', None)],
    'playfair_bold': [('PlayfairDisplay[wght].ttf', {'Weight': 800}), ('DejaVuSerif-Bold.ttf', None)],
    'playfair_italic': [('PlayfairDisplay-Italic[wght].ttf', {'Weight': 500}), ('DejaVuSerif-Italic.ttf', None)],
    'dmserif':       [('DMSerifDisplay-Regular.ttf', None), ('DejaVuSerif.ttf', None)],
    'dmserif_italic': [('DMSerifDisplay-Italic.ttf', None), ('DejaVuSerif-Italic.ttf', None)],
    'abril':         [('AbrilFatface-Regular.ttf', None), ('DejaVuSerif-Bold.ttf', None)],
    'cinzel':        [('Cinzel[wght].ttf', {'Weight': 600}), ('DejaVuSerif.ttf', None)],
    'oldstandard':   [('OldStandard-Regular.ttf', None), ('DejaVuSerif.ttf', None)],
    'oldstandard_italic': [('OldStandard-Italic.ttf', None), ('DejaVuSerif-Italic.ttf', None)],
    'typewriter':    [('SpecialElite-Regular.ttf', None), ('DejaVuSansMono.ttf', None)],
    'marker':        [('PermanentMarker-Regular.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'fraktur':       [('UnifrakturMaguntia-Book.ttf', None), ('DejaVuSerif-Bold.ttf', None)],
    'sans':          [('C:/Windows/Fonts/arialbd.ttf', None), ('DejaVuSans-Bold.ttf', None)],
    'serif':         [('C:/Windows/Fonts/times.ttf', None), ('DejaVuSerif.ttf', None)],
}

_FONT_DIRS = None


def _font_dirs():
    global _FONT_DIRS
    if _FONT_DIRS is None:
        _FONT_DIRS = [root(SUB['assets'], 'fonts'), os.path.join(KIT, 'fonts'), 'C:/Windows/Fonts',
                      os.path.expandvars(r'%LOCALAPPDATA%/Microsoft/Windows/Fonts'),
                      '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/liberation',
                      '/usr/share/fonts/truetype/freefont', '/usr/share/fonts/truetype']
    return _FONT_DIRS


def font_file(key):
    """Resout une cle de police (ou un chemin) -> (chemin, axes)."""
    if os.path.isfile(str(key)):
        return key, None
    for fname, axes in FONT_DB.get(key, [(key, None)]):
        if os.path.isabs(fname) or ':' in fname[:3]:
            if os.path.isfile(fname):
                return fname, axes
            continue
        for dd in _font_dirs():
            p = os.path.join(dd, fname)
            if os.path.isfile(p):
                return p, axes
    return None, None


_FCACHE = {}


def get_font(key, size):
    from PIL import ImageFont
    k = (key, int(size))
    if k in _FCACHE:
        return _FCACHE[k]
    path, axes = font_file(key)
    if not path:
        path, axes = font_file('sans')
    f = ImageFont.truetype(path, int(size))
    if axes:
        try:
            names = [a['name'].decode() if isinstance(a['name'], bytes) else a['name'] for a in f.get_variation_axes()]
            vals = []
            for a, n in zip(f.get_variation_axes(), names):
                v = axes.get(n, a.get('default'))
                vals.append(max(a['minimum'], min(a['maximum'], v)))
            f.set_variation_by_axes(vals)
        except Exception:
            pass
    _FCACHE[k] = f
    return f


def log(*a):
    print(*a, flush=True)
