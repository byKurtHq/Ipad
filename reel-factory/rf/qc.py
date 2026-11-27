"""Controle qualite automatique (agent 5) + planches de verification visuelle.

python rf.py qc <reel.mp4> [--spec spec.json] [--ref REF_ID]
Verifie : format 9:16 1080x1920 (ou 16:9), H.264/yuv420p, i/s, duree (= montage, = reference), image et son de meme
duree, images noires, images figees non voulues, loudness -14 LUFS +/-1, crete <= -1 dBTP, debut sans silence,
zones de securite du texte (interface Instagram), debit/poids. Ecrit <reel>.qc.json et <reel>.qc.jpg.
Code retour 0 = OK, 1 = a corriger (le detail est dans le JSON).
"""
import json, os, re, subprocess
import numpy as np
from . import common as C


def detect(path, filt, pat):
    p = subprocess.run([C.ff(), '-hide_banner', '-nostdin', '-i', path, '-vf' if 'detect' in filt and 'silence' not in filt else '-af', filt,
                        '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return re.findall(pat, p.stderr)


def safe_zone_check(layer_dir, W, H, step=3):
    """Texte hors zones de l'interface Instagram (haut ~ 12 %, bas ~ 25 %, bords ~ 5 %)."""
    from PIL import Image
    if not os.path.isdir(layer_dir): return []
    top, bot, side = int(H * 0.115), int(H * 0.75), int(W * 0.055)
    if W > H: top, bot, side = int(H * 0.05), int(H * 0.95), int(W * 0.03)
    bad = []; files = sorted(os.listdir(layer_dir))
    seen = set()
    for f in files[::step]:
        p = os.path.join(layer_dir, f)
        st = os.stat(p); k = (st.st_size, getattr(st, 'st_ino', 0))
        if k in seen: continue
        seen.add(k)
        bb = Image.open(p).getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
        if bb and (bb[1] < top or bb[3] > bot or bb[0] < side or bb[2] > W - side):
            bad.append({'frame': int(f[:5]), 'bbox': bb})
    return bad


def qc(path, spec_path=None, ref=None):
    res = {'file': path, 'checks': [], 'warnings': [], 'errors': []}
    def ok(m): res['checks'].append(m)
    def warn(m): res['warnings'].append(m)
    def err(m): res['errors'].append(m)
    pr = C.probe(path); res['probe'] = pr
    spec = C.jload(spec_path) if spec_path else None
    W, H = pr['w'], pr['h']
    vertical = H > W
    if vertical and (W, H) != (1080, 1920): err('resolution %dx%d au lieu de 1080x1920' % (W, H))
    elif not vertical and W > H and (W, H) != (1920, 1080): warn('resolution paysage %dx%d' % (W, H))
    else: ok('resolution %dx%d' % (W, H))
    p = C.run([C.ffp(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,profile,pix_fmt,nb_frames',
               '-of', 'json', path], capture=True)
    vs = json.loads(p.stdout)['streams'][0]
    if vs.get('codec_name') != 'h264' or vs.get('pix_fmt') != 'yuv420p': err('codec %s %s' % (vs.get('codec_name'), vs.get('pix_fmt')))
    else: ok('H.264 %s yuv420p' % vs.get('profile'))
    if spec:
        exp = sum(int(s['frames']) for s in spec['shots']); got = int(vs.get('nb_frames') or 0)
        if abs(got - exp) > 1: err('images: %d obtenues / %d attendues' % (got, exp))
        else: ok('images %d = montage' % got)
        if abs(pr['fps'] - spec['fps']) > 0.01: err('i/s %.3f au lieu de %s' % (pr['fps'], spec['fps']))
    rid = ref or (spec.get('ref') or spec.get('id') if spec else None)
    an = C.jload(os.path.join(C.d('refs', rid), 'analysis.json')) if rid else None
    if an and spec and spec.get('audio', {}).get('source', 'ref') == 'ref':
        if pr['dur'] > an['dur'] + 0.1: err('reel plus long que la reference (%.2f > %.2f s)' % (pr['dur'], an['dur']))
        else: ok('duree %.2f s (reference %.2f s)' % (pr['dur'], an['dur']))
    if pr['dur'] < 3: err('duree trop courte %.2f s' % pr['dur'])
    if pr['dur'] > 90: warn('duree > 90 s (%.1f s) : limite des Reels' % pr['dur'])
    # audio
    if not pr['audio']:
        warn('pas de piste audio')
    else:
        p = C.run([C.ffp(), '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=duration,sample_rate,codec_name', '-of', 'json', path], capture=True)
        a = json.loads(p.stdout)['streams'][0]
        ad = float(a.get('duration') or 0)
        if abs(ad - pr['dur']) > 0.08: warn('duree audio %.3f / video %.3f' % (ad, pr['dur']))
        else: ok('audio/video alignes (%.3f s)' % ad)
        lo = C.loudness(path); res['loudness'] = lo
        cfg = C.load_config()
        if lo['I'] is None or abs(lo['I'] - cfg['loudness_lufs']) > 1.0: err('loudness %s LUFS (cible %s)' % (lo['I'], cfg['loudness_lufs']))
        else: ok('loudness %.1f LUFS' % lo['I'])
        if lo['TP'] is not None and lo['TP'] > cfg['true_peak_db'] + 0.3: err('crete %.1f dBTP > %.1f' % (lo['TP'], cfg['true_peak_db']))
        else: ok('crete %s dBTP' % lo['TP'])
        sil = detect(path, 'silencedetect=n=-50dB:d=0.35', r'silence_start: (-?[0-9.]+)')
        if sil and float(sil[0]) < 0.05: warn('silence au tout debut (accroche sonore ?)')
    # images noires / figees
    blk = detect(path, 'blackdetect=d=0.25:pix_th=0.06', r'black_start:([0-9.]+) black_end:([0-9.]+)')
    if blk: warn('passages noirs: %s' % blk[:5])
    else: ok('aucun passage noir > 0.25 s')
    frz = detect(path, 'freezedetect=n=0.0015:d=0.8', r'freeze_start: ([0-9.]+)')
    intended = [s for s in (spec or {}).get('shots', []) if s.get('freeze') or s.get('color')]
    if frz and not intended: warn('images figees a %s s (voulu ?)' % frz[:5])
    # zones de securite
    if spec_path:
        lay = os.path.join(os.path.dirname(os.path.abspath(spec_path)), 'layer_%dx%d' % (W, H))
        bad = safe_zone_check(lay, W, H)
        if bad: warn('texte hors zone de securite sur %d images (ex. image %d, %s)' % (len(bad), bad[0]['frame'], bad[0]['bbox']))
        else: ok('texte dans les zones de securite')
    mb = os.path.getsize(path) / 1e6; res['size_mb'] = round(mb, 1)
    if mb / max(pr['dur'], 1) > 3.2: warn('fichier lourd (%.0f Mo)' % mb)
    # planches de verification
    fps = pr['fps'] or 30; n = int(pr['dur'] * fps)
    times = sorted(set([0.0, 0.5, 1.0, 1.5, 2.0, 2.5] + list(np.linspace(0, pr['dur'] - 0.05, 18))))
    tiles = [C.frame_at(path, t, 270 if vertical else 480) for t in times]
    C.sheet(tiles, ['%.2fs' % t for t in times], cols=12 if vertical else 6, tile_w=180 if vertical else 320,
            out=path + '.qc.jpg', title='QC %s' % os.path.basename(path))
    res['sheet'] = path + '.qc.jpg'
    res['verdict'] = 'OK' if not res['errors'] else 'A_CORRIGER'
    C.jsave(path + '.qc.json', res)
    return res


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py qc'); ap.add_argument('reel'); ap.add_argument('--spec'); ap.add_argument('--ref')
    a = ap.parse_args(argv)
    r = qc(a.reel, a.spec, a.ref)
    for k in ('checks', 'warnings', 'errors'):
        for m in r[k]: C.log({'checks': '  ok ', 'warnings': '  !! ', 'errors': '  XX '}[k] + m)
    C.log('VERDICT', r['verdict'], '->', r['sheet'])
    return 0 if r['verdict'] == 'OK' else 1
