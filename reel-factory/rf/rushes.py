"""Index des clips personnels (agent 2) : inventaire, mesures, planches, tags, moments.

python rf.py rushes index [--force]                 -> _index/rushes_index.json + planches/planche_XX.jpg (12 clips / planche)
python rf.py rushes sheet "<clip>" [--every 2] [--from 10 --to 40] [--bright]   -> planche detaillee horodatee d'un clip
python rf.py rushes tag "<clip|dossier/>" person=user outfit="hoodie bleu" framing=close angle=front lying=0 exercise="pec fly" quality=4 exclude=0 notes="..."
python rf.py rushes moment "<clip>" 12.0 18.5 "visage de face pendant la serie" [--q 5] [--framing face] [--angle front] [--mood intense]
python rf.py rushes list [--person user] [--untagged] [--folder "First Vlog"]
python rf.py rushes show "<clip>"
python rf.py rushes usage                           -> clips deja utilises (pour varier)

Valeurs conseillees :
  person  : user | other | none (insert d'objet / decor) | unsure
  framing : face | close | medium | wide | insert | detail
  angle   : front | three_quarter | side | back | low | high | pov
"""
import json, os, re, sys, time
import numpy as np
from . import common as C


def idx_path(): return C.d('index', 'rushes_index.json')
def tags_path(): return C.d('index', 'clip_tags.json')
def usage_path(): return C.d('index', 'usage.json')


def scan():
    cfg = C.load_config(); out = []
    for r in cfg['rush_roots']:
        for dp, dn, fn in os.walk(r):
            dn[:] = [x for x in dn if not x.startswith('.')]
            for f in sorted(fn):
                if os.path.splitext(f)[1].lower() in cfg['video_ext'] and not f.startswith('._'):
                    p = os.path.join(dp, f)
                    rel = os.path.relpath(p, r).replace('\\', '/')
                    key = os.path.splitext(rel)[0] if len(cfg['rush_roots']) == 1 else os.path.basename(r) + '/' + os.path.splitext(rel)[0]
                    out.append((key, p))
    return sorted(out, key=lambda kp: kp[0].lower())


def lap_var(g):
    g = g.astype(np.float32)
    l = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(l.var())


def measure(path, pr):
    """Mesures sur les images cles (rapide) : luminance, saturation, chaleur, nettete, mouvement."""
    w = 128; h = max(2, int(round(pr['h'] * w / max(pr['w'], 1) / 2) * 2))
    series = []; prev = None; prev_t = None
    for t, fr in C.iter_frames(path, w, h, keyframes_only=True, with_pts=True):
        f = fr.astype(np.float32); L = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        mx, mn = f.max(2), f.min(2)
        sat = float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0).mean())
        mot = float(np.abs(L - prev).mean() / max(0.2, (t - prev_t))) if prev is not None and t is not None and prev_t is not None else 0.0
        series.append([round(t or 0, 2), round(float(L.mean()) / 255, 3), round(sat, 3), round(float((f[..., 0] - f[..., 2]).mean()) / 255, 3),
                       round(lap_var(L), 1), round(mot, 2)])
        prev, prev_t = L, t
    if not series:
        return {}, []
    a = np.array(series)
    st = {'luma': round(float(a[:, 1].mean()), 3), 'sat': round(float(a[:, 2].mean()), 3), 'warmth': round(float(a[:, 3].mean()), 3),
          'sharp': round(float(np.median(a[:, 4])), 1), 'motion': round(float(np.median(a[1:, 5])) if len(a) > 1 else 0, 2)}
    return st, series


