"""Moteur de montage (agent 3) : rend chaque plan depuis les rushes et assemble la base video.

python rf.py edit build <spec.json> [--canvas 1080x1920] [--only s1,s2]
python rf.py edit raw <spec.json> <shot> <i,j,k> <prefix> [--canvas WxH]   (images non etalonnees, pour silhouettes)
python rf.py edit gradetest --clip "First Vlog/C0490" --t 12 --grades G1,G2,match --ref <ID> --shot 3 [--canvas WxH]
python rf.py edit presets

Plan (shot) dans spec.json :
 {"name":"s1", "clip":"First Vlog/C0490", "start":6.0, "frames":91,
  "z0":1.9, "z1":1.97, "cx":0.66, "cy":0.27,          zoom progressif et centre (0..1 dans l'image source)
  "speed":"auto"|0.48|1, "reverse":false, "freeze":false,
  "exposure":"auto"|1.2|null, "grade":"G1"|"match"|"<filtre ffmpeg>", "post":["RGB","flash_in"],
  "punch":[0.12,5], "shake":[0.01,3], "trans_in":{"type":"fadewhite","frames":4},
  "color":"white" (plan de couleur unie), "note":"..."}
"""
import hashlib, json, math, os, shutil, sys
import numpy as np
from . import common as C

# --- Etalonnages de la methode (mesures sur les references, session du 27-11) + looks complementaires
GRADES = {
    'G1': ("eq=saturation=0.28,curves=master='0/0.03 0.2/0.06 0.45/0.12 0.7/0.29 0.9/0.55 1/0.76',"
           "colorbalance=rs=-0.06:bs=0.05:rm=-0.09:gm=0.02:bm=0.06:rh=-0.04:bh=0.02,vignette=angle=PI/3.5,noise=alls=9:allf=t"),
    'G2': ("eq=saturation=0.5,curves=master='0/0 0.25/0.05 0.5/0.16 0.75/0.38 1/0.8',"
           "colorbalance=rs=-0.03:bs=0.03:rm=-0.06:gm=0.02:bm=0.04:rh=-0.06:gh=0.02:bh=0.05,vignette=angle=PI/4,noise=alls=7:allf=t"),
    'G3': ("eq=saturation=0.45,vignette=angle=PI/5,curves=master='0/0.1 0.3/0.19 0.6/0.34 1/0.52',"
           "colorbalance=rs=0.05:gs=-0.01:bs=0.02:rm=-0.08:gm=0.03:bm=0.05:rh=-0.05:gh=0.02:bh=0.03,gblur=sigma=0.7,noise=alls=8:allf=t"),
    'teal_orange': ("eq=saturation=1.08:contrast=1.08,colorbalance=rs=-0.08:gs=0.02:bs=0.10:rm=0.03:bm=-0.03:rh=0.08:gh=0.02:bh=-0.08,"
                    "curves=master='0/0.02 0.25/0.2 0.75/0.8 1/0.97',vignette=angle=PI/5"),
    'cold_night': ("eq=saturation=0.6:contrast=1.1:brightness=-0.04,colorbalance=rs=-0.08:bs=0.1:rm=-0.06:bm=0.08:rh=-0.02:bh=0.04,"
                   "curves=master='0/0.02 0.5/0.42 1/0.92',vignette=angle=PI/4,noise=alls=5:allf=t"),
    'warm_film': ("eq=saturation=0.9:contrast=1.04,colorbalance=rs=0.04:bs=-0.04:rm=0.05:gm=0.01:bm=-0.04:rh=0.03:bh=-0.05,"
                  "curves=master='0/0.05 0.5/0.5 1/0.93',vignette=angle=PI/5,noise=alls=6:allf=t"),
    'bleach': "eq=saturation=0.45:contrast=1.28:gamma=0.95,curves=master='0/0 0.2/0.12 0.8/0.9 1/1',vignette=angle=PI/5",
    'mono_contrast': "hue=s=0,eq=contrast=1.35:gamma=0.9,curves=master='0/0 0.15/0.05 0.85/0.95 1/1',vignette=angle=PI/4,noise=alls=8:allf=t",
    'faded_matte': "eq=saturation=0.75:contrast=0.92,curves=master='0/0.08 0.5/0.5 1/0.9',colorbalance=bs=0.03:rh=0.02",
    'clean_punchy': "eq=saturation=1.15:contrast=1.08,unsharp=5:5:0.6",
    'neutral': "eq=contrast=1.04:saturation=1.02",
    'none': '',
}
POST = {
    'RED': "colorbalance=rs=0.10:rm=0.09:gm=-0.035:bm=-0.01:rh=0.04",
    'RED_STRONG': "colorbalance=rs=0.25:rm=0.25:gm=-0.12:bm=-0.06:rh=0.1",
    'RGB': "rgbashift=rh=-10:bh=10",
    'RGB_BIG': "rgbashift=rh=-24:bh=24:gv=6",
    'flash_in': "fade=t=in:st=0:d=0.17:color=white",
    'fade_in': "fade=t=in:st=0:d=0.4",
    'blur': "gblur=sigma=6",
    'mblur': "tmix=frames=3:weights='1 2 1'",
    'bw': "hue=s=0",
    'invert': "negate",
    'grain': "noise=alls=12:allf=t",
    'vignette': "vignette=angle=PI/4",
    'glow': "split[a][b];[b]gblur=sigma=18,eq=brightness=0.06[g];[a][g]blend=all_mode=screen:all_opacity=0.35",
    'sharpen': "unsharp=5:5:0.8",
    'letterbox': "drawbox=x=0:y=0:w=iw:h=ih*0.12:color=black:t=fill,drawbox=x=0:y=ih*0.88:w=iw:h=ih*0.12:color=black:t=fill",
    'vhs': "rgbashift=rh=-4:bh=4,noise=alls=18:allf=t,eq=saturation=0.8,gblur=sigma=0.8",
}
XFADE = {'fade', 'fadeblack', 'fadewhite', 'dissolve', 'smoothleft', 'smoothright', 'smoothup', 'smoothdown', 'slideleft',
         'slideright', 'slideup', 'slidedown', 'wipeleft', 'wiperight', 'wipeup', 'wipedown', 'circleopen', 'circleclose',
         'radial', 'zoomin', 'hblur', 'pixelize', 'distance', 'squeezeh', 'squeezev', 'hlslice', 'hrslice', 'fadegrays',
         'diagtl', 'diagbr', 'rectcrop', 'circlecrop', 'horzopen', 'vertopen'}
