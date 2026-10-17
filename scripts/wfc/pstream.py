"""Decoder for WFC's compiled per-LOD particle module stream (the ParticleLODLevel native tail).

Layout (verified by validate_tagged.py-style cross-checks against surviving tagged module exports):
  +24  u8 N                      number of compiled modules
  +35  N records, 10 bytes each, separated by 7-byte running-count blocks:
         u8 ModuleId             Engine.ParticleModule.EParticleModuleId (enum names read from the cooked Engine enum)
         u8 flagA, u8 flagB      flagA = module enabled (HIGH); flagB = constant per module class, meaning UNKNOWN
                                 (pstream_flag_census.py over 2,736 MP-map LODs / 24,327 records)
         5 x 00, u16le payload   per-particle payload offset
  u8 count + count x u8          module indices (list following the records)
  ...                            further native lists (kept as raw hex, not decoded)
  float group:  u32 nF, nF raw distributions   (types 1 const, 2 curve, 3 uniform, 4 uniform curve)
  vector group: u32 nV, nV raw distributions   (types 7 const, 8 curve, 9 uniform, 10 uniform curve)
Distribution layout: u8 type, u8 op, u8 n, u8 chunk, i32 count, count BE floats (UE3 FRawDistribution).
Within each group the distributions follow MODULE ORDER; within a module, the property order in MODULE_DISTS.
A module with an unproven layout stops assignment for the rest of that group (values reported unassigned, never guessed).
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree  # noqa: E402

_ENUM = None
def module_ids():
    """EParticleModuleId names, read from the cooked Engine enum (index = compiled ModuleId byte)."""
    global _ENUM
    if _ENUM is None:
        p = objtree.package('Engine')
        x = p.exports[p._idx['engine.particlemodule.eparticlemoduleid'] - 1]
        raw = p.data[x['serial_offset']:x['serial_offset'] + x['serial_size']]
        n = struct.unpack_from('>i', raw, 20)[0]
        _ENUM = [p.names[struct.unpack_from('>i', raw, 24 + 8 * j)[0]] for j in range(n)]
    return _ENUM

# ModuleId -> (float-group property names, vector-group property names) in stream order.
# Property sets: cooked class schema (RawDistributionFloat / RawDistributionVector members).
MODULE_DISTS = {
    'PMI_Lifetime': (['Lifetime'], []),
    'PMI_Color': (['StartAlpha'], ['StartColor']),
    'PMI_ColorOverLife': (['AlphaOverLife'], ['ColorOverLife']),
    'PMI_ColorScaleOverLife': (['AlphaScaleOverLife'], ['ColorScaleOverLife']),
    'PMI_Size': ([], ['StartSize']),
    'PMI_SizeMultiplyVelocity': ([], ['VelocityMultiplier']),
    'PMI_SizeMultiplyLife': ([], ['LifeMultiplier']),
    'PMI_SizeScale': ([], ['SizeScale']),
    'PMI_MeshRotation': ([], ['StartRotation']),
    'PMI_MeshRotationRate': ([], ['StartRotationRate']),
    'PMI_MeshRotationRateMultiplyLife': ([], ['LifeMultiplier']),
    'PMI_Rotation': (['StartRotation'], []),
    'PMI_RotationOverLife': (['RotationOverLife'], []),
    'PMI_RotationRate': (['StartRotationRate'], []),
    'PMI_RotationRateMultiplyLife': (['LifeMultiplier'], []),
    'PMI_Location': ([], ['StartLocation']),
    'PMI_Velocity': (['StartVelocityRadial'], ['StartVelocity']),
    'PMI_VelocityOverLife': ([], ['VelOverLife']),
    'PMI_Acceleration': ([], ['Acceleration']),
    'PMI_AccelerationOverLife': ([], ['AccelOverLife']),
    'PMI_SubUV': (['SubImageIndex'], []),
    'PMI_VelocityInheritParent': ([], ['Scale']),
    # no distributions in the compiled stream (census: every LOD whose only unlayouted module is this one has
    # zero leftover float/vector entries: Gravity 392 LODs, ColorByParameter 561, Unknown 106, LocationEmitter 20)
    'PMI_Gravity': ([], []), 'PMI_ColorByParameter': ([], []), 'PMI_Unknown': ([], []), 'PMI_LocationEmitter': ([], []),
    # RE spawn runner case 0x15 (2026-10-18 addendum, 178abb0), CONFIRMED: base-class-first like the Sphere -> floats VelocityScale,
    # StartRadius (planar), StartHeight; vector StartLocation. (The first batch-2 note had StartRadius first: corrected.)
    'PMI_LocationPrimitiveCylinder': (['VelocityScale', 'StartRadius', 'StartHeight'], ['StartLocation']),
    # orders CONFIRMED by RE from the runners (spawn 0x8303E288 / update 0x83039A18, 2026-10-18): distribution k of the module
    'PMI_Orbit': ([], ['OffsetAmount', 'RotationAmount', 'RotationRateAmount']),
    'PMI_LocationDirect': ([], ['Location', 'LocationOffset', 'ScaleFactor']),     # Direction is not compiled (no runner reads it)
    # RE spawn runner 0x8303E288 case 0x16 (2026-10-18), CONFIRMED: the LocationPrimitiveBase fields come first, so float k=0 is
    # VelocityScale (read only when the block's Velocity flag is set) and k=1 StartRadius; vector k=0 StartLocation
    'PMI_LocationPrimitiveSphere': (['VelocityScale', 'StartRadius'], ['StartLocation']),
    'PMI_LocationEmitterDirect': ([], []),                          # case 0x14: no compiled distributions (param block only)
    'PMI_DynamicParameter': (['DynamicParams[0].ParamValue', 'DynamicParams[1].ParamValue',   # case 0x1D: k = slot index
                              'DynamicParams[2].ParamValue', 'DynamicParams[3].ParamValue'], []),
    # RE update runner 0x83039A18 case 0x21 (call site 0x8303DFD0..DFF0, 2026-10-18): vector k=0 -> payload +4/+8, k=1 -> +0x10/+0x14
    # (CONFIRMED); naming k=0 SubUVPosition, k=1 SubUVSize by class declaration order, as for every other module (RE: HIGH)
    'PMI_SubUVDirect': ([], ['SubUVPosition', 'SubUVSize']),
}
# order NOT read from the runner but taken from the runner's option order (PROVISIONAL): Orbit's options are read Offset (@4),
# Rotation (@0x10), RotationRate (@0x1C) in that order (RE 2026-10-18), so the three vector distributions are named in that order
# (SubUVDirect resolved by RE 2026-10-18: now in MODULE_DISTS)
ORDER_PROVISIONAL = {}
# census-proven distribution COUNTS whose property order inside the module is not proven
MULTI_UNPROVEN_EXTRA = {
}
CENSUS_COUNTS = {}     # LocationDirect resolved by RE 2026-10-18 (3 distributions, named)
# modules owning >1 float distribution whose internal order is not proven: values are assigned to the
# module, the property only when every candidate carries the identical value
MULTI_UNPROVEN = {
    # (Orbit, LocationDirect, Sphere, DynamicParameter: orders confirmed by RE 2026-10-18, now in MODULE_DISTS)
}
MULTI_UNPROVEN.update(MULTI_UNPROVEN_EXTRA)
FLOAT_T, VEC_T = (1, 2, 3, 4), (7, 8, 9, 10)
DIST_LAYOUT = {
    'constant (types 1/7)': 'values = the value (1 float / 3 floats)',
    'uniform (types 3/9)': 'values = two endpoints A then B (1 or 3 floats each); per-particle value = lerp(A, B, random). '
                           'Endpoint order is as stored; uniform sampling makes it irrelevant',
    'constant curve (types 2/8)': 'values[0:2] = output range min/max, values[2] = start time, values[3] = time scale '
                                  '(samples per unit time); then N samples of 1 (float) or 3 (vector) floats, sample i at '
                                  't = start + i / time_scale, linear between samples (UE3 FRawDistribution baking)',
    'uniform curve (types 4/10)': 'same header; each sample holds two endpoints (2 or 6 floats)',
    'op': '1 = constant/curve, 2 = random between endpoints (UE3 ERawDistributionOperation)',
    'Lifetime 0': 'UE3: particle lives until killed by the emitter (no expiry)',
    'provenance': 'header/sample layout from the Systems lodscan notes, consistent with every decoded table '
                  '(sample count = time_scale + 1 for 0..1 curves)'}
DIST_TYPE = {1: 'float constant', 2: 'float constant curve', 3: 'float uniform', 4: 'float uniform curve',
             7: 'vector constant', 8: 'vector constant curve', 9: 'vector uniform', 10: 'vector uniform curve'}

def _dist_at(d, i):
    t, op, n, ch = d[i], d[i + 1], d[i + 2], d[i + 3]
    cnt = struct.unpack_from('>i', d, i + 4)[0]
    if not (t in FLOAT_T + VEC_T and op <= 3 and 1 <= n <= 64 and 1 <= ch <= 16 and 1 <= cnt <= 4096
            and i + 8 + cnt * 4 <= len(d)):
        return None
    vals = list(struct.unpack_from('>%df' % cnt, d, i + 8))
    return {'offset': i, 'type': t, 'kind': DIST_TYPE.get(t), 'op': op, 'n': n, 'chunk': ch, 'count': cnt,
            'values': [round(v, 6) for v in vals]}, i + 8 + cnt * 4

def _group(d, i, types):
    n = struct.unpack_from('>I', d, i)[0]
    if not 0 <= n <= 64: return None
    out, j = [], i + 4
    for _ in range(n):
        r = _dist_at(d, j) if j + 8 <= len(d) else None
        if not r or r[0]['type'] not in types: return None
        out.append(r[0]); j = r[1]
    return out, j

def parse(t):
    """t = bytes after the LOD's tagged block."""
    ids = module_ids()
    n = t[24]; i = 35; recs = []
    for m in range(n):
        b = t[i:i + 10]
        recs.append({'index': m, 'module_id': b[0], 'module': ids[b[0]] if b[0] < len(ids) else 'PMI_?%d' % b[0],
                     'flagA': b[1], 'flagB': b[2], 'payload_offset': b[8] | (b[9] << 8),
                     # bytes 3..6 of the record: BE export index of the module object (non-zero on module classes without a
                     # compiled ModuleId, e.g. ParticleModuleCollision / ParticleModuleSwitchableColorScaleOverLife)
                     'object_ref': struct.unpack_from('>i', b, 3)[0]})
        i += 10 + (7 if m < n - 1 else 0)
    cnt = t[i]; lst = list(t[i + 1:i + 1 + cnt]); i += 1 + cnt
    for j in range(i, len(t) - 8):
        g = _group(t, j, FLOAT_T)
        if g is None or g[1] + 4 > len(t): continue
        g2 = _group(t, g[1], VEC_T)
        if g2 is None or not (g[0] or g2[0]): continue   # zero padding parses as two empty groups
        return {'records': recs, 'list_after_records': lst, 'float_group_offset': j, 'float_group': g[0],
                'vector_group_offset': g[1], 'vector_group': g2[0], 'trailing_bytes': len(t) - g2[1],
                'raw_between_list_and_groups': t[i:j].hex(' '), 'raw_trailing': t[g2[1]:].hex(' ')}
    raise ValueError('distribution groups not found')

