"""Bibliotheque de sound design generee par synthese (libre de droits, aucune licence a gerer).

python rf.py sfx build            -> genere _assets/sfx/*.wav (48 kHz stereo)
python rf.py sfx list             -> liste les sons et leur role

Chaque son est concu pour une fonction precise du montage :
  impact_*  : appuyer une coupe ou un mot fort      whoosh_*  : accompagner un mouvement / une transition
  riser_*   : construire la tension avant un drop   boom_*    : drop / revelation (basse + queue)
  glitch_*  : flashs RVB, coupes glitch             hit_metal : clin d'oeil salle de sport (disque)
  tape_stop / reverse_swell / heartbeat / drone_* / room_tone_gym : ambiances et effets
"""
import os, sys
import numpy as np
from . import common as C

SR = 48000
RNG = np.random.default_rng(1234)

DESCR = {
    'impact_sub': 'Impact grave court (coupe franche, mot fort)',
    'impact_punch': 'Impact sec et medium (texte qui claque, zoom punch)',
    'impact_cinematic': 'Impact cinematique avec queue reverb (debut / moment cle)',
    'boom_drop': 'Bass drop long (revelation, apres un riser)',
    'sub_drop': 'Chute de sub-basse (transition vers un passage lourd)',
    'whoosh_fast': 'Whoosh rapide 0.35 s (cut dynamique, whip pan)',
    'whoosh_soft': 'Whoosh doux 0.8 s (transition lente, apparition texte)',
    'whoosh_heavy': 'Whoosh lourd 1.1 s (grosse transition)',
    'swish_short': 'Swish tres court (apparition de mot)',
    'riser_2s': 'Riser 2 s (tension courte)',
    'riser_4s': 'Riser 4 s (montee longue avant drop)',
    'reverse_swell': 'Souffle inverse 1.5 s (aspiration vers une coupe)',
    'glitch_short': 'Glitch numerique 0.25 s (flash RVB)',
    'glitch_stutter': 'Glitch saccade 0.6 s (montage glitch)',
    'tape_stop': 'Arret de bande 0.7 s (coupure dramatique)',
    'hit_metal': 'Choc metallique (disque / barre de salle)',
    'heartbeat': 'Battement de coeur double (tension, silence)',
    'tick': 'Tic sec (rythme, texte mot a mot)',
    'camera_flash': 'Flash photo (flash blanc / silhouette)',
    'drone_dark': 'Nappe sombre 12 s, boucle (ambiance)',
    'drone_tension': 'Nappe de tension 12 s, boucle (ambiance)',
    'room_tone_gym': 'Ambiance de salle 12 s, boucle (fond realiste)',
}


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def noise(n, color='white'):
    x = RNG.standard_normal(n)
    if color == 'white':
        return x
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR); f[0] = f[1]
    if color == 'pink': X /= np.sqrt(f)
    if color == 'brown': X /= f
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def fft_filter(x, lo=None, hi=None, order=2):
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo: g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    if hi: g *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * g, n)


def sweep_filter(x, f_start, f_end, q=2.0, win=2048):
    """Passe-bande a frequence centrale glissante (STFT)."""
    hop = win // 4; n = len(x); w = np.hanning(win)
    out = np.zeros(n + win); norm = np.zeros(n + win)
    frames = max(1, (n - win) // hop + 1)
    f = np.fft.rfftfreq(win, 1 / SR)
    for i in range(frames):
        a = i * hop; seg = x[a:a + win]
        if len(seg) < win: seg = np.pad(seg, (0, win - len(seg)))
        k = i / max(frames - 1, 1)
        fc = f_start * (f_end / f_start) ** k
        bw = fc / q
        g = np.exp(-0.5 * ((f - fc) / bw) ** 2)
        y = np.fft.irfft(np.fft.rfft(seg * w) * g, win)
        out[a:a + win] += y * w; norm[a:a + win] += w ** 2
    return (out / np.maximum(norm, 1e-6))[:n]


def chirp(dur, f0, f1, curve='exp'):
    t = t_(dur)
    if curve == 'exp':
        k = np.log(f1 / f0) / dur
        ph = 2 * np.pi * f0 * (np.exp(k * t) - 1) / k
    else:
        ph = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * dur))
    return np.sin(ph)


