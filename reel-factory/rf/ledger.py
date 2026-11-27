"""Registre de production : une entree par video enregistree Instagram. Rien n'est oublie.

python rf.py ledger stats
python rf.py ledger list [--status S]
python rf.py ledger next [--n 5]                  -> prochaines references a traiter
python rf.py ledger set ID status=edited note="..." key=value
python rf.py ledger add URL [--collection C]
python rf.py ledger csv                           -> 06_rapports/registre.csv
"""
import csv, os, re, sys, time
from . import common as C

STAGES = ['listed', 'downloaded', 'analyzed', 'clips_selected', 'edited', 'sound_done', 'qc_pass', 'delivered']
TERMINAL = ('delivered', 'skipped', 'failed')
URL_RE = re.compile(r'https?://(?:www\.)?instagram\.com/(?:[A-Za-z0-9_.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]{5,})')


def path():
    return C.d('reports', 'registre.json')


def load():
    return C.jload(path(), {'items': {}, 'order': []})


def save(L):
    C.jsave(path(), L)


def shortcode(url):
    m = URL_RE.search(url or '')
    return m.group(2) if m else None


def canonical(url):
    m = URL_RE.search(url)
    kind = 'reel' if m.group(1) in ('reel', 'reels') else m.group(1)
    return 'https://www.instagram.com/%s/%s/' % (kind, m.group(2))


def add(url, collection=None, saved_at=None, author=None, source='manual'):
    sc = shortcode(url)
    if not sc:
        return None
    with C.FileLock(path()):
        L = load()
        it = L['items'].get(sc)
        if it is None:
            it = {'id': sc, 'url': canonical(url), 'status': 'listed', 'collections': [], 'saved_at': saved_at,
                  'author': author, 'source': source, 'added': time.strftime('%Y-%m-%d %H:%M'), 'history': [],
                  'notes': []}
            L['items'][sc] = it; L['order'].append(sc)
        if collection and collection not in it['collections']:
            it['collections'].append(collection)
        if author and not it.get('author'): it['author'] = author
        if saved_at and not it.get('saved_at'): it['saved_at'] = saved_at
        save(L)
    return sc


def get(sc):
    return load()['items'].get(sc)


def update(sc, **kw):
    with C.FileLock(path()):
        L = load(); it = L['items'][sc]
        note = kw.pop('note', None)
        if 'status' in kw and kw['status'] != it.get('status'):
            it['history'].append([time.strftime('%Y-%m-%d %H:%M'), it.get('status'), kw['status']])
        it.update(kw)
        if note:
            it['notes'].append(time.strftime('%H:%M ') + note)
        save(L)
    return it


def stage_index(st):
    base = (st or '').split(':')[0]
    return STAGES.index(base) if base in STAGES else -1


def pending(L=None):
    L = L or load()
    out = []
    for sc in L['order']:
        st = L['items'][sc]['status']
        if not st.split(':')[0] in TERMINAL:
            out.append(sc)
    return out


def stats(L=None):
    L = L or load(); cnt = {}
    for it in L['items'].values():
        k = it['status'].split(':')[0]; cnt[k] = cnt.get(k, 0) + 1
    return {'total': len(L['items']), **cnt}


def export_csv():
    L = load(); p = C.d('reports', 'registre.csv')
    cols = ['n', 'id', 'url', 'status', 'collections', 'author', 'reel_file', 'duration', 'qc', 'clips', 'notes']
    with open(p, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(cols)
        for n, sc in enumerate(L['order'], 1):
            it = L['items'][sc]
            w.writerow([n, sc, it['url'], it['status'], ', '.join(it.get('collections', [])), it.get('author') or '',
                        it.get('reel_file') or '', it.get('duration') or '', it.get('qc') or '',
                        ', '.join(it.get('clips', []) or []), ' | '.join(it.get('notes', []))])
    return p


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py ledger')
    ap.add_argument('cmd', choices=['stats', 'list', 'next', 'set', 'add', 'csv', 'show'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--status'); ap.add_argument('--collection'); ap.add_argument('--n', type=int, default=5)
    a = ap.parse_args(argv)
    if a.cmd == 'stats':
        C.log(stats())
    elif a.cmd == 'list':
        L = load()
        for n, sc in enumerate(L['order'], 1):
            it = L['items'][sc]
            if a.status and not it['status'].startswith(a.status): continue
            C.log('%3d %-14s %-22s %s' % (n, sc, it['status'], it.get('reel_file') or ''))
    elif a.cmd == 'next':
        for sc in pending()[:a.n]:
            it = get(sc); C.log(sc, it['status'], it['url'])
    elif a.cmd == 'show':
        import json; C.log(json.dumps(get(a.args[0]), ensure_ascii=False, indent=1))
    elif a.cmd == 'add':
        for u in a.args: C.log(add(u, a.collection))
    elif a.cmd == 'set':
        sc = a.args[0]; kw = {}
        for kv in a.args[1:]:
            k, v = kv.split('=', 1); kw[k] = v
        C.log(update(sc, **kw)['status'])
    elif a.cmd == 'csv':
        C.log(export_csv())
