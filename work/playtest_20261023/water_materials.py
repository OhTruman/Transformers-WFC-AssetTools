"""Playtest 2026-10-23 #14 (water presentation): the authored water / coolant / liquid materials of the MP maps, for Rendering. Read-only.

Per material (the water-like set found in Rebuild/work/render/MP_*/materials_glsl.json): maps using it; the translator's own record
(master, chain, blend / lighting model, connected inputs, graph features used, textures with files / sizes, error); from authored.db
the master's expression classes (Panner, Time, SceneDepth / DepthBiasedAlpha, Fresnel, ReflectionVector, refraction / distortion ...)
and the instance chain's scalar / vector / texture parameter values. Writes water_materials.json here.
"""
import glob, json, os, re, sqlite3
from collections import Counter, OrderedDict as OD, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
RX = r'water|ocean|liquid|fluid|puddle|river|coolant|waterfall'

def props(o):
    r = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
    return (r[0], json.loads(r[1] or '{}')) if r else (None, {})

def expression_classes(master):
    c = Counter()
    for (cls,) in DB.execute("select class from objects where outer_path like ? or opath like ?", (master + '%', master + '.%')):
        if cls and cls.startswith('MaterialExpression'): c[cls[len('MaterialExpression'):]] += 1
    return dict(c.most_common())

def params(chain):
    out = OD([('scalars', OD()), ('vectors', OD()), ('textures', OD())])
    for mic in reversed(chain):
        _, p = props(mic)
        for k, key, vk in (('scalars', 'ScalarParameterValues', 'ParameterValue'), ('vectors', 'VectorParameterValues', 'ParameterValue'),
                           ('textures', 'TextureParameterValues', 'ParameterValue')):
            for e in p.get(key) or []:
                if isinstance(e, dict) and e.get('ParameterName'): out[k][e['ParameterName']] = e.get(vk)
    return out

def main():
    use, rec = defaultdict(list), {}
    for f in sorted(glob.glob(os.path.join(TR, 'Rebuild', 'work', 'render', 'MP_*', 'materials_glsl.json'))):
        mp = os.path.basename(os.path.dirname(f)); d = json.load(open(f, encoding='utf-8'))
        for k, v in d.items():
            if re.search(RX, k, re.I): use[k].append(mp); rec.setdefault(k, v)
    rows = []
    for k in sorted(use):
        info = (rec[k] or {}).get('info') or {}; master = info.get('master')
        mcls, mp = props(master) if master else (None, {})
        rows.append(OD([('material', k), ('maps', use[k]), ('translator_error', rec[k].get('error')),
                        ('master', master), ('chain', info.get('chain')), ('blend_mode', info.get('blend_mode')),
                        ('lighting_model', info.get('lighting_model')), ('two_sided', info.get('two_sided')),
                        ('connected_inputs', info.get('connected')), ('graph_uses', info.get('uses')),
                        ('master_flags', {x: mp.get(x) for x in ('bUsedWithFogVolumes', 'bUseOneLayerDistortion', 'bUsedWithStaticLighting',
                                                                 'TwoSided', 'bDisableDepthTest', 'bAllowFog', 'TranslucencyLightingMode') if x in mp}),
                        ('master_expressions', expression_classes(master) if master else None),
                        ('parameters (instance chain, authored)', params(info.get('chain') or [])),
                        ('textures', [OD([('object', t.get('object')), ('class', t.get('class')), ('size', t.get('size')), ('format', t.get('format')),
                                          ('lod_group', t.get('lod_group')), ('file', t.get('file'))]) for t in info.get('textures') or []])]))
    json.dump({'generated_by': 'AssetTools/work/playtest_20261023/water_materials.py', 'materials': rows},
              open(os.path.join(HERE, 'water_materials.json'), 'w', encoding='utf-8'), indent=1)
    for r in rows:
        ex = r['master_expressions'] or {}
        print('%-62s %-28s %-15s %s | uses %s | panners %d time %d depth %d fresnel %d | tex %d' % (
            r['material'][-62:], ','.join(m.replace('MP_', '') for m in r['maps'][:3]) + ('...' if len(r['maps']) > 3 else ''),
            r['blend_mode'], r['connected_inputs'], r['graph_uses'], ex.get('Panner', 0), ex.get('Time', 0),
            ex.get('SceneDepth', 0) + ex.get('DepthBiasedAlpha', 0) + ex.get('DestDepth', 0), ex.get('Fresnel', 0), len(r['textures'])))

if __name__ == '__main__':
    main()
