"""Recherche des meilleurs clips personnels pour chaque plan d'une reference (agent 2).

python rf.py match propose <REF_ID> [--plan plan.json] [--n 6] [--speed auto] [--allow-reuse]
   -> 02_clips/<REF_ID>/proposals.json + proposals_XX.jpg : pour chaque plan de la reference, la vignette de la
      reference puis les meilleurs candidats (clip, debut, score, raisons). L'agent choisit visuellement.
python rf.py match commit <spec.json>     -> enregistre les clips utilises (usage.json) pour varier les reels suivants
python rf.py match export <spec.json>     -> 02_clips/<REF_ID>/ : extraits 720p de chaque plan choisi + selection.json

plan.json (optionnel, ecrit par l'analyste) : {"shots": [{"i": 0, "want": "face|close|medium|wide|insert", "mood": "...",
   "motion": "low|mid|high", "angle": "front"}]}
Candidats : moments tagues (rushes moment) en priorite, sinon fenetres glissantes des clips person=user.
Exclusions dures : person other/unsure (sauf inserts person=none), exclude=1, lying=1, angle=back
(regle de l'utilisateur : pas de plans de dos ni allonge), sauf "allow": 1 sur le clip.
"""
import json, os
import numpy as np
from . import common as C


def _pct(vals):
    v = np.array(vals, float)
    if len(v) == 0: return v
    order = v.argsort().argsort()
    return order / max(1, len(v) - 1)


def candidates(I, T, need_s):
    out = []
    for k, c in I['clips'].items():
        t = T.get(k, {})
        person = t.get('person', 'unsure')
        if t.get('exclude'): continue
        if not t.get('allow') and (t.get('lying') or t.get('angle') == 'back'): continue
        if person not in ('user', 'none'): continue
        ser = np.array(c.get('series') or [[0, c['stats'].get('luma', .4), .2, 0, 0, c['stats'].get('motion', 0)]])
        moms = t.get('moments') or []
        if moms:
            for m in moms:
                if m.get('exclude'): continue
                out.append({'clip': k, 't0': m['t0'], 't1': m['t1'], 'q': m.get('q', 3), 'framing': m.get('framing') or t.get('framing'),
                            'angle': m.get('angle') or t.get('angle'), 'person': person, 'desc': m.get('desc', ''), 'fps': c['fps'],
                            'path': c['path'], 'w': c['w'], 'h': c['h'], 'ser': ser})
        else:
            step = max(2.0, need_s)
            for a in np.arange(0.5, max(0.6, c['dur'] - need_s - 0.2), step):
                out.append({'clip': k, 't0': float(a), 't1': float(a + need_s), 'q': t.get('quality', 3), 'framing': t.get('framing'),
                            'angle': t.get('angle'), 'person': person, 'desc': t.get('notes', ''), 'fps': c['fps'], 'path': c['path'],
                            'w': c['w'], 'h': c['h'], 'ser': ser})
    for cd in out:
        s = cd['ser']; sel = s[(s[:, 0] >= cd['t0'] - 0.5) & (s[:, 0] <= cd['t1'] + 0.5)]
        sel = sel if len(sel) else s
        cd['luma'] = float(sel[:, 1].mean()); cd['motion'] = float(sel[:, 5].mean()); cd['sharp'] = float(sel[:, 4].mean())
        del cd['ser']
    return out


COMPAT = {'face': {'face': 3, 'close': 2}, 'close': {'close': 3, 'face': 2, 'medium': 1}, 'medium': {'medium': 3, 'close': 1, 'wide': 1},
          'wide': {'wide': 3, 'medium': 1}, 'insert': {'insert': 3, 'detail': 3}, 'detail': {'detail': 3, 'insert': 2}}