def assign(parsed):
    res = {}
    for g, key, gi in (('float', 'float_group', 0), ('vector', 'vector_group', 1)):
        q = list(parsed[key]); ok = True; out = []
        for r in parsed['records']:
            if not ok: break
            m = r['module']
            if m in MODULE_DISTS:
                for prop in MODULE_DISTS[m][gi]:
                    if not q: ok = False; break
                    out.append({'module_index': r['index'], 'module': m, 'property': prop, 'dist': q.pop(0),
                                'confidence': 'CONFIRMED'})
            elif m in ORDER_PROVISIONAL:
                for prop in ORDER_PROVISIONAL[m][gi]:
                    if not q: ok = False; break
                    out.append({'module_index': r['index'], 'module': m, 'property': prop, 'dist': q.pop(0), 'confidence': 'PROVISIONAL',
                                'note': 'order rated HIGH by RE (not read directly from the runner)'})
            elif m in MULTI_UNPROVEN:
                props = MULTI_UNPROVEN[m][gi]
                n = CENSUS_COUNTS[m][gi] if m in CENSUS_COUNTS else len(props)
                if len(q) < n: ok = False; break
                take = [q.pop(0) for _ in range(n)]
                same = len(set(str(x['values']) for x in take)) <= 1
                for pi, x in enumerate(take):
                    known = len(props) == 1 or (same and n == len(props))
                    out.append({'module_index': r['index'], 'module': m, 'property': props[pi] if known else None,
                                'property_candidates': props, 'dist': x,
                                'confidence': 'CONFIRMED' if known else 'PARTIAL',
                                'note': None if len(props) == 1 else ('every candidate property holds this same value' if same
                                         else 'belongs to this module; order among candidates unproven')})
            else:
                ok = False
        res[g] = out
        res[g + '_unassigned'] = q
        res[g + '_complete'] = ok and not q
    return res

