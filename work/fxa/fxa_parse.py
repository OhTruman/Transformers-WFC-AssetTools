"""FaceFX .fxa (FACB 1710, UE3 Xbox 360 cook, big-endian) parser - AssetTools continuation of Systems' first pass
(Rebuild/docs/handoff/CAMPAIGN_FACEFX_FORMAT.md). Read-only on ExtractedAssets; output only to this folder.

Proven layout so far (all labels refer to the parse round trip over the 22 files; see report):
  header      "FACB", u32 archive version (1710), str licensee, str project, u32 1000, u16 1
  class table u32 nBuckets; per bucket: u32 hash, u32 n, n x (str className, u16 classVersion)
  name table  u32 nNames, nNames x str                         (name indices below index this table)
  actor       u32 ?, u32 ?   (FxActor / FxNamedObject header: actor name index 0, ...)
  master bone list   u32 nBones; per bone:
              u32 nameIdx, f32 restPos[3], f32 restRot[4] (w,x,y,z), f32 restScale[3], f32 invRestRot[4],
              u32 0x7FFFFFFF, f32 1.0, u32 nLinks,
              nLinks x {u32 nodeNameIdx, u32 1, f32 dPos[3], f32 rot[4], f32 dScale[3]}   (per face-graph node bone pose)
str = u32 length + bytes (no terminator)

  python fxa_parse.py            -> fxa_report.json (all 22 files) + prints a summary
"""
import glob, json, os, struct, sys

EA = r'F:\Transformers Rebuild\ExtractedAssets\content'
HERE = os.path.dirname(os.path.abspath(__file__))

class R:
    def __init__(self, d, o=0): self.d = d; self.o = o
    def u32(self): v = struct.unpack_from('>I', self.d, self.o)[0]; self.o += 4; return v
    def i32(self): v = struct.unpack_from('>i', self.d, self.o)[0]; self.o += 4; return v
    def u16(self): v = struct.unpack_from('>H', self.d, self.o)[0]; self.o += 2; return v
    def f32(self, n=1):
        v = struct.unpack_from('>%df' % n, self.d, self.o); self.o += 4 * n; return v if n > 1 else v[0]
    def s(self):
        n = self.u32()
        if n > 4096: raise ValueError('string length %d at 0x%x' % (n, self.o - 4))
        v = self.d[self.o:self.o + n].decode('latin1'); self.o += n; return v

def parse(path):
    d = open(path, 'rb').read(); r = R(d)
    assert d[:4] == b'FACB'; r.o = 4
    out = {'file': os.path.relpath(path, EA), 'bytes': len(d), 'version': r.u32(), 'licensee': r.s(), 'project': r.s(),
           'internal_version': r.u32(), 'flag': r.u16()}
    classes = []
    for _ in range(r.u32()):
        h = r.u32()
        for _ in range(r.u32()): classes.append({'hash': h, 'name': r.s(), 'version': r.u16()})
    out['classes'] = classes
    names = [r.s() for _ in range(r.u32())]
    out['names_count'] = len(names); out['names_end'] = r.o
    out['actor_header'] = [r.u32(), r.u32()]
    bones = []
    for _ in range(r.u32()):
        b = {'name': names[r.u32()], 'rest_pos': r.f32(3), 'rest_rot': r.f32(4), 'rest_scale': r.f32(3), 'inv_rest_rot': r.f32(4)}
        b['marker'] = r.u32(); b['weight'] = r.f32()
        links = []
        for _ in range(r.u32()):
            ni = r.u32(); flag = r.u32()
            links.append({'node': names[ni], 'flag': flag, 'dpos': r.f32(3), 'rot': r.f32(4), 'dscale': r.f32(3)})
        b['links'] = links; bones.append(b)
    out['bones'] = bones; out['bones_end'] = r.o
    out['after_bones_hex'] = d[r.o:r.o + 64].hex(' ')
    out['_names'] = names
    return out

