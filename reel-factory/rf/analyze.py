"""Analyse complete d'une reference (agent 1).

python rf.py analyze <ID|chemin.mp4> [--no-asr] [--whisper small]

Produit dans 01_references/<ID>/ :
  analysis.json   : format, fps, plans (coupes a l'image pres, flashs), couleur par plan, mouvement,
                    segments de texte a l'ecran, audio (loudness, impacts, BPM, silences), transcription mot a mot
  analysis.md     : resume lisible + gabarit de brief (message, emotion, structure) a completer par l'agent
  sheets/         : overview.jpg (toutes les 0,5 s), shots.jpg (1 vignette par plan), hook.jpg (3 premieres s),
                    text_*.jpg (1 vignette par changement de texte), spectrum.png
  audio_48k.wav   : piste audio de reference (pour le mixage)
"""
import json, os, re, subprocess, sys
import numpy as np
from . import common as C


def resolve(arg):
    if os.path.isfile(arg):
        return os.path.splitext(os.path.basename(arg))[0], arg, os.path.dirname(os.path.abspath(arg))
    dd = C.d('refs', arg)
    return arg, os.path.join(dd, 'ref.mp4'), dd


def scene_scores(path, n_hint):
    """Score de changement de scene par image (filtre select/scene de ffmpeg, lu dans le journal)."""
    p = subprocess.run([C.ff(), '-hide_banner', '-nostdin', '-loglevel', 'info', '-i', path, '-an', '-vf',
                        "scale=192:-2,select='gte(scene\\,0)',metadata=print", '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    sc = [float(x) for x in re.findall(r'lavfi\.scene_score=([0-9.]+)', p.stderr)]
    return np.array(sc if sc else [0.0] * n_hint)


def detect_cuts(scores, diffs, fps):
    n = len(scores); cuts = [0]
    for i in range(1, n):
        lo, hi = max(1, i - 12), min(n, i + 13)
        loc = np.median(scores[lo:hi]) if hi > lo else 0
        dl = np.median(diffs[lo:hi]) if hi > lo and len(diffs) >= hi else 0
        s = scores[i]; dv = diffs[i] if i < len(diffs) else 0
        if (s > max(0.12, 4 * loc)) or (s > 0.08 and dv > max(18, 3.5 * dl)):
            cuts.append(i)
    return cuts


def onset_analysis(a, sr):
    x = a.mean(1) if a.ndim == 2 else a
    hop = int(0.01 * sr)
    n = len(x) // hop
    if n < 10:
        return {}, []
    fr = x[:n * hop].reshape(n, hop)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12); db = 20 * np.log10(rms + 1e-9)
    # bande grave (impacts) via difference d'energie lissee
    lowx = np.convolve(x, np.ones(48) / 48, mode='same')[:n * hop].reshape(n, hop)
    low = 20 * np.log10(np.sqrt((lowx ** 2).mean(1) + 1e-12) + 1e-9)
    on = np.maximum(0, np.diff(db, prepend=db[0]))
    onl = np.maximum(0, np.diff(low, prepend=low[0]))
    env = on + onl
    thr = np.percentile(env, 97.5) if len(env) > 50 else env.max()
    hits = []
    for i in range(2, n - 2):
        if env[i] >= thr and env[i] == env[i - 2:i + 3].max() and db[i] > db.max() - 30:
            if not hits or i - hits[-1] > 12:
                hits.append(i)
    # BPM par autocorrelation de l'enveloppe d'onset
    e = env - env.mean(); ac = np.correlate(e, e, 'full')[len(e) - 1:]
    lags = np.arange(len(ac)) * 0.01
    sel = (lags >= 60 / 180) & (lags <= 60 / 60)
    bpm = None
    if sel.any() and ac[0] > 0:
        L = lags[sel][np.argmax(ac[sel])]; conf = ac[sel].max() / ac[0]
        bpm = {'bpm': round(float(60 / L), 1), 'confidence': round(float(conf), 3)}
    sil = []; quiet = db < -45; i = 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]: j += 1
            if j - i >= 25: sil.append([round(i * 0.01, 2), round(j * 0.01, 2)])
            i = j
        else:
            i += 1
    curve = [round(float(v), 1) for v in db[::10]]
    return {'bpm': bpm, 'silences': sil, 'rms_db_every_100ms': curve}, [round(h * 0.01, 2) for h in hits]