def lod_tail(p, i):
    tags, used = p._tr.read_object(i)
    x = p.exports[i - 1]
    return p.data[x['serial_offset'] + used:x['serial_offset'] + x['serial_size']]

# Scalar module fields Rendering's batch 1 needs (2026-10-18). The per-instance module objects are stripped in the cook and the compiled
# stream decoded here carries only distributions, so these are CLASS DEFAULTS from the cooked CDOs (labelled per field); a class with
# no CDO in the cook gives UNKNOWN (None), never a guess. Per-instance values: only if RE finds them in the compiled stream.
_FIELDS = None
def class_default_fields():
    global _FIELDS
    if _FIELDS is None:
        import authored as _A
        sph = _A.values('Engine.Default__ParticleModuleLocationPrimitiveSphere') or {}
        cbp = _A.values('Engine.Default__ParticleModuleColorByParameter') or {}
        src_s = 'class default: Engine.Default__ParticleModuleLocationPrimitiveSphere (per-instance value not in the cook stream)'
        src_s0 = 'class default: not set in the cooked CDO, so the UE3 property default (bool False) (per-instance value not in the cook stream)'
        src_c = 'class default: Engine.Default__ParticleModuleColorByParameter (per-instance value not in the cook stream)'
        _FIELDS = {
            'PMI_Gravity': ({'GravityMultiplier': None},
                            {'GravityMultiplier': 'UNKNOWN: HM_Engine.HmParticleModuleGravity has no CDO in the cook; per-instance value not in the cook stream'}),
            'PMI_LocationPrimitiveSphere': (
                {**{k: bool(sph.get(k, False)) for k in ('Positive_X', 'Positive_Y', 'Positive_Z', 'Negative_X', 'Negative_Y', 'Negative_Z')},
                 'SurfaceOnly': bool(sph.get('SurfaceOnly', False)), 'Velocity': bool(sph.get('Velocity', False))},
                {**{k: (src_s if k in sph else src_s0) for k in ('Positive_X', 'Positive_Y', 'Positive_Z', 'Negative_X', 'Negative_Y', 'Negative_Z')},
                 'SurfaceOnly': src_s if 'SurfaceOnly' in sph else src_s0, 'Velocity': src_s if 'Velocity' in sph else src_s0}),
            'PMI_ColorByParameter': ({'ColorParam': cbp.get('ColorParam'), 'DefaultColor': cbp.get('DefaultColor')},
                                     {'ColorParam': src_c if 'ColorParam' in cbp else 'class default: not set in the cooked CDO, so the UE3 name default (None) '
                                      '(per-instance value not in the cook stream)', 'DefaultColor': src_c}),
            'PMI_DynamicParameter': ({'DynamicParams': None},
                                     {'DynamicParams': 'UNKNOWN: ParticleModuleParameterDynamic has no CDO in the cook; slot ParamName / bUseEmitterTime / '
                                                       'bSpawnTimeOnly per instance not in the cook stream'}),
        }
    return _FIELDS

