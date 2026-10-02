"""Authored material setup of a map, from manifests/authored.db (authored.py) + compiled-resource names.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/materials_authored.json
  (materials.json from vs_map.py is a role-based PBR summary and is left unchanged)
  materials{}   every material the map uses (prop sections incl. per-component overrides, BSP surfaces, decals, emitters):
                usage, MIC chain (each level's overrides), master Material (blend/lighting/two-sided/masked/phys
                material/usage flags), EFFECTIVE parameters (nearest MIC override, else master default) with the
                object that set them, static switches (master defaults), texture sets (blueprint + intermediates +
                unpack ranges + files), resolved texture files, the parameter names referenced by the cooked compiled
                resource (uniform-expression table in each MIC's native tail), validation flags
  masters{}     each base Material: meta, graph size, root-pin inputs, declared parameters/switches with defaults
  texture_set_blueprints{}
  python vs_materials.py [MAP]
"""
import json, os, re, struct, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, matgraph, extract  # noqa: E402
from vs_common import VS  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
PARAM_LISTS = (('ScalarParameterValues', 'scalar'), ('VectorParameterValues', 'vector'), ('TextureParameterValues', 'texture'),
               ('TextureSetParameterValues', 'texture_set'), ('FontParameterValues', 'font'))
META = ('BlendMode', 'LightingModel', 'TwoSided', 'bIsMasked', 'OpacityMaskClipValue', 'PhysMaterial', 'bUsesSceneColor', 'bUsesDistortion',
        'Wireframe', 'bDisableDepthTest', 'bUsedWithStaticLighting', 'bUsedWithSkeletalMesh', 'bUsedWithDecals', 'bUsedWithParticleSprites',
        'bUsedWithBeamTrails', 'bUsedWithMeshParticles', 'bUsedWithFracturedMeshes', 'bUsedWithSpeedTree', 'bUsedWithFogVolumes',
        'bSupports1Light', 'bSupports2Lights', 'bReceivesShadows', 'bUsedInsideFogVolumes', 'bUsedWithToggleableLights',
        'bUsedWithDirectLights', 'bUsedWithStaticInterpolatedLighting', 'bAllowFog', 'bAllowLightmapSpecular', 'bNonLit')

_tex = None
def tex_file(op):
    global _tex
    if _tex is None:
        _tex = {}
        for l in open(os.path.join(extract.MANI, 'extracted', 'textures.jsonl'), encoding='utf-8'):
            r = json.loads(l)
            if os.path.exists(os.path.join(os.path.dirname(extract.OUT), r['output'])): _tex.setdefault(r['object_path'], r['output'])
    return _tex.get(op)

def tex_rec(op):
    if not op: return None
    o = A.get(op) or {}; v = A.values(op) if o else {}
    return {'texture': op, 'class': o.get('class'), 'file': tex_file(op),
            **{k: v.get(k) for k in ('SizeX', 'SizeY', 'Format', 'SRGB', 'UnpackMin', 'UnpackMax', 'CompressionSettings', 'LODGroup', 'AddressX', 'AddressY') if k in v}}

_fg = {}
def _fn_graph(fn, pkg):
    if fn not in _fg: _fg[fn] = matgraph.graph(fn, pkg)
    return _fg[fn]

def compiled_params(op):
    """parameter names the cooked compiled resource references (native tail uniform-expression table)."""
    o = A.get(op)
    if not o: return None
    p = objtree.package(o['package']); i = p._idx.get(op.lower())
    if not i: return None
    e = p.exports[i - 1]
    try: _, used = p._tr.read_object(i)
    except Exception: return None
    tail = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
    out = defaultdict(list)
    for k in range(0, len(tail) - 16, 4):
        a, b = struct.unpack_from('>ii', tail, k)
        if 0 <= a < len(p.names) and b == 0 and p.names[a].startswith('FMaterialUniformExpression') and p.names[a].endswith('Parameter'):
            c, d = struct.unpack_from('>ii', tail, k + 8)
            if 0 <= c < len(p.names) and d == 0:
                kind = p.names[a][len('FMaterialUniformExpression'):-len('Parameter')] or 'Parameter'
                if p.names[c] not in out[kind]: out[kind].append(p.names[c])
    return dict(out)

MASTERS, BLUEPRINTS = {}, {}
masters, blueprints = MASTERS, BLUEPRINTS

