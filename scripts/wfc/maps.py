"""Map/level metadata -> ExtractedAssets/maps/<map>.json (+ manifests/maps.json index)

For each package containing a World: every actor placed in PersistentLevel
with class, name, location, rotation (UE units and degrees), scale, and the
assets its components reference (static/skeletal mesh, materials, sounds,
particles), plus LevelStreaming entries (sub-level package names).

Known gap: StaticMeshCollectionActor stores its component transforms in
native (non-property) data; those components are listed with mesh refs but
transform 'native_unparsed'.  UE units: 1 uu ~ 2 cm in UE3 convention.
"""
import json, os, sys, sqlite3
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract  # noqa: E402

OUTDIR = os.path.join(os.path.dirname(extract.OUT), 'maps')
ROT = 360.0 / 65536.0

def refval(v):
    return v.get('ref') if isinstance(v, dict) else None

def one_map(pkgname):
    pkg = ue3pkg.Package(os.path.join(extract.COOKED, pkgname + '.xxx'))
    pr = props.PropReader(pkg)
    cls = [pkg.class_name(e) for e in pkg.exports]
    level_idx = [i + 1 for i, c in enumerate(cls) if c == 'Level']
    cache = {}
    def P0(i):
        if i not in cache:
            try: cache[i] = props.props_dict(pr.read_object(i)[0])
            except Exception: cache[i] = None
        return cache[i]
    def P(i, depth=0):
        """Properties merged down the archetype chain (instance overrides win)."""
        own = P0(i)
        if own is None: return None
        arch = pkg.exports[i - 1]['archetype']
        if arch > 0 and depth < 8:
            base = P(arch, depth + 1) or {}
            merged = dict(base); merged.update(own)
            return merged
        return own
    children = defaultdict(list)
    for i, e in enumerate(pkg.exports):
        children[e['outer']].append(i + 1)
    path_index = {pkg.object_path(i + 1).lower(): i + 1 for i in range(len(pkg.exports))}
    actors, streaming, errors = [], [], 0
    for lv in level_idx:
        for a in children[lv]:
            c = cls[a - 1]
            if c.endswith('Component') or c in ('Model', 'Polys', 'Level'): continue
            d = P(a)
            if d is None:
                errors += 1; actors.append({'class': c, 'name': pkg.exports[a - 1]['name'], 'props': 'unparsed'}); continue
            if 'Location' not in d and 'StaticMeshComponent' not in d and not c.startswith('LevelStreaming'):
                # non-placed objects (sequences, infos) still recorded compactly
                if c in ('Sequence', 'WorldInfo', 'PrefabInstance') or c.startswith('Hm'):
                    actors.append({'class': c, 'name': pkg.exports[a - 1]['name'], 'placed': False})
                continue
            act = {'class': c, 'name': pkg.exports[a - 1]['name']}
            ar = pkg.exports[a - 1]['archetype']
            if ar:
                act['archetype'] = pkg.object_path(ar) if ar > 0 else pkg.full_path(ar)
            if 'Location' in d: act['location'] = d['Location']
            if 'Rotation' in d:
                act['rotation_uu'] = d['Rotation']
                act['rotation_deg'] = [round(x * ROT, 4) for x in d['Rotation']]  # pitch,yaw,roll
            if 'DrawScale' in d: act['draw_scale'] = d['DrawScale']
            if 'DrawScale3D' in d: act['draw_scale_3d'] = d['DrawScale3D']
            if 'Tag' in d and d['Tag'] != 'None': act['tag'] = d['Tag']
            comps = []
            # components referenced by the actor's properties
            for k, v in d.items():
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if isinstance(x, dict) and str(x.get('class', '')).endswith('Component') and 'ref' in x:
                        comps.append(x['ref'])
            if c == 'StaticMeshCollectionActor' and 'StaticMeshComponents' in d:
                act['collection_transforms'] = 'native_unparsed'
            refs = {}
            for i in _component_exports(pkg, a, children, comps, path_index):
                cd = P(i)
                if not cd: continue
                for key, kind in (('StaticMesh', 'static_mesh'), ('SkeletalMesh', 'skeletal_mesh'),
                                  ('Template', 'particle_system'), ('SoundCue', 'sound_cue'),
                                  ('PhysicsAsset', 'physics_asset')):
                    r = refval(cd.get(key))
                    if r: refs.setdefault(kind, []).append(r)
                mats = cd.get('Materials')
                if isinstance(mats, list):
                    for m in mats:
                        r = refval(m)
                        if r: refs.setdefault('materials', []).append(r)
                sets = cd.get('AnimSets')
                if isinstance(sets, list):
                    for m in sets:
                        r = refval(m)
                        if r: refs.setdefault('animsets', []).append(r)
            if refs: act['assets'] = {k: sorted(set(v)) for k, v in refs.items()}
            if c.startswith('LevelStreaming'):
                streaming.append({'class': c, 'package': d.get('PackageName'),
                                  'should_be_loaded': d.get('bShouldBeLoaded'), 'visible': d.get('bShouldBeVisible')})
            actors.append(act)
    # WorldInfo streaming levels are objects (not actors) under the World/level
    for i, c in enumerate(cls):
        if c.startswith('LevelStreaming'):
            d = P(i + 1) or {}
            streaming.append({'class': c, 'object': pkg.exports[i]['name'], 'package': d.get('PackageName'),
                              'should_be_loaded': d.get('bShouldBeLoaded'), 'visible': d.get('bShouldBeVisible')})
    out = {'map': pkgname, 'actor_count': sum(1 for a in actors if a.get('placed', True)),
           'actor_classes': dict(Counter(a['class'] for a in actors).most_common()),
           'streaming_levels': streaming, 'unparsed_actors': errors, 'actors': actors}
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(out, open(os.path.join(OUTDIR, pkgname + '.json'), 'w'), indent=0)
    used = Counter()
    for a in actors:
        for k, v in a.get('assets', {}).items():
            used[k] += len(v)
    return {'map': pkgname, 'actors': out['actor_count'], 'streaming': [s['package'] for s in streaming if s.get('package')],
            'unparsed': errors, 'asset_refs': dict(used), 'top_classes': dict(Counter(a['class'] for a in actors).most_common(8))}

def _component_exports(pkg, actor_idx, children, comp_paths, path_index):
    """Components are usually direct children of the actor; prefab/archetype
    components live elsewhere, so also resolve referenced paths."""
    res = list(children.get(actor_idx, []))
    have = set(res)
    for p in comp_paths:
        j = path_index.get(p.lower())
        if j and j not in have:
            res.append(j); have.add(j)
    return res

def main():
    con = sqlite3.connect(os.path.join(extract.MANI, 'inventory.db'))
    maps = sorted(r[0] for r in con.execute("SELECT DISTINCT package FROM exports WHERE class='World'"))
    with ProcessPoolExecutor() as ex:
        idx = list(ex.map(one_map, maps, chunksize=2))
    json.dump(idx, open(os.path.join(extract.MANI, 'maps.json'), 'w'), indent=1)
    print('maps:', len(idx), 'actors:', sum(m['actors'] for m in idx), 'unparsed actors:', sum(m['unparsed'] for m in idx))

if __name__ == '__main__':
    main()