# Compiled parameter blob (RE re-workspace-0c, 2026-10-18; runner layouts read from the native code, verified on
# FX_AssaultRifle_p.FX.Tracer_AssaultRifle_FX ...ParticleLODLevel_8227): after the four module-order lists of the raw region come
# u32 SIZE, SIZE bytes = the modules' parameter blocks concatenated IN RECORD ORDER (modules without parameters add nothing),
# then the LOD name list (u32 n + n x {i32 name index, i32 number}) that name-typed fields index. All big-endian.
_I, _F, _N = 'i', 'f', 'name'
_AX = [('Positive_X', _I), ('Positive_Y', _I), ('Positive_Z', _I), ('Negative_X', _I), ('Negative_Y', _I), ('Negative_Z', _I)]
BLOCKS = {
    'PMI_SizeMultiplyLife': [('MultiplyX', _I), ('MultiplyY', _I), ('MultiplyZ', _I)],
    'PMI_ColorByParameter': [('ColorParam', _N), ('DefaultColor', 'argb')],
    'PMI_ColorScaleOverLife': [('bEmitterTime', _I)],
    'PMI_Gravity': [('GravityMultiplier', _F)],
    'PMI_LocationEmitter': [('EmitterName', _N), ('InheritSourceVelocityScale', _F), ('InheritSourceRotationScale', _F),
                            ('SelectionMethod', 'enum:ELESM_Random,ELESM_Sequential'), ('bInheritSourceVelocity', _I), ('bInheritSourceRotation', _I)],
    'PMI_DynamicParameter': [('bUseEmitterTime[0]', _I), ('bUseEmitterTime[1]', _I), ('bUseEmitterTime[2]', _I), ('bUseEmitterTime[3]', _I)],
    'PMI_LocationPrimitiveSphere': _AX + [('SurfaceOnly', _I), ('Velocity', _I)],
    'PMI_LocationPrimitiveCylinder': _AX + [('SurfaceOnly', _I), ('Velocity', _I), ('RadialVelocity', _I), ('HeightAxis', 'enum:PMLPC_HEIGHTAXIS_X,PMLPC_HEIGHTAXIS_Y,PMLPC_HEIGHTAXIS_Z')],
    'PMI_Orbit': [('ChainMode (H, not read by the runners)', _I)] + [(f'{a}.{b}', _I) for a in ('OffsetOptions', 'RotationOptions', 'RotationRateOptions')
                                                                       for b in ('bProcessDuringSpawn', 'bProcessDuringUpdate', 'bUseEmitterTime')],
    'PMI_LocationEmitterDirect': [('EmitterName (H)', _N)],
    # named by RE from the runners (2026-10-18; sizes from the AssetTools census)
    'PMI_MeshRotation': [('bInheritParent', _I)],
    'PMI_VelocityOverLife': [('Absolute', _I)],
    'PMI_SizeMultiplyVelocity': [('MultiplyX', _I), ('MultiplyY', _I), ('MultiplyZ', _I)],
    'PMI_SizeScale': [('EnableX', _I), ('EnableY', _I), ('EnableZ', _I)],
}
ZERO_BLOCK = {'PMI_Lifetime', 'PMI_Size', 'PMI_Velocity', 'PMI_LocationDirect', 'PMI_VelocityInheritParent', 'PMI_AccelerationOverLife'}
# block sizes SOLVED by the census (pstream_blob_census.py: LODs where the module is the only unknown, SIZE - known = constant);
# their field layout is not from RE, so values are emitted as raw big-endian int32 words 'raw[k]' (UNNAMED) for RE to name
CENSUS_SIZES = {'PMI_Color': 0, 'PMI_Location': 0, 'PMI_Rotation': 0, 'PMI_SubUV': 0, 'PMI_Unknown': 0,
                'PMI_ColorOverLife': 0, 'PMI_MeshRotationRate': 0, 'PMI_RotationRate': 0,
                'PMI_SubUVDirect': 0, 'PMI_Acceleration': 0}