def reverb(x, dur=1.8, wet=0.35, damp=4000, seed=7):
    n = int(dur * SR); r = np.random.default_rng(seed)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / (dur * SR / 6.9))
    ir = fft_filter(ir, hi=damp); ir /= np.sqrt((ir ** 2).sum()) + 1e-9
    m = len(x) + n - 1; N = 1 << (m - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:m]
    xx = np.pad(x, (0, n - 1))
    return (1 - wet) * xx + wet * y * (np.abs(x).max() / (np.abs(y).max() + 1e-9))


def sat(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def stereo(x, width=0.0, pan=0.0, delay_ms=0.0):
    l = x.copy(); r = x.copy()
    if delay_ms:
        dly = int(delay_ms * SR / 1000); r = np.concatenate([np.zeros(dly), x])[:len(x)]
    if width:
        dec = fft_filter(noise(len(x)), lo=200) * 0
        l = l + width * dec; r = r - width * dec
    gl = np.cos((pan + 1) * np.pi / 4); gr = np.sin((pan + 1) * np.pi / 4)
    return np.stack([l * gl * 1.414, r * gr * 1.414], 1)


def pan_sweep(x, a=-0.8, b=0.8):
    p = np.linspace(a, b, len(x))
    gl = np.cos((p + 1) * np.pi / 4); gr = np.sin((p + 1) * np.pi / 4)
    return np.stack([x * gl * 1.414, x * gr * 1.414], 1)


def fade(x, fi=0.002, fo=0.01):
    n = len(x); a = int(fi * SR); b = int(fo * SR)
    e = np.ones(n)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] *= np.linspace(1, 0, b)
    return x * (e[:, None] if x.ndim == 2 else e)


def norm(x, peak_db=-1.0):
    return x / (np.abs(x).max() + 1e-9) * 10 ** (peak_db / 20)


def loopable(x, xf=0.5):
    n = int(xf * SR); a = x[:n]; b = x[-n:]
    r = np.linspace(0, 1, n)[:, None] if x.ndim == 2 else np.linspace(0, 1, n)
    mid = x[n:-n].copy() if len(x) > 2 * n else x
    head = b * (1 - r) + a * r
    return np.concatenate([head, mid])


# ------------------------------------------------------------------ sons

def impact_sub():
    d = 1.4; t = t_(d)
    body = chirp(d, 110, 38) * env_exp(len(t), 0.32)
    click = fft_filter(noise(len(t)), lo=1500) * env_exp(len(t), 0.004) * 0.6
    thump = fft_filter(noise(len(t), 'brown'), hi=180) * env_exp(len(t), 0.05) * 0.8
    return fade(stereo(sat(body + click + thump, 2.5)), 0.0005, 0.2)


def impact_punch():
    d = 0.6; t = t_(d)
    body = chirp(d, 180, 55) * env_exp(len(t), 0.09)
    snap = fft_filter(noise(len(t)), lo=800, hi=9000) * env_exp(len(t), 0.018)
    x = sat(body + 0.7 * snap, 3)
    return fade(stereo(reverb(x, 0.6, 0.15)[:int(0.9 * SR)], 0, delay_ms=0.0), 0.0005, 0.1)


def impact_cinematic():
    d = 1.2; t = t_(d)
    body = chirp(d, 95, 32) * env_exp(len(t), 0.4)
    crack = fft_filter(noise(len(t)), lo=300, hi=6000) * env_exp(len(t), 0.06)
    low = fft_filter(noise(len(t), 'brown'), hi=120) * env_exp(len(t), 0.25)
    x = sat(body + 0.6 * crack + 0.7 * low, 2.2)
    x = reverb(x, 3.2, 0.45, damp=2500)
    return fade(stereo(x, delay_ms=0), 0.0005, 0.6)


