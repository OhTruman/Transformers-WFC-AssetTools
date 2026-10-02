"""Build the reconstruction asset database: AssetTools/manifests/assets.json

One record per unique asset (deduplicated by original object path + class):
  id, key, asset_type, class, object_name, object_path, original_package,
  owner_package (copy used for extraction), cooked_copies (#packages holding a
  copy), extracted (output files), references (object refs found in tagged
  properties of the asset and its sub-objects, grouped by kind), materials,
  textures, parent, skeleton (bone signature), compatible_skeletal_meshes /
  animsets, sequences, sounds, map_usage, notes.

Uncertain relations are flagged with `confidence` rather than asserted.
"""
import hashlib, json, os, sqlite3, sys, time
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract  # noqa: E402

ASSET_TYPES = {
    'Texture2D': 'texture', 'TextureCube': 'texture_cube', 'StaticMesh': 'static_mesh',
    'FracturedStaticMesh': 'static_mesh', 'SkeletalMesh': 'skeletal_mesh', 'AnimSet': 'animation_set',
    'AnimSequence': 'animation_sequence', 'Material': 'material', 'MaterialInstanceConstant': 'material_instance',
    'MaterialInstanceTimeVarying': 'material_instance', 'SoundNodeWaveEx': 'sound_wave', 'SoundNodeWave': 'sound_wave',
    'SoundCue': 'sound_cue', 'HmSoundEvent': 'sound_event', 'ParticleSystem': 'particle_system',
    'PhysicsAsset': 'physics_asset', 'FaceFXAsset': 'facefx', 'FaceFXAnimSet': 'facefx',
    'GFxMovieInfo': 'ui_movie', 'SwfMovie': 'ui_movie', 'Font': 'font', 'World': 'map',
}
REF_KIND = {
    'Texture2D': 'textures', 'TextureCube': 'textures', 'Material': 'materials',
    'MaterialInstanceConstant': 'materials', 'MaterialInstanceTimeVarying': 'materials',
    'StaticMesh': 'static_meshes', 'SkeletalMesh': 'skeletal_meshes', 'AnimSet': 'animsets',
    'AnimSequence': 'anim_sequences', 'SoundNodeWaveEx': 'sounds', 'SoundNodeWave': 'sounds',
    'SoundCue': 'sound_cues', 'HmSoundEvent': 'sound_events', 'ParticleSystem': 'particle_systems',
    'PhysicsAsset': 'physics_assets', 'FaceFXAsset': 'facefx', 'AnimTree': 'animtrees',
}
MANI = extract.MANI

def walk_refs(v, out):
    if isinstance(v, dict):
        if 'ref' in v and v.get('class'):
            out.append((v['class'], v['ref']))
        else:
            for x in v.values(): walk_refs(x, out)
    elif isinstance(v, list):
        for x in v: walk_refs(x, out)

def analyse_package(args):
    """Parse properties of the given assets (and their sub-objects) in one owner package."""
    pkgname, wanted = args                      # wanted: {opath_lower: class}
    pkg = ue3pkg.Package(os.path.join(extract.COOKED, pkgname + '.xxx'))
    pr = props.PropReader(pkg)
    children = defaultdict(list)
    for i, e in enumerate(pkg.exports):
        if e['outer'] > 0: children[e['outer']].append(i + 1)
    res = {}
    for i, e in enumerate(pkg.exports):
        idx = i + 1
        op = pkg.object_path(idx)
        cls = wanted.get(op.lower())
        if cls is None or pkg.class_name(e) != cls: continue
        refs, info, errors = [], {}, 0
        stack = [idx]; seen = set()
        while stack:
            j = stack.pop()
            if j in seen or len(seen) > 5000: continue
            seen.add(j)
            try:
                pl, _ = pr.read_object(j)
            except Exception:
                errors += 1; pl = []
            d = props.props_dict(pl)
            walk_refs(pl, refs)
            if j == idx:
                for k in ('Parent', 'SequenceName', 'SequenceLength', 'NumFrames', 'PreviewSkelMeshName',
                          'TrackBoneNames', 'LODGroup', 'SRGB', 'CompressionSettings', 'SizeX', 'SizeY',
                          'Duration', 'NumChannels', 'SampleRate', 'SoundGroup', 'Volume'):
                    if k in d: info[k] = d[k]
            else:
                cj = pkg.class_name(pkg.exports[j - 1])
                if cj == 'AnimSequence':
                    info.setdefault('sequences', []).append({
                        'name': d.get('SequenceName'), 'length': d.get('SequenceLength'),
                        'frames': d.get('NumFrames'), 'additive': d.get('bIsAdditive', False)})
            stack.extend(children.get(j, []))
        rk = defaultdict(set)
        for c, r in refs:
            if r.lower() == op.lower(): continue
            rk[REF_KIND.get(c, 'other')].add(r)
        res[op] = {'refs': {k: sorted(v) for k, v in rk.items() if k != 'other'},
                   'other_ref_count': len(rk.get('other', ())), 'info': info,
                   'subobjects': len(seen) - 1, 'prop_errors': errors}
    return res

