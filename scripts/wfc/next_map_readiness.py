"""Second-map readiness assessment against the generalized Streets pipeline (report + manifests only; no geometry export).

For every cooked MP map (BASE + streamed levels) measures, from inventory.db / authored.db / the extracted tree:
  package completeness, sublevels, extraction coverage on disk (StaticMesh .gltf, Texture2D .png, SoundNodeWaveEx .wav,
  MaterialInstanceConstant .mat), authored.db coverage of the level's own objects, geometry (BSP Model, SMCA components,
  static meshes), lightmap format (LightMap/ShadowMap classes, _LM companions), materials (parent Materials not used by
  Streets), collision inputs (BlockingVolumes, RB_BodySetup per StaticMesh), movers, destructibles, particles and audio
  new vs Streets, and the actor/component classes Streets never exercised, grouped by native-behaviour category.
Bounded: indexed queries, one map's sets at a time, working-set guard.
Output: manifests/next_map/readiness.json   python next_map_readiness.py
"""
import json, os, sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
from fe_map_catalog import streamed, rss_gb  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
OUT = os.path.join(MANI, 'next_map')
REF = 'MP_IAC_Streets_BASE_m'
MEM_LIMIT_GB = 6
EXT = {'StaticMesh': '.gltf', 'Texture2D': '.png', 'SoundNodeWaveEx': '.wav', 'MaterialInstanceConstant': '.mat',
       'SkeletalMesh': '.gltf'}
GRAPH = ('Material', 'ParticleSystem', 'SoundCue')
CATEGORIES = OrderedDict([
    ('visibility_system (native)', ('HmRoom', 'Portal', 'CullDistance', 'PrecomputedVisibility', 'Occlusion')),
    ('render_feature', ('LensFlare', 'Fog', 'HeightFog', 'PostProcessVolume', 'LightVolume', 'Decal', 'Terrain', 'Foliage', 'SpeedTree',
                        'Fluid', 'Water', 'RadialBlur')),
    ('lighting', ('Light',)),
    ('physics / forces', ('RadialForce', 'Force', 'KActor', 'KAsset', 'Rigid', 'Physics', 'Constraint', 'Fractured', 'Apex', 'Cloth')),
    ('animation / skeletal', ('SkeletalMesh', 'Anim', 'Matinee', 'Interp')),
    ('gameplay / script actors', ('Tn', 'Hm', 'Trigger', 'Volume')),
    ('kismet', ('Seq',)),
    ('audio', ('Sound', 'Ambient', 'Reverb')),
])

def category(cls):
    for c, keys in CATEGORIES.items():
        if any(k.lower() in cls.lower() for k in keys): return c
    return 'other'

def profile(inv, levels):
    rows = []
    for lv in levels:
        rows += inv.execute('SELECT class, opath, serial_size, package FROM exports WHERE package=?', (lv,)).fetchall()
    lvset = {l.lower() for l in levels}
    foreign = {}
    for c, o, s, p in rows:
        if o.split('.')[0].lower() not in lvset: foreign.setdefault(o, c)
    classes = Counter()
    for c, o, s, p in rows:
        if o.split('.')[0].lower() in lvset and '.theworld.persistentlevel.' in o.lower() and o.count('.') in (3, 4):
            classes[c] += 1
    own = sum(1 for c, o, s, p in rows if o.split('.')[0].lower() in lvset)
    own_in_db = sum(A.con().execute('SELECT COUNT(*) FROM objects WHERE opath >= ? AND opath < ?', (lv + '.', lv + '/')).fetchone()[0]
                    for lv in levels)
    cov = {}
    for cls, ext in EXT.items():
        objs = [o for o, c in foreign.items() if c == cls]
        have = sum(1 for o in objs if os.path.exists(os.path.join(ROOT, 'content', *o.split('.')) + ext))
        cov[cls] = {'objects': len(objs), 'extracted': have, 'pct': round(100.0 * have / len(objs), 1) if objs else None}
    graph = {}
    for cls in GRAPH:
        objs = [o for o, c in foreign.items() if c == cls]
        have = sum(1 for o in objs if A.con().execute('SELECT 1 FROM objects WHERE opath=?', (o,)).fetchone())
        graph[cls] = {'objects': len(objs), 'in_authored_db': have}
    sm = [o for o, c in foreign.items() if c == 'StaticMesh']
    body = {o.rsplit('.', 1)[0] for o, c in foreign.items() if c == 'RB_BodySetup'}
    return {'rows': len(rows), 'foreign': foreign, 'classes': classes, 'own_exports': own, 'own_in_authored_db': own_in_db,
            'coverage_on_disk': cov, 'graph_objects': graph,
            'model_bytes': sum(s for c, o, s, p in rows if c == 'Model'),
            'smca_components': sum(1 for c, o, s, p in rows if c == 'StaticMeshComponent' and 'StaticMeshCollectionActor' in o),
            'static_mesh_bytes': sum(s for c, o, s, p in rows if c == 'StaticMesh'),
            'static_meshes_with_bodysetup': sum(1 for o in sm if o in body), 'static_meshes': len(sm),
            'lightmap_classes': Counter(c for c, o, s, p in rows if 'LightMap' in c or 'ShadowMap' in c)}

