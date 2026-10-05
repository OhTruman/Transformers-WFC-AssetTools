"""Reference validator for manifests/mp_content (mp_roster.py, mp_handoffs.py). Writes logs/validate_mp_content.json; exit 1 on failure.

  paths        every content/... path string exists
  ue_objects   every dotted object path whose first segment is a cooked package exists (inventory.db / authored.db)
  roster       every MP chassis (in all MP maps) has robot + vehicle definitions, meshes with extracted glTF, resolved material
               slots, a portrait symbol, a default class among the 4 specialties
  weapons      every weapon in every MP map has a class default; meshes resolve or carry an explicit absence note
  animation    every MP character's robot anim sets are compatible or partial (partial listed), none incompatible
  bundles      bundle files exist
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import ROOT  # noqa: E402
from validate_frontend_package import strings, OBJ_RX, PATH_RX  # noqa: E402

D = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests', 'mp_content'))
LOGS = os.path.normpath(os.path.join(HERE, '..', '..', 'logs'))

def main():
    res, fails = {}, []
    def chk(n, c, m=''):
        res.setdefault(n, [0, 0]); res[n][0] += 1
        if not c: res[n][1] += 1; fails.append('%s: %s' % (n, m))
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(D) for f in fs if f.endswith('.json')]
    inv = objtree.inv()
    pk = {r[0].lower() for r in inv.execute('SELECT package FROM packages')} | {'transgame', 'transcontent', 'engine', 'core', 'gfxui', 'hm_engine'}
    seen = set()
    for f in files:
        for s in strings(json.load(open(f, encoding='utf-8'))):
            if s in seen: continue
            seen.add(s)
            if PATH_RX.match(s): chk('paths', os.path.exists(os.path.join(ROOT, s)), s)
            elif OBJ_RX.match(s) and s.split('.')[0].lower() in pk and not re.search(r'\.(swf|gfx|mkv|png|tga)$', s):
                ok = inv.execute('SELECT 1 FROM exports WHERE opath=? LIMIT 1', (s,)).fetchone() is not None or A.get(s) is not None
                if not ok:   # UE3 object names are case-insensitive; config ObjectPaths sometimes differ in case from the cooked name
                    ok = inv.execute('SELECT 1 FROM exports WHERE opath=? COLLATE NOCASE LIMIT 1', (s,)).fetchone() is not None
                chk('ue_objects', ok, s)
    C = json.load(open(os.path.join(D, 'mp_characters.json'), encoding='utf-8'))
    S = json.load(open(os.path.join(D, 'character_select_ui.json'), encoding='utf-8'))['per_character']
    for c in C['characters']:
        if not c['in_all_mp_maps']: continue
        cid = c['chassis_id']
        for form in ('robot', 'vehicle'):
            f = c[form] or {}
            chk('roster', bool(f.get('definition')) and bool(f.get('gltf')), '%s %s mesh' % (cid, form))
            chk('roster', all(x['material'] for x in f.get('material_slots (umodel short names resolved within the mesh package family - HIGH)', [])), '%s %s materials' % (cid, form))
        chk('roster', c['default_class'] in ('Scout', 'Scientist', 'Soldier', 'Leader'), cid + ' class')
        chk('roster', bool((S[cid].get('robot_portrait') or {}).get('symbol')), cid + ' portrait')
        chk('roster', c['cooked_copies']['consistent'], cid + ' cooked copies differ')
    W = json.load(open(os.path.join(D, 'mp_weapons.json'), encoding='utf-8'))['weapons']
    for cls, w in W.items():
        if not w['mp']['in_every_mp_map']: continue
        chk('weapons', A.get('%s.Default__%s' % tuple(cls.split('.', 1))) is not None, cls)
        chk('weapons', bool(w['mesh']['gltf']) or bool(w['mesh'].get('mesh_note')), cls + ' mesh')
    AC = json.load(open(os.path.join(D, 'mp_animation_compat.json'), encoding='utf-8'))['per_character']
    for c in C['characters']:
        if not c['in_all_mp_maps']: continue
        for a, r in AC[c['chassis_id']]['robot']['anim_sets'].items():
            chk('animation', r['status'] in ('compatible', 'partial'), '%s %s %s' % (c['chassis_id'], a, r['status']))
    for f in os.listdir(os.path.join(D, 'bundles')):
        b = json.load(open(os.path.join(D, 'bundles', f), encoding='utf-8'))
        chk('bundles', not b['validation']['missing_files'], f)
    # product-ready exports (vs_roster_export.py / vs_weapon_export.py): open every glb, check the recorded validation
    from vs_common import read_glb
    def glb_ok(rel_path, want_skin):
        j, _ = read_glb(os.path.join(ROOT, rel_path))
        return bool(j.get('meshes')) and (not want_skin or bool(j.get('skins'))), len(j.get('animations') or [])
    ci = os.path.join(D, 'character_export_index.json')
    if os.path.exists(ci):
        for cid, e in json.load(open(ci, encoding='utf-8'))['chassis'].items():
            chk('char_export', 'error' not in e, cid + ' exported')
            if 'error' in e: continue
            v = e['validation']
            chk('char_export', not v['missing'], cid + ' paths')
            for form in ('robot', 'vehicle'):
                g = e.get(form + '_glb')
                if not g: continue
                ok, n = glb_ok(g, True)
                chk('char_export', ok and n == e[form + '_clips'], '%s %s glb skin/clips %d' % (cid, form, n))
            m = json.load(open(os.path.join(ROOT, e['dir'], 'character.json'), encoding='utf-8'))
            # transform clips: every authored Transform_* clip on each form must be in that glb (Laserbeak: one bird mesh, no VEH set)
            single_mesh = (m.get('robot') or {}).get('mesh_object') == (m.get('vehicle') or {}).get('mesh_object')
            chk('char_export', v['transform_clips_present'] or single_mesh, cid + ' transform clips')
            chk('char_export', m['chassis_id'] == cid and bool(m.get('faction')) and bool(m.get('class (chassis DefaultSpecialty)')), cid + ' identity')
    wi = os.path.join(D, 'weapon_export_index.json')
    if os.path.exists(wi):
        for pid, e in json.load(open(wi, encoding='utf-8'))['weapons'].items():
            chk('wpn_export', 'error' not in e, pid + ' exported')
            if 'error' in e: continue
            chk('wpn_export', not e['validation']['missing'], pid + ' paths')
            if e.get('glb'):
                ok, n = glb_ok(e['glb'], False)
                chk('wpn_export', ok and n == e['validation']['clips'], '%s glb clips %d' % (pid, n))
            else:
                chk('wpn_export', bool(e.get('mesh_note')), pid + ' no mesh: CONFIRMED absence note')
    os.makedirs(LOGS, exist_ok=True)
    json.dump({'checks': res, 'failures': fails}, open(os.path.join(LOGS, 'validate_mp_content.json'), 'w'), indent=1)
    for k, v in res.items(): print('%-11s %6d checks %4d failed' % (k, v[0], v[1]))
    bad = sum(v[1] for v in res.values())
    print('validate_mp_content: %d checks, %d failures' % (sum(v[0] for v in res.values()), bad))
    for f in fails[:40]: print('  FAIL', f)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
