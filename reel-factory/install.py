#!/usr/bin/env python
"""Installation de la Reel Factory sur le PC de production (Windows ou Linux).

python install.py --root "D:/ReelFactory" --rushes "D:/RUSH" --project "D:/Vault IA" [--no-pip] [--whisper small]

1. Cree l'arborescence (00_inbox ... 06_rapports, _assets, _index) et config.json
2. Installe les bibliotheques Python (numpy, pillow, yt-dlp, faster-whisper, rembg[cpu])
3. Telecharge les polices libres (OFL), genere la bibliotheque de sons et les overlays
4. Installe le skill /reel-factory et les 5 agents dans <project>/.claude/ (et ~/.claude/ avec --user)
5. Test de fumee : rend un mini-reel synthetique et passe le QC
"""
import argparse, json, os, shutil, subprocess, sys
KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)

REQ = ['numpy', 'pillow', 'yt-dlp', 'faster-whisper', 'rembg[cpu]']


def pip_install(pkgs):
    for p in pkgs:
        mod = {'pillow': 'PIL', 'yt-dlp': 'yt_dlp', 'faster-whisper': 'faster_whisper', 'rembg[cpu]': 'rembg'}.get(p, p)
        try:
            __import__(mod); print('  ok', p); continue
        except Exception:
            pass
        print('  installation', p)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', p])
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'yt-dlp'])


def install_claude(project, user=False):
    dests = []
    if project: dests.append(os.path.join(project, '.claude'))
    if user: dests.append(os.path.join(os.path.expanduser('~'), '.claude'))
    for d in dests:
        sk = os.path.join(d, 'skills', 'reel-factory'); os.makedirs(sk, exist_ok=True)
        for f in os.listdir(os.path.join(KIT, 'skill')):
            shutil.copy(os.path.join(KIT, 'skill', f), os.path.join(sk, f))
        ag = os.path.join(d, 'agents'); os.makedirs(ag, exist_ok=True)
        for f in os.listdir(os.path.join(KIT, 'agents')):
            shutil.copy(os.path.join(KIT, 'agents', f), os.path.join(ag, f))
        print('  skill + agents ->', d)


def smoke(root):
    import numpy as np
    from rf import common as C, edit, textfx, sound, compose, qc
    t = os.path.join(root, '_index', 'smoke'); os.makedirs(t, exist_ok=True)
    clip = os.path.join(t, 'clip.mp4')
    C.ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=50:d=5', '-c:v', 'libx264', '-preset', 'ultrafast', clip)
    spec = {'id': 'smoke', 'name': '_smoke_test', 'fps': 24, 'canvas': [1080, 1920], 'grade': 'G1',
            'shots': [{'name': 'a', 'clip': clip, 'start': 0.5, 'frames': 48, 'z0': 1.2, 'z1': 1.3},
                      {'name': 'b', 'clip': clip, 'start': 2.0, 'frames': 40, 'post': ['RED'], 'trans_in': {'type': 'flash', 'frames': 4}}],
            'text': {'events': [{'t0': 0.1, 't1': 1.5, 'text': 'TEST', 'style': 'serif', 'color': 'red'}]},
            'audio': {'source': None, 'sfx': [{'name': 'impact_sub', 't': 0.1, 'gain_db': -6}]}}
    sp = os.path.join(t, 'spec.json'); C.jsave(sp, spec)
    sound.mix(sp); edit.build(sp); textfx.render(sp); outs = compose.compose(sp); r = qc.qc(outs['final'], sp)
    for f in [outs['final'], outs['preview'], outs['final'] + '.qc.json', outs['final'] + '.qc.jpg']:
        try: os.remove(f)
        except OSError: pass
    return r['errors']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='D:/ReelFactory' if os.name == 'nt' else os.path.expanduser('~/ReelFactory'))
    ap.add_argument('--rushes', action='append', default=None)
    ap.add_argument('--project', default=None); ap.add_argument('--user', action='store_true')
    ap.add_argument('--no-pip', action='store_true'); ap.add_argument('--whisper', default='small')
    ap.add_argument('--skip-smoke', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.root, exist_ok=True)
    cfgp = os.path.join(a.root, 'config.json')
    cfg = json.load(open(cfgp, encoding='utf-8')) if os.path.isfile(cfgp) else {}
    cfg.update({'factory_root': a.root.replace('\\', '/'), 'kit': KIT.replace('\\', '/'), 'whisper_model': a.whisper})
    if a.rushes: cfg['rush_roots'] = [r.replace('\\', '/') for r in a.rushes]
    cfg.setdefault('rush_roots', ['D:/RUSH'] if os.name == 'nt' else [])
    json.dump(cfg, open(cfgp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    os.environ['RF_CONFIG'] = cfgp
    from rf import common as C, fonts, sfx, overlays
    C._CFG = None; C.load_config(cfgp); C.ensure_tree()
    print('1. arborescence + config ->', cfgp)
    if not a.no_pip:
        print('2. bibliotheques Python'); pip_install(REQ)
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool): print('  !! %s introuvable dans le PATH (winget install Gyan.FFmpeg)' % tool)
    print('3. polices'); ok, ko = fonts.install(); print('  %d fichiers, echecs: %s' % (ok, ko or 'aucun'))
    print('   sons'); sfx.build(); print('   overlays'); overlays.main([])
    print('4. skill + agents'); install_claude(a.project, a.user)
    if not a.skip_smoke:
        print('5. test de fumee'); errs = smoke(a.root); print('  OK' if not errs else '  ERREURS: %s' % errs)
    print('\nPret. Commande : python "%s" <commande>   (config : %s)' % (os.path.join(KIT, 'rf.py'), cfgp))


if __name__ == '__main__':
    main()
