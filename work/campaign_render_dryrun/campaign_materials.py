"""Campaign render gap #4 (CAMPAIGN_RENDER_DRYRUN.md finding 4): the material lists the campaign needs beyond world.glb, per chapter.

Rendering's MP lists come from the MP roster (character_materials.py), MP_* maps (energy_death_materials.py) and render_index
skeletal actors (scene_materials.py). The campaign counterparts, from authored.db / inventory.db and the campaign VerticalSlice:
  - chapter materials = Material / MaterialInstanceConstant / MaterialInstanceTimeVarying exports cooked into the chapter's level
    packages (map.json sublevels; inventory.db); 'in_world_glb' = named by a world.glb material's extras.wfc_material;
  - skeletal: every SkeletalMesh cooked into the chapter (chassis forms, weapons, skeletal world actors): its extracted glTF's material
    slot names resolved to chapter materials, preferring the mesh's own package family (scene_materials.py's rule; cooked skeletal
    materials are native, not tagged);
  - energy_death: MICs whose Parent is TR_AllShader_p.Release.TR_Defrag_MAT, and FormBlueprint EnergyDeathMaterial keyed by the
    package of the form's SkeletalMesh (energy_death_materials.py's rule);
  - every other material not in world.glb is classed by the classes of the chapter objects (inventory.db) referencing it (authored.db refs):
    runtime_assigned (any referrer other than ObjectReferencer / a material), parent_only (referenced only as a Parent of another
    material: compiled through its children), objectreferencer_only, unreferenced.
Writes manifests/campaign/render_materials/<chapter>.json and <chapter>.txt (the build list: skeletal + energy_death +
runtime_assigned + objectreferencer_only, one path per line, world.glb materials excluded). Read-only on all inputs.
"""
import json, os, sqlite3, struct, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')
CONTENT = r'F:\Transformers Rebuild\ExtractedAssets\content'
OUT = os.path.join(AT, 'manifests', 'campaign', 'render_materials')
MATS = ('Material', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying')
DEFRAG = 'tr_allshader_p.release.tr_defrag_mat'
DB = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
# membership comes from inventory.db (every cooked copy); authored.db keeps one row per opath (first package seen), so its
# package column under-counts objects shared with other maps. authored.db supplies props and refs by opath.

def glb_materials(path):
    with open(path, 'rb') as f:
        f.read(12); n, _ = struct.unpack('<II', f.read(8)); j = json.loads(f.read(n))
    return {(m.get('extras') or {}).get('wfc_material') for m in j.get('materials') or []} - {None}

def q(sql, args): return DB.execute(sql, args).fetchall()

def chapter(ch):
    subs = json.load(open(os.path.join(CVS, ch, 'map.json'), encoding='utf-8')).get('sublevels') or []
    ph = ','.join('?' * len(subs))
    here = {}
    for op, cls in INV.execute('select opath, class from exports where package in (%s)' % ph, subs): here.setdefault(op, cls)
    mats = {op: c for op, c in here.items() if c in MATS}
    props = {}
    for op in mats:
        r = DB.execute('select props from objects where opath=?', (op,)).fetchone(); props[op] = r[0] if r else None
    world = glb_materials(os.path.join(CVS, ch, 'world.glb'))
    byname = defaultdict(list)
    for op in mats: byname[op.split('.')[-1].lower()].append(op)
    # skeletal meshes: glTF slot names -> chapter materials
    skeletal, sk_missing = {}, []
    for mesh in sorted(op for op, c in here.items() if c == 'SkeletalMesh'):
        g = os.path.join(CONTENT, *mesh.split('.')) + '.gltf'
        if not os.path.exists(g): sk_missing.append(mesh); continue
        pkg = mesh.split('.')[0].lower(); got = []
        for mt in json.load(open(g, encoding='utf-8')).get('materials') or []:
            c = byname.get((mt.get('name') or '').lower(), [])
            pick = next((x for x in c if x.lower().startswith(pkg)), c[0] if c else None)
            if pick and pick not in got: got.append(pick)
        if got: skeletal[mesh] = got
    # energy death
    ed = sorted(op for op in mats if DEFRAG in ((json.loads(props[op] or '{}').get('Parent') or '') if isinstance(json.loads(props[op] or '{}').get('Parent'), str) else '').lower())
    ed_by_pkg = {}
    for op in sorted(o for o, c in here.items() if c.endswith('FormBlueprint')):
        r = DB.execute('select props from objects where opath=?', (op,)).fetchone(); o = json.loads((r[0] if r else None) or '{}'); e, s = o.get('EnergyDeathMaterial'), o.get('SkeletalMesh')
        if isinstance(e, str) and isinstance(s, str): ed_by_pkg[s.split('.')[0].lower()] = e
    for op in ed: ed_by_pkg.setdefault(op.split('.')[0].lower(), op)
    # referrer classes for every material not in world.glb
    in_sk = {m for v in skeletal.values() for m in v}; in_ed = set(ed) | set(ed_by_pkg.values())
    runtime, parent_only, objref_only, unref = defaultdict(list), [], [], []
    for op in sorted(mats):
        if op in world or op in in_sk or op in in_ed: continue
        classes = {here[s] for (s,) in q('select distinct src from refs where dst=?', (op,)) if s in here}
        if not classes: unref.append(op); continue
        other = sorted(c for c in classes if c != 'ObjectReferencer' and c not in MATS)
        if other:
            for c in other: runtime[c].append(op)
        elif classes & set(MATS): parent_only.append(op)
        else: objref_only.append(op)
    runtime_set = sorted({m for v in runtime.values() for m in v})
    build = []
    for m in [x for v in skeletal.values() for x in v] + sorted(in_ed) + runtime_set + objref_only:
        if m not in build and m not in world: build.append(m)
    rec = {'chapter': ch, 'level_packages': len(subs), 'chapter_materials': len(mats), 'in_world_glb': len(set(mats) & world),
           'world_glb_materials_not_cooked_in_chapter (other packages)': len(world - set(mats)),
           'build_list': len(build), 'skeletal_meshes': len(skeletal), 'skeletal_meshes_without_gltf': sk_missing,
           'skeletal': skeletal, 'energy_death': sorted(in_ed), 'energy_death_by_package': dict(sorted(ed_by_pkg.items())),
           'runtime_assigned_by_referrer_class': {k: v for k, v in sorted(runtime.items())}, 'parent_only': parent_only,
           'objectreferencer_only': objref_only, 'unreferenced': unref}
    os.makedirs(OUT, exist_ok=True)
    json.dump(rec, open(os.path.join(OUT, ch + '.json'), 'w', encoding='utf-8'), indent=1)
    open(os.path.join(OUT, ch + '.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(build) + '\n')
    print(ch, {k: rec[k] for k in ('chapter_materials', 'in_world_glb', 'build_list', 'skeletal_meshes')}, 'ed', len(in_ed),
          'runtime', len(runtime_set), 'parent', len(parent_only), 'objref', len(objref_only), 'unref', len(unref),
          'top referrers', sorted(((len(v), k) for k, v in runtime.items()), reverse=True)[:6])

if __name__ == '__main__':
    for ch in (sys.argv[1:] or sorted(os.listdir(CVS))): chapter(ch)