def main():
    files = sorted(glob.glob(os.path.join(EA, '**', '*.fxa'), recursive=True))
    rep = []
    for f in files:
        try:
            x = parse(f)
            ok_marker = all(b['marker'] == 0x7FFFFFFF and abs(b['weight'] - 1.0) < 1e-6 for b in x['bones'])
            ok_flag = all(l['flag'] == 1 for b in x['bones'] for l in b['links'])
            print('%-55s names %4d bones %2d links %4d marker/weight ok %s link flag ok %s  next: %s' % (
                x['file'][-55:], x['names_count'], len(x['bones']), sum(len(b['links']) for b in x['bones']), ok_marker, ok_flag,
                x['after_bones_hex'][:47]))
            x.pop('_names'); rep.append(x)
        except Exception as ex:
            print('FAIL', f, ex); rep.append({'file': f, 'error': str(ex)})
    json.dump(rep, open(os.path.join(HERE, 'fxa_report.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()

# ---------------------------------------------------------------- compiled face graph + animation groups (2026-10-16 night)
def parse_full(path):
    """header .. bones (parse), then: face graph nodes, node lookup, groups / animations; returns dict + end offset"""
    x = parse(path); d = open(path, 'rb').read(); N = x['_names']; r = R(d, x['bones_end'])
    nodes = []
    for _ in range(r.u32()):
        t = r.u32(); ni = r.u32(); fl = r.f32(4); a0 = r.u32(); links = []
        for _ in range(r.u32()):                         # input links: {u32 inputNode, u32 linkFn, u32 nParams, nParams x f32}
            src = r.u32(); fn = r.u32(); np_ = r.u32(); links.append({'input': src, 'fn': fn, 'params': [r.f32() for _ in range(np_)]})
        props = []
        for _ in range(r.u32()):                         # user properties: u32 name, u32 type, i32 int, f32 real, u32 nStr, strs
            pn = r.u32(); pt = r.u32(); iv = r.i32(); rv = r.f32(); props.append({'name': N[pn], 'type': pt, 'int': iv, 'real': rv,
                                                                                  'strings': [r.s() for _ in range(r.u32())]})
        nodes.append({'type': t, 'name': N[ni], 'f': fl, 'a': a0, 'links': links, 'props': props})
    lut = {}
    for _ in range(r.u32()):
        r.u32()
        for _ in range(r.u32()): k = r.s(); lut[k] = r.u32()
    x['nodes'] = nodes; x['node_lookup_ok'] = len(lut) == len(nodes) and all(nodes[v]['name'] == k for k, v in lut.items())
    x['groups_at'] = r.o
    return x, d, N, r

def read_anim(r, N):
    a = {'name': N[r.u32()]}
    nc = r.u32(); a['curves'] = []
    for _ in range(nc):
        ni = r.u32(); z = r.u32(); a['curves'].append(N[ni])
        if z != 0: raise ValueError('curve pad %d' % z)
    k = -r.i32(); a['start'], a['end'] = r.f32(), r.f32()
    n2 = r.u32(); a['flag'] = r.u32(); a['end2'], a['b'] = r.f32(), r.f32()
    a['extra'] = [r.f32() for _ in range(a['flag'])]                  # flag = count of extra floats (ZetaPrime CINE_A2_Zeta_Grunt: 1)
    if n2 != nc: raise ValueError('curve count %d / %d at 0x%x' % (n2, nc, r.o))
    counts = struct.unpack_from('>%dH' % nc, r.d, r.o); r.o += 2 * nc
    if sum(counts) != k: raise ValueError('key counts %d != K %d' % (sum(counts), k))
    a['times'] = struct.unpack_from('>%dh' % k, r.d, r.o); r.o += 2 * k
    a['values'] = struct.unpack_from('>%db' % k, r.d, r.o); r.o += k
    if a['flag']:                                       # flag 1 (cinematic curves): K x (i8 slopeIn, i8 slopeOut) after the values
        a['slopes'] = struct.unpack_from('>%db' % (2 * k), r.d, r.o); r.o += 2 * k
    a['counts'] = counts; a['K'] = k
    a['blend_in'], a['blend_out'] = r.f32(), r.f32(); a['t_pad'] = r.u32()
    a['cue'] = r.s(); a['name2'] = r.s(); a['t_pad2'] = r.u32()
    return a

def parse_anims(path):
    x, d, N, r = parse_full(path)
    groups = []
    g0 = {'name': N[r.u32()], 'n': r.u32(), 'x': r.u32()}
    groups.append(g0); anims = []
    for _ in range(g0['x']):                            # x = number of groups after 'Default' (Dialogue + cinematic groups)
        g = {'name': N[r.u32()], 'n': r.u32()}; groups.append(g)
        for _ in range(g['n']): a = read_anim(r, N); a['group'] = g['name']; anims.append(a)
    return x, groups, anims, r.o, len(d)

def parse_all(path):
    """the whole file: ... animations, then the phoneme map (u32 n, n x {u32 phonemeId, u32 targetNameIdx, f32 weight},
    u32 nTargets, nTargets x u32 targetNameIdx); returns (actor, groups, anims, phoneme_map, end offset, file length)"""
    x, groups, anims, end, L = parse_anims(path)
    d = open(path, 'rb').read(); N = parse(path)['_names']; r = R(d, end)
    pm = [{'phoneme': r.u32(), 'target': N[r.u32()], 'weight': r.f32()} for _ in range(r.u32())]
    targets = [N[r.u32()] for _ in range(r.u32())]
    return x, groups, anims, {'map': pm, 'targets': targets}, r.o, L
