"""Rapport de production : 06_rapports/rapport_production.md + .html + registre.csv

python rf.py report
"""
import html, os, time
from . import common as C, ledger

LABEL = {'listed': 'a traiter', 'downloaded': 'telechargee', 'analyzed': 'analysee', 'clips_selected': 'clips choisis',
         'edited': 'montee (QC a revoir)', 'sound_done': 'son fait', 'qc_pass': 'QC OK', 'delivered': 'livree',
         'skipped': 'ignoree', 'failed': 'bloquee'}


def build():
    L = ledger.load(); st = ledger.stats(L); csvp = ledger.export_csv()
    rows = []
    for n, sc in enumerate(L['order'], 1):
        it = L['items'][sc]; base = it['status'].split(':')[0]
        rows.append((n, sc, it['url'], LABEL.get(base, base) + (' (' + it['status'].split(':', 1)[1] + ')' if ':' in it['status'] else ''),
                     it.get('reel_file') or '', it.get('duration') or '', it.get('qc') or '', ', '.join(it.get('clips', []) or [])[:80],
                     ' | '.join(it.get('notes', [])[-3:])[:300]))
    md = ['# Rapport de production Reels', '', 'Mis a jour : %s' % time.strftime('%Y-%m-%d %H:%M'), '',
          '| Etat | Nombre |', '|---|---|'] + ['| %s | %s |' % (LABEL.get(k, k), v) for k, v in st.items() if k != 'total'] + \
         ['| **Total references** | **%d** |' % st['total'], '', '## Detail', '',
          '| # | Reference | Etat | Reel | Duree | QC | Clips | Notes |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        md.append('| %d | [%s](%s) | %s | %s | %s | %s | %s | %s |' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8].replace('|', '/')))
    p = os.path.join(C.d('reports'), 'rapport_production.md')
    with open(p, 'w', encoding='utf-8') as f: f.write('\n'.join(md) + '\n')
    css = ('body{font-family:system-ui,Segoe UI,sans-serif;background:#111;color:#eee;margin:24px}table{border-collapse:collapse;width:100%}'
           'td,th{border-bottom:1px solid #333;padding:6px 8px;font-size:13px;text-align:left;vertical-align:top}th{color:#f5c542}'
           'a{color:#8cf}.ok{color:#6d6}.ko{color:#f66}')
    hrows = ''.join('<tr><td>%d</td><td><a href="%s">%s</a></td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        r[0], html.escape(r[2]), r[1], 'ok' if 'OK' in r[3] or 'livree' in r[3] else ('ko' if 'bloquee' in r[3] else ''), html.escape(r[3]),
        html.escape(str(r[4])), r[5], r[6], html.escape(r[7]), html.escape(r[8])) for r in rows)
    summ = ' &middot; '.join('%s : <b>%s</b>' % (LABEL.get(k, k), v) for k, v in st.items() if k != 'total')
    h = ('<!doctype html><meta charset="utf-8"><title>Rapport Reels</title><style>%s</style><h1>Rapport de production Reels</h1>'
         '<p>%s references &middot; %s</p><p>Mis a jour %s</p><table><tr><th>#</th><th>Reference</th><th>Etat</th><th>Reel</th><th>Duree</th>'
         '<th>QC</th><th>Clips</th><th>Notes</th></tr>%s</table>' % (css, st['total'], summ, time.strftime('%Y-%m-%d %H:%M'), hrows))
    ph = os.path.join(C.d('reports'), 'rapport_production.html')
    with open(ph, 'w', encoding='utf-8') as f: f.write(h)
    return p, ph, csvp


def main(argv):
    for p in build(): C.log(p)
