"""Sound design et mixage (agent 4).

python rf.py sound mix <spec.json>          -> 03_projects/<id>/audio/mix.wav (+ sfx_only.wav)
python rf.py sound cues <spec.json>         -> propose des SFX cales sur les coupes/flashs du montage (a valider)

Bloc "audio" de spec.json :
 "audio": {"source": "ref" | "<chemin audio/video>" | null, "offset": 0.0, "gain_db": 0, "fade_out": 0.25,
           "sfx":  [{"name": "impact_sub", "t": 3.96, "gain_db": -14, "align": "start|peak|end", "pan": 0.0}],
           "beds": [{"name": "drone_dark", "t0": 0, "t1": 16.5, "gain_db": -30, "fade": 1.0}],
           "loudness": -14, "true_peak": -1.0}
Regle : la voix / musique de reference porte le reel. Les SFX renforcent (coupes, flashs, mots forts) sans jamais
masquer la voix : -12 a -20 dB sous la piste principale, aucun SFX sur un mot parle important.
"""
import json, os, re, subprocess
import numpy as np
from . import common as C, sfx as SFX

SR = 48000


def source_path(spec, pdir):
    a = spec.get('audio', {})
    src = a.get('source', 'ref')
    if src == 'ref':
        rid = spec.get('ref') or spec.get('id')
        rd = C.d('refs', rid)
        for c in ('audio_48k.wav', 'ref.mp4'):
            if os.path.isfile(os.path.join(rd, c)): return os.path.join(rd, c)
        return None
    if src and not os.path.isabs(src): src = os.path.join(pdir, src)
    return src if src and os.path.isfile(src) else None


def place(buf, x, start, gain_db=0.0, pan=0.0):
    g = 10 ** (gain_db / 20)
    if pan:
        gl = np.cos((pan + 1) * np.pi / 4) * 1.414; gr = np.sin((pan + 1) * np.pi / 4) * 1.414
        x = x * np.array([gl, gr])[None, :]
    a = max(0, start); b = min(len(buf), start + len(x))
    if b > a:
        buf[a:b] += x[a - start:b - start] * g


def loudnorm_2pass(src, dst, I=-14.0, TP=-1.0, LRA=11.0):
    p = subprocess.run([C.ff(), '-hide_banner', '-nostdin', '-i', src, '-af',
                        'loudnorm=I=%s:TP=%s:LRA=%s:print_format=json' % (I, TP, LRA), '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', p.stderr, re.S)
    if not m:
        C.ffmpeg('-i', src, '-af', 'loudnorm=I=%s:TP=%s:LRA=%s,aresample=48000' % (I, TP, LRA), '-ar', SR, dst)
        return None
    j = json.loads(m.group(0))
    af = ('loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true,'
          'aresample=48000' % (I, TP, LRA, j['input_i'], j['input_tp'], j['input_lra'], j['input_thresh'], j['target_offset']))
    C.ffmpeg('-i', src, '-af', af, '-ar', SR, '-c:a', 'pcm_s16le', dst)
    return j


def mix(spec_path):
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    fps = spec['fps']; total = sum(int(s['frames']) for s in spec['shots']); dur = total / fps
    a = spec.get('audio', {}); n = int(round(dur * SR))
    adir = os.path.join(pdir, 'audio'); os.makedirs(adir, exist_ok=True)
    main = np.zeros((n, 2), np.float32); fx = np.zeros((n, 2), np.float32)
    src = source_path(spec, pdir)
    if src and a.get('source', 'ref') is not None:
        x = C.read_audio(src)
        off = int(float(a.get('offset', 0)) * SR)
        x = x[off:off + n]
        main[:len(x)] = x * 10 ** (float(a.get('gain_db', 0)) / 20)
    for e in a.get('sfx', []):
        x = C.read_audio(SFX.path(e['name']))
        t = int(float(e['t']) * SR); al = e.get('align', 'start')
        if al == 'peak': t -= int(np.argmax(np.abs(x).sum(1)))
        elif al == 'end': t -= len(x)
        place(fx, x, t, float(e.get('gain_db', -14)), float(e.get('pan', 0)))
    for b in a.get('beds', []):
        x = C.read_audio(SFX.path(b['name']))
        t0 = int(float(b.get('t0', 0)) * SR); t1 = int(float(b.get('t1', dur)) * SR); L = max(0, min(n, t1) - t0)
        if L <= 0: continue
        reps = int(np.ceil(L / len(x))) + 1; y = np.tile(x, (reps, 1))[:L].copy()
        fl = int(float(b.get('fade', 1.0)) * SR)
        if fl: e = np.ones(L); e[:min(fl, L)] = np.linspace(0, 1, min(fl, L)); e[-min(fl, L):] *= np.linspace(1, 0, min(fl, L)); y *= e[:, None]
        place(fx, y, t0, float(b.get('gain_db', -28)))
    fo = int(float(a.get('fade_out', 0.0)) * SR)
    if fo:
        e = np.linspace(1, 0, fo)[:, None]; main[-fo:] *= e; fx[-fo:] *= e
    pre = os.path.join(adir, 'premix.wav'); C.write_wav(pre, np.clip(main + fx, -1, 1), SR)
    out = os.path.join(adir, 'mix.wav')
    I = float(a.get('loudness', C.load_config()['loudness_lufs'])); TP = float(a.get('true_peak', C.load_config()['true_peak_db']))
    if np.abs(main + fx).max() < 1e-5:
        C.write_wav(out, main + fx, SR); C.log('  (silence)'); return out
    j = loudnorm_2pass(pre, out, I, TP)
    gain_db = (I - float(j['input_i'])) if j and j.get('input_i') not in (None, '-inf') else 0.0
    if np.abs(fx).max() > 1e-5:
        so = os.path.join(adir, 'sfx_only.wav')
        C.write_wav(so, np.clip(fx * 10 ** (min(gain_db, 20) / 20), -0.89, 0.89), SR)
    lo = C.loudness(out)
    C.log('  mix %s : %.2f s, %s LUFS, crete %s dBFS' % (out, dur, lo['I'], lo['TP']))
    return out


def cues(spec_path):
    """Propose des SFX a partir des evenements du montage (le sound designer garde/retire)."""
    spec = C.jload(spec_path); fps = spec['fps']; acc = 0; out = []
    for s in spec['shots']:
        t = acc / fps
        if s.get('color') == 'white' or 'flash_in' in (s.get('post') or []):
            out.append({'name': 'camera_flash', 't': round(t, 3), 'gain_db': -18})
        tr = (s.get('trans_in') or {}).get('type')
        if tr in ('whip', 'smoothleft', 'smoothright', 'smoothup', 'slideleft', 'slideup'):
            out.append({'name': 'whoosh_fast', 't': round(t, 3), 'gain_db': -16, 'align': 'peak'})
        if tr in ('flash', 'fadewhite'):
            out.append({'name': 'impact_punch', 't': round(t, 3), 'gain_db': -16})
        if any(p in (s.get('post') or []) for p in ('RGB', 'RGB_BIG')) and int(s['frames']) <= 2:
            out.append({'name': 'glitch_short', 't': round(t, 3), 'gain_db': -20})
        if s.get('punch'):
            out.append({'name': 'impact_sub', 't': round(t, 3), 'gain_db': -16})
        acc += int(s['frames'])
    C.log(json.dumps(out, indent=1))
    return out


def main(argv):
    if argv and argv[0] == 'cues': cues(argv[1])
    else: mix(argv[1] if argv and argv[0] == 'mix' else argv[0])