def load_extracted():
    out = defaultdict(list)
    d = os.path.join(MANI, 'extracted')
    for fn in os.listdir(d):
        if not fn.endswith('.jsonl'): continue
        for line in open(os.path.join(d, fn), encoding='utf-8'):
            r = json.loads(line)
            if r.get('object_path') and r.get('output'):
                out[r['object_path'].lower()].append(r['output'])
    root = os.path.dirname(extract.OUT)
    for k, v in out.items():
        extra = []
        for o in v:
            if o.endswith('.fsb') and os.path.exists(os.path.join(root, o[:-4] + '.wav')): extra.append(o[:-4] + '.wav')
            if o.endswith('.gltf'): extra.append(o[:-5] + '.bin')
            if o.endswith('.psa') and os.path.exists(os.path.join(root, o[:-4] + '.anim.gltf')):
                extra += [o[:-4] + '.anim.gltf', o[:-4] + '.anim.bin']
        # umodel logs "Exporting" even when it writes nothing (e.g. textures
        # whose mips were stripped by the cooker) -> keep only real files
        out[k] = sorted(o for o in set(v + extra) if os.path.exists(os.path.join(root, o)))
    return out

def gltf_info(path):
    try:
        g = json.load(open(path, encoding='utf-8'))
    except Exception:
        return None
    mats = [m.get('name') for m in g.get('materials', [])]
    bones = []
    if g.get('skins'):
        bones = [g['nodes'][j].get('name') for j in g['skins'][0]['joints']]
    return {'materials': mats, 'bones': bones}

