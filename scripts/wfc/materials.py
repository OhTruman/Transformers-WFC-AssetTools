"""Practical UE3 material resolution for the renderer (not a shader reimplementation).

For a Material: trace every material input (DiffuseColor, Normal, EmissiveColor,
SpecularColor, SpecularPower, Opacity, OpacityMask, CustomLighting, ...) through the
cooked MaterialExpression graph down to texture-sample nodes, recording parameter
name, default texture and the channel mask on the edge.  For a MaterialInstance:
resolve the parent chain and apply TextureParameterValues / Scalar / Vector overrides
by parameter name.  Texture roles come from graph connectivity first and texture-name
heuristics second (recorded as `role_source`).
"""
import json, os, re, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract  # noqa: E402

INPUTS = ['DiffuseColor', 'Normal', 'EmissiveColor', 'SpecularColor', 'SpecularPower', 'Opacity',
          'OpacityMask', 'CustomLighting', 'CustomSkylightDiffuse', 'Distortion', 'TwoSidedLightingMask',
          'AnisotropicDirection', 'WorldPositionOffset']
ROLE_OF_INPUT = {'DiffuseColor': 'base_color', 'Normal': 'normal', 'EmissiveColor': 'emissive',
                 'SpecularColor': 'specular', 'SpecularPower': 'specular', 'Opacity': 'opacity',
                 'OpacityMask': 'opacity', 'CustomLighting': 'base_color'}
NAME_ROLES = [('normal', re.compile(r'(norm|nrm|_n$|normal)', re.I)),
              ('emissive', re.compile(r'(emis|glow|illum)', re.I)),
              ('specular', re.compile(r'(spec)', re.I)),
              ('opacity', re.compile(r'(opac|alpha)', re.I)),
              ('mask', re.compile(r'(mask|lut|grunge|cust)', re.I)),
              ('base_color', re.compile(r'(clr|diff|color|colour|albedo|_d$|base)', re.I))]

_assets = None
def assets():
    global _assets
    if _assets is None:
        A = json.load(open(os.path.join(extract.MANI, 'assets.json'), encoding='utf-8'))['assets']
        _assets = {a['object_path'].lower(): a for a in A}
    return _assets

@lru_cache(maxsize=24)
def package(name):
    p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
    p._pr = props.PropReader(p)
    p._pidx = {p.object_path(i + 1).lower(): i + 1 for i in range(len(p.exports))}
    return p

def tex_file(opath):
    a = assets().get((opath or '').lower())
    if not a: return None
    return next((o for o in a['extracted'] if o.endswith('.png')), None)

def _obj(pkg, path):
    i = pkg._pidx.get(path.lower())
    if not i: return None, None
    try:
        return i, props.props_dict(pkg._pr.read_object(i)[0])
    except Exception:
        return i, None

def _edges(value):
    """Yield (expression_ref, mask) for every FExpressionInput inside a property value."""
    if isinstance(value, list):
        if value and isinstance(value[0], dict) and 'name' in value[0] and 'type' in value[0]:
            d = {t['name']: t['value'] for t in value}
            ex = d.get('Expression')
            if isinstance(ex, dict) and 'ref' in ex:
                mask = ''.join(c for c, k in zip('RGBA', ('MaskR', 'MaskG', 'MaskB', 'MaskA')) if d.get(k)) \
                    if d.get('Mask') else ''
                yield ex['ref'], mask
            for t in value:
                yield from _edges(t['value'])
        else:
            for x in value: yield from _edges(x)
    elif isinstance(value, dict) and 'ref' not in value:
        for x in value.values(): yield from _edges(x)

def trace(pkg, start_ref, start_mask, depth_limit=60):
    """Return [(texture_node_props, depth, mask)] reachable from an expression."""
    out, seen, stack = [], set(), [(start_ref, 0, start_mask)]
    while stack:
        ref, depth, mask = stack.pop()
        if ref in seen or depth > depth_limit: continue
        seen.add(ref)
        i, d = _obj(pkg, ref)
        if d is None: continue
        cls = pkg.class_name(pkg.exports[i - 1])
        if 'TextureSample' in cls or cls == 'MaterialExpressionTextureSampleParameterCube':
            out.append({'node': ref.rsplit('.', 1)[-1], 'class': cls, 'param': d.get('ParameterName'),
                        'texture': (d.get('Texture') or {}).get('ref'), 'depth': depth, 'mask': mask})
        own = ''.join(c for c in 'RGBA' if d.get(c)) if cls == 'MaterialExpressionComponentMask' else ''
        for k, v in d.items():
            if k in ('Texture',): continue
            for r2, m2 in _edges(v):
                # nearest channel selection above the texture wins
                stack.append((r2, depth + 1, own or m2 or mask))
    return out