def master_rec(mop):
    if mop in masters: return masters[mop]
    o = A.get(mop)
    if not o: masters[mop] = {'material': mop, 'missing': True}; return masters[mop]
    g = matgraph.graph(mop, o['package'])
    params, switches, functions = {}, {}, []
    def collect(gr, where, depth=0):
        for k, n in gr.get('nodes', {}).items():
            if n['class'] == 'MaterialExpressionFunction' and n['props'].get('Function') and depth < 8:
                fn = n['props']['Function']
                if fn not in functions:
                    functions.append(fn)
                    fo = A.get(fn)
                    if fo: collect(_fn_graph(fn, fo['package']), fn, depth + 1)
                continue
            pn = n['props'].get('ParameterName')
            if not pn: continue
            cls = n['class'].replace('MaterialExpression', '')
            dv = n['props'].get('DefaultValue', n['props'].get('Texture'))
            if 'StaticSwitch' in cls or 'StaticComponentMask' in cls:
                switches.setdefault(pn, []).append({'class': cls, 'default': n['props'].get('DefaultValue', False) if 'Switch' in cls else
                                                    {c: n['props'].get('Default' + c, False) for c in 'RGBA'}, 'node': k, 'in': where})
            else:
                params.setdefault(pn, []).append({'class': cls, 'default': dv, 'node': k, 'in': where})
    collect(g, mop)
    mv = A.values(mop)
    masters[mop] = {'material': mop, 'package_owner': o['package'], 'meta': {k: mv.get(k) for k in META if k in mv},
                    'node_count': len(g.get('nodes', {})),
                    'roots': {pin: sorted(set('%s %s' % x for x in matgraph.leaves(matgraph.upstream(g, v['node']))))
                              for pin, v in (g.get('roots') or {}).items()},
                    'parameters': params, 'static_switches': switches, 'material_functions': functions,
                    'duplicate_parameter_names': sorted(k for k, v in params.items() if len(v) > 1)}
    return masters[mop]

_sw = {}
def switch_evidence(master):
    """for each StaticSwitchParameter node of a master: parameter names that reach the material's root pins ONLY through
    that switch's A (true) input / ONLY through its B (false) input (reachability from roots with the edge cut;
    every other switch keeps both branches, so the test is conservative; MaterialFunction internals not traversed)."""
    if master in _sw: return _sw[master]
    o = A.get(master)
    if not o: _sw[master] = {}; return {}
    g = matgraph.graph(master, o['package'])
    roots = [v['node'] for v in (g.get('roots') or {}).values()]
    def reach(cut=None):
        seen, out, stack = set(), set(), list(roots)
        while stack:
            k = stack.pop()
            if k in seen or k not in g['nodes']: continue
            seen.add(k); n = g['nodes'][k]
            if n['props'].get('ParameterName') and 'StaticSwitch' not in n['class']: out.add(n['props']['ParameterName'])
            for e in n['inputs']:
                if cut and k == cut[0] and e['pin'] == cut[1]: continue
                stack.append(e['node'])
        return out
    full = reach()
    res = {}
    for k, n in g['nodes'].items():
        if n['class'] != 'MaterialExpressionStaticSwitchParameter': continue
        only_a = full - reach((k, 'A')); only_b = full - reach((k, 'B'))
        res.setdefault(n['props'].get('ParameterName'), []).append({'node': k, 'true_only': sorted(only_a), 'false_only': sorted(only_b),
                                                                    'default': n['props'].get('DefaultValue', False)})
    _sw[master] = res
    return res

def infer_switches(master, compiled):
    """static switch state from the compiled resource: A-only params referenced -> True, B-only -> False."""
    names = {x for v in (compiled or {}).values() for x in v}
    out = {}
    for sw, nodes in switch_evidence(master).items():
        votes = set()
        for nd in nodes:
            t = bool(set(nd['true_only']) & names); f = bool(set(nd['false_only']) & names)
            if t and not f: votes.add(True)
            elif f and not t: votes.add(False)
        out[sw] = {'compiled_state': (votes.pop() if len(votes) == 1 else ('conflict' if votes else 'undetermined')),
                   'master_default': nodes[0]['default'],
                   'evidence_true_only': sorted({p for nd in nodes for p in nd['true_only']} & names),
                   'evidence_false_only': sorted({p for nd in nodes for p in nd['false_only']} & names)}
    return out

