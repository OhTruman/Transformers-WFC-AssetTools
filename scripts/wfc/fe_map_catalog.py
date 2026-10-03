"""Multiplayer map catalog (frontend selection data + package profile) and second-map readiness report.

Inputs: frontend_maps.json (fe_frontend.py), inventory.db, authored.db. Indexed queries only; one map's working sets in memory
at a time; a working-set guard aborts above MEM_LIMIT_GB.  Outputs (AssetTools/manifests/):
  mp_map_catalog.json        every MapInfo map: selection data (ids, names, thumbnail, modes, order) + streamed sublevels,
                             companions, source-package dependencies, actor profile, mode-actor counts, WorldInfo presentation refs
  mp_next_map_readiness.json per cooked map: objective metrics vs MP_IAC_Streets (package completeness, dependencies, geometry,
                             unique classes/state, movers, destructibles, lighting format, overlap with Streets) + ranking
  python fe_map_catalog.py
"""
import ctypes, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
GEN = 'AssetTools/scripts/wfc/fe_map_catalog.py'
REF = 'MP_IAC_Streets_BASE_m'
MEM_LIMIT_GB = 6

def rss_gb():
    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('a', ctypes.c_size_t), ('b', ctypes.c_size_t), ('c', ctypes.c_size_t),
                    ('d', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    try:
        k = ctypes.windll.kernel32; ps = ctypes.windll.psapi
        k.GetCurrentProcess.restype = ctypes.c_void_p
        m = PMC(); m.cb = ctypes.sizeof(m)
        ps.GetProcessMemoryInfo(ctypes.c_void_p(k.GetCurrentProcess()), ctypes.byref(m), m.cb)
        return m.WorkingSetSize / 2**30
    except Exception:
        return 0.0

def guard(tag):
    g = rss_gb()
    if g > MEM_LIMIT_GB: raise MemoryError('working set %.2f GB > %d GB at %s' % (g, MEM_LIMIT_GB, tag))
    return g

MOVER = ('InterpActor', 'StaticInterpActor', 'KActor', 'KAsset', 'Mover')
LIGHTS = ('PointLight', 'SpotLight', 'DirectionalLight', 'SkyLight', 'PointLightToggleable', 'SpotLightToggleable',
          'PointLightMovable', 'SpotLightMovable', 'DominantDirectionalLight', 'DominantSpotLight', 'DominantPointLight')
MODE_ACTORS = ('TnTeamPlayerStart', 'TnFreeForAllPlayerStart', 'TnSpawnCluster', 'TnAmmoCratePickupFactory', 'TnHealthPickupFactory',
               'TnOverShieldPickupFactory', 'TnKingOfTheHillZone', 'TnDominationPoint', 'TnBombPlantPoint', 'TnFlagCapturePoint',
               'TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb', 'TnWeaponPickupFactory', 'TnSurvivalGenerator')

def level_profile(inv, pkg):
    rows = inv.execute('SELECT class, opath, serial_size FROM exports WHERE package=?', (pkg,)).fetchall()
    lvl = pkg.lower() + '.theworld.persistentlevel.'
    actors = Counter(c for c, o, s in rows if o.lower().startswith(lvl) and o.count('.') == 3)
    comps = Counter(c for c, o, s in rows if o.lower().startswith(lvl) and o.count('.') == 4)
    own = [(c, o, s) for c, o, s in rows if o.split('.')[0].lower() == pkg.lower()]
    src = Counter(o.split('.')[0] for c, o, s in rows if o.split('.')[0].lower() != pkg.lower())
    objs = {o for c, o, s in rows if o.split('.')[0].lower() != pkg.lower()}
    size = lambda cl: sum(s for c, o, s in rows if c == cl)
    seq = sum(1 for c, o, s in own if c.startswith(('SeqAct', 'SeqEvent', 'SeqCond', 'SeqVar', 'TnSeq', 'GFxAction', 'GFxEvent')))
    return {'exports': len(rows), 'actors': actors, 'components': comps, 'source_packages': src, 'objects': objs,
            'model_bytes': size('Model'), 'static_mesh_bytes': size('StaticMesh'), 'static_meshes': sum(1 for r in rows if r[0] == 'StaticMesh'),
            'kismet_nodes': seq, 'matinee': sum(1 for c, o, s in own if c == 'SeqAct_Interp'),
            'lightmap_textures': sum(1 for r in rows if r[0] in ('LightMapTexture2D', 'ShadowMapTexture2D')),
            'lightmap_classes': Counter(r[0] for r in rows if 'LightMap' in r[0] or 'ShadowMap' in r[0])}

def streamed(mp):
    d = A.con()
    out = []
    for o, c in d.execute("SELECT opath, class FROM objects WHERE opath >= ? AND opath < ? AND class LIKE 'LevelStreaming%'",
                          (mp + '.TheWorld.', mp + '.TheWorld/')).fetchall():
        v = A.values(o)
        out.append({'object': o, 'class': c, 'PackageName': v.get('PackageName'),
                    'bShouldBeVisibleInEditor': v.get('bShouldBeVisibleInEditor')})
    return out

def main():
    inv = objtree.inv()
    fm = json.load(open(os.path.join(MANI, 'frontend_maps.json'), encoding='utf-8'))
    allpk = {r[0].lower(): r for r in inv.execute('SELECT package, role, contains_map, uncompressed_size, export_count FROM packages')}
    cat, prof = [], {}
    ref_objs, ref_src, ref_classes = None, None, None
    order = sorted(fm['maps'], key=lambda m: (m['cooked_package_present'] or '').lower() != REF.lower())
    for m in order:
        base = m['cooked_package_present']
        rec = {k: m[k] for k in ('MapFilename', 'MapId', 'PresenceId', 'ini_order', 'FriendlyName', 'Description', 'CompatibleGameTypes',
                                 'Faction', 'ImagePath', 'thumbnail_png', 'image_inherited_default')}
        rec['family_prefix (MP_<prefix>_)'] = m['MapFilename'].split('_')[1]
        rec['loading_presentation'] = {'movie': 'shared TF_LoadingScreen (no per-map loading art authored; frontend_loading.json)',
                                       'map_name_on_loading_screen': 'LoadScreen_GFX mc_levelInfo via SetLevelText (RE)',
                                       'description': None, 'confidence': HIGH}
        if not base:
            rec['cooked'] = False; rec['confidence'] = CONF + ' (config only; no cooked package -> not selectable in the shipped game)'
            cat.append(rec); continue
        rec['cooked'] = True
        st = streamed(base)
        subs = [s['PackageName'] for s in st if s['PackageName']]
        comp = sorted(r[0] for k, r in allpk.items() if k.startswith(base.lower().rsplit('_m', 1)[0].lower() + '_m_'))
        levels = [base] + [s for s in subs if s and s.lower() in allpk]
        P = {}
        for lv in levels:
            P[lv] = level_profile(inv, allpk[lv.lower()][0]); guard(lv)
        actors = sum((p['actors'] for p in P.values()), Counter())
        comps = sum((p['components'] for p in P.values()), Counter())
        src = sum((p['source_packages'] for p in P.values()), Counter())
        objs = set().union(*(p['objects'] for p in P.values()))
        wi = next((o for o in A.con().execute("SELECT opath FROM objects WHERE opath >= ? AND opath < ? AND class='TnWorldInfo'",
                                              (base + '.TheWorld.PersistentLevel.', base + '.TheWorld.PersistentLevel/')).fetchall()), None)
        wv = A.values(wi[0]) if wi else {}
        rec.update({
            'packages': {'base': base, 'streamed_levels (LevelStreaming objects)': st, 'missing_streamed': [s for s in subs if s.lower() not in allpk],
                         'companions (_LM / _LOC)': [c for c in comp if c not in levels],
                         'uncompressed_bytes': {lv: allpk[lv.lower()][3] for lv in levels}},
            'source_package_dependencies (cooked copies inside the level files, by object count)': dict(src.most_common()),
            'actor_profile': dict(actors.most_common()),
            'mode_actors': {k: actors.get(k, 0) for k in MODE_ACTORS},
            'world_info': {'object': wi[0] if wi else None, 'AnnouncerSoundEventSet': wv.get('AnnouncerSoundEventSet'),
                           'LevelCamera': wv.get('LevelCamera')},
            'confidence': CONF})
        if base.lower() == REF.lower():
            rec['reference_implementation'] = {
                'complete_manifest': 'manifests/mp_iac_streets_complete.json',
                'render_index': 'ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/render_index.json',
                'docs': ['docs/MAP_STREETS_COMPLETE.md', 'docs/STREETS_NATIVE_FIDELITY_M05.md', 'docs/GAMEPLAY_STREETS.md']}
            ref_objs, ref_src, ref_classes = objs, set(src), set(actors) | set(comps)
        classes = set(actors) | set(comps)
        lmc = sum((p['lightmap_classes'] for p in P.values()), Counter())
        prof[base] = {
            'MapFilename': m['MapFilename'], 'name': m['FriendlyName']['INT'], 'modes': m['CompatibleGameTypes'],
            'package_completeness': {'levels_present': len(levels), 'levels_referenced': 1 + len(subs),
                                     'missing': [s for s in subs if s.lower() not in allpk], 'has_LM': any(c.endswith('_LM') for c in comp)},
            'dependencies': {'source_packages': len(src), 'source_packages_not_in_streets': sorted(set(src) - ref_src) if ref_src is not None else None,
                             'objects': len(objs), 'objects_shared_with_streets': len(objs & ref_objs) if ref_objs is not None else None},
            'geometry': {'bsp_model_bytes': sum(p['model_bytes'] for p in P.values()),
                         'static_mesh_assets': sum(p['static_meshes'] for p in P.values()),
                         'static_mesh_bytes': sum(p['static_mesh_bytes'] for p in P.values()),
                         'smca_components': comps.get('StaticMeshComponent', 0),
                         'static_mesh_actors': actors.get('StaticMeshActor', 0) + actors.get('StaticMeshCollectionActor', 0),
                         'terrain': actors.get('Terrain', 0)},
            'unique_code_state': {'kismet_nodes': sum(p['kismet_nodes'] for p in P.values()), 'matinee': sum(p['matinee'] for p in P.values()),
                                  'classes_not_in_streets': sorted(classes - ref_classes) if ref_classes is not None else None},
            'movers': {k: v for k, v in actors.items() if any(x in k for x in MOVER)},
            'destructibles': {k: v for k, v in list(actors.items()) + list(comps.items())
                              if any(x in k for x in ('Destruct', 'Fracture', 'Breakable'))},
            'lighting': {'lights': {k: v for k, v in actors.items() if k in LIGHTS or k.endswith('Light')},
                         'lightmap_related_classes': dict(lmc),
                         'light_components': {k: v for k, v in comps.items() if 'LightComponent' in k}},
            'emitters': actors.get('Emitter', 0), 'decals': actors.get('DecalActor', 0) + comps.get('DecalComponent', 0),
            'ambient_sounds': {k: v for k, v in actors.items() if k.startswith('AmbientSound')}}
        cat.append(rec)
        P.clear(); objs = None
        print('%-26s levels %d  actors %5d  src %3d  rss %.2f GB' % (base, len(levels), sum(actors.values()), len(src), rss_gb()))
    cat.sort(key=lambda r: r['ini_order'])
    write('mp_map_catalog.json', {
        'generated_by': GEN, 'reference_map': REF,
        'sources': ['frontend_maps.json (TransLevels.ini, TransGame.int/FRA, UI_LevelThumbnails_p)', 'inventory.db exports/packages',
                    'authored.db LevelStreaming / TnWorldInfo objects'],
        'notes': ['menu order = ini_order (HIGH); MapId = online id; family_prefix is the package-name code (expansion not authored)',
                  'no MapInfo Description strings and no per-map loading art are authored in the shipped data (CONFIRMED by absence)',
                  'source_package_dependencies counts cooked object copies; the level files are self-contained for loading'],
        'maps': cat})
    write('mp_next_map_readiness.json', score(prof))

def score(prof):
    ref = prof[next(k for k in prof if k.lower() == REF.lower())]
    rows = []
    for k, p in prof.items():
        if k.lower() == REF.lower(): continue
        g, rg = p['geometry'], ref['geometry']
        ratio = lambda a, b: round(a / b, 3) if b else None
        m = {'new_source_packages': len(p['dependencies']['source_packages_not_in_streets']),
             'object_overlap_with_streets': ratio(p['dependencies']['objects_shared_with_streets'], p['dependencies']['objects']),
             'geometry_ratio (static mesh bytes + bsp bytes vs Streets)': ratio(g['static_mesh_bytes'] + g['bsp_model_bytes'],
                                                                                rg['static_mesh_bytes'] + rg['bsp_model_bytes']),
             'smca_components': g['smca_components'],
             'new_classes': len(p['unique_code_state']['classes_not_in_streets']),
             'kismet_nodes': p['unique_code_state']['kismet_nodes'], 'matinee': p['unique_code_state']['matinee'],
             'movers': sum(p['movers'].values()), 'destructibles': sum(p['destructibles'].values()),
             'lightmap_format_same_as_streets': set(p['lighting']['lightmap_related_classes']) == set(ref['lighting']['lightmap_related_classes']),
             'terrain': g['terrain'], 'versus_modes': len([x for x in p['modes'] if x in ('DM', 'TDM', 'CTF', 'KOTH', 'EXT', 'DOM')]),
             'package_complete': not p['package_completeness']['missing']}
        rows.append((k, m))
    # transparent effort index: each metric normalised to the max across candidates; lower = easier
    W = {'new_source_packages': 3, 'geometry_ratio (static mesh bytes + bsp bytes vs Streets)': 2, 'new_classes': 3,
         'kismet_nodes': 1, 'matinee': 1, 'movers': 1, 'destructibles': 1, 'smca_components': 1}
    mx = {w: max((r[1][w] or 0) for r in rows) or 1 for w in W}
    out = []
    for k, m in rows:
        e = sum(W[w] * (m[w] or 0) / mx[w] for w in W) + 3 * (1 - (m['object_overlap_with_streets'] or 0))
        e += 0 if m['lightmap_format_same_as_streets'] else 2
        e += 0 if m['package_complete'] else 5
        e += 0 if m['versus_modes'] == 6 else 2
        out.append({'map': k, 'name': prof[k]['name'], 'effort_index': round(e, 3), 'metrics': m, 'profile': prof[k]})
    out.sort(key=lambda r: r['effort_index'])
    return {'generated_by': GEN, 'reference': REF, 'reference_profile': ref,
            'method': {'weights': W, 'extra': '+3 x (1 - object overlap with Streets); +2 if lightmap texture classes differ; '
                                              '+5 if a streamed level is missing; +2 if not all six versus modes',
                       'normalisation': 'each weighted metric divided by its maximum over the candidates',
                       'nature': 'objective metrics are CONFIRMED counts from cooked data; the weighting is an analysis choice '
                                 '(documented, adjustable); ranking = recommendation, not a fact'},
            'ranking': [{'rank': i + 1, 'map': r['map'], 'name': r['name'], 'effort_index': r['effort_index']} for i, r in enumerate(out)],
            'candidates': out,
            'recommendation': out[0]['map'] if out else None}

if __name__ == '__main__':
    main()
