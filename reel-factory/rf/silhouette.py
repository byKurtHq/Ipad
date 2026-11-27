"""Silhouette blanche detouree (flash de la methode) avec rembg (u2net_human_seg).

python rf.py sil <spec.json> [--canvas WxH]
spec.json : "silhouettes": [{"shot": "s1", "local": [0, 2, 4], "at": [4, 6, 8]}]
  local = images du plan (0 = premiere image du plan), at = images du reel ou la silhouette clignote.
Sortie : sil_WxH/sil{at}.png (RGBA blanc 245), integrees automatiquement au calque texte.
"""
import os
from . import common as C


def build(spec_path, canvas=None):
    from .edit import canvas_of, raw_frames
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    W, H = canvas_of(spec, canvas)
    jobs = spec.get('silhouettes', [])
    if not jobs:
        return []
    try:
        from rembg import remove, new_session
    except Exception:
        raise SystemExit('rembg absent : pip install "rembg[cpu]"')
    from PIL import Image
    sess = new_session('u2net_human_seg')
    out = os.path.join(pdir, 'sil_%dx%d' % (W, H)); os.makedirs(out, exist_ok=True)
    made, prev = [], []
    for j in jobs:
        srcs = raw_frames(spec_path, j['shot'], j['local'], os.path.join(out, 'raw_' + j['shot']), canvas)
        for src, at in zip(srcs, j['at']):
            im = Image.open(src).convert('RGB')
            m = remove(im, session=sess, only_mask=True)
            w = Image.new('RGBA', im.size, tuple(j.get('color', [245, 245, 245])) + (0,))
            w.putalpha(m.point(lambda v: 255 if v > int(j.get('threshold', 110)) else 0))
            p = os.path.join(out, 'sil%d.png' % at); w.save(p); made.append(p)
            pv = im.copy(); pv.paste(Image.new('RGB', im.size, (255, 255, 255)), mask=w.split()[3]); prev.append(pv)
    C.sheet(prev, [os.path.basename(p) for p in made], cols=min(6, len(prev)), out=os.path.join(pdir, 'sil_check_%dx%d.jpg' % (W, H)),
            tile_w=270 if H > W else 480)
    C.log('silhouettes:', len(made), '-> verifier', os.path.join(pdir, 'sil_check_%dx%d.jpg' % (W, H)))
    return made


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py sil'); ap.add_argument('spec'); ap.add_argument('--canvas')
    a = ap.parse_args(argv); build(a.spec, a.canvas)