def index(force=False):
    I = C.jload(idx_path(), {'clips': {}})
    found = scan(); t0 = time.time()
    C.log('%d clips trouves' % len(found))
    for n, (key, p) in enumerate(found, 1):
        stt = os.stat(p); sig = '%d_%d' % (stt.st_size, int(stt.st_mtime))
        c = I['clips'].get(key)
        if c and c.get('sig') == sig and not force:
            continue
        try:
            pr = C.probe(p)
        except Exception as e:
            C.log('  ! illisible', key, e); continue
        st, series = measure(p, pr)
        I['clips'][key] = {'key': key, 'path': p, 'folder': os.path.dirname(key), 'sig': sig, 'dur': round(pr['dur'], 2),
                           'w': pr['w'], 'h': pr['h'], 'fps': round(pr['fps'], 3), 'audio': pr['audio'],
                           'size_mb': round(pr['size'] / 1e6, 1), 'stats': st, 'series': series}
        if n % 10 == 0:
            C.jsave(idx_path(), I); C.log('  %d/%d (%.0f s)' % (n, len(found), time.time() - t0))
    keys = [k for k, _ in found]
    I['clips'] = {k: I['clips'][k] for k in keys if k in I['clips']}
    for i, k in enumerate(keys, 1):
        if k in I['clips']: I['clips'][k]['n'] = i
    C.jsave(idx_path(), I)
    planches(I)
    C.log('index ok : %d clips, %.0f s' % (len(I['clips']), time.time() - t0))
    return I