def transcribe(wav16, model='small'):
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return {'error': 'faster-whisper non installe'}
    import wave
    m = WhisperModel(model, device='cpu', compute_type='int8')
    w = wave.open(wav16); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    segs, info = m.transcribe(a, word_timestamps=True, vad_filter=False)
    words, text = [], []
    for s in segs:
        text.append(s.text.strip())
        for wd in (s.words or []):
            words.append({'w': wd.word.strip(), 't0': round(wd.start, 2), 't1': round(wd.end, 2),
                          'p': round(wd.probability, 2)})
    return {'language': info.language, 'lang_prob': round(info.language_probability, 2), 'text': ' '.join(text),
            'words': words}


def analyze(arg, asr=True, whisper='small'):
    rid, path, out = resolve(arg)
    sheets = os.path.join(out, 'sheets'); os.makedirs(sheets, exist_ok=True)
    pr = C.probe(path)
    fps = pr['fps'] or 30.0; W, H = pr['w'], pr['h']
    aw = 480; ah = int(round(H * aw / W / 2) * 2)
    C.log('analyse', rid, '%dx%d %.2f fps %.2fs' % (W, H, fps, pr['dur']))
    # --- passe image unique : luminance, mouvement, masques texte
    lum, diffs, tmask_change, tboxes, jpgs = [], [], [], [], []
    prev_small = prev_mask = None
    from PIL import Image
    import io
    for fr in C.iter_frames(path, aw, ah):
        bio = io.BytesIO(); Image.fromarray(fr).save(bio, 'JPEG', quality=82); jpgs.append(bio.getvalue())
        f = fr.astype(np.int16)
        small = f[::6, ::6].mean(2)
        lum.append(float(small.mean()) / 255)
        diffs.append(float(np.abs(small - prev_small).mean()) if prev_small is not None else 0.0)
        prev_small = small
        R, G, B = f[..., 0], f[..., 1], f[..., 2]
        mx, mn = f.max(2), f.min(2)
        m = (mn > 205) | ((R > 110) & (G < 70) & (B < 80) & (R - G > 70)) | ((mx - mn > 90) & (mx > 150))
        tmask_change.append(int(np.logical_xor(m, prev_mask).sum()) if prev_mask is not None else 0)
        ys, xs = np.nonzero(m)
        tboxes.append([round(xs.min() / aw, 3), round(ys.min() / ah, 3), round(xs.max() / aw, 3), round(ys.max() / ah, 3)]
                      if len(xs) > 30 else None)
        prev_mask = m
    n = len(lum)
    lum = np.array(lum); diffs = np.array(diffs)
    scores = scene_scores(path, n)
    if len(scores) != n:
        scores = np.resize(scores, n) if len(scores) else np.zeros(n)
    cuts = detect_cuts(scores, diffs, fps)
    shots = []
    def frm(i):
        i = int(max(0, min(n - 1, i)))
        return Image.open(io.BytesIO(jpgs[i])).convert('RGB')
    for k, a in enumerate(cuts):
        b = cuts[k + 1] if k + 1 < len(cuts) else n
        mid = (a + b) // 2
        im = frm(mid)
        st = C.img_stats(im) if im is not None else {}
        flash = (b - a) <= 2
        shots.append({'i': k, 'f0': a, 'f1': b, 'frames': b - a, 't0': round(a / fps, 3), 't1': round(b / fps, 3),
                      'dur': round((b - a) / fps, 3), 'flash': bool(flash),
                      'motion': round(float(diffs[a + 1:b].mean()) if b - a > 1 else 0.0, 2),
                      'luma_peak': round(float(lum[a:b].max()), 3), **st})
    # --- segments de texte (changement du masque texte)
    px = aw * ah; thr = max(250, int(px * 0.0012))
    segs, s0 = [], 0
    cutset = set(cuts)
    for i in range(1, n + 1):
        if i == n or (tmask_change[i] > thr and (i - s0 >= 2 or i in cutset)):
            if i - s0 >= 1:
                mid = (s0 + i - 1) // 2
                segs.append({'f0': s0, 'f1': i, 't0': round(s0 / fps, 3), 't1': round(i / fps, 3), 'box': tboxes[mid]})
            s0 = i
    # --- planches
    def tiles_at(times, w=320):
        return [frm(round(t * fps)) for t in times]
    step = 0.5 if pr['dur'] <= 40 else 1.0
    ts = list(np.arange(0, pr['dur'], step))[:96]
    C.sheet(tiles_at(ts), ['%.1fs' % t for t in ts], cols=8 if W >= H else 12, out=os.path.join(sheets, 'overview.jpg'),
            tile_w=320 if W >= H else 200, title='%s  %dx%d  %.2f fps  %.2fs' % (rid, W, H, fps, pr['dur']))
    C.sheet(tiles_at([(s['f0'] + s['f1']) / 2 / fps for s in shots]),
            ['#%d %.2f-%.2f (%df)' % (s['i'], s['t0'], s['t1'], s['frames']) for s in shots],
            cols=6 if W >= H else 10, out=os.path.join(sheets, 'shots.jpg'), tile_w=320 if W >= H else 200,
            title='Plans: %d' % len(shots))
    hk = [i / 8 for i in range(int(min(3.0, pr['dur']) * 8))]
    C.sheet(tiles_at(hk), ['%.2fs' % t for t in hk], cols=8 if W >= H else 12, out=os.path.join(sheets, 'hook.jpg'),
            tile_w=320 if W >= H else 180, title='Accroche: 3 premieres secondes')
    for p0 in range(0, len(segs), 48):
        ch = segs[p0:p0 + 48]
        C.sheet(tiles_at([(s['f0'] + s['f1'] - 1) / 2 / fps for s in ch]),
                ['T%d %.2f-%.2f' % (p0 + k, s['t0'], s['t1']) for k, s in enumerate(ch)],
                cols=6 if W >= H else 10, out=os.path.join(sheets, 'text_%d.jpg' % (p0 // 48)),
                tile_w=320 if W >= H else 200, title='Changements du calque texte (indicatif)')
    # --- audio
    audio = {'present': pr['audio']}
    transcript = None; hits = []
    if pr['audio']:
        wav = C.extract_wav(path, os.path.join(out, 'audio_48k.wav'))
        a = C.read_audio(wav)
        info, hits = onset_analysis(a, 48000)
        audio.update(info); audio['loudness'] = C.loudness(path); audio['hits'] = hits
        try:
            C.ffmpeg('-i', wav, '-lavfi', 'showspectrumpic=s=1200x300:legend=0', os.path.join(sheets, 'spectrum.png'))
        except Exception:
            pass
        if asr:
            w16 = C.extract_wav(path, os.path.join(out, 'audio_16k.wav'), rate=16000, ch=1)
            transcript = transcribe(w16, whisper)
            C.jsave(os.path.join(out, 'transcript.json'), transcript)
    res = {'id': rid, 'path': path, 'w': W, 'h': H, 'aspect': 'vertical' if H > W else ('landscape' if W > H else 'square'),
           'fps': round(fps, 3), 'dur': pr['dur'], 'frames': n, 'shots': shots, 'n_shots': len(shots),
           'avg_shot': round(pr['dur'] / max(1, len(shots)), 2), 'cuts_t': [s['t0'] for s in shots[1:]],
           'text_segments': segs, 'audio': audio, 'luma_curve': [round(float(x), 3) for x in lum[::max(1, int(fps / 4))]],
           'transcript': transcript, 'meta': C.jload(os.path.join(out, 'meta.json'), {})}
    C.jsave(os.path.join(out, 'analysis.json'), res)
    write_md(res, os.path.join(out, 'analysis.md'))
    return res


def write_md(r, p):
    L = ['# Reference %s' % r['id'], '']
    m = r.get('meta') or {}
    if m:
        L += ['- Auteur : %s' % (m.get('uploader') or m.get('channel') or '?'),
              '- Legende : %s' % (str(m.get('description') or '')[:300].replace('\n', ' ')),
              '- Musique : %s %s' % (m.get('track') or '', ('- ' + m['artist']) if m.get('artist') else ''), '']
    L += ['## Technique', '- Format : %dx%d (%s), %.3f i/s, %.2f s, %d images' % (r['w'], r['h'], r['aspect'], r['fps'], r['dur'], r['frames']),
          '- Plans : %d (moyenne %.2f s). Flashs (<=2 images) : %d' % (r['n_shots'], r['avg_shot'], sum(s['flash'] for s in r['shots'])),
          '- Coupes (s) : ' + ' '.join('%.2f' % t for t in r['cuts_t']), '']
    L += ['| # | debut | fin | duree | flash | lum | sat | chaleur | contraste | mvt |', '|---|---|---|---|---|---|---|---|---|---|']
    for s in r['shots']:
        L.append('| %d | %.2f | %.2f | %.2f | %s | %.2f | %.2f | %+.2f | %.2f | %.1f |' % (
            s['i'], s['t0'], s['t1'], s['dur'], 'x' if s['flash'] else '', s.get('luma', 0), s.get('sat', 0),
            s.get('warmth', 0), s.get('contrast', 0), s['motion']))
    a = r['audio']
    L += ['', '## Audio']
    if a.get('present'):
        lo = a.get('loudness') or {}
        L += ['- Loudness : %s LUFS, LRA %s, crete %s dBFS' % (lo.get('I'), lo.get('LRA'), lo.get('TP')),
              '- BPM estime : %s' % (a.get('bpm')), '- Impacts / attaques (s) : ' + ' '.join('%.2f' % h for h in a.get('hits', [])),
              '- Silences : %s' % a.get('silences')]
    else:
        L.append('- Pas de piste audio')
    t = r.get('transcript')
    if t and t.get('words'):
        L += ['', '## Transcription (%s)' % t.get('language'), t.get('text', ''), '',
              'Mots horodates : ' + ' '.join('%s@%.2f' % (w['w'], w['t0']) for w in t['words'])]
    L += ['', '## Texte a l\'ecran', '%d changements detectes (voir sheets/text_*.jpg, indicatif)' % len(r['text_segments']),
          '', '## Brief (a completer par l\'agent analyste apres visionnage des planches)',
          '- Sujet principal :', '- Message / intention :', '- Emotion visee :', '- Ambiance, rythme, identite visuelle :',
          '- Moments forts (t) :', '- Passages inutiles :', '- Methode de montage (coupes, texte, etalonnage, effets, son) :',
          '- Type de plans necessaires (par plan de la reference) :', '- Adaptation originale proposee :']
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py analyze')
    ap.add_argument('ref'); ap.add_argument('--no-asr', action='store_true'); ap.add_argument('--whisper', default=None)
    a = ap.parse_args(argv)
    r = analyze(a.ref, asr=not a.no_asr, whisper=a.whisper or C.load_config().get('whisper_model', 'small'))
    C.log('plans', r['n_shots'], 'coupes', r['cuts_t'][:20], 'segments texte', len(r['text_segments']))