def boom_drop():
    d = 3.5; t = t_(d)
    body = chirp(d, 70, 28) * env_exp(len(t), 0.9)
    hit = fft_filter(noise(len(t)), lo=200, hi=4000) * env_exp(len(t), 0.08)
    x = sat(body + 0.5 * hit, 2.0)
    x = reverb(x, 3.0, 0.35, damp=1800)
    return fade(stereo(x), 0.0005, 1.0)


def sub_drop():
    d = 2.2; x = chirp(d, 90, 25) * np.linspace(1, 0.0, int(d * SR)) ** 0.7
    return fade(stereo(sat(x, 1.8)), 0.01, 0.4)


def _whoosh(d, f0, f1, q, peak_at=0.6, heavy=False):
    n = int(d * SR); x = noise(n, 'pink')
    x = sweep_filter(x, f0, f1, q=q)
    k = np.linspace(0, 1, n)
    e = np.where(k < peak_at, (k / peak_at) ** 2, ((1 - k) / (1 - peak_at)) ** 1.5)
    x = x * e
    if heavy:
        x = x + 0.6 * fft_filter(noise(n, 'brown'), hi=250) * e
    return fade(pan_sweep(norm(x, 0), -0.7, 0.7), 0.002, 0.03)


def whoosh_fast(): return _whoosh(0.35, 600, 5000, 1.5, 0.55)
def whoosh_soft(): return _whoosh(0.8, 300, 2500, 1.2, 0.6)
def whoosh_heavy(): return _whoosh(1.1, 150, 3000, 1.0, 0.65, heavy=True)
def swish_short(): return _whoosh(0.18, 2000, 8000, 2.0, 0.4)


def _riser(d):
    n = int(d * SR); k = np.linspace(0, 1, n)
    nz = sweep_filter(noise(n, 'pink'), 300, 9000, q=1.0) * k ** 2
    tone = (chirp(d, 110, 880) + 0.5 * chirp(d, 220, 1760)) * k ** 3 * 0.35
    trem = 1 + 0.25 * np.sin(2 * np.pi * (4 + 12 * k) * k * d)
    x = (nz + tone) * trem
    return fade(stereo(sat(norm(x, 0), 1.3), delay_ms=11), 0.05, 0.005)


def riser_2s(): return _riser(2.0)
def riser_4s(): return _riser(4.0)


def reverse_swell():
    d = 1.5; n = int(d * SR)
    x = fft_filter(noise(n), lo=400, hi=9000) * env_exp(n, 0.25)
    x = reverb(x, 1.2, 0.5)[:n]
    return fade(stereo(x[::-1], delay_ms=9), 0.02, 0.003)


def glitch_short():
    d = 0.25; n = int(d * SR); x = np.zeros(n)
    i = 0
    while i < n:
        L = int(RNG.integers(200, 1600)); seg = RNG.standard_normal(min(L, n - i))
        q = 2 ** int(RNG.integers(2, 5)); seg = np.round(seg * q) / q
        x[i:i + len(seg)] = seg * (RNG.random() > 0.25) * RNG.uniform(0.3, 1)
        i += L
    x = x + 0.5 * np.sign(np.sin(2 * np.pi * 1200 * t_(d)))  * (RNG.random(n) > 0.995)
    return fade(stereo(fft_filter(x, lo=150)), 0.001, 0.02)


def glitch_stutter():
    base = glitch_short()[:, 0]; d = 0.6; n = int(d * SR); x = np.zeros(n)
    chunk = base[:int(0.05 * SR)]
    pos = 0
    while pos < n:
        L = min(len(chunk), n - pos); x[pos:pos + L] += chunk[:L] * RNG.uniform(0.5, 1)
        pos += int(RNG.choice([0.04, 0.06, 0.08]) * SR)
    return fade(stereo(x, delay_ms=4), 0.001, 0.05)


def tape_stop():
    d = 0.7; t = t_(d)
    f = 220 * (1 - t / d) ** 2 + 20
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sign(np.sin(ph)) * 0.5 + np.sin(ph)) * (1 - t / d) ** 0.5
    x = fft_filter(x, hi=3000)
    return fade(stereo(x), 0.002, 0.05)


