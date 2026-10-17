"""FaceFX visual proof (headless): one Dialogue animation -> 14 face-bone poses at 30 Hz, jaw angle vs the voice's RMS envelope.
Read only (ExtractedAssets .fxa / .wav); writes CSVs + a PNG plot into this folder.

Evaluation (CAMPAIGN_FACEFX_RE.md): keys t = i16 * end / 32767, v = i8 / 127 * b; node value clamped to [min, max];
bone pose = rest (+) sum over the bone's links of value * delta (translation / scale add; rotation slerp from identity by value).
Interpolation: 'linear' or 'hermite' (Catmull-Rom slopes, FaceFX derives slopes for compressed curves - which one is right is
what this tool shows).

  python fxa_proof.py [actor substring] [animation name]     default Trypticon DX_TRPTCN_LK004350
"""
import glob, os, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fxa_parse as P  # noqa: E402

def curves_of(a):
    out = {}; i = 0
    for name, n in zip(a['curves'], a['counts']):
        t = np.array(a['times'][i:i + n], float) * a['end'] / 32767.0
        v = np.array(a['values'][i:i + n], float) / 127.0 * a['b']
        out[name] = (t, v); i += n
    return out

def sample(t, v, ts, mode):
    if len(t) == 0: return np.zeros_like(ts)
    if len(t) == 1 or mode == 'linear': return np.interp(ts, t, v)
    m = np.gradient(v, t) if len(t) > 2 else np.full(len(t), (v[1] - v[0]) / max(t[1] - t[0], 1e-6))
    out = np.interp(ts, t, v)                                     # outside the key range: clamp (= linear ends)
    k = np.clip(np.searchsorted(t, ts) - 1, 0, len(t) - 2)
    inside = (ts >= t[0]) & (ts <= t[-1])
    h = t[k + 1] - t[k]; u = np.where(h > 0, (ts - t[k]) / np.where(h > 0, h, 1), 0)
    h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
    herm = h00 * v[k] + h10 * h * m[k] + h01 * v[k + 1] + h11 * h * m[k + 1]
    return np.where(inside, herm, out)

def quat_angle(q):
    return 2 * np.degrees(np.arccos(np.clip(np.abs(q[..., 0]), 0, 1)))

def slerp_id(q, s):
    """slerp from identity (1,0,0,0) to q by s (w-first)"""
    q = np.asarray(q, float); q = q / np.linalg.norm(q)
    if q[0] < 0: q = -q
    th = np.arccos(np.clip(q[0], -1, 1))
    if th < 1e-6: return np.tile([1, 0, 0, 0], (len(s), 1)).astype(float)
    a = np.sin((1 - s) * th) / np.sin(th); b = np.sin(s * th) / np.sin(th)
    return a[:, None] * np.array([1, 0, 0, 0]) + b[:, None] * q

def qmul(a, b):
    w1, x1, y1, z1 = a.T; w2, x2, y2, z2 = b.T
    return np.stack([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2], 1)

