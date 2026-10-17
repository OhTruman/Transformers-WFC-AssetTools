"""Trail2 particle templates for Rendering's Trail2 item (Integration 2026-10-18).

For every ParticleSystem with a ParticleModuleTypeDataTrail2 emitter: per emitter and LOD the type-data fields (authored values over the
Engine class defaults), the RequiredModule (material, spawn), the compiled modules with their distributions (pstream), and the body
notifies that attach the template to pawn / weapon sockets (Integration's merged Rebuild/src/game/AnimNotifies.inc + MeshSockets.inc).
MP scope: templates referenced by the MP per-map FX sets, MP weapons / characters, the TR_* / WEP_* notifies or TransGame CDOs.
Read-only. Writes manifests/particles/trail2_templates.json.
"""
import glob, json, os, re, sqlite3, sys
from collections import OrderedDict as OD, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pstream  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
EA = os.path.join(TR, 'ExtractedAssets'); RB = os.path.join(TR, 'Rebuild')
OUT = os.path.join(ROOT, 'manifests', 'particles', 'trail2_templates.json')
MP_MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
           'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))

# TypeDataTrail2 schema (cooked class) with the Engine class default; a field the CDO does not set is the type's zero value
TD_SCHEMA = json.loads(DB.execute("select props from types where path='Engine.ParticleModuleTypeDataTrail2'").fetchone()[0])
TD_DEFAULT = json.loads(DB.execute("select props from objects where opath='Engine.Default__ParticleModuleTypeDataTrail2'").fetchone()[0])
ZERO = {'IntProperty': 0, 'FloatProperty': 0.0, 'BoolProperty': False}

def td_fields(props):
    out, src = OD(), OD()
    for k in sorted(TD_SCHEMA):
        if k in (props or {}): out[k] = props[k]; src[k] = 'authored'
        elif k in TD_DEFAULT: out[k] = TD_DEFAULT[k]; src[k] = 'Engine.Default__ParticleModuleTypeDataTrail2'
        elif TD_SCHEMA[k]['type'] in ZERO: out[k] = ZERO[TD_SCHEMA[k]['type']]; src[k] = 'type zero (not set by CDO)'
        else: out[k] = None; src[k] = 'struct, not set'
    return out, src

def strings(o, acc):
    if isinstance(o, dict):
        for v in o.values(): strings(v, acc)
    elif isinstance(o, list):
        for v in o: strings(v, acc)
    elif isinstance(o, str): acc.add(o)

def load_inc(path, rx):
    return [m.groups() for m in re.finditer(rx, open(path, encoding='utf-8').read())]

