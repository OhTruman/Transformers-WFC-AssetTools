"""Escalation horde roster asset check (Integration 2026-10-18; Gameplay spec section 4 + RE MP_ESCALATION_RE.md section 7.1). Read-only.

Per enemy template (TnAiCharacterDefinition from both maps' spawn lists + the RE 7.1 table): chassis ROBODEF -> SkelMesh, PhysicsAsset,
AnimSets, vehicle form (VEHDEF -> its mesh / anim sets), SoundEventSet; ActionOverride weapon classes. For each asset: cooked size
(inventory.db), extracted state (ExtractedAssets/content files), whether our runtime data already uses it (a VerticalSlice character /
weapon export). Plus FX templates and sound cues reachable from the template's ROBODEF / VEHDEF (authored refs, 2 hops), the Escalation
HUD GFx movies and the mode's wave start / end cues. Writes roster.json here.
"""
import glob, json, os, re, sqlite3
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
EA = os.path.join(TR, 'ExtractedAssets'); CONTENT = os.path.join(EA, 'content'); RE = os.path.join(TR, 'RE-Workspace', 'notes', 'data', 'escalation')
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db')); INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))

def props(o):
    r = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
    return (r[0], json.loads(r[1] or '{}')) if r else (None, None)

def size(o):
    r = INV.execute('select max(serial_size), count(distinct package) from exports where opath=?', (o,)).fetchone()
    return (r[0] or 0, r[1] or 0)

def files(o, exts):
    if not o: return []
    b = os.path.join(CONTENT, *o.split('.'))
    return [os.path.relpath(b + e, EA).replace(os.sep, '/') for e in exts if os.path.exists(b + e)]

# what our runtime data already carries
used_meshes, used_animsets, chars = {}, {}, {}
for f in glob.glob(os.path.join(EA, 'VerticalSlice', 'Characters', '*', 'character.json')):
    c = os.path.basename(os.path.dirname(f)); s = open(f, encoding='utf-8').read()
    for m in set(re.findall(r'TR_[A-Za-z0-9_]+_p\.[A-Za-z0-9_]+_SKEL(?:MESH)?', s)): used_meshes.setdefault(m, []).append(c)
    for m in set(re.findall(r'TR_[A-Za-z0-9_]+_ANM_p\.[A-Za-z0-9_]+|TR_[A-Za-z0-9_]+_p\.[A-Za-z0-9_]+_ANIM', s)): used_animsets.setdefault(m, []).append(c)
weapons = {os.path.basename(os.path.dirname(f)): json.load(open(f, encoding='utf-8')).get('class')
           for f in glob.glob(os.path.join(EA, 'VerticalSlice', 'Weapons', '*', 'weapon.json'))}
weapon_by_class = {v.split('.')[-1] if v else None: k for k, v in weapons.items()}

def asset(o, kind):
    if not o: return None
    ex = {'mesh': ['.gltf'], 'anim': ['.anim.gltf', '.psa'], 'physics': []}[kind]
    sz, npk = size(o)
    r = OD([('object', o), ('cooked_bytes', sz), ('cooked_in_packages', npk), ('extracted', files(o, ex))])
    if kind == 'mesh': r['used_by_our_characters'] = sorted(used_meshes.get(o, []))
    if kind == 'anim': r['used_by_our_characters'] = sorted(used_animsets.get(o, []))
    return r

def reach(starts, classes, hops=3):
    """refs by exact src only (indexed); an object's own sub-objects enter through its property values (component / blueprint
    paths), so no LIKE scans of the refs table"""
    out, seen, front = set(), set(starts), list(starts)
    for _ in range(hops):
        nxt = []
        for s in front:
            for d, dc in DB.execute('select dst, dst_class from refs where src=?', (s,)):
                if dc in classes: out.add(d)
                elif d and d not in seen: seen.add(d); nxt.append(d)
        front = nxt
    return sorted(out)

# FX templates already compiled into the MP render data (Rendering's map_fx_runtime 'systems', any MP map)
RENDER_FX = set()
for f in glob.glob(os.path.join(TR, 'Rebuild', 'work', 'render', 'MP_*', 'map_fx_runtime.json')):
    RENDER_FX |= set((json.load(open(f, encoding='utf-8')).get('systems') or {}).keys())
import sys; sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc')); import authored as A  # noqa: E402

def cue_files(c):
    ws = (A.cue(c) or {}).get('waves') or []
    have = 0
    for w in ws:
        pk, rest = w['wave'].split('.', 1); parts = rest.split('.')
        cand = [os.path.join(CONTENT, pk, *parts), os.path.join(CONTENT, '_LOC', 'int', pk, *parts), os.path.join(CONTENT, pk + '_INT', *parts)]
        have += any(os.path.exists(b + e) for b in cand for e in ('.wav', '.fsb'))
    return len(ws), have