def main():
    os.makedirs(OUT, exist_ok=True)
    inv = objtree.inv()
    cat = json.load(open(os.path.join(MANI, 'mp_map_catalog.json'), encoding='utf-8'))
    allpk = {r[0].lower(): r[0] for r in inv.execute('SELECT package FROM packages')}
    maps = [m for m in cat['maps'] if m.get('cooked')]
    maps.sort(key=lambda m: m['packages']['base'].lower() != REF.lower())
    ref = None; out = OrderedDict()
    for m in maps:
        base = m['packages']['base']
        subs = [s['PackageName'] for s in m['packages']['streamed_levels (LevelStreaming objects)'] if s['PackageName']]
        levels = [base] + [allpk[s.lower()] for s in subs if s.lower() in allpk]
        P = profile(inv, levels)
        g = rss_gb()
        if g > MEM_LIMIT_GB: raise MemoryError('working-set guard %.2f GB' % g)
        mats = {o for o, c in P['foreign'].items() if c == 'Material'}
        psys = {o for o, c in P['foreign'].items() if c == 'ParticleSystem'}
        cues = {o for o, c in P['foreign'].items() if c == 'SoundCue'}
        if ref is None:
            ref = {'mats': mats, 'psys': psys, 'cues': cues, 'classes': set(P['classes']), 'lm': set(P['lightmap_classes'])}
        new_classes = sorted(set(P['classes']) - ref['classes'])
        rec = OrderedDict([
            ('map', m['MapFilename']), ('name', m['FriendlyName']['INT']), ('modes', m['CompatibleGameTypes']),
            ('package_completeness', {'levels': levels, 'streamed_referenced': subs,
                                      'missing': [s for s in subs if s.lower() not in allpk],
                                      'companions': m['packages']['companions (_LM / _LOC)'],
                                      'own_exports': P['own_exports'], 'own_objects_in_authored_db': P['own_in_authored_db'],
                                      'authored_db_coverage_pct': round(100.0 * P['own_in_authored_db'] / P['own_exports'], 1) if P['own_exports'] else None}),
            ('sublevels', len(levels) - 1),
            ('extraction_coverage_on_disk', P['coverage_on_disk']),
            ('graph_objects_decoded (authored.db)', P['graph_objects']),
            ('geometry', {'bsp_model_bytes': P['model_bytes'], 'smca_components': P['smca_components'],
                          'static_meshes': P['static_meshes'], 'static_mesh_bytes': P['static_mesh_bytes'],
                          'compatibility': 'same classes as Streets (Model/BSP, StaticMeshCollectionActor, StaticMeshActor)'
                                           if not ({'Terrain', 'FracturedStaticMeshActor', 'FracturedStaticMeshComponent'} & set(P['classes']))
                                           else 'adds terrain / fractured meshes'}),
            ('lightmaps', {'classes': dict(P['lightmap_classes']), 'same_as_streets': set(P['lightmap_classes']) == ref['lm'],
                           'extra_vs_streets': sorted(set(P['lightmap_classes']) - ref['lm']),
                           'lm_companions': [c for c in m['packages']['companions (_LM / _LOC)'] if c.endswith('_LM')]}),
            ('materials', {'parent_materials': len(mats), 'not_used_by_streets': len(mats - ref['mats']),
                           'new_material_list': sorted(mats - ref['mats'])[:60]}),
            ('collision', {'BlockingVolume': P['classes'].get('BlockingVolume', 0),
                           'static_meshes_with_RB_BodySetup': P['static_meshes_with_bodysetup'], 'static_meshes': P['static_meshes']}),
            ('movers', {k: v for k, v in P['classes'].items() if any(x in k for x in ('InterpActor', 'KActor', 'Mover'))}),
            ('matinee', P['classes'].get('SeqAct_Interp', 0)),
            ('destructibles', {k: v for k, v in P['classes'].items() if any(x in k for x in ('Destruct', 'Fracture'))}),
            ('particles', {'systems': len(psys), 'not_used_by_streets': len(psys - ref['psys'])}),
            ('audio', {'cues': len(cues), 'not_used_by_streets': len(cues - ref['cues']),
                       'wav_coverage': P['coverage_on_disk']['SoundNodeWaveEx']}),
            ('classes_not_in_streets', {c: {'count': P['classes'][c], 'category': category(c)} for c in new_classes}),
        ])
        cats = Counter(category(c) for c in new_classes)
        rec['special_native_behaviour'] = {
            'visibility_system': [c for c in new_classes if category(c) == 'visibility_system (native)'],
            'render_features': [c for c in new_classes if category(c) == 'render_feature'],
            'physics_forces': [c for c in new_classes if category(c) == 'physics / forces'],
            'skeletal_animation': [c for c in new_classes if category(c) == 'animation / skeletal'],
            'category_counts': dict(cats)}
        out[base] = rec
        print('%-26s levels %d cov mesh %s tex %s wav %s  newcls %d  mats+%d psys+%d  rss %.2f' % (
            base, len(levels), P['coverage_on_disk']['StaticMesh']['pct'], P['coverage_on_disk']['Texture2D']['pct'],
            P['coverage_on_disk']['SoundNodeWaveEx']['pct'], len(new_classes), len(mats - ref['mats']), len(psys - ref['psys']), g))
        P = None
    json.dump({'generated_by': 'AssetTools/scripts/wfc/next_map_readiness.py', 'reference': REF,
               'method': 'counts and set differences from inventory.db / authored.db / ExtractedAssets; no weighting here - '
                         'the ranking and its rationale are in docs/NEXT_MAP_READINESS.md',
               'maps': out}, open(os.path.join(OUT, 'readiness.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('->', os.path.join(OUT, 'readiness.json'))

if __name__ == '__main__':
    main()