def main(actor='Trypticon', anim='DX_TRPTCN_LK004350'):
    f = [x for x in glob.glob(os.path.join(P.EA, '**', '*.fxa'), recursive=True) if actor.lower() in os.path.basename(x).lower()][0]
    x, groups, anims, pm, end, L = P.parse_all(f)
    a = next(y for y in anims if y['name'] == anim)
    nodes = {n['name']: n for n in x['nodes']}
    ts = np.arange(a['start'], a['end'], 1 / 30.0)
    cur = curves_of(a); res = {}
    for mode in ('linear', 'hermite'):
        val = {}
        for name, (t, v) in cur.items():
            s = sample(t, v, ts, mode); n = nodes.get(name)
            if n: s = np.clip(s, n['f'][0], n['f'][2])
            val[name] = s
        rows = {}
        for b in x['bones']:
            acc = np.tile([1.0, 0, 0, 0], (len(ts), 1)); pos = np.zeros((len(ts), 3)); scl = np.zeros((len(ts), 3))
            for l in b['links']:
                s = val.get(l['node'])
                if s is None: continue
                # spec (CAMPAIGN_FACEFX_RE.md, pose hook): link rot = the bone's absolute rotation at value 1; delta = conj(rest)*rot;
                # rotation = normalize(1 + sum v * (delta - 1)) (nlerp of the deltas); translation / scale add v * dPos / v * dScale
                rest = np.array(b['rest_rot'], float); conj = rest * np.array([1, -1, -1, -1])
                dq = qmul(conj[None, :], np.array(l['rot'], float)[None, :])[0]
                if dq[0] < 0: dq = -dq
                acc = acc + s[:, None] * (dq - np.array([1.0, 0, 0, 0]))
                pos += s[:, None] * np.array(l['dpos']); scl += s[:, None] * np.array(l['dscale'])
            rot = acc / np.linalg.norm(acc, axis=1)[:, None]
            rows[b['name']] = (pos, rot)
        res[mode] = rows
        with open(os.path.join(HERE, 'proof_%s_%s.csv' % (anim, mode)), 'w') as fo:
            fo.write('t,' + ','.join('%s_%s' % (bn, c) for bn in rows for c in ('px', 'py', 'pz', 'qw', 'qx', 'qy', 'qz')) + '\n')
            for i, t in enumerate(ts):
                fo.write('%.4f,' % t + ','.join('%.5f' % v for bn in rows for v in list(rows[bn][0][i]) + list(rows[bn][1][i])) + '\n')
    # voice envelope
    wav = os.path.join(P.EA, '..', 'content', *(a['cue'] and []))  # placeholder, resolved below
    import sqlite3
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'wfc'))
    import authored as A
    def find(t):
        if isinstance(t, dict):
            if t.get('class') == 'SoundNodeWaveEx' and t.get('wav'): return t
            for v in t.values():
                r = find(v)
                if r: return r
        elif isinstance(t, list):
            for v in t:
                r = find(v)
                if r: return r
    w = find(A.cue(a['cue'])) if a['cue'] else None
    if not w:
        out = {'actor': os.path.basename(f), 'anim': anim, 'curves': len(cur), 'start': a['start'], 'end': a['end'], 'b': a['b'],
               'wave': 'none in the cue tree: CSVs written, no voice comparison'}
        print(out); return out
    wp = os.path.join(os.path.dirname(P.EA), w['wav'])
    with wave.open(wp) as wf:
        sr = wf.getframerate(); ch = wf.getnchannels(); raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, np.int16).astype(float).reshape(-1, ch).mean(1) / 32768
    env = np.array([np.sqrt(np.mean(pcm[int(max(t, 0) * sr):int(max(t, 0) * sr + sr / 30)] ** 2)) if 0 <= t < len(pcm) / sr else 0 for t in ts])
    out = {'actor': os.path.basename(f), 'anim': anim, 'curves': len(cur), 'start': a['start'], 'end': a['end'], 'b': a['b'],
           'wave_s': round(len(pcm) / sr, 3)}
    jaw = [bn for bn in res['linear'] if 'Jaw' in bn][0]
    for mode in res:
        ang = quat_angle(res[mode][jaw][1])
        out['jaw_env_corr_' + mode] = round(float(np.corrcoef(ang, env)[0, 1]), 3)
        out['jaw_max_deg_' + mode] = round(float(ang.max()), 2)
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 4)); ax2 = ax.twinx()
        ax.plot(ts, env, color='0.6', label='voice RMS'); ax2.plot(ts, quat_angle(res['linear'][jaw][1]), label='jaw (linear)')
        ax2.plot(ts, quat_angle(res['hermite'][jaw][1]), label='jaw (hermite)', alpha=0.7)
        ax.set_xlabel('s'); ax.set_ylabel('voice RMS'); ax2.set_ylabel('jaw angle (deg)'); fig.legend(loc='upper right'); fig.tight_layout()
        fig.savefig(os.path.join(HERE, 'proof_%s.png' % anim), dpi=90); out['plot'] = 'proof_%s.png' % anim
    except Exception as ex:
        out['plot'] = 'not drawn: %s' % ex
    print(out)
    return out

if __name__ == '__main__':
    main(*sys.argv[1:3])
