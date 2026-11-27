"""Enchaine toute la fabrication d'un projet et met a jour le registre.

python rf.py render <spec.json> [--canvas 1080x1920] [--landscape] [--skip-qc]
Etapes : edit build -> silhouettes -> calque texte -> mix audio -> export -> QC.
Par defaut : 9:16 (1080x1920). --landscape (ou spec "outputs": {"landscape": true}) ajoute la version 16:9.
"""
import os, time
from . import common as C, edit, textfx, silhouette, sound, compose, qc, ledger


def render(spec_path, canvases=None, skip_qc=False):
    spec = C.jload(spec_path)
    rid = spec.get('ref') or spec.get('id')
    if not canvases:
        canvases = ['%dx%d' % tuple(spec.get('canvas', C.load_config()['canvas']))]
        if (spec.get('outputs') or {}).get('landscape'):
            canvases.append('1920x1080')
    t0 = time.time(); results = []
    sound.mix(spec_path)
    for cv in canvases:
        C.log('== rendu', rid, cv)
        edit.build(spec_path, cv)
        if spec.get('silhouettes'):
            silhouette.build(spec_path, cv)
        textfx.render(spec_path, cv)
        outs = compose.compose(spec_path, cv)
        r = None if skip_qc else qc.qc(outs['final'], spec_path, rid)
        results.append((cv, outs, r))
        if r:
            for m in r['warnings']: C.log('  !!', m)
            for m in r['errors']: C.log('  XX', m)
            C.log('  QC', r['verdict'], r['sheet'])
    if rid and ledger.get(rid):
        main_out = results[0][1]['final']; verdict = results[0][2]['verdict'] if results[0][2] else 'non_verifie'
        ledger.update(rid, status='qc_pass' if verdict == 'OK' else 'edited', reel_file=os.path.basename(main_out),
                      duration=round(C.probe(main_out)['dur'], 2), qc=verdict,
                      clips=sorted({s['clip'] for s in spec['shots'] if s.get('clip')}),
                      outputs=[o['final'] for _, o, _ in results])
    C.log('termine en %.0f s' % (time.time() - t0))
    return results


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py render'); ap.add_argument('spec'); ap.add_argument('--canvas', action='append')
    ap.add_argument('--landscape', action='store_true'); ap.add_argument('--skip-qc', action='store_true')
    a = ap.parse_args(argv)
    cv = a.canvas or None
    if a.landscape:
        spec = C.jload(a.spec); cv = (cv or ['%dx%d' % tuple(spec.get('canvas', C.load_config()['canvas']))]) + ['1920x1080']
    res = render(a.spec, cv, a.skip_qc)
    return 0 if all((r is None or r['verdict'] == 'OK') for _, _, r in res) else 1