def describe(m, usage=None):
    """authoritative record of one material (MIC chain, effective params, textures, compiled names)."""
    o = A.get(m)
    rec = {'material': m, 'usage': dict(usage or {})}
    if not o:
        rec['missing'] = True; return rec
    chain = matgraph.mic_chain(m, o['package'])
    levels, master = [], None
    for c in chain:
        if c.get('class') == 'Material': master = c['object']; break
        p = c.get('props') or {}
        lvl = {'object': c['object'], 'class': c.get('class'), 'parent': p.get('Parent')}
        for key, kind in PARAM_LISTS:
            if p.get(key): lvl[kind] = {x['ParameterName']: x.get('ParameterValue') for x in p[key]}
        if p.get('BoolPropertyValues'): lvl['bool_property_overrides'] = {x['PropertyName']: x['PropertyValue'] for x in p['BoolPropertyValues']}
        if p.get('PhysMaterial'): lvl['phys_material'] = p['PhysMaterial']
        levels.append(lvl)
    rec['class'] = o['class']; rec['chain'] = [l['object'] for l in levels] + ([master] if master else [])
    rec['instance_levels'] = levels
    if not master:
        rec['master'] = None; rec['broken_chain'] = True; return rec
    mr = master_rec(master)
    rec['master'] = master
    meta = dict(mr.get('meta') or {})
    for l in reversed(levels):                                    # nearest instance wins
        for k, v in (l.get('bool_property_overrides') or {}).items(): meta[k] = v
        if l.get('phys_material'): meta['PhysMaterial'] = l['phys_material']
    rec['meta'] = meta
    eff = {}
    for pn, decls in (mr.get('parameters') or {}).items():
        src, val = 'master default', decls[0]['default']
        for l in levels:
            hit = next((l[k][pn] for k in ('scalar', 'vector', 'texture', 'texture_set', 'font') if pn in (l.get(k) or {})), None)
            if hit is not None or any(pn in (l.get(k) or {}) for k in ('scalar', 'vector', 'texture', 'texture_set', 'font')):
                src, val = l['object'], hit; break
        eff[pn] = {'value': val, 'from': src, 'kind': decls[0]['class']}
        if len(decls) > 1: eff[pn]['duplicate_nodes'] = len(decls)
    rec['effective_parameters'] = eff
    unknown = sorted({pn for l in levels for k in ('scalar', 'vector', 'texture', 'texture_set', 'font') for pn in (l.get(k) or {})
                      if pn not in (mr.get('parameters') or {})})
    rec['overrides_not_in_master'] = unknown
    rec['static_switch_defaults'] = {k: v[0]['default'] for k, v in (mr.get('static_switches') or {}).items()}
    # textures + texture sets
    texs, sets = {}, {}
    for pn, e in eff.items():
        v = e['value']
        if not isinstance(v, str): continue
        c = (A.get(v) or {}).get('class')
        if c == 'TextureSet':
            tv = A.values(v); bp = tv.get('Blueprint')
            if bp and bp not in blueprints: blueprints[bp] = A.values(bp)
            sets[pn] = {'texture_set': v, 'blueprint': bp, 'intermediates': [tex_rec(x) for x in tv.get('Intermediates') or []]}
        elif c and c.startswith('Texture'):
            texs[pn] = tex_rec(v)
    rec['textures'] = texs; rec['texture_sets'] = sets
    rec['compiled_resource_parameters'] = compiled_params(m) if o['class'].startswith('MaterialInstance') else None
    cp = rec['compiled_resource_parameters'] or {}
    if cp and master: rec['static_switches_compiled'] = infer_switches(master, cp)
    if sets:
        # static permutation evidence: the compiled resource samples TextureSet intermediates only if the
        # UseTextureSet branch is enabled for this instance (master default may be false)
        rec['texture_set_live'] = ('TextureSetIntermediate' in cp) if cp else None
    return rec