def block_size(m):
    if m in ZERO_BLOCK: return 0
    if m in BLOCKS: return 4 * len(BLOCKS[m])
    return CENSUS_SIZES.get(m)

def _fields_for(r, name, pb):
    """the record's fields: compiled values from the parameter blob when decoded, else (A) class defaults, labelled per field"""
    blk = (pb.get('blocks') or {}).get(r['index'])
    if blk is not None:
        return {'fields': dict(blk), 'fields_source': {k: 'compiled' for k in blk}}
    if name in class_default_fields():
        f, s = class_default_fields()[name]
        return {'fields': dict(f), 'fields_source': {k: 'class_default: ' + v for k, v in s.items()},
                'fields_note': 'parameter blob not decoded for this LOD (%s)' % pb.get('status')}
    return {}

def param_blob(pr, p=None):
    """-> {'size', 'blocks': {record index: {field: value}}, 'names', 'status'}; status 'decoded' only when SIZE == the sum of the known
    block sizes of the LOD's records (every record's size known)."""
    raw = bytes.fromhex((pr.get('raw_between_list_and_groups') or '').replace(' ', ''))
    o = 0
    try:
        # FOUR module-order lists (u32 count + count bytes), then u32 SIZE. RE read the 4th list's count as "int 0": it is empty in most
        # LODs, but holds the Orbit module's index in the Orbit LODs (census 2026-10-18: SIZE then fits exactly)
        for _ in range(4):
            n = struct.unpack_from('>I', raw, o)[0]; o += 4 + n
        size = struct.unpack_from('>I', raw, o)[0]; o += 4
    except struct.error:
        return {'status': 'no blob header'}
    if o + size > len(raw): return {'status': 'no blob header', 'at': o - 4}
    blob = raw[o:o + size]; o += size; names = []
    try:
        nn = struct.unpack_from('>I', raw, o)[0]
        for k in range(nn):
            ni, num = struct.unpack_from('>ii', raw, o + 4 + 8 * k)
            nm = p.names[ni] if p is not None and 0 <= ni < len(p.names) else ni
            names.append(nm if not num else '%s_%d' % (nm, num - 1))
    except struct.error:
        pass
    sizes = [block_size(r['module']) for r in pr['records']]
    out = {'size': size, 'names': names}
    if any(s is None for s in sizes):
        out['status'] = 'unknown block size for ' + ', '.join(sorted({r['module'] for r, s in zip(pr['records'], sizes) if s is None})); return out
    if sum(sizes) != size:
        out['status'] = 'size mismatch: SIZE %d != sum of known blocks %d' % (size, sum(sizes)); return out
    blocks = {}; b = 0
    for r, s in zip(pr['records'], sizes):
        if not s: continue
        f = {}
        if r['module'] not in BLOCKS:                         # census-sized block, layout unknown: raw words
            for k in range(s // 4): f['raw[%d] (UNNAMED: size from census, layout not from RE)' % k] = struct.unpack('>i', blob[b + 4 * k:b + 4 * k + 4])[0]
            blocks[r['index']] = f; b += s; continue
        for k, (name, typ) in enumerate(BLOCKS[r['module']]):
            w = blob[b + 4 * k:b + 4 * k + 4]
            if typ == _F: v = round(struct.unpack('>f', w)[0], 7)
            elif typ == 'argb': v = {'A': w[0], 'R': w[1], 'G': w[2], 'B': w[3]}
            else:
                v = struct.unpack('>i', w)[0]
                if typ == _N: v = names[v] if 0 <= v < len(names) else {'name_index': v}
                elif typ.startswith('enum:'):
                    opts = typ[5:].split(','); v = opts[v] if 0 <= v < len(opts) else (opts[-1] if 'HEIGHTAXIS' in typ else v)
                elif name in [a for a, _ in _AX] or name.startswith(('b', 'Surface', 'Velocity', 'Radial', 'Offset', 'Rotation', 'Multiply', 'Enable', 'Absolute')):
                    v = bool(v) if v in (0, 1) else v
            f[name] = v
        blocks[r['index']] = f; b += s
    out.update({'status': 'decoded', 'blocks': blocks})
    return out

def system(ps, pkg=None):
    """particles.summarize() (tagged data) + every LOD's compiled module list with assigned distributions."""
    import particles
    s = particles.summarize(ps, pkg)
    if s.get('missing_in'): return s
    p = objtree.package(s['package'])
    s['provenance'] = ('tagged props (ParticleSystem / Emitter / LOD / RequiredModule / TypeData): CONFIRMED AUTHORED DATA; '
                       'compiled modules: ModuleId from the cooked EParticleModuleId enum + distributions assigned by '
                       'pstream.assign (module order; per-class property order) - CONFIRMED where "complete" is true')
    s['distribution_layout'] = DIST_LAYOUT
    for e in s['emitters']:
        for L in e['lods']:
            L.pop('native_stream', None)
            try:
                pr = parse(lod_tail(p, p._idx[L['lod'].lower()]))
            except Exception as ex:
                L['compiled_modules_error'] = str(ex); continue
            a = assign(pr)
            pb = param_blob(pr, p)
            L['parameter_blob'] = {k: v for k, v in pb.items() if k != 'blocks'}
            mods = []
            for r in pr['records']:
                obj = cls = None; props = None; name = r['module']
                ref = r.get('object_ref') or 0
                if 0 < ref <= len(p.exports) and p.class_name(p.exports[ref - 1]).startswith('ParticleModule'):
                    obj = p.object_path(ref); cls = p.class_name(p.exports[ref - 1])
                    if r['module_id'] == 0:   # PMI_Unknown: name the slot by its object class, carry its authored properties
                        import authored as _A
                        name = 'PMI_' + cls[len('ParticleModule'):]
                        props = dict(_A.values(obj) or {})
                        if cls == 'ParticleModuleCollision': props.setdefault('CollisionCompletionOption', 'EPCC_Kill (default, enum 0)')
                        if cls == 'ParticleModuleSwitchableColorScaleOverLife': props.setdefault('ChannelSwitch', 'PMC_A (default)')
                if name == 'PMI_VelocityOverLife':
                    # Absolute: the compiled parameter blob carries it (RE 2026-10-18: VelocityOverLife block = int Absolute); else the class
                    # default False (Engine.Default__ParticleModuleVelocityOverLifetime does not set it): velocity *= VelOverLife(t) (UE3)
                    blk = (pb.get('blocks') or {}).get(r['index']) or {}
                    vol_props = {'Absolute': bool(blk['Absolute'])} if 'Absolute' in blk else {'Absolute': False}
                mods.append({'index': r['index'], 'module': name, 'module_id': r['module_id'],
                             **({'module_enum': r['module'], 'module_object': obj, 'module_class': cls,
                                 'module_properties (authored, defaults filled)': props} if props is not None else {}),
                             'in_list_after_records': r['index'] in pr['list_after_records'],
                             'raw_flags': [r['flagA'], r['flagB']],
                             'enabled (flagA; HIGH - particle_flag_census.json)': r['flagA'] == 1,
                             'payload_offset': r['payload_offset'],
                             **({'props': vol_props} if name == 'PMI_VelocityOverLife' else {}),
                             **(_fields_for(r, name, pb)),
                             'distributions': [{'property': x['property'], 'property_candidates': x.get('property_candidates'),
                                                'kind': x['dist']['kind'], 'op': x['dist']['op'],
                                                'values': x['dist']['values'], 'confidence': x['confidence'],
                                                **({'note': x['note']} if x.get('note') else {})}
                                               for x in a['float'] + a['vector'] if x['module_index'] == r['index']]})
            L['compiled_modules'] = mods
            L['assignment_complete'] = a['float_complete'] and a['vector_complete']
            if a['float_unassigned'] or a['vector_unassigned']:
                L['unassigned_distributions'] = {'float': a['float_unassigned'], 'vector': a['vector_unassigned']}
            L['raw_unparsed_hex'] = {'between_lists_and_groups': pr['raw_between_list_and_groups'],
                                     'trailing': pr['raw_trailing']}
    return s

if __name__ == '__main__':
    p = objtree.package(sys.argv[1])
    for k, i in sorted(p._idx.items()):
        if k.startswith(sys.argv[2].lower()) and p.class_name(p.exports[i - 1]) == 'ParticleLODLevel':
            pr = parse(lod_tail(p, i)); a = assign(pr)
            print(k, [(r['module'], r['flagA'], r['flagB']) for r in pr['records']])
            for g in ('float', 'vector'):
                for e in a[g]: print('  ', g, e['module'], e['property'], e['dist']['type'], e['dist']['values'][:12])
                print('   complete', a[g + '_complete'], 'unassigned', len(a[g + '_unassigned']))
