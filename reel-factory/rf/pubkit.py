"""Fiche de publication (agent 5) : accroche, legende, CTA, hashtags, couverture, notes audio/droits.

python rf.py pub init <spec.json>       -> 05_publication/<nom>.md (gabarit pre-rempli) + <nom>_couverture.jpg
python rf.py pub cover <spec.json> --t 1.2   -> change l'image de couverture
L'agent remplit la fiche a partir du brief (message, emotion) : pas de promesse trompeuse, 3 a 8 hashtags cibles.
"""
import os
from . import common as C


def init(spec_path, t_cover=None):
    from .compose import out_name
    spec = C.jload(spec_path); rid = spec.get('ref') or spec.get('id')
    W, H = tuple(spec.get('canvas', C.load_config()['canvas']))
    name = out_name(spec, W, H); final = os.path.join(C.d('reels'), name + '.mp4')
    meta = C.jload(os.path.join(C.d('refs', rid), 'meta.json'), {}) or {}
    an = C.jload(os.path.join(C.d('refs', rid), 'analysis.json'), {}) or {}
    cover = os.path.join(C.d('pub'), name + '_couverture.jpg')
    if os.path.isfile(final):
        im = C.frame_at(final, t_cover if t_cover is not None else spec.get('cover_t', 0.6), 1080)
        if im: im.save(cover, quality=92)
    p = os.path.join(C.d('pub'), name + '.md')
    if os.path.isfile(p) and t_cover is None:
        return p
    words = ' '.join(w['w'] for w in ((an.get('transcript') or {}).get('words') or []))
    L = ['# %s' % name, '',
         '- Fichier : `04_reels/%s.mp4`' % name, '- Reference : %s (%s)' % (meta.get('webpage_url') or rid, meta.get('uploader') or '?'),
         '- Son de la reference : %s %s' % (meta.get('track') or '(son original)', ('- ' + meta['artist']) if meta.get('artist') else ''),
         '- Couverture : `05_publication/%s_couverture.jpg`' % name, '',
         '## Accroche (premiere ligne, < 80 caracteres)', '', '', '## Legende', '', '', '## Appel a l\'action', '', '',
         '## Hashtags (3 a 8, niche + communaute)', '', '',
         '## Publication', '- Format : Reel 9:16, publier avec le son ORIGINAL de la reference selectionne dans Instagram',
         '  (version `_sans_son_original/` = video + SFX seuls) ou garder l\'audio integre si le compte l\'autorise.',
         '- Ne pas reprendre d\'images de la reference : seulement la methode, le rythme et l\'audio sous licence Instagram.',
         '- Meilleur moment de publication : (selon les statistiques du compte)', '',
         '## Texte prononce (reference)', words[:1500]]
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    return p


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py pub'); ap.add_argument('cmd', choices=['init', 'cover']); ap.add_argument('spec'); ap.add_argument('--t', type=float)
    a = ap.parse_args(argv); C.log(init(a.spec, a.t))