def describe_material(opath):
    a = assets().get(opath.lower())
    if not a: return {'material': opath, 'error': 'not in assets.json'}
    pkg = package(a['owner_package'])
    i, d = _obj(pkg, opath)
    if d is None: return {'material': opath, 'error': 'properties unparsed'}
    res = {'material': opath, 'class': 'Material', 'blend_mode': d.get('BlendMode', 'BLEND_Opaque'),
           'two_sided': bool(d.get('TwoSided', False)), 'lighting_model': d.get('LightingModel', 'MLM_Phong'),
           'opacity_mask_clip': d.get('OpacityMaskClipValue'), 'samplers': {}, 'inputs': {}}
    for inp in INPUTS:
        v = d.get(inp)
        if v is None: continue
        hits = []
        for ref, mask in _edges(v):
            hits += trace(pkg, ref, mask)
        if hits: res['inputs'][inp] = hits
        for h in hits:
            key = h['param'] or h['node']
            s = res['samplers'].setdefault(key, {'param': h['param'], 'default_texture': h['texture'],
                                                 'inputs': [], 'min_depth': h['depth'], 'channels': set()})
            if inp not in s['inputs']: s['inputs'].append(inp)
            s['min_depth'] = min(s['min_depth'], h['depth'])
            if h['mask']: s['channels'].add(h['mask'])
    for s in res['samplers'].values(): s['channels'] = sorted(s['channels'])
    return res

def _param_list(d, key, valkey):
    out = {}
    for item in d.get(key) or []:
        if isinstance(item, list):
            t = {x['name']: x['value'] for x in item}
            out[t.get('ParameterName')] = t.get(valkey)
    return out

def resolve(opath, _depth=0):
    """Full description with parent chain, overrides and texture roles."""
    a = assets().get(opath.lower())
    if not a: return {'material': opath, 'error': 'not in assets.json', 'roles': {}}
    if a['class'] == 'Material':
        base = describe_material(opath); base['parent_chain'] = []
        base['texture_params'] = {k: s['default_texture'] for k, s in base.get('samplers', {}).items()}
        base['scalars'] = {}; base['vectors'] = {}
    else:
        pkg = package(a['owner_package'])
        _, d = _obj(pkg, opath)
        d = d or {}
        parent = (d.get('Parent') or {}).get('ref')
        base = resolve(parent, _depth + 1) if parent and _depth < 10 else {'samplers': {}, 'texture_params': {}, 'scalars': {}, 'vectors': {}, 'parent_chain': []}
        base = json.loads(json.dumps(base, default=list))
        base['parent_chain'] = [parent] + base.get('parent_chain', []) if parent else []
        tp = {k: (v or {}).get('ref') if isinstance(v, dict) else v for k, v in _param_list(d, 'TextureParameterValues', 'ParameterValue').items()}
        # a TextureParameterValues entry whose value is None is 'not set': inherit the parent's texture (stock UE3
        # UMaterialInstanceConstant::GetTextureParameterValue; RE 2026-10-05, HIGH)
        base['texture_params'].update({k: v for k, v in tp.items() if k and v})
        base['scalars'].update(_param_list(d, 'ScalarParameterValues', 'ParameterValue'))
        base['vectors'].update({k: v for k, v in _param_list(d, 'VectorParameterValues', 'ParameterValue').items()})
        base['material'] = opath; base['class'] = a['class']
        if 'BlendMode' in d: base['blend_mode'] = d['BlendMode']
    if _depth: return base
    return finalize(base)