def planches(I=None, per=12):
    I = I or C.jload(idx_path())
    from PIL import Image, ImageDraw
    tdir = C.d('index', 'thumbs'); pdir = C.d('index', 'planches')
    clips = sorted(I['clips'].values(), key=lambda c: c['n'])
    tags = C.jload(tags_path(), {})
    lab = C.font_label(22)
    for pg in range(0, len(clips), per):
        chunk = clips[pg:pg + per]
        tw, th = 300, 169
        sh = Image.new('RGB', (2 * 3 * tw + 10, 6 * (th + 30)), (14, 14, 14)); d = ImageDraw.Draw(sh)
        for k, c in enumerate(chunk):
            col, row = k % 2, k // 2; x0 = col * (3 * tw + 10); y0 = row * (th + 30)
            tg = tags.get(c['key'], {})
            txt = '#%d %s  %.0fs %dx%d %.0fi/s %s' % (c['n'], c['key'], c['dur'], c['w'], c['h'], c['fps'],
                                                    ('[' + tg.get('person', '') + ']') if tg else '')
            d.text((x0 + 4, y0 + 3), txt[:70], font=lab, fill=(255, 215, 0))
            for j, frac in enumerate((0.15, 0.5, 0.85)):
                tp = os.path.join(tdir, '%s_%d.jpg' % (C.slug(c['key'], 60), j))
                if not os.path.isfile(tp):
                    im = C.frame_at(c['path'], c['dur'] * frac, 320)
                    if im is None: continue
                    im.save(tp, quality=82)
                im = Image.open(tp)
                if im.height > im.width:
                    canvas = Image.new('RGB', (tw, th), (0, 0, 0)); im2 = im.resize((int(th * im.width / im.height), th))
                    canvas.paste(im2, ((tw - im2.width) // 2, 0)); im = canvas
                sh.paste(im.resize((tw, th)), (x0 + j * tw, y0 + 28))
        sh.save(os.path.join(pdir, 'planche_%02d.jpg' % (pg // per + 1)), quality=84)
    C.log('planches ->', pdir)


def clip_sheet(key, every=2.0, t_from=None, t_to=None, bright=False, cols=10):
    I = C.jload(idx_path()); c = I['clips'].get(key) or next((v for k, v in I['clips'].items() if k.endswith(key)), None)
    if not c: raise SystemExit('clip inconnu: %s' % key)
    a = t_from or 0.0; b = min(t_to or c['dur'], c['dur'] - 0.05)
    ts = list(np.arange(a, b, every))[:120]
    vf = 'eq=gamma=1.6' if bright else None
    tiles = [C.frame_at(c['path'], t, 320, vf=vf) for t in ts]
    out = os.path.join(C.d('index', 'sheets'), '%s_%s.jpg' % (C.slug(c['key'], 60), C.slug('%g-%g-%g' % (a, b, every))))
    C.sheet(tiles, ['%.1fs' % t for t in ts], cols=cols, tile_w=256 if c['w'] >= c['h'] else 160, out=out,
            title='%s (%.0f s, %dx%d, %.0f i/s)' % (c['key'], c['dur'], c['w'], c['h'], c['fps']))
    return out


def _parse_kv(items):
    kv = {}
    for it in items:
        k, v = it.split('=', 1)
        if v.lower() in ('1', 'true', 'oui', 'yes'): v = True
        elif v.lower() in ('0', 'false', 'non', 'no'): v = False
        elif re.fullmatch(r'-?\d+(\.\d+)?', v): v = float(v) if '.' in v else int(v)
        kv[k] = v
    return kv


def tag(target, items):
    I = C.jload(idx_path(), {'clips': {}})
    keys = [k for k in I['clips'] if k == target or (target.endswith('/') and k.startswith(target))]
    if not keys:
        keys = [k for k in I['clips'] if k.endswith(target)]
    kv = _parse_kv(items)
    with C.FileLock(tags_path()):
        T = C.jload(tags_path(), {})
        for k in keys:
            T.setdefault(k, {}).update(kv)
        C.jsave(tags_path(), T)
    return keys


def moment(key, t0, t1, desc, q=3, **kw):
    with C.FileLock(tags_path()):
        T = C.jload(tags_path(), {})
        m = {'t0': float(t0), 't1': float(t1), 'desc': desc, 'q': int(q)}
        m.update({k: v for k, v in kw.items() if v is not None})
        T.setdefault(key, {}).setdefault('moments', []).append(m)
        C.jsave(tags_path(), T)


def usage():
    U = C.jload(usage_path(), {})
    for k, v in sorted(U.items(), key=lambda kv: -len(kv[1])):
        C.log('%-40s %d reels : %s' % (k, len(v), ', '.join(sorted({u['reel'] for u in v}))))


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py rushes')
    ap.add_argument('cmd', choices=['index', 'planches', 'sheet', 'tag', 'moment', 'list', 'show', 'usage'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--every', type=float, default=2.0)
    ap.add_argument('--from', dest='t_from', type=float); ap.add_argument('--to', dest='t_to', type=float)
    ap.add_argument('--bright', action='store_true'); ap.add_argument('--q', type=int, default=3)
    ap.add_argument('--framing'); ap.add_argument('--angle'); ap.add_argument('--mood')
    ap.add_argument('--person'); ap.add_argument('--untagged', action='store_true'); ap.add_argument('--folder')
    a = ap.parse_args(argv)
    if a.cmd == 'index': index(a.force)
    elif a.cmd == 'planches': planches()
    elif a.cmd == 'sheet': C.log(clip_sheet(a.args[0], a.every, a.t_from, a.t_to, a.bright))
    elif a.cmd == 'tag': C.log('tagues:', tag(a.args[0], a.args[1:]))
    elif a.cmd == 'moment':
        moment(a.args[0], a.args[1], a.args[2], a.args[3] if len(a.args) > 3 else '', a.q, framing=a.framing, angle=a.angle, mood=a.mood)
        C.log('ok')
    elif a.cmd == 'list':
        I = C.jload(idx_path()); T = C.jload(tags_path(), {})
        for k, c in sorted(I['clips'].items(), key=lambda kv: kv[1]['n']):
            t = T.get(k, {})
            if a.person and t.get('person') != a.person: continue
            if a.untagged and t: continue
            if a.folder and not k.startswith(a.folder): continue
            C.log('#%-4d %-36s %6.1fs %4dx%-4d %5.1f lum%.2f mvt%-6s %s' % (c['n'], k, c['dur'], c['w'], c['h'], c['fps'],
                  c['stats'].get('luma', 0), c['stats'].get('motion', ''), json.dumps({x: y for x, y in t.items() if x != 'moments'}, ensure_ascii=False)
                  + (' +%d moments' % len(t.get('moments', [])) if t.get('moments') else '')))
    elif a.cmd == 'show':
        I = C.jload(idx_path()); T = C.jload(tags_path(), {}); k = a.args[0]
        c = dict(I['clips'].get(k, {})); c.pop('series', None)
        C.log(json.dumps({'clip': c, 'tags': T.get(k)}, ensure_ascii=False, indent=1))
    elif a.cmd == 'usage': usage()