def main():
    props = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))['props']
    usage = defaultdict(Counter)
    for p in props:
        sm = p.get('section_materials') or []; ov = p.get('material_overrides') or []
        for i in range(max(len(sm), len(ov))):
            m = ov[i] if i < len(ov) and ov[i] else (sm[i] if i < len(sm) else None)
            if m: usage[m]['prop_sections'] += 1
            if i < len(ov) and ov[i]: usage[m]['component_overrides'] += 1
    for m in json.load(open(os.path.join(OUT, 'materials.json'), encoding='utf-8')):
        if m not in usage: usage[m]['bsp_or_other(vs_map)'] += 1
    fxp = os.path.join(OUT, 'map_fx.json')
    if os.path.exists(fxp):
        fx = json.load(open(fxp, encoding='utf-8'))
        for d in fx['decals']: usage[d['props'].get('DecalMaterial')]['decals'] += 1
        for ps in fx['particle_systems'].values():
            for m in (ps.get('materials') or {}): usage[m]['particles'] += 1
    usage.pop(None, None)
    masters, blueprints = MASTERS, BLUEPRINTS
    mats = {m: describe(m, usage[m]) for m in sorted(usage)}
    # ------------------------------------------------------------------ validation / stats
    M = [r for r in mats.values() if not r.get('missing')]
    files_missing = sorted({t['texture'] for r in M for t in r.get('textures', {}).values() if t and not t.get('file') and t.get('class') == 'Texture2D'} |
                           {t['texture'] for r in M for s in r.get('texture_sets', {}).values() for t in s['intermediates'] if t and not t.get('file')})
    cubes = sorted({t['texture'] for r in M for t in r.get('textures', {}).values() if t and t.get('class') == 'TextureCube'})
    comp_ok = comp_n = 0; comp_unknown = Counter()
    for r in M:
        cp = r.get('compiled_resource_parameters')
        if not cp: continue
        names = {n for v in cp.values() for n in v}
        comp_n += 1
        declared = set(r['effective_parameters'])
        extra = names - declared - {'SelectionColor'}
        comp_ok += not extra
        for x in extra: comp_unknown[x] += 1
    stats = {'materials': len(mats), 'missing': [r['material'] for r in mats.values() if r.get('missing')],
             'by_class': dict(Counter(r.get('class') for r in mats.values())), 'masters': len(masters),
             'master_usage': dict(Counter(r.get('master') for r in M).most_common(15)),
             'blend_modes': dict(Counter((r.get('meta') or {}).get('BlendMode', 'BLEND_Opaque') for r in M)),
             'lighting_models': dict(Counter((r.get('meta') or {}).get('LightingModel', 'MLM_Phong') for r in M)),
             'two_sided': sum(1 for r in M if (r.get('meta') or {}).get('TwoSided')),
             'phys_materials': dict(Counter((r.get('meta') or {}).get('PhysMaterial') for r in M)),
             'with_texture_sets': sum(1 for r in M if r.get('texture_sets')), 'texture_set_blueprints': len(blueprints),
             'texture_set_live_in_compiled_resource': dict(Counter(str(r.get('texture_set_live')) for r in M if r.get('texture_sets'))),
             'texture_set_bound_but_not_compiled': [r['material'] for r in M if r.get('texture_sets') and r.get('texture_set_live') is False],
             'broken_chains': [r['material'] for r in M if r.get('broken_chain')],
             'overrides_not_in_master': {r['material']: r['overrides_not_in_master'] for r in M if r.get('overrides_not_in_master')},
             'dead_overrides_not_compiled': sum(1 for r in M for n in r.get('overrides_not_in_master') or []
                                               if n != 'None' and n not in {x for v in (r.get('compiled_resource_parameters') or {}).values() for x in v}),
             'blank_override_entries_named_None': sum(1 for r in M for n in r.get('overrides_not_in_master') or [] if n == 'None'),
             'texture_files_missing': files_missing, 'cubemaps_not_extracted': cubes,
             'compiled_resource_check': {'mics_checked': comp_n, 'all_compiled_names_declared_in_master': comp_ok,
                                         'undeclared_compiled_names': dict(comp_unknown.most_common(10))}}
    out = {'map': MAP, 'source': 'manifests/authored.db (MIC chains, master graphs) + cooked MIC compiled-resource names',
           'stats': stats, 'materials': mats, 'masters': masters, 'texture_set_blueprints': blueprints, 'notes': [
               'Effective parameter = nearest MaterialInstance override along the Parent chain, else the master node DefaultValue '
               '(UE3 MIC semantics, CONFIRMED structure). Static switch VALUES actually compiled live in each MIC\'s cooked static '
               'permutation (native, not decoded here); static_switch_defaults are the master defaults. compiled_resource_parameters '
               'lists the parameter names the cooked compiled resource references, i.e. those that survive the static permutation.',
               'TextureSets (WFC licensee): the Blueprint authors Color/Masks/Normal sources packed into Color_NormX and Masks_NormY '
               'intermediates. The cooked blueprint says OutputTextureChannel R/G for the normal inputs (byte-level CONFIRMED), but '
               'the intermediates unpack ALPHA to -1..1 (UnpackMin[A] = -1) and carry normal X/Y in alpha: the cooker routes '
               'TSTT_Normal channels to alpha (INFERRED); trust the intermediates\' unpack ranges.',
               'overrides_not_in_master: MIC overrides whose name the master (incl. its MaterialFunctions) no longer declares; 76 of 78 '
               'on Streets are also absent from the cooked compiled resource, i.e. dead leftovers of older master versions (ignored at '
               'runtime); the rest are blank entries named None.',
               'Colors in parameters: LinearColor (floats, unambiguous). TextureCubes are not extracted by AssetTools (Rendering decodes them).']}
    path = os.path.join(OUT, 'materials_authored.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(stats, default=str)[:3500]); print('->', path)

if __name__ == '__main__':
    main()
