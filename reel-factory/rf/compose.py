"""Export final (fin de chaine) : base video + calque texte + overlays + mix audio.

python rf.py compose <spec.json> [--canvas 1080x1920]
Sorties (04_reels/) :
  <nom>_9x16.mp4                    master Instagram : H.264 High, CRF 18 (20 Mb/s max), AAC 192 k, 48 kHz, faststart
  _apercus/<nom>_9x16_apercu.mp4    copie legere (< 28 Mo) pour le telephone
  _sans_son_original/<nom>_9x16_sfx.mp4   video + SFX seuls, a publier avec le son original choisi dans Instagram
"""
import os
from . import common as C, overlays as OV


def out_name(spec, W, H):
    tag = '9x16' if H > W else ('16x9' if W > H else '1x1')
    return '%s_%s' % (spec.get('name') or spec.get('id'), tag)


def compose(spec_path, canvas=None):
    from .edit import canvas_of
    spec = C.jload(spec_path); pdir = os.path.dirname(os.path.abspath(spec_path))
    W, H = canvas_of(spec, canvas); fps = spec['fps']
    total = sum(int(s['frames']) for s in spec['shots']); dur = total / fps
    base = os.path.join(pdir, 'build_%dx%d' % (W, H), 'base.mp4')
    layer = os.path.join(pdir, 'layer_%dx%d' % (W, H))
    mixw = os.path.join(pdir, 'audio', 'mix.wav'); sfxw = os.path.join(pdir, 'audio', 'sfx_only.wav')
    name = out_name(spec, W, H)
    final = os.path.join(C.d('reels'), name + '.mp4')
    args = ['-i', base]; fc = []; v = '[0:v]'; idx = 1
    for k, o in enumerate(spec.get('overlays', [])):
        args += ['-stream_loop', '-1', '-i', OV.path(o['asset'])]
        t0, t1 = float(o.get('t0', 0)), float(o.get('t1', dur))
        fc.append('[%d:v]scale=%d:%d,fps=%s,format=gbrp,trim=duration=%.3f,setpts=PTS-STARTPTS[o%d]' % (idx, W, H, fps, dur, k))
        fc.append("%sformat=gbrp[b%d];[b%d][o%d]blend=all_mode=%s:all_opacity=%.3f:enable='between(t,%.3f,%.3f)'[v%d]"
                  % (v, k, k, k, o.get('blend', 'screen'), float(o.get('opacity', 0.3)), t0, t1, k))
        v = '[v%d]' % k; idx += 1
    has_layer = os.path.isdir(layer) and os.path.isfile(os.path.join(layer, '00000.png'))
    if has_layer:
        args += ['-framerate', str(fps), '-i', os.path.join(layer, '%05d.png')]
        fc.append('%s[%d:v]overlay=0:0:format=auto[vt]' % (v, idx)); v = '[vt]'; idx += 1
    fc.append('%sformat=yuv420p,setsar=1[vout]' % v)
    aidx = None
    if os.path.isfile(mixw):
        args += ['-i', mixw]; aidx = idx; idx += 1
    x = C.load_config()['x264']
    venc = ['-c:v', 'libx264', '-preset', x['preset'], '-crf', str(x['crf']), '-maxrate', x['maxrate'], '-bufsize', x['bufsize'],
            '-profile:v', 'high', '-level', '4.2', '-pix_fmt', 'yuv420p', '-r', str(fps), '-frames:v', str(total),
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
    aenc = ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']
    maps = ['-map', '[vout]'] + (['-map', '%d:a' % aidx] if aidx is not None else [])
    C.ffmpeg(*args, '-filter_complex', ';'.join(fc), *maps, *venc, *(aenc if aidx is not None else []), '-t', '%.4f' % dur,
             '-movflags', '+faststart', final)
    # apercu leger
    prev = os.path.join(C.d('reels', '_apercus'), name + '_apercu.mp4')
    pw, ph = (720, 1280) if H > W else (1280, 720) if W > H else (720, 720)
    kbps = int(min(6000, (C.load_config()['preview_max_mb'] * 8 * 1024 / max(dur, 1)) - 160))
    C.ffmpeg('-i', final, '-vf', 'scale=%d:%d' % (pw, ph), '-c:v', 'libx264', '-preset', 'medium', '-b:v', '%dk' % max(800, kbps),
             '-maxrate', '%dk' % max(800, kbps), '-bufsize', '%dk' % (2 * max(800, kbps)), '-c:a', 'aac', '-b:a', '128k',
             '-movflags', '+faststart', prev)
    outs = {'final': final, 'preview': prev}
    if spec.get('audio', {}).get('source', 'ref') == 'ref' and os.path.isfile(sfxw):
        mute = os.path.join(C.d('reels', '_sans_son_original'), name + '_sfx.mp4')
        C.ffmpeg('-i', final, '-i', sfxw, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', *aenc, '-shortest', '-movflags', '+faststart', mute)
        outs['sfx_only'] = mute
    C.log('export', final, '%.1f Mo' % (os.path.getsize(final) / 1e6))
    return outs


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='rf.py compose'); ap.add_argument('spec'); ap.add_argument('--canvas')
    a = ap.parse_args(argv); compose(a.spec, a.canvas)