def propose(rid, plan=None, n=6, speed='auto', allow_reuse=False):
    an = C.jload(os.path.join(C.d('refs', rid), 'analysis.json'))
    I = C.jload(C.d('index', 'rushes_index.json')); T = C.jload(C.d('index', 'clip_tags.json'), {})
    U = C.jload(C.d('index', 'usage.json'), {})
    plan = C.jload(plan) if isinstance(plan, str) else (plan or {})
    wants = {p['i']: p for p in plan.get('shots', [])}
    shots = [s for s in an['shots'] if not s['flash']]
    if not shots: shots = an['shots']
    ref_mot = _pct([s['motion'] for s in shots]); ref_lum = _pct([s.get('luma', .4) for s in shots])
    out_dir = C.d('clips', rid); res = []
    max_need = max(s['dur'] for s in shots)
    for si, s in enumerate(shots):
        sp = 0.48 if speed == 'auto' else float(speed)
        need = s['dur'] * sp + 0.2
        cands = candidates(I, T, need)
        if not cands:
            res.append({'shot': s['i'], 'cands': []}); continue
        cm = _pct([c['motion'] for c in cands]); cl = _pct([c['luma'] for c in cands]); cs = _pct([c['sharp'] for c in cands])
        w = wants.get(s['i'], {})
        for k, c in enumerate(cands):
            sc = 0.0; why = []
            if w.get('want'):
                b = COMPAT.get(w['want'], {}).get(c.get('framing') or '', 0); sc += b * 1.5
                if b: why.append('cadrage %s' % c.get('framing'))
                if w['want'] in ('insert', 'detail') and c['person'] != 'none': sc -= 3
                if w['want'] not in ('insert', 'detail') and c['person'] == 'none': sc -= 4
            elif c['person'] == 'none':
                sc -= 2
            if w.get('angle') and c.get('angle') == w['angle']: sc += 1; why.append('angle')
            mm = {'low': 0.15, 'mid': 0.5, 'high': 0.85}.get(w.get('motion'), ref_mot[si])
            sc += 2.0 * (1 - abs(cm[k] - mm)); sc += 0.8 * (1 - abs(cl[k] - ref_lum[si])); sc += 0.6 * cs[k]
            sc += 0.6 * (c['q'] - 3)
            if c['t1'] - c['t0'] < need: sc -= 3
            used = U.get(c['clip'], [])
            if used and not allow_reuse:
                overlap = [u for u in used if not (u['t1'] < c['t0'] or u['t0'] > c['t1'])]
                sc -= 1.2 * len(used) + 3.0 * len(overlap)
                if overlap: why.append('deja utilise %dx' % len(overlap))
            c['score'] = round(sc, 2); c['why'] = why
        top = sorted(cands, key=lambda c: -c['score'])
        picked, seen = [], {}
        for c in top:
            if seen.get(c['clip'], 0) >= 2: continue
            seen[c['clip']] = seen.get(c['clip'], 0) + 1; picked.append(c)
            if len(picked) >= n: break
        res.append({'shot': s['i'], 't0': s['t0'], 'dur': s['dur'], 'need_src_s': round(need, 2), 'want': w,
                    'cands': [{k2: v for k2, v in c.items() if k2 not in ('path',)} for c in picked]})
    C.jsave(os.path.join(out_dir, 'proposals.json'), res)
    # planches : une ligne par plan = reference + candidats
    rows = []; labels = []
    for r in res:
        s = next(x for x in an['shots'] if x['i'] == r['shot'])
        rows.append(C.frame_at(an['path'], (s['t0'] + s['t1']) / 2, 320)); labels.append('REF #%d %.2fs' % (s['i'], s['dur']))
        for c in r['cands']:
            p = I['clips'][c['clip']]['path']
            rows.append(C.frame_at(p, (c['t0'] + c['t1']) / 2, 320)); labels.append('%s @%.1f s%.1f' % (c['clip'][-14:], c['t0'], c['score']))
        for _ in range(n - len(r['cands'])):
            rows.append(None if False else _blank()); labels.append('')
    per = 8 * (n + 1)
    outs = []
    for pg in range(0, len(rows), per):
        o = os.path.join(out_dir, 'proposals_%02d.jpg' % (pg // per))
        C.sheet(rows[pg:pg + per], labels[pg:pg + per], cols=n + 1, tile_w=240, out=o, title='%s : reference | candidats' % rid)
        outs.append(o)
    C.log('propositions ->', outs)
    return res


def _blank():
    from PIL import Image
    return Image.new('RGB', (320, 180), (10, 10, 10))


def commit(spec_path):
    spec = C.jload(spec_path); rid = spec.get('ref') or spec.get('id'); fps = spec['fps']
    with C.FileLock(C.d('index', 'usage.json')):
        U = C.jload(C.d('index', 'usage.json'), {})
        for k in list(U):
            U[k] = [u for u in U[k] if u['reel'] != rid]
        for s in spec['shots']:
            if not s.get('clip'): continue
            key = os.path.splitext(s['clip'])[0] if os.path.splitext(s['clip'])[1].lower() in C.load_config()['video_ext'] else s['clip']
            sp = 0.48 if s.get('speed', spec.get('speed', 'auto')) == 'auto' else float(s.get('speed', 1))
            U.setdefault(key, []).append({'reel': rid, 't0': float(s.get('start', 0)), 't1': round(float(s.get('start', 0)) + int(s['frames']) / fps * sp, 2)})
        C.jsave(C.d('index', 'usage.json'), U)
    C.log('usage enregistre pour', rid)


def export(spec_path):
    from .edit import find_clip
    spec = C.jload(spec_path); rid = spec.get('ref') or spec.get('id'); fps = spec['fps']
    od = C.d('clips', rid); sel = []
    for i, s in enumerate(spec['shots']):
        if not s.get('clip'): continue
        src = find_clip(s['clip']); st = float(s.get('start', 0))
        sp = 0.48 if s.get('speed', spec.get('speed', 'auto')) == 'auto' else float(s.get('speed', 1))
        d = max(0.5, int(s['frames']) / fps * sp)
        o = os.path.join(od, '%02d_%s_%s_%.1fs.mp4' % (i, C.slug(s.get('name', ''), 10), C.slug(s['clip'], 30), st))
        if not os.path.isfile(o):
            C.ffmpeg('-ss', '%.3f' % st, '-t', '%.3f' % d, '-i', src, '-vf', 'scale=-2:720', '-c:v', 'libx264', '-crf', '23', '-preset', 'veryfast', '-an', o)
        sel.append({'shot': s.get('name'), 'clip': s['clip'], 'start': st, 'src_dur': round(d, 2), 'file': os.path.basename(o), 'note': s.get('note', '')})
    C.jsave(os.path.join(od, 'selection.json'), sel)
    C.log('extraits ->', od)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py match'); ap.add_argument('cmd', choices=['propose', 'commit', 'export']); ap.add_argument('arg')
    ap.add_argument('--plan'); ap.add_argument('--n', type=int, default=6); ap.add_argument('--speed', default='auto')
    ap.add_argument('--allow-reuse', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'propose': propose(a.arg, a.plan, a.n, a.speed, a.allow_reuse)
    elif a.cmd == 'commit': commit(a.arg)
    else: export(a.arg)
