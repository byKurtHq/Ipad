"""Construit la liste des videos enregistrees (Saved) sans scraping du compte.

Sources acceptees (par ordre de preference) :
 1. Export officiel Instagram (Espace Comptes > Vos informations > Telecharger vos informations,
    format JSON ou HTML) : dossier decompresse ou .zip contenant saved_posts / saved_collections.
 2. Fichier texte d'URLs (une par ligne), par ex. 00_inbox/saved_urls.txt, rempli depuis le navigateur
    de l'utilisateur (Claude in Chrome qui lit la page Enregistrements) ou a la main.

python rf.py saved import-export <dossier|zip>
python rf.py saved import-urls <fichier.txt> [--collection NOM]
python rf.py saved find-exports      -> cherche des exports Instagram dans Telechargements / Bureau / 00_inbox
"""
import glob, html, json, os, re, sys, zipfile
from . import common as C, ledger


def _walk_json(o, ctx, out):
    """Parcourt l'export JSON. Un en-tete de collection ({"Name": {"value": ...}} sans lien)
    s'applique aux elements qui le suivent dans la meme liste."""
    if isinstance(o, list):
        cur = dict(ctx)
        for x in o:
            if isinstance(x, dict):
                smd = x.get('string_map_data') or {}
                name = smd.get('Name') or smd.get('Nom') or {}
                if isinstance(name, dict) and name.get('value') and not name.get('href'):
                    cur = dict(ctx, collection=name['value']); continue
            _walk_json(x, cur, out)
    elif isinstance(o, dict):
        smd = o.get('string_map_data')
        if isinstance(smd, dict):
            ts = None; urls = []
            for k, v in smd.items():
                if isinstance(v, dict):
                    ts = v.get('timestamp') or ts
                    for m in ledger.URL_RE.finditer(str(v.get('href', '')) + ' ' + str(v.get('value', ''))):
                        urls.append(m.group(0))
            for u in dict.fromkeys(urls):
                out.append((u, ctx.get('collection'), ts, o.get('title')))
            return
        for k, v in o.items():
            if isinstance(v, str):
                for m in ledger.URL_RE.finditer(v):
                    out.append((m.group(0), ctx.get('collection'), None, None))
            else:
                _walk_json(v, ctx, out)


def parse_export_files(files):
    """files : liste de (nom, contenu texte). Renvoie [(url, collection, ts, author)]."""
    out = []
    for name, txt in files:
        base = os.path.basename(name).lower()
        if 'saved' not in base and 'enregistr' not in base:
            continue
        coll_default = None
        if base.endswith('.json'):
            try:
                _walk_json(json.loads(txt), {'collection': coll_default}, out)
                continue
            except Exception:
                pass
        # HTML : on suit l'ordre, les titres de collection sont des en-tetes
        cur = None
        for m in re.finditer(r'(<h2[^>]*>(.*?)</h2>)|(' + ledger.URL_RE.pattern + ')', txt, re.S):
            if m.group(1):
                cur = html.unescape(re.sub('<[^>]+>', '', m.group(2))).strip() or cur
            else:
                out.append((m.group(3), cur if 'collection' in base else None, None, None))
    return out


def load_export(src):
    files = []
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for n in z.namelist():
                if n.lower().endswith(('.json', '.html')) and ('saved' in n.lower() or 'enregistr' in n.lower()):
                    files.append((n, z.read(n).decode('utf-8', 'replace')))
    else:
        for p in glob.glob(os.path.join(src, '**', '*'), recursive=True):
            if p.lower().endswith(('.json', '.html')) and ('saved' in p.lower() or 'enregistr' in p.lower()):
                with open(p, encoding='utf-8', errors='replace') as f:
                    files.append((p, f.read()))
    return files


def import_export(src):
    rows = parse_export_files(load_export(src))
    n0 = ledger.stats()['total']
    for url, coll, ts, author in rows:
        ledger.add(url, collection=coll, saved_at=ts, author=author, source='instagram_export')
    return len(rows), ledger.stats()['total'] - n0


def import_urls(path, collection=None):
    n = 0
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            for m in ledger.URL_RE.finditer(line):
                if ledger.add(m.group(0), collection=collection, source=os.path.basename(path)):
                    n += 1
    return n


def find_exports():
    home = os.path.expanduser('~')
    pats = [os.path.join(home, 'Downloads', '*instagram*'), os.path.join(home, 'Téléchargements', '*instagram*'),
            os.path.join(home, 'Desktop', '*instagram*'), os.path.join(home, 'OneDrive', '*', '*instagram*'),
            os.path.join(C.d('inbox'), '*')]
    found = []
    for p in pats:
        found += glob.glob(p)
    for p in glob.glob(os.path.join(home, 'Downloads', '**', 'saved_posts.*'), recursive=True):
        found.append(os.path.dirname(p))
    return sorted(set(found))


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py saved')
    ap.add_argument('cmd', choices=['import-export', 'import-urls', 'find-exports'])
    ap.add_argument('path', nargs='?'); ap.add_argument('--collection')
    a = ap.parse_args(argv)
    if a.cmd == 'import-export':
        C.log('liens lus: %d, nouvelles references: %d' % import_export(a.path))
    elif a.cmd == 'import-urls':
        C.log('URLs importees:', import_urls(a.path, a.collection))
    else:
        for p in find_exports(): C.log(p)
    C.log(ledger.stats())