def main():
    # trail templates = owners of every TypeDataTrail2 export
    tds = [r[0] for r in INV.execute("select distinct opath from exports where class='ParticleModuleTypeDataTrail2' and opath not like 'Engine.Default__%'")]
    templates = sorted({t.rsplit('.', 1)[0] for t in tds})
    # MP references
    uses = defaultdict(set)
    for mp in MP_MAPS:
        f = os.path.join(RB, 'work', 'render', mp, 'map_fx_runtime.json')
        if os.path.exists(f):
            acc = set(); strings(json.load(open(f, encoding='utf-8')), acc)
            for s in acc: uses[s].add('map_fx_runtime:' + mp)
    for f in glob.glob(os.path.join(EA, 'VerticalSlice', 'Weapons', '*', 'weapon.json')):
        acc = set(); strings(json.load(open(f, encoding='utf-8')), acc)
        for s in acc: uses[s].add('weapon:' + os.path.basename(os.path.dirname(f)))
    for f in glob.glob(os.path.join(EA, 'VerticalSlice', 'Characters', '*', 'character.json')):
        d = json.load(open(f, encoding='utf-8'))
        if not str(d.get('mp_status') or '').startswith('MP character'): continue
        acc = set(); strings(d, acc)
        for s in acc: uses[s].add('character:' + os.path.basename(os.path.dirname(f)))
    for src, dst in DB.execute("select src, dst from refs where dst_class='ParticleSystem' and src like 'TransGame.%'"):
        uses[dst].add('TransGame CDO:' + src.split('.')[1])
    notifies = load_inc(os.path.join(RB, 'src', 'game', 'AnimNotifies.inc'),
                        r'\{"([^"]*)", "([^"]*)", ([0-9.]+)f, true, "([^"]*)", "([^"]*)", (\d+)\}')
    sockets = load_inc(os.path.join(RB, 'src', 'game', 'MeshSockets.inc'),
                       r'\{"([^"]*)", "([^"]*)", "([^"]*)", ([-0-9.]+)f, ([-0-9.]+)f, ([-0-9.]+)f, (-?\d+), (-?\d+), (-?\d+), ([-0-9.]+)f\}')
    sock_by_name = defaultdict(list)
    for mesh, sock, bone, x, y, z, p, yw, r, sc in sockets:
        sock_by_name[sock].append(OD([('mesh', mesh), ('bone', bone), ('offset_uu', [float(x), float(y), float(z)]),
                                     ('rotation_ue', [int(p), int(yw), int(r)]), ('scale', float(sc))]))
    for anim_set, seq, t, what, sock, fl in notifies: uses[what].add('anim_notify')

    out_t = []; used_sockets = set()
    for ps in templates:
        u = sorted(uses.get(ps, ()))
        s = pstream.system(ps)
        if s.get('missing_in'): out_t.append(OD([('template', ps), ('mp_referenced', bool(u)), ('error', 'not decodable: ' + str(s['missing_in']))])); continue
        ems = []
        for e in s['emitters']:
            lods = []
            for L in e['lods']:
                td = L.get('TypeDataModule') or {}
                if td.get('class') != 'ParticleModuleTypeDataTrail2': continue
                fields, src = td_fields(td.get('props'))
                mods = L.get('compiled_modules') or []
                partial = []
                if L.get('compiled_modules_error'): partial.append('compiled modules not parsed: ' + L['compiled_modules_error'])
                if not L.get('assignment_complete', False): partial.append('distribution assignment incomplete')
                nc = [(m['module'], d['property']) for m in mods for d in m['distributions'] if d.get('confidence') != 'CONFIRMED']
                if nc: partial.append('non-CONFIRMED distributions: %s' % nc)
                if (L.get('parameter_blob') or {}).get('status') not in (None, 'decoded'): partial.append('parameter blob: ' + str(L['parameter_blob'].get('status')))
                req = L.get('RequiredModule') or {}
                lods.append(OD([('lod', L['lod']), ('level', L.get('level')), ('lod_props', L.get('props')),
                                ('type_data', OD([('object', td.get('object')), ('fields', fields), ('field_source', src)])),
                                ('required_module', req),
                                ('material', (req.get('props') or {}).get('Material')),
                                ('compiled_modules', [OD([('module', m['module']), ('enabled', m.get('enabled (flagA; HIGH - particle_flag_census.json)')),
                                                          ('fields', m.get('fields')), ('props', m.get('props') or m.get('module_properties (authored, defaults filled)')),
                                                          ('distributions', [OD([('property', d['property']), ('kind', d['kind']), ('values', d['values']),
                                                                                 ('confidence', d['confidence'])]) for d in m['distributions']])]) for m in mods]),
                                ('status', 'PARTIAL' if partial else 'COMPLETE'), ('partial_reasons', partial)]))
            if lods:
                ems.append(OD([('emitter', e['emitter']), ('name', e.get('name')), ('emitter_props', e.get('props')), ('lods', lods)]))
        att = [OD([('anim_set', a), ('sequence', q), ('time_s', float(t)), ('socket', so), ('attach', fl == '1')])
               for a, q, t, w, so, fl in notifies if w == ps]
        used_sockets.update(x['socket'] for x in att)
        out_t.append(OD([('template', ps), ('package_decoded', s.get('package')), ('mp_referenced', bool(u)), ('referenced_by', u),
                         ('materials', s.get('materials')), ('system_props', s.get('props')),
                         ('trail2_emitters', ems), ('body_notify_attachments', att)]))
    mp = [t for t in out_t if t['mp_referenced']]
    m = OD([('generated_by', 'AssetTools/scripts/wfc/trail2_templates.py'),
            ('sources', ['manifests/inventory.db + authored.db', 'scripts/wfc/pstream.py (compiled modules)',
                         'Rebuild/work/render/<MP>/map_fx_runtime.json', 'ExtractedAssets/VerticalSlice/{Weapons,Characters}',
                         'Rebuild/src/game/AnimNotifies.inc + MeshSockets.inc (Integration merged, generated from authored.db)']),
            ('engine_facts', OD([
                ('trail_source_spawn_taper_modules', 'NOT PRESENT: the cooked EParticleModuleId enum has no trail / spawn-per-unit ids; '
                 'ParticleModuleTrailSource / TrailSpawn / SpawnPerUnit exist only as Engine class defaults (0 cooked instances), and '
                 'no ParticleModuleTrailTaper class exists in this engine. So no Trail2 emitter has source names / offsets / '
                 'inherit-rotation / spawn-per-unit / taper data: the trail follows the emitter (component) location, i.e. the notify '
                 'socket. CONFIRMED (cooked enum + class table).'),
                ('type_data_fields', sorted(TD_SCHEMA)),
                ('type_data_class_default', TD_DEFAULT)])),
            ('counts', OD([('trail_templates', len(out_t)), ('mp_referenced', len(mp)),
                           ('trail_emitters_mp', sum(len(t.get('trail2_emitters') or []) for t in mp)),
                           ('trail_lods_mp', sum(len(e['lods']) for t in mp for e in t.get('trail2_emitters') or [])),
                           ('partial_lods_mp', sum(1 for t in mp for e in t.get('trail2_emitters') or [] for L in e['lods'] if L['status'] == 'PARTIAL')),
                           ('partial_lods_all', sum(1 for t in out_t for e in t.get('trail2_emitters') or [] for L in e['lods'] if L['status'] == 'PARTIAL'))])),
            ('templates', out_t),
            ('sockets (every TR_ / WEP_ mesh defining each socket a trail notify uses; MeshSockets.inc)',
             OD((k, sock_by_name.get(k, [])) for k in sorted(used_sockets)))])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(m, open(OUT, 'w', encoding='utf-8'), indent=1)
    print(json.dumps(m['counts']))

if __name__ == '__main__':
    main()