def hit_metal():
    d = 1.6; t = t_(d); x = np.zeros(len(t))
    for f, a, tau in ((523, 1, .5), (1187, .6, .35), (1976, .4, .25), (2731, .3, .18), (3911, .2, .12), (163, .7, .3)):
        x += a * np.sin(2 * np.pi * f * t + RNG.random() * 6) * env_exp(len(t), tau)
    x += fft_filter(noise(len(t)), lo=2000) * env_exp(len(t), 0.01)
    return fade(stereo(reverb(x, 1.0, 0.25)[:len(t)]), 0.0005, 0.2)


def heartbeat():
    d = 1.3; n = int(d * SR); x = np.zeros(n)
    for t0, a in ((0.0, 1), (0.28, 0.7)):
        i = int(t0 * SR); L = int(0.25 * SR)
        x[i:i + L] += a * chirp(0.25, 70, 40)[:L] * env_exp(L, 0.06)
    return fade(stereo(sat(x, 2)), 0.001, 0.1)


def tick():
    d = 0.08; n = int(d * SR)
    x = fft_filter(noise(n), lo=2500) * env_exp(n, 0.006) + np.sin(2 * np.pi * 1800 * t_(d)) * env_exp(n, 0.01) * 0.5
    return fade(stereo(x), 0.0002, 0.01)


def camera_flash():
    d = 0.9; n = int(d * SR)
    click = fft_filter(noise(n), lo=1500) * env_exp(n, 0.01)
    whine = chirp(d, 2500, 9000) * np.linspace(0.15, 0, n)
    return fade(stereo(reverb(click + whine, 0.5, 0.2)[:n]), 0.0005, 0.1)


def _drone(d, base, dark=True):
    t = t_(d); x = np.zeros(len(t))
    for k, (m, a) in enumerate(((1, 1), (1.5, .5), (2, .45), (3, .2), (0.5, .7))):
        det = 1 + 0.003 * np.sin(2 * np.pi * (0.07 + 0.03 * k) * t)
        x += a * np.sin(2 * np.pi * base * m * det * t + k)
    x += 0.25 * fft_filter(noise(len(t), 'brown'), hi=300 if dark else 1200)
    mod = 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
    x = fft_filter(x * mod, hi=900 if dark else 2500)
    return loopable(stereo(norm(x, -3), delay_ms=17), 0.5)


def drone_dark(): return _drone(12.5, 55, True)
def drone_tension(): return _drone(12.5, 73.4, False)


def room_tone_gym():
    d = 12.5; n = int(d * SR)
    x = fft_filter(noise(n, 'pink'), lo=80, hi=3500) * 0.3
    hum = 0.05 * np.sin(2 * np.pi * 50 * t_(d)) + 0.03 * np.sin(2 * np.pi * 100 * t_(d))
    x = x + hum
    for _ in range(5):
        i = int(RNG.integers(0, n - SR)); h = hit_metal()[:, 0][:SR] * RNG.uniform(0.04, 0.12)
        h = fft_filter(h, hi=2500); x[i:i + len(h)] += h
    return loopable(stereo(x, delay_ms=13), 0.5)


SOUNDS = {k: globals()[k] for k in DESCR}


def build(out_dir=None, only=None):
    out_dir = out_dir or C.d('assets', 'sfx')
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for k, fn in SOUNDS.items():
        if only and k not in only: continue
        p = os.path.join(out_dir, k + '.wav')
        x = fn()
        if x.ndim == 1: x = stereo(x)
        x = norm(x, -1.0)
        C.write_wav(p, x, SR); made.append(p)
    return made


def path(name):
    p = os.path.join(C.d('assets', 'sfx'), name + '.wav')
    if not os.path.isfile(p):
        build(only=[name])
    return p


def main(argv):
    if not argv or argv[0] == 'build':
        for p in build(): C.log('ok', p)
    elif argv[0] == 'list':
        for k, v in DESCR.items(): C.log('%-18s %s' % (k, v))
