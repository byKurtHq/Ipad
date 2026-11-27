"""Calque texte anime (typographie de la methode) -> sequence PNG transparente.

python rf.py text render <spec.json> [--canvas 1080x1920]
python rf.py text preview <spec.json> --t 1.2,3.4 [--canvas WxH]       (images de controle sur la base)
python rf.py text skeleton <REF_ID> [--style serif] [--upper] [--out text_events.json]
       -> un evenement par mot depuis la transcription horodatee (a ajuster : couleurs, positions, empilements)

Bloc "text" de spec.json :
 "text": {
   "colors": {"red": [169,23,29]},
   "styles": {
     "serif": {"font": "didone", "cap": 0.13, "fit": ["ANGER", 0.58], "color": "white",
               "grunge": {"seed": 7, "strength": 0.75}},
     "heavy": {"font": "impact", "cap": 0.11, "fit": ["DON'T", 0.58], "grunge": {"seed": 3, "strength": 0.95, "scale": 2, "t1": 200, "t2": 240}},
     "sub":   {"font": "poppins_xbold", "size": 0.07, "stroke": [0.007, "black"], "shadow": [0.004, 0.006, 0.55]}
   },
   "events": [
     {"t0": 0.25, "t1": 0.46, "text": "MY", "style": "serif", "x": 0.5, "y": 0.49},
     {"t0": 1.20, "t1": 1.66, "parts": [["BE", "white"], ["CAUSE", "red"]], "style": "serif"},
     {"t0": 4.58, "t1": 5.83, "text": "DON'T", "color": "red", "glitch": ["heavy", "serif", "condensed"], "period": 3},
     {"t0": 2.75, "t1": 4.00, "text": "away", "style": "gara", "color": "lav", "italic": true, "underline": true,
      "align": "left", "x": 0.08, "y": 0.49, "anim": "pop"},
     {"t0": 8.0, "t1": 10.0, "karaoke": [["no", 8.0], ["excuses", 8.4]], "style": "sub", "hl": "yellow", "y": 0.66}
   ],
   "images": [{"frames": [4, 6, 8], "png": "sil_1080x1920/sil{n}.png"}],
   "flashes": [{"frame": 10, "color": "white", "alpha": 0.85}]
 }
 Unites : tailles en fraction de min(largeur, hauteur) ; x en fraction de la largeur, y en fraction de la hauteur
 (y = centre des capitales, ou de la hauteur d'x pour un mot en minuscules).
 anim : cut (defaut) | pop | fade | slide_up | zoom_slow | flicker | shake | type (machine a ecrire)
"""
import json, math, os, shutil, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from . import common as C

COLORS = {'white': (245, 244, 245), 'red': (169, 23, 29), 'blood': (150, 10, 18), 'lav': (150, 135, 235),
          'gold': (215, 175, 65), 'salmon': (215, 95, 85), 'lightblue': (150, 205, 245), 'orange': (245, 165, 25),
          'yellow': (255, 214, 10), 'black': (0, 0, 0), 'grey': (170, 170, 170), 'green': (60, 220, 120),
          'cream': (240, 230, 210), 'cyan': (80, 220, 235)}

DEFAULT_STYLES = {
    'serif': {'font': 'didone', 'cap': 0.13, 'fit': ['ANGER', 0.58], 'color': 'white', 'grunge': {'seed': 7, 'strength': 0.75}},
    'heavy': {'font': 'impact', 'cap': 0.11, 'fit': ["DON'T", 0.58], 'grunge': {'seed': 3, 'strength': 0.95, 'scale': 2, 't1': 200, 't2': 240}},
    'condensed': {'font': 'impact', 'cap': 0.139, 'fit': ["DON'T", 0.222], 'grunge': {'seed': 3, 'strength': 0.95, 'scale': 2, 't1': 200, 't2': 240}},
    'gara': {'font': 'garamond', 'italic_font': 'garamond_italic', 'bold_font': 'garamond_bold', 'fit': ['walked', 0.483], 'color': 'white'},
    'gara_big': {'font': 'garamond', 'italic_font': 'garamond_italic', 'bold_font': 'garamond_bold', 'fit': ['human', 0.722], 'color': 'white'},
    'sub': {'font': 'poppins_xbold', 'size': 0.068, 'color': 'white', 'stroke': [0.007, 'black'], 'shadow': [0.003, 0.005, 0.5]},
    'sub_serif': {'font': 'instrument', 'size': 0.085, 'color': 'white', 'shadow': [0.002, 0.004, 0.6]},
    'title': {'font': 'anton', 'size': 0.12, 'color': 'white', 'stroke': [0.004, 'black']},
}