ALIASES = {'whip': 'smoothleft', 'whip_up': 'smoothup', 'flash': 'fadewhite', 'dip_black': 'fadeblack', 'blur': 'hblur',
           'zoom': 'zoomin', 'cross': 'fade'}

_PROBE = {}


def find_clip(clip):
    if os.path.isfile(clip):
        return clip
    cfg = C.load_config()
    roots = cfg.get('rush_roots', [])
    base, ext = os.path.splitext(clip)
    cands = [clip] if ext else [clip + e for e in ('.MP4', '.mp4', '.MOV', '.mov', '.MXF', '.m4v')]
    for r in roots:
        for c in cands:
            p = os.path.join(r, c)
            if os.path.isfile(p):
                return p
    raise FileNotFoundError('Clip introuvable : %s (racines %s)' % (clip, roots))


def probe(path):
    if path not in _PROBE:
        _PROBE[path] = C.probe(path)
    return _PROBE[path]


def canvas_of(spec, override=None):
    if override:
        w, h = [int(x) for x in override.lower().split('x')]
        return w, h
    return tuple(spec.get('canvas', C.load_config()['canvas']))


def grade_filter(name, spec):
    if name is None:
        name = spec.get('grade', 'neutral')
    custom = spec.get('grades', {})
    parts = []
    for n in (name if isinstance(name, list) else [name]):
        if n in custom: parts.append(custom[n])
        elif n in GRADES: parts.append(GRADES[n])
        elif n: parts.append(n)
    return ','.join(p for p in parts if p)


