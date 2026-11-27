"""Recupere chaque reference (video publique) pour analyse privee, avec yt-dlp.

python rf.py fetch [ID ...] [--limit N]

- Une reference = 01_references/<ID>/ref.mp4 + meta.json (auteur, legende, musique, duree).
- Pas de cookies ni de connexion : seules les videos accessibles publiquement sont recuperees.
  Une video privee / supprimee / photo est notee dans le registre et la production continue.
- Pause aleatoire entre deux telechargements (respect du service).
- Les fichiers de reference restent prives : ils servent a l'analyse, jamais a la publication.
"""
import glob, json, os, random, subprocess, sys, time
from . import common as C, ledger


def ref_dir(sc):
    return C.d('refs', sc)


def fetch_one(sc):
    it = ledger.get(sc); dst = ref_dir(sc)
    have = glob.glob(os.path.join(dst, 'ref.mp4'))
    if have:
        return 'downloaded', 'deja present'
    cmd = [sys.executable, '-m', 'yt_dlp', '--no-progress', '--no-warnings', '--playlist-items', '1',
           '-f', 'bv*+ba/b', '--merge-output-format', 'mp4', '--write-info-json',
           '-o', os.path.join(dst, 'ref.%(ext)s'), '--sleep-requests', '1', it['url']]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    vids = [f for f in glob.glob(os.path.join(dst, 'ref.*')) if f.lower().endswith(('.mp4', '.mkv', '.webm', '.mov'))]
    if vids and not vids[0].endswith('.mp4'):
        C.ffmpeg('-i', vids[0], '-c', 'copy', os.path.join(dst, 'ref.mp4')); os.remove(vids[0])
    err = (p.stderr or '')[-600:]
    if not os.path.isfile(os.path.join(dst, 'ref.mp4')):
        low = err.lower()
        if 'no video' in low or 'there is no video' in low:
            return 'skipped:not_video', err
        if '429' in low or 'too many requests' in low or 'rate-limit' in low or 'rate limit' in low:
            return 'failed:rate_limited', err
        if 'login' in low or 'private' in low or 'not available' in low or 'removed' in low or '404' in low:
            return 'failed:inaccessible', err
        return 'failed:download', err
    info = (glob.glob(os.path.join(dst, '*.info.json')) or [None])[0]
    meta = {}
    if info:
        with open(info, encoding='utf-8') as f:
            j = json.load(f)
        meta = {k: j.get(k) for k in ('id', 'title', 'description', 'uploader', 'uploader_id', 'channel', 'duration',
                                      'width', 'height', 'fps', 'like_count', 'comment_count', 'track', 'artist',
                                      'upload_date', 'webpage_url')}
        os.replace(info, os.path.join(dst, 'info_full.json'))
    pr = C.probe(os.path.join(dst, 'ref.mp4'))
    meta['probe'] = pr
    if pr['dur'] <= 0.5 or not pr['w']:
        return 'skipped:not_video', 'pas de piste video exploitable'
    C.jsave(os.path.join(dst, 'meta.json'), meta)
    return 'downloaded', ''


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py fetch')
    ap.add_argument('ids', nargs='*'); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    retry = ('listed', 'failed:download', 'failed:rate_limited')
    ids = a.ids or [sc for sc in [x for x in ledger.load()['order']] if ledger.get(sc)['status'] in retry]
    if a.limit: ids = ids[:a.limit]
    lo, hi = C.load_config()['download_pause_s']; fails = 0
    for k, sc in enumerate(ids):
        if ledger.get(sc)['status'].startswith('failed:inaccessible') and not a.ids:
            continue
        st, err = fetch_one(sc)
        ledger.update(sc, status=st, **({'note': 'telechargement: ' + err.strip().splitlines()[-1][:200]} if err.strip() and st != 'downloaded' else {}))
        C.log(sc, st)
        fails = fails + 1 if st == 'failed:rate_limited' else 0
        if fails >= 2:
            C.log('Limite de debit Instagram (429): pause 15 min puis reprise'); time.sleep(900); fails = 0
        if k < len(ids) - 1 and err != 'deja present':
            time.sleep(random.uniform(lo, hi))