def template(aicd):
    cls, p = props(aicd)
    if p is None: return OD([('template', aicd), ('in_authored_db', False)])
    data = p.get('AiCharacterDataResolved') or {}
    robo = data.get('ChassisType'); rc, rp = props(robo) if robo else (None, {})
    rp = rp or {}; veh = rp.get('TransformerVehicle'); vc, vp = props(veh) if veh else (None, {}); vp = vp or {}
    wcls = []
    for ov in p.get('ActionOverrides') or []:
        oc, opp = props(ov)
        for k, v in (opp or {}).items():
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, str) and 'TnWeapon' in x: wcls.append(x)
    fx = reach([robo, veh] if veh else [robo], {'ParticleSystem'}) if robo else []
    cues = reach([robo, veh] if veh else [robo], {'SoundCue'}) if robo else []
    return OD([('template', aicd), ('class', cls), ('chassis', robo), ('chassis_class', rc), ('loot', data.get('LootClassification')),
               ('robot_mesh', asset(rp.get('SkelMesh'), 'mesh')), ('physics_asset', asset(rp.get('PhysicsAsset'), 'physics')),
               ('anim_sets', [asset(x, 'anim') for x in rp.get('AnimSets') or []]), ('anim_tree', rp.get('AnimTree')),
               ('vehicle_form', veh),
               ('vehicle_mesh', asset((vp or {}).get('SkeletalMesh') or (vp or {}).get('SkelMesh'), 'mesh') if veh else None),
               ('vehicle_anim_sets', [asset(x, 'anim') for x in (vp or {}).get('AnimSets') or []] if veh else []),
               ('sound_event_set', rp.get('SoundEventSet')),
               ('weapon_classes', [OD([('class', w), ('our_weapon_export', weapon_by_class.get(w.split('.')[-1]))]) for w in sorted(set(wcls))]),
               ('fx_templates', [OD([('template', f), ('cooked_bytes', size(f)[0]), ('in_mp_render_data', f in RENDER_FX)]) for f in fx]),
               ('sound_cues', [OD([('cue', c), ('cooked_bytes', size(c)[0]), ('waves_total_with_file', cue_files(c))]) for c in cues])])

def main():
    tpl = []
    for m in ('MP_ESC_BrokenHope', 'MP_ESC_Remnant'):
        for e in json.load(open(os.path.join(RE, m + '.json'), encoding='utf-8'))['spawn_list'][0]['Enemies']:
            if e['EnemyType'] not in tpl: tpl.append(e['EnemyType'])
    for extra in ('TR_AiEscalation_p.Brute_Autobot_AICD', 'TR_AiEscalation_p.Titan_Decepticon_AICD', 'TR_AiEscalation_p.Soldier_Tank_Decepticon_AICD'):
        if extra not in tpl and props(extra)[1] is not None: tpl.append(extra)
    rows = [template(t) for t in tpl]
    gfx = [OD([('object', o), ('class', c), ('cooked_bytes', s), ('extracted', files(o, ['.gfx', '.swf']))])
           for o, c, s in INV.execute("select opath, class, max(serial_size) from exports where class in ('SwfMovie','GFxMovieInfo') and "
                                      "(lower(opath) like '%surviv%' or lower(opath) like '%escalat%' or lower(opath) like '%wave%') group by opath")]
    cues = [OD([('cue', o), ('cooked_bytes', s), ('waves_total_with_file', cue_files(o))]) for o, s in INV.execute(
        "select opath, max(serial_size) from exports where class='SoundCue' and (lower(opath) like '%surviv%' or lower(opath) like '%escalat%' "
        "or lower(opath) like '%wave_start%' or lower(opath) like '%wave_end%' or lower(opath) like '%round_begin%' or lower(opath) like '%round_end%' "
        "or lower(opath) like '%roundstart%' or lower(opath) like '%roundend%') group by opath")]
    out = OD([('generated_by', 'AssetTools/work/escalation_roster/roster.py'), ('templates', rows), ('hud_gfx', gfx), ('mode_cues', cues)])
    json.dump(out, open(os.path.join(HERE, 'roster.json'), 'w', encoding='utf-8'), indent=1)
    allfx = {f['template'] for r in rows for f in r.get('fx_templates') or []}
    allcue = {c['cue']: c['waves_total_with_file'] for r in rows for c in r.get('sound_cues') or []}
    print('distinct FX', len(allfx), 'in MP render data', len(allfx & RENDER_FX), '| distinct cues', len(allcue),
          'waves', sum(t for t, h in allcue.values()), 'with file', sum(h for t, h in allcue.values()))
    print('FX not in MP render data:', sorted(allfx - RENDER_FX))
    for r in rows:
        if not r.get('chassis'): print('NO DATA', r['template']); continue
        rm = r['robot_mesh'] or {}; vm = r['vehicle_mesh'] or {}
        an = r['anim_sets']; an_ex = sum(1 for a in an if a and a['extracted'])
        print('%-48s mesh %s ext=%s ours=%s | veh %s ext=%s | anims %d/%d ext | weapons %s | fx %d cues %d' % (
            r['template'].split('.')[-1], (rm.get('object') or '-').split('.')[-1], bool(rm.get('extracted')), rm.get('used_by_our_characters'),
            (vm.get('object') or '-').split('.')[-1], bool(vm.get('extracted')) if vm else None, an_ex, len(an),
            [(w['class'].split('.')[-1], w['our_weapon_export']) for w in r['weapon_classes']], len(r['fx_templates']), len(r['sound_cues'])))
    print('HUD gfx', [(g['object'], bool(g['extracted'])) for g in gfx]); print('mode cues', [(c['cue'], c['waves_total_with_file']) for c in cues][:20])

if __name__ == '__main__':
    main()