def main():
    t0 = time.time()
    con = sqlite3.connect(os.path.join(MANI, 'inventory.db'))
    classes = list(ASSET_TYPES)
    rows = con.execute('SELECT package, opath, class, name, serial_size FROM exports WHERE class IN (%s)'
                       % ','.join('?' * len(classes)), classes).fetchall()
    cands = defaultdict(list)
    for pkg, op, cls, name, size in rows:
        cands[(op, cls)].append((pkg, size, name))
    # owner = original package if it holds a full-size copy, else biggest copy
    pkg_load = Counter(p for lst in cands.values() for p, _, _ in lst)
    assets = {}
    for (op, cls), lst in cands.items():
        best = max(c[1] for c in lst)
        orig = op.split('.', 1)[0]
        own = [c for c in lst if c[0] == orig and c[1] >= best]
        pick = own[0] if own else max((c for c in lst if c[1] >= best), key=lambda c: pkg_load[c[0]])
        assets[(op, cls)] = {'owner': pick[0], 'name': pick[2], 'copies': len({c[0] for c in lst}),
                             'serial_size': best}
    print('unique assets:', len(assets), '%.0fs' % (time.time() - t0), flush=True)

    # map usage: map package contains a copy of, or imports, the object
    maps = [r[0] for r in con.execute("SELECT DISTINCT package FROM exports WHERE class='World'")]
    usage = defaultdict(set)
    keyset = {op.lower() for op, _ in assets}
    for m in maps:
        for (op,) in con.execute('SELECT opath FROM exports WHERE package=?', (m,)):
            if op.lower() in keyset: usage[op.lower()].add(m)
        for (p,) in con.execute('SELECT path FROM imports WHERE package=?', (m,)):
            if p.lower() in keyset: usage[p.lower()].add(m)
    print('map usage computed', '%.0fs' % (time.time() - t0), flush=True)

    # property analysis, one task per owner package
    work = defaultdict(dict)
    for (op, cls), a in assets.items():
        if cls in ('World',): continue          # maps handled by maps.py
        work[a['owner']][op.lower()] = cls
    analysed = {}
    with ProcessPoolExecutor() as ex:
        for r in ex.map(analyse_package, sorted(work.items(), key=lambda kv: -len(kv[1])), chunksize=2):
            analysed.update({k.lower(): v for k, v in r.items()})
    print('properties analysed', len(analysed), '%.0fs' % (time.time() - t0), flush=True)

    extracted = load_extracted()
    root = os.path.dirname(extract.OUT)
    by_name = defaultdict(list)                 # material short name -> opaths
    for op, cls in assets:
        if ASSET_TYPES[cls] in ('material', 'material_instance'):
            by_name[op.rsplit('.', 1)[-1].lower()].append(op)

    records = []
    skel_sigs = {}
    for (op, cls), a in sorted(assets.items()):
        k = op.lower()
        rec = {'id': hashlib.sha1(('%s:%s' % (cls, op)).encode()).hexdigest()[:16],
               'key': '%s:%s' % (cls, op), 'asset_type': ASSET_TYPES[cls], 'class': cls,
               'object_name': op.rsplit('.', 1)[-1], 'object_path': op,
               'original_package': op.split('.', 1)[0], 'owner_package': a['owner'],
               'cooked_copies': a['copies'], 'serial_size': a['serial_size'],
               'extracted': extracted.get(k, []), 'map_usage': sorted(usage.get(k, ()))}
        if not rec['extracted']:
            rec['extraction_status'] = {
                'Texture2D': 'not extracted: no mip data in any cooked copy (likely cooker-stripped) or export failed',
                'TextureCube': 'not extracted: umodel has no TextureCube exporter; WFC cube stores face data natively',
                'Material': 'not exported by umodel (cooked expression graph); see references.textures',
                'SoundNodeWaveEx': 'not extracted: export holds no FSB4 payload (stub)',
            }.get(cls, 'not extracted (no exporter in pipeline for this class yet)')
        an = analysed.get(k)
        if an:
            rec['references'] = an['refs']
            if an['info']: rec['info'] = an['info']
            if an['prop_errors']: rec['notes'] = ['%d sub-object property blocks unparsed' % an['prop_errors']]
            if 'textures' in an['refs']: rec['textures'] = an['refs']['textures']
            if 'materials' in an['refs']: rec['materials'] = an['refs']['materials']
            if 'sounds' in an['refs']: rec['sounds'] = an['refs']['sounds']
            p = an['info'].get('Parent')
            if isinstance(p, dict) and 'ref' in p: rec['parent'] = p['ref']
            if 'sequences' in an['info']:
                rec['sequences'] = an['info'].pop('sequences')
        gl = next((o for o in rec['extracted'] if o.endswith('.gltf')), None)
        if gl:
            gi = gltf_info(os.path.join(root, gl))
            if gi:
                mats = []
                for mname in gi['materials']:
                    c = by_name.get((mname or '').lower(), [])
                    if len(c) == 1: mats.append({'ref': c[0], 'confidence': 'name-unique'})
                    elif c:
                        same = [x for x in c if x.split('.', 1)[0] == rec['original_package']]
                        if len(same) == 1: mats.append({'ref': same[0], 'confidence': 'name+same-package'})
                        else: mats.append({'name': mname, 'candidates': c, 'confidence': 'ambiguous'})
                    elif mname and not mname.startswith('dummy_material'): mats.append({'name': mname, 'confidence': 'unresolved'})
                if mats: rec['materials'] = mats
                if gi['bones']:
                    rec['skeleton'] = {'bone_count': len(gi['bones']), 'root': gi['bones'][0],
                                       'signature': hashlib.sha1('|'.join(sorted(gi['bones'])).encode()).hexdigest()[:12]}
                    skel_sigs[op] = set(b.lower() for b in gi['bones'])
        records.append(rec)

    # animation set <-> skeletal mesh compatibility by bone-name coverage
    for rec in records:
        if rec['class'] != 'AnimSet': continue
        tb = rec.get('info', {}).get('TrackBoneNames')
        if not isinstance(tb, list) or not tb: continue
        tbs = {str(b).lower() for b in tb}
        rec['info']['track_bone_count'] = len(tbs)
        rec['info'].pop('TrackBoneNames', None)
        rec['compatible_skeletal_meshes'] = sorted(
            m for m, bones in skel_sigs.items() if len(tbs & bones) >= 0.95 * len(tbs))
        rec['skeleton_match_confidence'] = 'bone-name coverage >= 95%'
    for rec in records:
        pv = rec.get('info', {}).get('PreviewSkelMeshName')
        if rec['class'] == 'AnimSet' and pv and pv != 'None':
            rec['preview_skeletal_mesh'] = pv        # authored link, high confidence
    mesh_anims = defaultdict(list)
    for rec in records:
        for m in rec.get('compatible_skeletal_meshes', []): mesh_anims[m].append(rec['object_path'])
    for rec in records:
        if rec['class'] == 'SkeletalMesh' and rec['object_path'] in mesh_anims:
            rec['compatible_animsets'] = sorted(mesh_anims[rec['object_path']])

    out = {'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
           'source': 'Transformers: War for Cybertron (Xbox 360) - local owned copy',
           'counts': dict(Counter(r['asset_type'] for r in records)),
           'extracted_counts': dict(Counter(r['asset_type'] for r in records if r['extracted'])),
           'assets': records}
    json.dump(out, open(os.path.join(MANI, 'assets.json'), 'w', encoding='utf-8'), indent=0)
    print('assets.json written: %d records in %.0fs' % (len(records), time.time() - t0))
    print(json.dumps(out['counts'])); print(json.dumps(out['extracted_counts']))

if __name__ == '__main__':
    main()