def finalize(m):
    textures = {}
    for key, s in m.get('samplers', {}).items():
        tex = m['texture_params'].get(s['param'] or key, s['default_texture']) if s.get('param') else s['default_texture']
        textures[key] = {'texture': tex, 'file': tex_file(tex), 'inputs': s['inputs'],
                         'channels': s.get('channels', []), 'graph_depth': s['min_depth']}
    for k, tex in m.get('texture_params', {}).items():
        if k not in textures and tex:
            textures[k] = {'texture': tex, 'file': tex_file(tex), 'inputs': [], 'channels': [], 'graph_depth': None}
    roles = {}
    names = dict(NAME_ROLES)
    def name_role(k, t):
        """role implied by the authored parameter name, else the texture name"""
        for src in (k, (t['texture'] or '').rsplit('.', 1)[-1]):
            for role, rx in NAME_ROLES:
                if rx.search(src): return role
        return None
    blend = m.get('blend_mode', 'BLEND_Opaque')
    cube = {k for k, t in textures.items() if re.search(r'cube', (t['texture'] or '') + k, re.I)}
    if cube:
        k = sorted(cube)[0]; roles['reflection'] = dict(textures[k], sampler=k, role_source='cubemap')
    textures_nc = {k: t for k, t in textures.items() if k not in cube}
    # 0) authored parameter name agrees with graph connectivity (strongest evidence)
    for role in ('normal', 'base_color', 'specular', 'emissive', 'opacity'):
        if role == 'opacity' and blend == 'BLEND_Opaque': continue
        c = [(t['graph_depth'], k) for k, t in textures_nc.items()
             if t['graph_depth'] is not None and name_role(k, t) == role
             and any(ROLE_OF_INPUT.get(i) == role for i in t['inputs'])]
        if c:
            k = min(c)[1]; roles[role] = dict(textures[k], sampler=k, role_source='param_name+graph')
    # 1) graph connectivity: shallowest texture feeding each input, excluding textures
    #    whose names say they are something else (masks/normals/LUTs)
    for role in ('normal', 'base_color', 'specular', 'emissive', 'opacity'):
        if role in roles: continue
        if role == 'opacity' and blend == 'BLEND_Opaque': continue
        cands = [(t['graph_depth'], k) for k, t in textures_nc.items()
                 if t['graph_depth'] is not None and any(ROLE_OF_INPUT.get(i) == role for i in t['inputs'])]
        cands = [c for c in cands if name_role(c[1], textures[c[1]]) in (None, role)]
        if role == 'emissive':     # require name evidence: effect masks also feed emissive
            cands = [c for c in cands if name_role(c[1], textures[c[1]]) == 'emissive']
        taken = {r['sampler'] for r in roles.values()}
        cands = [c for c in cands if c[1] not in taken] if role != 'normal' else cands
        if cands:
            k = min(cands)[1]
            roles[role] = dict(textures[k], sampler=k, role_source='graph')
    # 2) name heuristics for roles still empty
    for role, rx in NAME_ROLES:
        if role in roles: continue
        for k, t in textures_nc.items():
            if role == 'opacity' and blend == 'BLEND_Opaque': break
            if t['texture'] and rx.search(t['texture'].rsplit('.', 1)[-1]) and k not in [r['sampler'] for r in roles.values()]:
                roles[role] = dict(t, sampler=k, role_source='name'); break
    notes = []
    if not roles.get('base_color'):
        notes.append('no base color texture identified; use constant fallback')
    if any('DifLum' in (t['texture'] or '') or 'SpecPwr' in (t['texture'] or '') for t in textures.values()):
        notes.append('packed-channel texture (e.g. SpecPwr_DifLum_EnrGlow): R/G/B carry separate terms; see channels')
    if m.get('lighting_model') == 'MLM_Custom':
        notes.append('custom lighting model; renderer should approximate with Phong')
    out = {'material': m['material'], 'class': m.get('class'), 'parent_chain': m.get('parent_chain', []),
           'blend_mode': m.get('blend_mode', 'BLEND_Opaque'), 'two_sided': m.get('two_sided', False),
           'lighting_model': m.get('lighting_model'), 'opacity_mask_clip': m.get('opacity_mask_clip'),
           'roles': roles, 'textures': textures, 'scalars': m.get('scalars', {}),
           'vectors': m.get('vectors', {}), 'notes': notes}
    if m.get('error'): out['error'] = m['error']
    return out

if __name__ == '__main__':
    for op in sys.argv[1:]:
        print(json.dumps(resolve(op), indent=1, default=list)[:4000])
