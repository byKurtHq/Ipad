"""Overlays proceduraux (libres de droits) : fuite de lumiere, poussiere, balayage lumineux.

python rf.py overlays build      -> _assets/overlays/*.mp4 (fond noir, a fusionner en mode screen)
Utilisation dans spec.json : "overlays": [{"asset": "leak_warm", "t0": 0, "t1": 3, "opacity": 0.35}]
"""
import os, subprocess
import numpy as np
from . import common as C

W, H, FPS = 360, 640, 24


def _write(name, frames_fn, n):
    out = os.path.join(C.d('assets', 'overlays'), name + '.mp4')
    p = subprocess.Popen([C.ff(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(np.clip(frames_fn(i, n), 0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    return out


def leak(color=(255, 150, 60), seed=1):
    rng = np.random.default_rng(seed); yy, xx = np.mgrid[0:H, 0:W] / max(W, H)
    blobs = [(rng.uniform(-.2, .8), rng.uniform(0, 1.6), rng.uniform(.15, .35), rng.uniform(.2, .6), rng.uniform(0, 6)) for _ in range(4)]
    col = np.array(color, np.float32)
    def f(i, n):
        t = i / n * 2 * np.pi; img = np.zeros((H, W), np.float32)
        for x0, y0, r, sp, ph in blobs:
            cx = x0 + 0.15 * np.sin(t + ph); cy = y0 + 0.2 * np.cos(t * sp + ph)
            img += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * (0.6 + 0.4 * np.sin(t * 2 + ph))
        return (np.clip(img, 0, 1.2)[..., None] * col[None, None, :])
    return f


def dust(seed=2):
    rng = np.random.default_rng(seed)
    def f(i, n):
        img = np.zeros((H, W), np.float32)
        k = rng.integers(8, 25); ys = rng.integers(0, H, k); xs = rng.integers(0, W, k)
        img[ys, xs] = rng.uniform(120, 255, k)
        if rng.random() < 0.15:
            x = rng.integers(0, W); img[:, x] = np.maximum(img[:, x], 60)
        if rng.random() < 0.08:
            y = rng.integers(0, H); x = rng.integers(0, W - 40); img[y:y + 2, x:x + 30] = 140
        return np.repeat(img[..., None], 3, 2)
    return f


def sweep():
    yy, xx = np.mgrid[0:H, 0:W]
    def f(i, n):
        pos = -0.3 + 1.6 * i / n; d = (xx / W + yy / H * 0.5) / 1.5 - pos
        v = np.exp(-(d ** 2) / (2 * 0.04 ** 2)) * 230
        return np.repeat(v[..., None], 3, 2)
    return f


ASSETS = {'leak_warm': (leak((255, 140, 50), 1), 144), 'leak_red': (leak((230, 40, 30), 3), 144),
          'leak_cold': (leak((80, 150, 255), 5), 144), 'dust': (dust(), 96), 'light_sweep': (sweep(), 36)}


def path(name):
    p = os.path.join(C.d('assets', 'overlays'), name + '.mp4')
    if not os.path.isfile(p):
        fn, n = ASSETS[name]; _write(name, fn, n)
    return p


def main(argv):
    for k, (fn, n) in ASSETS.items():
        C.log(_write(k, fn, n))
