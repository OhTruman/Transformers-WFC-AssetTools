"""Authored asset closure for MP abilities / killstreaks -> manifests/mp_content/ability_assets.json

  python ability_assets.py

Roots: TransCustomization.ini TnDataProvider_Ability / _Killstreak ObjectPath (a class -> its CDO <pkg>.Default__<Class>), for
the abilities Rendering / Systems / Gameplay still need (Barrier, SpawnSentry, SpawnAmmoCrate, RollerSphere, GuidedMissile +
the guided-missile killstreak). Every object reference reachable from the root (authored.db effective values, depth-limited)
is followed through archetypes / sub-objects / spawned classes (class refs resolve to their CDO); leaf assets are reported by
class with their extraction status:
  StaticMesh / SkeletalMesh -> glTF in the asset index; ParticleSystem -> in authored.db (+ emitter meshes / materials);
  SoundCue -> resolved SoundNodeWave(s) with WAV on disk; Material* / Texture* -> exported file; AnimSet / AnimSequence.
"""
import glob, json, os, re, sys, time
from collections import OrderedDict as OD, defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
CFG = os.path.join(ROOT, 'config', 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
WANT = ['Barrier', 'SpawnSentry', 'SpawnAmmoCrate', 'RollerSphere', 'GuidedMissile']
LEAF = ('StaticMesh', 'SkeletalMesh', 'ParticleSystem', 'SoundCue', 'SoundNodeWave', 'Material', 'MaterialInstanceConstant',
        'Texture2D', 'TextureCube', 'TextureFlipBook', 'AnimSet', 'AnimTree', 'PhysicsAsset', 'SwfMovie', 'GFxMovieInfo')
SKIP_PREFIX = ('Engine.', 'Core.', 'TransGame.Default__TnPawn', 'TransGame.Default__TnPlayerController', 'TransGame.Default__TnGame')
MAX_DEPTH = 6
MAX_NODES = 4000

def ini_sections(fn):
    out = {}; cur = None
    for line in open(os.path.join(CFG, fn), encoding='utf-8', errors='replace'):
        s = line.strip()
        m = re.match(r'^\[(\S+) (TnDataProvider_\w+)\]$', s)
        if m: cur = out.setdefault(m.group(1), {'type': m.group(2)}); continue
        if cur is not None and '=' in s: k, v = s.split('=', 1); cur.setdefault(k, v)
    return out

def cdo(cls_path):
    pkg, cls = cls_path.split('.', 1)
    return '%s.Default__%s' % (pkg, cls)

_assets = None
def assets():
    global _assets
    if _assets is None: _assets = {a['object_path'].lower(): a for a in json.load(open(os.path.join(AT, 'manifests', 'assets.json'), encoding='utf-8'))['assets']}
    return _assets

def refs_in(v, out):
    if isinstance(v, str):
        if '.' in v and A.get(v): out.add(v)
        elif v.count('.') == 1 and A.get(cdo(v)): out.add(cdo(v))   # class reference -> its CDO
    elif isinstance(v, dict):
        for x in v.values(): refs_in(x, out)
    elif isinstance(v, list):
        for x in v: refs_in(x, out)

def leaf_status(o, cls):
    a = assets().get(o.lower()) or {}
    ex = [x for x in a.get('extracted') or [] if os.path.exists(os.path.join(ROOT, x))]
    if cls in ('StaticMesh', 'SkeletalMesh'): return {'gltf': next((x for x in ex if x.endswith('.gltf')), None)}
    if cls == 'SoundCue':
        waves = [d for (d,) in A.con().execute("SELECT dst FROM refs WHERE src LIKE ? AND dst_class = 'SoundNodeWave'", (o + '%',)).fetchall()]
        for (s,) in A.con().execute("SELECT opath FROM objects WHERE opath LIKE ? AND class = 'SoundNodeWaveEvent'", (o + '.%',)).fetchall():
            waves += [w for w in (A.values(s) or {}).get('ChildNodes') or [] if isinstance(w, str)]
        waves = sorted(set(waves))
        wav = [w for w in waves if glob.glob(os.path.join(ROOT, 'content', *w.split('.')) + '.wav')]
        return {'waves': waves, 'wav_on_disk': len(wav), 'silent_cue': not waves}
    if cls == 'ParticleSystem':
        ms = []
        for (m, c) in A.con().execute("SELECT opath, class FROM objects WHERE opath LIKE ? AND class LIKE 'ParticleModuleTypeDataMesh%'", (o + '.%',)).fetchall():
            mm = (A.values(m) or {}).get('Mesh')
            if mm: ms.append({'mesh': mm, 'gltf': any(x.endswith('.gltf') for x in (assets().get(mm.lower()) or {}).get('extracted') or [])})
        return {'in_authored_db': True, 'mesh_emitters': ms or None}
    return {'file': ex[0] if ex else None}

def closure(root):
    seen = {root: 0}; dq = deque([root]); leaves = OD(); objs = 0
    while dq and objs < MAX_NODES:
        o = dq.popleft(); d = seen[o]; objs += 1
        row = A.get(o)
        if not row: continue
        if row['class'] in LEAF:
            leaves[o] = OD([('class', row['class'])] + list(leaf_status(o, row['class']).items()))
            if row['class'] != 'ParticleSystem': continue
        if d >= MAX_DEPTH: continue
        nxt = set(); refs_in(A.values(o) or {}, nxt)
        for (s,) in A.con().execute('SELECT opath FROM objects WHERE outer_path = ?', (o,)).fetchall(): nxt.add(s)
        arch = row.get('archetype')
        if arch and A.get(arch): nxt.add(arch)
        for x in nxt:
            if x in seen or x.startswith(SKIP_PREFIX): continue
            seen[x] = d + 1; dq.append(x)
    return leaves, objs

def main():
    ab = ini_sections('TransCustomization.ini')
    roots = OD()
    for n in WANT:
        s = ab.get(n)
        if s and s.get('ObjectPath'): roots[n] = [cdo(s['ObjectPath'])]
    for n, s in ab.items():
        if s['type'] == 'TnDataProvider_Killstreak' and 'Guided' in n and s.get('ObjectPath'):
            roots['Killstreak_' + n] = [cdo(s['ObjectPath'])]
    if not any(k.startswith('Killstreak_') for k in roots) and A.get('TransGame.Default__TnKillstreakGuidedMissile'):
        roots['Killstreak_GuidedMissile'] = ['TransGame.Default__TnKillstreakGuidedMissile', 'TransGame.Default__TnKillstreakActivatedGuidedMissile']
    # classes the ability script spawns / applies (not authored as properties on the ability CDO): name-matched, RE to confirm
    SCRIPT_SPAWNED = {'Barrier': ['TransGame.TnBarrierSpawnable', 'TransGame.TnBarrierSpawnableNative'],
                      'RollerSphere': ['TransGame.TnBuffRollerSphere', 'TransGame.TnBuffDotRollerSphere', 'TransGame.TnActorFactoryRollerMine'],
                      'GuidedMissile': ['TransGame.TnGuidedMissile', 'TransGame.TnGuidedMissileData'],
                      'Killstreak_GuidedMissileStreak': ['TransGame.TnGuidedMissile', 'TransGame.TnGuidedMissileData']}
    extra = {}
    for n, cl in SCRIPT_SPAWNED.items():
        if n in roots:
            ex = [cdo(c) for c in cl if A.get(cdo(c))]; roots[n] = roots[n] + ex; extra[n] = ex
    out = OD()
    for n, rs in roots.items():
        leaves = OD(); objs = 0
        for r in rs:
            l, k = closure(r); leaves.update(l); objs += k
        by = defaultdict(list)
        for o, v in leaves.items(): by[v['class']].append(dict(v, object=o))
        missing = [o for o, v in leaves.items() if (v['class'] in ('StaticMesh', 'SkeletalMesh') and not v.get('gltf')) or
                   (v['class'] == 'SoundCue' and v.get('waves') and not v.get('wav_on_disk')) or
                   (v['class'].startswith('Texture') and not v.get('file'))]
        out[n] = OD([('roots', rs), ('script_spawned_roots (name-matched, PROVISIONAL)', extra.get(n)), ('ini', ab.get(n)), ('objects_walked', objs),
                     ('summary', {c: len(v) for c, v in sorted(by.items())}), ('missing_exports', missing),
                     ('assets', OD(sorted(by.items())))])
        print(n, out[n]['summary'], 'missing', len(missing), missing[:4])
    res = OD([('generated_by', 'AssetTools/scripts/wfc/ability_assets.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('method', 'reference closure from the ability / killstreak CDOs (TransCustomization.ini ObjectPath) through authored.db '
                         'values, sub-objects, archetypes and class refs (-> CDO), depth %d' % MAX_DEPTH),
              ('abilities', out)])
    json.dump(res, open(os.path.join(AT, 'manifests', 'mp_content', 'ability_assets.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
