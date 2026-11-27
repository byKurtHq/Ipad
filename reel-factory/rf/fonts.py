"""Installe une bibliotheque de polices professionnelles libres (SIL OFL / Apache) depuis google/fonts.

python rf.py fonts install      -> _assets/fonts/ (+ licences)
python rf.py fonts list         -> cles utilisables dans les styles de texte et fichier resolu
python rf.py fonts sheet        -> planche d'apercu de toutes les polices (_assets/fonts/apercu.jpg)
"""
import os, urllib.parse, urllib.request
from . import common as C

BASE = 'https://raw.githubusercontent.com/google/fonts/main/'
FILES = {
    'ofl/bodonimoda': ['BodoniModa[opsz,wght].ttf', 'BodoniModa-Italic[opsz,wght].ttf'],
    'ofl/librebodoni': ['LibreBodoni[wght].ttf', 'LibreBodoni-Italic[wght].ttf'],
    'ofl/playfairdisplay': ['PlayfairDisplay[wght].ttf', 'PlayfairDisplay-Italic[wght].ttf'],
    'ofl/ebgaramond': ['EBGaramond[wght].ttf', 'EBGaramond-Italic[wght].ttf'],
    'ofl/cormorantgaramond': ['CormorantGaramond[wght].ttf', 'CormorantGaramond-Italic[wght].ttf'],
    'ofl/instrumentserif': ['InstrumentSerif-Regular.ttf', 'InstrumentSerif-Italic.ttf'],
    'ofl/dmserifdisplay': ['DMSerifDisplay-Regular.ttf', 'DMSerifDisplay-Italic.ttf'],
    'ofl/abrilfatface': ['AbrilFatface-Regular.ttf'],
    'ofl/oldstandardtt': ['OldStandard-Regular.ttf', 'OldStandard-Italic.ttf', 'OldStandard-Bold.ttf'],
    'ofl/cinzel': ['Cinzel[wght].ttf'],
    'ofl/anton': ['Anton-Regular.ttf'],
    'ofl/bebasneue': ['BebasNeue-Regular.ttf'],
    'ofl/leaguegothic': ['LeagueGothic[wdth].ttf'],
    'ofl/archivoblack': ['ArchivoBlack-Regular.ttf'],
    'ofl/oswald': ['Oswald[wght].ttf'],
    'ofl/poppins': ['Poppins-SemiBold.ttf', 'Poppins-Bold.ttf', 'Poppins-ExtraBold.ttf', 'Poppins-Black.ttf', 'Poppins-BoldItalic.ttf'],
    'ofl/montserrat': ['Montserrat[wght].ttf', 'Montserrat-Italic[wght].ttf'],
    'ofl/inter': ['Inter[opsz,wght].ttf'],
    'apache/specialelite': ['SpecialElite-Regular.ttf'],
    'apache/permanentmarker': ['PermanentMarker-Regular.ttf'],
    'ofl/unifrakturmaguntia': ['UnifrakturMaguntia-Book.ttf'],
}


def install(dst=None):
    dst = dst or C.d('assets', 'fonts'); os.makedirs(os.path.join(dst, 'licences'), exist_ok=True)
    ok, ko = 0, []
    for fam, files in FILES.items():
        lic = 'LICENSE.txt' if fam.startswith('apache') else 'OFL.txt'
        for f in files + [lic]:
            out = os.path.join(dst, 'licences', fam.split('/')[1] + '_' + lic) if f == lic else os.path.join(dst, f)
            if os.path.isfile(out) and os.path.getsize(out) > 1000:
                ok += 1; continue
            url = BASE + fam + '/' + urllib.parse.quote(f)
            try:
                with urllib.request.urlopen(url, timeout=60) as r, open(out, 'wb') as w:
                    w.write(r.read())
                ok += 1
            except Exception as e:
                ko.append('%s (%s)' % (f, e))
    # copie Inter-Bold statique pour les etiquettes de planches
    return ok, ko


def preview():
    from PIL import Image, ImageDraw
    keys = list(C.FONT_DB.keys())
    W = 1600; rowh = 110
    im = Image.new('RGB', (W, rowh * len(keys) + 20), (18, 18, 18)); d = ImageDraw.Draw(im)
    lab = C.font_label(20)
    for i, k in enumerate(keys):
        f = C.get_font(k, 64); p, _ = C.font_file(k)
        d.text((10, 10 + i * rowh), '%s  (%s)' % (k, os.path.basename(p or '?')), font=lab, fill=(255, 210, 0))
        d.text((10, 36 + i * rowh), 'ANGER  Sinner  belong  0123', font=f, fill=(240, 240, 240))
    out = os.path.join(C.d('assets', 'fonts'), 'apercu.jpg'); im.save(out, quality=85)
    return out


def main(argv):
    cmd = argv[0] if argv else 'install'
    if cmd == 'install':
        ok, ko = install(); C.log('polices ok: %d' % ok)
        for k in ko: C.log('  echec', k)
    elif cmd == 'list':
        for k in C.FONT_DB: C.log('%-20s %s' % (k, C.font_file(k)[0]))
    elif cmd == 'sheet':
        C.log(preview())