def post_filter(post, spec):
    if not post:
        return ''
    if isinstance(post, str):
        post = [x for x in post.split(',') if x] if post in POST or post.split(',')[0] in POST else [post]
    custom = spec.get('post_presets', {})
    out = []
    for p in post:
        out.append(custom.get(p) or POST.get(p) or p)
    return ','.join(out)


def speed_of(s, spec, pr):
    sp = s.get('speed', spec.get('speed', 'auto'))
    fps = spec['fps']
    if sp in (None, 'auto'):
        return round(fps / pr['fps'], 6) if pr['fps'] >= 47 and fps <= 31 else 1.0
    return float(sp)


def window(pr, W, H, cx, cy):
    """Fenetre de base (aspect du canevas) dans l'image source, centree sur (cx, cy)."""
    pw, ph = pr['w'], pr['h']; A = W / H
    if pw / ph > A:
        bh = ph; bw = int(round(ph * A / 2) * 2)
    else:
        bw = pw; bh = int(round(pw / A / 2) * 2)
    x0 = int(min(max(cx * pw - bw / 2, 0), pw - bw)); y0 = int(min(max(cy * ph - bh / 2, 0), ph - bh))
    ux = (cx * pw - x0) / bw; uy = (cy * ph - y0) / bh
    return bw, bh, x0, y0, ux, uy