def rgb(c, colors):
    if c is None: return COLORS['white']
    if isinstance(c, (list, tuple)): return tuple(int(x) for x in c[:3])
    if isinstance(c, str) and c.startswith('#'):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(colors.get(c) or COLORS.get(c) or COLORS['white'])


class Grunge:
    _cache = {}

    @classmethod
    def get(cls, W, H, seed=7, strength=0.75, scale=3, t1=224, t2=249):
        k = (W, H, seed, strength, scale, t1, t2)
        if k not in cls._cache:
            rng = np.random.default_rng(seed)
            n1 = np.asarray(Image.fromarray((rng.random((H // scale, W // scale)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32)
            n2 = rng.random((H, W)) * 255
            tex = ((n1 > t1) | (n2 > t2)).astype(np.uint8) * 255
            tex = np.asarray(Image.fromarray(tex).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255
            cls._cache[k] = 1 - np.clip(tex * strength, 0, 1)
        return cls._cache[k]


class Engine:
    def __init__(self, tspec, W, H, fps):
        self.W, self.H, self.fps = W, H, fps
        self.u = min(W, H)
        self.colors = dict(COLORS); self.colors.update({k: tuple(v) for k, v in tspec.get('colors', {}).items()})
        self.styles = dict(DEFAULT_STYLES); self.styles.update(tspec.get('styles', {}))
        self._sz = {}; self._img = {}

    # ---- metrique de police
    def size_of(self, st, font_key):
        k = (json.dumps(st, sort_keys=True), font_key)
        if k in self._sz: return self._sz[k]
        if 'size' in st:
            px = max(8, int(st['size'] * self.u))
        else:
            cap = st.get('cap', 0.12) * self.u
            lo, hi = 8, 2000
            while lo < hi:
                mid = (lo + hi) // 2; b = C.get_font(font_key, mid).getbbox('H')
                if b[3] - b[1] >= cap: hi = mid
                else: lo = mid + 1
            px = lo
        f = C.get_font(font_key, px)
        xs = float(st.get('xscale', 1.0))
        if st.get('fit'):
            word, wf = st['fit']; b = f.getbbox(word)
            xs = wf * self.u / max(1, b[2] - b[0])
            if 'size' not in st and 'cap' not in st:
                # 'fit' seul : on fixe la taille pour obtenir la largeur voulue, sans deformation
                px = max(8, int(px * xs)); f = C.get_font(font_key, px); xs = 1.0
                b = f.getbbox(word); px2 = int(px * wf * self.u / max(1, b[2] - b[0]))
                px = max(8, px2); f = C.get_font(font_key, px)
        self._sz[k] = (px, xs)
        return px, xs

    def word_img(self, parts, st, italic=False, bold=False, underline=False, scale=1.0):
        key = (tuple(parts), json.dumps(st, sort_keys=True), italic, bold, underline, round(scale, 3))
        if key in self._img: return self._img[key]
        font_key = st.get('font', 'didone')
        synth_italic = False
        if italic:
            if st.get('italic_font'): font_key = st['italic_font']
            else: synth_italic = True
        synth_bold = False
        if bold:
            if st.get('bold_font') and not italic: font_key = st['bold_font']
            elif st.get('bold_font') and italic and st.get('bolditalic_font'): font_key = st['bolditalic_font']
            else: synth_bold = True
        px, xs = self.size_of(st, st.get('font', 'didone'))
        px = max(6, int(px * float(st.get('scale', 1.0)) * scale))
        F = C.get_font(font_key, px)
        full = ''.join(t for t, _ in parts)
        bb = F.getbbox(full)
        stroke = st.get('stroke'); sw = int(stroke[0] * self.u) if stroke else 0
        if synth_bold: sw_b = max(1, px // 28)
        else: sw_b = 0
        pad = int(px * 0.35) + sw + sw_b
        w = (bb[2] - bb[0]) + 2 * pad; h = int(px * 1.45) + 2 * pad
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x = pad - bb[0]; y0 = pad
        for t, c in parts:
            col = rgb(c, self.colors)
            if sw:
                d.text((x, y0), t, font=F, fill=col + (255,), stroke_width=sw, stroke_fill=rgb(stroke[1], self.colors) + (255,))
            elif sw_b:
                d.text((x, y0), t, font=F, fill=col + (255,), stroke_width=sw_b, stroke_fill=col + (255,))
            else:
                d.text((x, y0), t, font=F, fill=col + (255,))
            if underline:
                ascent, descent = F.getmetrics(); uy = y0 + ascent + int(px * 0.08)
                d.line([(x, uy), (x + F.getlength(t), uy)], fill=col + (255,), width=max(2, px // 22))
            x += F.getlength(t)
        hb = F.getbbox('H'); xb = F.getbbox('x')
        cap_c = y0 + (hb[1] + hb[3]) / 2; x_c = y0 + (xb[1] + xb[3]) / 2
        if synth_italic:
            sh = 0.22; im = im.transform((w + int(h * sh), h), Image.AFFINE, (1, sh, -h * sh, 0, 1, 0), Image.BICUBIC); w = im.width
        if abs(xs - 1.0) > 1e-3:
            im = im.resize((max(1, int(w * xs)), h), Image.LANCZOS)
        if st.get('shadow'):
            dx, dy, op = st['shadow']
            a = im.split()[3].filter(ImageFilter.GaussianBlur(max(1, px // 30)))
            shadow = Image.new('RGBA', im.size, (0, 0, 0, 0)); shadow.putalpha(a.point(lambda v: int(v * op)))
            base = Image.new('RGBA', (im.width + int(abs(dx) * self.u) + 4, im.height + int(abs(dy) * self.u) + 4), (0, 0, 0, 0))
            base.alpha_composite(shadow, (int(dx * self.u) + 2 if dx > 0 else 2, int(dy * self.u) + 2 if dy > 0 else 2))
            base.alpha_composite(im, (2 if dx > 0 else int(-dx * self.u) + 2, 2 if dy > 0 else int(-dy * self.u) + 2))
            im = base
        if st.get('glow'):
            r, op = st['glow']
            g = im.filter(ImageFilter.GaussianBlur(r * self.u)); ga = np.asarray(g).astype(np.float32); ga[..., 3] *= op
            gl = Image.fromarray(ga.astype(np.uint8)); gl.alpha_composite(im); im = gl
        res = (im, cap_c, x_c, pad)
        self._img[key] = res
        return res

    def place(self, layer, ev, st, parts, fr_rel, n_frames):
        italic = ev.get('italic', st.get('italic', False)); bold = ev.get('bold', st.get('bold', False))
        underline = ev.get('underline', st.get('underline', False))
        anim = ev.get('anim', st.get('anim', 'cut'))
        scale = 1.0; alpha = 1.0; dy = 0.0; dx = 0.0
        if anim == 'pop':
            k = min(1.0, fr_rel / 3.0); scale = 1.18 - 0.18 * (1 - (1 - k) ** 2)
        elif anim == 'fade':
            n = int(ev.get('fade_frames', 4)); alpha = min(1.0, (fr_rel + 1) / n, (n_frames - fr_rel) / n)
        elif anim == 'slide_up':
            k = min(1.0, fr_rel / 4.0); dy = 0.025 * (1 - k) ** 2; alpha = min(1.0, (fr_rel + 1) / 3)
        elif anim == 'zoom_slow':
            scale = 1.0 + 0.06 * fr_rel / max(1, n_frames)
        elif anim == 'flicker':
            alpha = 1.0 if fr_rel > 5 or (fr_rel * 7919) % 3 else 0.25
        elif anim == 'shake':
            dx = 0.004 * math.sin(fr_rel * 2.1); dy = 0.004 * math.cos(fr_rel * 2.9)
        elif anim == 'type':
            full = ''.join(t for t, _ in parts); n_chars = max(1, int(len(full) * min(1.0, (fr_rel + 1) / max(1, ev.get('type_frames', len(full))))))
            out, acc = [], 0
            for t, c in parts:
                if acc >= n_chars: break
                out.append((t[:n_chars - acc], c)); acc += len(t)
            parts = out
        im, cap_c, x_c, pad = self.word_img(parts, st, italic, bold, underline, scale)
        full = ''.join(t for t, _ in parts)
        va = ev.get('vanchor', st.get('vanchor') or ('cap' if full.upper() == full else 'x'))
        cy = {'cap': cap_c, 'x': x_c, 'box': im.height / 2}[va]
        x = (ev.get('x', st.get('x', 0.5)) + dx) * self.W; y = (ev.get('y', st.get('y', 0.49)) + dy) * self.H
        al = ev.get('align', st.get('align', 'center'))
        if al == 'center': px = int(x - im.width / 2)
        elif al == 'right': px = int(x - im.width + pad)
        else: px = int(x - pad)
        py = int(y - cy)
        if ev.get('box') or st.get('box'):
            bc = ev.get('box') or st.get('box'); col = rgb(bc[0], self.colors); op = bc[1] if len(bc) > 1 else 0.6
            bpad = int((bc[2] if len(bc) > 2 else 0.015) * self.u)
            a = np.asarray(im.split()[3]); ys, xs = np.nonzero(a > 10)
            if len(xs):
                d = ImageDraw.Draw(layer)
                d.rounded_rectangle([px + xs.min() - bpad, py + ys.min() - bpad, px + xs.max() + bpad, py + ys.max() + bpad],
                                    radius=bpad, fill=col + (int(255 * op),))
        g = st.get('grunge')
        if g or alpha < 1:
            a = np.asarray(im).astype(np.float32)
            if g:
                tex = Grunge.get(self.W, self.H, g.get('seed', 7), g.get('strength', 0.75), g.get('scale', 3), g.get('t1', 224), g.get('t2', 249))
                x0, y0 = max(0, px), max(0, py); x1, y1 = min(self.W, px + im.width), min(self.H, py + im.height)
                if x1 > x0 and y1 > y0:
                    a[y0 - py:y1 - py, x0 - px:x1 - px, 3] *= tex[y0:y1, x0:x1]
            a[..., 3] *= alpha
            im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        layer.alpha_composite(im, (px, py)) if px >= 0 and py >= 0 and px + im.width <= self.W and py + im.height <= self.H else _paste_clip(layer, im, px, py)
        return (tuple(parts), round(scale, 3), round(alpha, 2), px, py)


def _paste_clip(layer, im, px, py):
    x0, y0 = max(0, -px), max(0, -py)
    crop = im.crop((x0, y0, min(im.width, layer.width - px), min(im.height, layer.height - py)))
    if crop.width > 0 and crop.height > 0:
        layer.alpha_composite(crop, (max(0, px), max(0, py)))


def render(spec_path, canvas=None, frames=None):
    from .edit import canvas_of
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    W, H = canvas_of(spec, canvas); fps = spec['fps']
    total = frames or sum(int(s['frames']) for s in spec['shots'])
    ts = spec.get('text', {})
    eng = Engine(ts, W, H, fps)
    out = os.path.join(pdir, 'layer_%dx%d' % (W, H))
    if os.path.isdir(out): shutil.rmtree(out)
    os.makedirs(out)
    evs = []
    for k, e in enumerate(ts.get('events', [])):
        f0 = int(round(e['t0'] * fps)) if 'f0' not in e else int(e['f0'])
        f1 = int(round(e['t1'] * fps)) - 1 if 'f1' not in e else int(e['f1'])
        evs.append((f0, f1, k, e))
    imgs = {}
    sil_imgs = [{'frames': j['at'], 'png': 'sil_%dx%d/sil{n}.png' % (W, H)} for j in spec.get('silhouettes', [])]
    for im in ts.get('images', []) + sil_imgs:
        for n in im.get('frames', [im.get('frame')]):
            p = im['png'].replace('{n}', str(n))
            p = p if os.path.isabs(p) else os.path.join(pdir, p)
            if os.path.isfile(p): imgs.setdefault(n, []).append(p)
            else: C.log('  ! image absente', p)
    flashes = {}
    for fl in ts.get('flashes', []):
        for n in fl.get('frames', [fl.get('frame')]):
            flashes[n] = fl
    empty = None; last = None; lastkey = None; n_written = 0
    for fr in range(total):
        active = [(f0, f1, k, e) for (f0, f1, k, e) in evs if f0 <= fr <= f1]
        if not active and fr not in imgs and fr not in flashes:
            p = os.path.join(out, '%05d.png' % fr)
            if empty is None:
                empty = p; Image.new('RGBA', (W, H), (0, 0, 0, 0)).save(p, compress_level=1)
            else:
                _dup(empty, p)
            lastkey = None
            continue
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); key = [fr if (fr in imgs or fr in flashes) else None]
        if fr in flashes:
            fl = flashes[fr]; col = rgb(fl.get('color', 'white'), eng.colors)
            layer.alpha_composite(Image.new('RGBA', (W, H), col + (int(255 * fl.get('alpha', 0.85)),)))
        for p in imgs.get(fr, []):
            im = Image.open(p).convert('RGBA')
            if im.size != (W, H): im = im.resize((W, H), Image.LANCZOS)
            layer.alpha_composite(im)
        for f0, f1, k, e in sorted(active, key=lambda a: a[3].get('z', 0)):
            st = dict(eng.styles.get(e.get('style', 'serif'), {}))
            rel = fr - f0; n = f1 - f0 + 1
            if e.get('glitch'):
                per = int(e.get('period', 3)); names = e['glitch']
                st = dict(eng.styles.get(names[(rel // per) % len(names)], {}))
            st.update(e.get('style_override', {}))
            if 'karaoke' in e:
                words = e['karaoke']; t = fr / fps; parts = []
                for i, (w, tw) in enumerate(words):
                    on = tw <= t < (words[i + 1][1] if i + 1 < len(words) else e['t1'] + 1)
                    parts.append((w + (' ' if i < len(words) - 1 else ''), e.get('hl', 'yellow') if on else e.get('color', st.get('color', 'white'))))
            elif 'parts' in e:
                parts = [(t, c) for t, c in e['parts']]
            else:
                parts = [(e['text'], e.get('color', st.get('color', 'white')))]
            key.append((k, eng.place(layer, e, st, parts, rel, n)))
        key = tuple(key)
        p = os.path.join(out, '%05d.png' % fr)
        if key == lastkey and last:
            _dup(last, p)
        else:
            layer.save(p, compress_level=1); last = p; lastkey = key; n_written += 1
    C.log('calque texte %s : %d images (%d uniques)' % (out, total, n_written))
    return out


def _dup(src, dst):
    try:
        os.link(src, dst)
    except Exception:
        shutil.copyfile(src, dst)


def skeleton(ref, style='serif', upper=False, out=None, y=0.49):
    an = C.jload(os.path.join(C.d('refs', ref), 'analysis.json'))
    words = (an.get('transcript') or {}).get('words') or []
    evs = []
    for i, w in enumerate(words):
        t1 = words[i + 1]['t0'] if i + 1 < len(words) and words[i + 1]['t0'] - w['t1'] < 0.6 else w['t1'] + 0.15
        txt = w['w'].strip(' ,.!?;:"')
        evs.append({'t0': w['t0'], 't1': round(t1, 3), 'text': txt.upper() if upper else txt, 'style': style, 'x': 0.5, 'y': y})
    out = out or os.path.join(C.d('projects', ref), 'text_events.json')
    C.jsave(out, evs)
    return out, len(evs)


def preview(spec_path, times, canvas=None):
    from .edit import canvas_of
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    W, H = canvas_of(spec, canvas); fps = spec['fps']
    base = os.path.join(pdir, 'build_%dx%d' % (W, H), 'base.mp4'); lay = os.path.join(pdir, 'layer_%dx%d' % (W, H))
    tiles, labels = [], []
    for t in times:
        fr = int(round(t * fps))
        b = C.frame_at(base, (fr + 0.5) / fps, W) if os.path.isfile(base) else Image.new('RGB', (W, H), (40, 40, 40))
        p = os.path.join(lay, '%05d.png' % fr)
        if os.path.isfile(p):
            b = b.convert('RGBA'); b.alpha_composite(Image.open(p).convert('RGBA')); b = b.convert('RGB')
        tiles.append(b); labels.append('%.2fs f%d' % (t, fr))
    out = os.path.join(pdir, 'preview_text.jpg')
    C.sheet(tiles, labels, cols=min(6, len(tiles)), out=out, tile_w=360 if H > W else 640)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py text')
    ap.add_argument('cmd', choices=['render', 'preview', 'skeleton'])
    ap.add_argument('arg'); ap.add_argument('--canvas'); ap.add_argument('--t', default='0.5')
    ap.add_argument('--style', default='serif'); ap.add_argument('--upper', action='store_true'); ap.add_argument('--out')
    a = ap.parse_args(argv)
    if a.cmd == 'render': render(a.arg, a.canvas)
    elif a.cmd == 'preview': C.log(preview(a.arg, [float(x) for x in a.t.split(',')], a.canvas))
    else: C.log(*skeleton(a.arg, a.style, a.upper, a.out))