def luma_at(path, t, crop=None):
    vf = (crop + ',' if crop else '') + 'scale=160:-2,format=gray'
    import subprocess
    p = subprocess.run([C.ff(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', '%.3f' % t, '-i', path,
                        '-frames:v', '1', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True)
    if not p.stdout:
        return 0.4
    return np.frombuffer(p.stdout, np.uint8).mean() / 255


def match_lut(src_stats, ref_stats, strength=1.0):
    """Transfert de couleur moyenne/ecart-type par canal (Reinhard RGB) -> filtre lutrgb."""
    exprs = []
    for c, ch in enumerate('rgb'):
        ms, ss = src_stats['mean_rgb'][c], max(src_stats['std_rgb'][c], 1)
        mt, st = ref_stats['mean_rgb'][c], max(ref_stats['std_rgb'][c], 1)
        k = 1 + (st / ss - 1) * strength; mt2 = ms + (mt - ms) * strength
        exprs.append("%s='clip((val-%.2f)*%.4f+%.2f,0,255)'" % (ch, ms, k, mt2))
    return 'lutrgb=' + ':'.join(exprs)


def shot_filters(s, spec, W, H, raw=False):
    fps = spec['fps']
    if s.get('color'):
        return None, 0, 1
    src = find_clip(s['clip']); pr = probe(src)
    sp = speed_of(s, spec, pr)
    cx, cy = s.get('cx', 0.5), s.get('cy', 0.5)
    bw, bh, x0, y0, ux, uy = window(pr, W, H, cx, cy)
    crop = 'crop=%d:%d:%d:%d' % (bw, bh, x0, y0)
    nf = int(s['frames'])
    z0 = float(s.get('z0', 1.0)); z1 = float(s.get('z1', z0))
    rate = (z1 - z0) / max(nf - 1, 1)
    zexpr = '%.5f+%.7f*on' % (z0, rate)
    if s.get('punch'):
        pa, pn = s['punch']; zexpr += '+%.4f*max(0\\,1-on/%d)' % (pa, max(1, int(pn)))
    xs = ys = ''
    if s.get('shake'):
        sa, sf = s['shake']; xs = '+%.4f*iw*sin(on*%.3f)' % (sa, sf); ys = '+%.4f*ih*cos(on*%.3f)' % (sa, sf * 1.37)
    pre = []
    if s.get('reverse'):
        pre.append('reverse')
    pre.append('setpts=(PTS-STARTPTS)/%.6f' % sp)
    pre.append('fps=%s' % fps)
    if s.get('freeze'):
        pre = ['trim=end_frame=1', 'loop=loop=%d:size=1:start=0' % (nf + 2), 'setpts=N/%s/TB' % fps]
    pre.append(crop)
    static = abs(z1 - 1) < 1e-6 and abs(z0 - 1) < 1e-6 and not s.get('punch') and not s.get('shake')
    if static:
        geo = ['scale=%d:%d:flags=lanczos' % (W, H)]
    else:
        geo = ['scale=%d:%d:flags=lanczos' % (W * 2, H * 2),
               "zoompan=z='%s':x='max(0\\,min(iw-iw/zoom\\,%.4f*iw-iw/zoom/2%s))':y='max(0\\,min(ih-ih/zoom\\,%.4f*ih-ih/zoom/2%s))':d=1:s=%dx%d:fps=%s"
               % (zexpr, ux, xs, uy, ys, W, H, fps)]
    chain = pre + geo
    if raw:
        return ','.join(chain + ['setsar=1', 'format=rgb24']), sp, None
    exp = s.get('exposure', spec.get('exposure', 'auto'))
    g = None
    grade_name = s.get('grade', spec.get('grade'))
    if grade_name == 'match' or (isinstance(grade_name, str) and grade_name.startswith('match')):
        ref_stats = s.get('match_stats') or spec.get('match_stats')
        if ref_stats:
            im = C.frame_at(src, s.get('start', 0) + 0.2, 480, vf=crop)
            chain.append(match_lut(C.img_stats(im), ref_stats, float(s.get('match_strength', 0.85))))
        extra = grade_name.split(':', 1)[1] if ':' in grade_name else ''
        gf = grade_filter(extra, spec) if extra else ''
    else:
        if exp == 'auto':
            m = luma_at(src, s.get('start', 0) + 0.2, crop)
            tgt = float(spec.get('exposure_target', 0.40))
            g = min(3.0, max(0.6, math.log(max(m, 0.02)) / math.log(tgt)))
            chain.append('eq=gamma=%.3f' % g)
        elif isinstance(exp, (int, float)):
            chain.append('eq=gamma=%.3f' % exp)
        gf = grade_filter(grade_name, spec)
    if gf: chain.append(gf)
    pf = post_filter(s.get('post'), spec)
    if pf: chain.append(pf)
    chain += ['setsar=1', 'format=yuv420p']
    return ','.join(chain), sp, g


def render_shot(s, spec, W, H, out, extra_frames=0):
    fps = spec['fps']; nf = int(s['frames']) + int(extra_frames)
    enc = ['-an', '-c:v', 'libx264', '-crf', '12', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', str(fps),
           '-frames:v', str(nf), out]
    if s.get('color'):
        pf = post_filter(s.get('post'), spec)
        C.ffmpeg('-f', 'lavfi', '-i', 'color=c=%s:s=%dx%d:r=%s' % (s['color'], W, H, fps),
                 *(['-vf', pf + ',setsar=1,format=yuv420p'] if pf else ['-vf', 'setsar=1,format=yuv420p']), *enc)
        return {'gamma': None, 'speed': None}
    s2 = dict(s, frames=nf)
    vf, sp, g = shot_filters(s2, spec, W, H)
    src = find_clip(s['clip']); pr = probe(src)
    need = nf / fps * sp + 0.4
    inp = []
    ext = os.path.splitext(src)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.webp'):
        inp = ['-loop', '1', '-framerate', str(fps), '-t', '%.3f' % (nf / fps + 0.5), '-i', src]
    else:
        st = float(s.get('start', 0))
        if st + need > pr['dur'] + 0.05 and not s.get('freeze'):
            C.log('  ! %s: le plan depasse la fin du clip (%.2f+%.2f > %.2f) -> debut recule' % (s.get('name'), st, need, pr['dur']))
            st = max(0, pr['dur'] - need)
        inp = ['-ss', '%.3f' % st, '-t', '%.3f' % need, '-i', src]
    C.ffmpeg(*inp, '-vf', vf, *enc)
    return {'gamma': g, 'speed': sp}


def build(spec_path, canvas=None, only=None):
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    W, H = canvas_of(spec, canvas); fps = spec['fps']
    bdir = os.path.join(pdir, 'build_%dx%d' % (W, H)); os.makedirs(bdir, exist_ok=True)
    shots = spec['shots']
    trans = {}
    for i, s in enumerate(shots):
        t = s.get('trans_in')
        if t and i > 0:
            typ = ALIASES.get(t.get('type'), t.get('type'))
            if typ not in XFADE:
                raise ValueError('transition inconnue %s' % t.get('type'))
            trans[i] = (typ, int(t.get('frames', 6)))
    starts, acc = [], 0
    for s in shots:
        starts.append(acc); acc += int(s['frames'])
    log = []
    for i, s in enumerate(shots):
        name = s.get('name', 's%02d' % i)
        out = os.path.join(bdir, 'shot_%03d_%s.mp4' % (i, C.slug(name, 20)))
        extra = trans.get(i + 1, (None, 0))[1]
        key = hashlib.md5(json.dumps([s, extra, W, H, fps, spec.get('grade'), spec.get('grades'), spec.get('exposure_target'),
                                      spec.get('speed'), spec.get('match_stats') if s.get('grade', spec.get('grade', '')).startswith('match') else 0],
                                     sort_keys=True).encode()).hexdigest()[:10]
        stamp = out + '.key'
        if (only and name not in only) or (os.path.isfile(out) and os.path.isfile(stamp) and open(stamp).read() == key):
            if not only or name not in only:
                log.append((name, 'cache')); continue
        info = render_shot(s, spec, W, H, out, extra)
        open(stamp, 'w').write(key)
        log.append((name, info)); C.log('  plan %-8s %4d img  debut %5d  %s' % (name, s['frames'], starts[i], info))
    files = [os.path.join(bdir, 'shot_%03d_%s.mp4' % (i, C.slug(s.get('name', 's%02d' % i), 20))) for i, s in enumerate(shots)]
    base = os.path.join(bdir, 'base.mp4')
    # Segments sans transition -> concat demuxer (copie exacte image par image),
    # puis xfade entre segments uniquement (le filtre concat perd des images sur les plans d'1 image).
    runs, cur = [], [0]
    for i in range(1, len(files)):
        if i in trans:
            runs.append(cur); cur = [i]
        else:
            cur.append(i)
    runs.append(cur)
    run_files = []
    for k, r in enumerate(runs):
        lst = os.path.join(bdir, 'list_%d.txt' % k)
        with open(lst, 'w', encoding='utf-8') as f:
            for i in r: f.write("file '%s'\n" % os.path.basename(files[i]))
        rf_ = base if len(runs) == 1 else os.path.join(bdir, 'run_%d.mp4' % k)
        C.ffmpeg('-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', rf_)
        run_files.append(rf_)
    if len(runs) > 1:
        args = []
        for p in run_files: args += ['-i', p]
        fc = ['[%d:v]setsar=1,fps=%s,settb=AVTB,format=yuv420p[n%d]' % (i, fps, i) for i in range(len(run_files))]
        last = '[n0]'
        for k in range(1, len(runs)):
            i = runs[k][0]; typ, n = trans[i]
            fc.append('%s[n%d]xfade=transition=%s:duration=%.6f:offset=%.6f[v%d]' % (last, k, typ, n / fps, starts[i] / fps, k))
            last = '[v%d]' % k
        total_f = sum(int(x['frames']) for x in shots)
        C.ffmpeg(*args, '-filter_complex', ';'.join(fc) + ';%strim=end_frame=%d,format=yuv420p[out]' % (last, total_f),
                 '-map', '[out]', '-c:v', 'libx264', '-crf', '12', '-preset', 'medium', '-r', str(fps), base)
    total = sum(int(s['frames']) for s in shots)
    pr = C.probe(base)
    got = count_frames(base)
    C.log('base %s : %d images attendues, %d obtenues, %.3f s (%dx%d)' % (base, total, got, pr['dur'], pr['w'], pr['h']))
    if got != total:
        C.log('  ! ATTENTION : nombre d\'images different -> verifier la synchro')
    return base, total


def count_frames(path):
    p = C.run([C.ffp(), '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_packets',
               '-of', 'csv=p=0', path], capture=True)
    try:
        return int((p.stdout or '0').strip().split(',')[0])
    except ValueError:
        return -1


def raw_frames(spec_path, shot_name, idx, prefix, canvas=None):
    spec = C.jload(spec_path); W, H = canvas_of(spec, canvas)
    s = [x for x in spec['shots'] if x.get('name') == shot_name][0]
    s2 = dict(s, frames=max(idx) + 1)
    vf, sp, _ = shot_filters(s2, spec, W, H, raw=True)
    src = find_clip(s['clip'])
    os.makedirs(os.path.dirname(os.path.abspath(prefix)), exist_ok=True)
    C.ffmpeg('-ss', '%.3f' % float(s.get('start', 0)), '-t', '%.3f' % ((max(idx) + 2) / spec['fps'] * sp + 0.3), '-i', src,
             '-an', '-vf', vf, '-frames:v', str(max(idx) + 1), prefix + '_%03d.png')
    return [prefix + '_%03d.png' % (i + 1) for i in idx]


def gradetest(clip, t, grades, canvas='1080x1920', ref=None, shot=None, cx=0.5, cy=0.5, out=None):
    W, H = [int(x) for x in canvas.split('x')]
    src = find_clip(clip); pr = probe(src)
    bw, bh, x0, y0, ux, uy = window(pr, W, H, cx, cy)
    crop = 'crop=%d:%d:%d:%d,scale=%d:-2' % (bw, bh, x0, y0, 360 if H > W else 640)
    tiles, labels = [], []
    ref_stats = None
    if ref:
        an = C.jload(os.path.join(C.d('refs', ref), 'analysis.json'))
        sh = an['shots'][int(shot or 0)]; ref_stats = sh
        im = C.frame_at(an['path'], (sh['t0'] + sh['t1']) / 2, 360 if H > W else 640)
        tiles.append(im); labels.append('REF #%s l%.2f s%.2f w%+.2f' % (shot, sh['luma'], sh['sat'], sh['warmth']))
    base = C.frame_at(src, t, 480, vf=crop.split(',scale')[0])
    for gname in grades:
        if gname == 'match' and ref_stats:
            vf = crop + ',' + match_lut(C.img_stats(base), ref_stats)
        else:
            m = luma_at(src, t, crop.split(',scale')[0]); g = min(3.0, max(0.6, math.log(max(m, 0.02)) / math.log(0.40)))
            vf = crop + ',eq=gamma=%.3f' % g + (',' + grade_filter(gname, {}) if grade_filter(gname, {}) else '')
        im = C.frame_at(src, t, 360 if H > W else 640, vf=vf)
        st = C.img_stats(im)
        tiles.append(im); labels.append('%s l%.2f s%.2f w%+.2f' % (gname, st['luma'], st['sat'], st['warmth']))
    out = out or os.path.join(C.d('index'), 'gradetest_%s.jpg' % C.slug(clip + '_' + str(t)))
    C.sheet(tiles, labels, cols=min(6, len(tiles)), out=out, tile_w=360 if H > W else 480)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py edit')
    ap.add_argument('cmd', choices=['build', 'raw', 'gradetest', 'presets'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--canvas'); ap.add_argument('--only')
    ap.add_argument('--clip'); ap.add_argument('--t', type=float, default=1.0); ap.add_argument('--grades', default='G1,G2,G3')
    ap.add_argument('--ref'); ap.add_argument('--shot'); ap.add_argument('--cx', type=float, default=0.5); ap.add_argument('--cy', type=float, default=0.5)
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        build(a.args[0], a.canvas, a.only.split(',') if a.only else None)
    elif a.cmd == 'raw':
        C.log(raw_frames(a.args[0], a.args[1], [int(x) for x in a.args[2].split(',')], a.args[3], a.canvas))
    elif a.cmd == 'gradetest':
        C.log(gradetest(a.clip, a.t, a.grades.split(','), a.canvas or '1080x1920', a.ref, a.shot, a.cx, a.cy))
    else:
        for k, v in GRADES.items(): C.log('GRADE %-14s %s' % (k, v[:90]))
        for k, v in POST.items(): C.log('POST  %-14s %s' % (k, v[:90]))
        C.log('TRANSITIONS', sorted(XFADE), 'alias', ALIASES)
