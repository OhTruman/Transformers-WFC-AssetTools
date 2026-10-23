"""Campaign spawnable destructibles (Gameplay 2026-10-23: D5's TnActorFactoryOmegaBatteryDestructible x 4, plus the Cybertron batteries).
Per HmDestructibleBlueprint a pawn factory spawns (roster.json destructible_blueprints): the blueprint decoded the way the MP / Streets
exporter decodes placed destructibles (scripts/wfc/vs_destructibles.py helpers, that file unchanged): pieces -> states (handle, StateName,
InitialHealth, AutomaticTransitionTime) -> effect factories (class, authored + effective values; meshes with cooked sections + glTF,
particle systems decoded, sound cues) and links (NextStateHandle, Enabled, TransitionTrigger + meaning) -> the state graph; plus every
factory that spawns it (action, sublevel, factory class / NewActorClass / authored props, spawn points with class + location, fired_by).
Read only -> out/campaign_characters/destructibles/<blueprint name>.json + index.json.
"""
import json, os, sqlite3, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, os.path.join(AT, 'work', 'campaign_render'))
_argv = sys.argv; sys.argv = [_argv[0]]            # vs_destructibles resolves its map at import: keep its default, it is not run
import vs_destructibles as VD  # noqa: E402
sys.argv = _argv
import authored as A  # noqa: E402
from m03_common import field  # noqa: E402
import campaign_render as CR  # noqa: E402
INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
OUT = os.path.join(AT, 'out', 'campaign_characters', 'destructibles')

def cooked_pkg(o, prefer):
    own = [r[0] for r in INV.execute('select distinct package from exports where opath=?', (o,)).fetchall()]
    return next((p for p in prefer if p in own), own[0] if own else None)

def blueprint(bp, levels):
    bpv = ((A.get(bp) or {}).get('props') or {})
    prefer = list(levels) + [bp.split('.')[0]]
    meshes, particles, cues, pieces = {}, {}, {}, []
    for pb in bpv.get('PieceBlueprints') or []:
        pv = ((A.get(pb) or {}).get('props') or {}); states = []
        for h, sb in enumerate(pv.get('StateBlueprints') or []):
            sv = ((A.get(sb) or {}).get('props') or {})
            st = OD([('handle', h), ('object', sb), ('StateName', field(sb, 'StateName')), ('InitialHealth', field(sb, 'InitialHealth', default=0)),
                     ('AutomaticTransitionTime', field(sb, 'AutomaticTransitionTime', default=0.0)), ('effects', []), ('links', [])])
            for ef in sv.get('EffectFactories') or []:
                er = A.get(ef) or {}; ev = er.get('props') or {}
                e = OD([('object', ef), ('class', er.get('class')), ('authored', ev),
                        ('effective', {k: v for k, v in A.values(ef).items() if k not in ('ComponentTemplates',)})])
                m = ev.get('Mesh') or ev.get('MeshTemplate')
                if m and m not in meshes:
                    pk = cooked_pkg(m, prefer)
                    try: meshes[m] = VD.mesh_rec(m, pk) if pk else {'mesh': m, 'cooked_in': None, 'gltf': VD.gltf(m)}
                    except Exception as x: meshes[m] = {'mesh': m, 'cooked_in': pk, 'gltf': VD.gltf(m), 'sections_error': repr(x)[:200]}
                if ev.get('Template') and ev['Template'] not in particles:
                    try: particles[ev['Template']] = VD.particle_rec(ev['Template'], prefer)
                    except Exception as x: particles[ev['Template']] = {'particle_system': ev['Template'], 'error': repr(x)[:200]}
                if ev.get('Cue') and ev['Cue'] not in cues: cues[ev['Cue']] = A.cue(ev['Cue'])
                st['effects'].append(e)
            for lk in sv.get('LinkBlueprints') or []:
                lv = A.values(lk)
                st['links'].append(OD([('object', lk), ('NextStateHandle', lv.get('NextStateHandle')), ('Enabled', field(lk, 'Enabled')),
                                       ('TransitionTrigger', lv.get('TransitionTrigger')),
                                       ('trigger_meaning (class name)', VD.TRIGGER_MEANING.get(lv.get('TransitionTrigger')))]))
            states.append(st)
        pieces.append(OD([('object', pb), ('PieceName', pv.get('PieceName')), ('Transform', pv.get('Transform')), ('states', states)]))
    edges = [OD([('piece', pc['PieceName']), ('from_handle', st['handle']), ('to_handle', lk['NextStateHandle']), ('trigger', lk['TransitionTrigger']),
                 ('enabled', (lk['Enabled'] or {}).get('value'))]) for pc in pieces for st in pc['states'] for lk in st['links']]
    return OD([('blueprint', bp), ('class', (A.get(bp) or {}).get('class')), ('BlueprintVersion', bpv.get('BlueprintVersion')),
               ('blueprint_defaults (inherited)', {k: field(bp, k) for k in ('DamageAngle', 'AIDamageModifier', 'RadiusDamageModifier',
                                                                             'MinRadiusDamageDistanceForModifier')}),
               ('pieces', pieces),
               ('state_graph', OD([('edges', edges), ('initial_state', OD([('value', 0), ('note', 'handle 0 = first StateBlueprints entry '
                                   '(HmDestructibleComponent convention, as for the MP destructibles; native confirmation pending)')]))])),
               ('meshes', meshes), ('particle_systems', particles), ('sound_cues', cues)])

def main():
    os.makedirs(OUT, exist_ok=True)
    R = json.load(open(os.path.join(HERE, 'roster.json'), encoding='utf-8'))
    idx = OD()
    for b in R['destructible_blueprints']:
        bp = b['blueprint']; facs = []; levels = []
        for ch in b['chapters']:
            lv = CR.chapter_levels(ch); levels += [l for l in lv if l not in levels]
            for f in json.load(open(os.path.join(AT, 'manifests', 'next_map', ch + '_pawn_factories.json'), encoding='utf-8'))['pawn_factories']:
                if (f.get('factory') or {}).get('Blueprint') == bp:
                    fo = (f['factory'] or {}).get('object')
                    facs.append(OD([('chapter', ch), ('action', f.get('action')), ('sublevel', f.get('sublevel')), ('sequence', f.get('sequence')),
                                    ('factory', f.get('factory')), ('factory_authored', ((A.get(fo) or {}).get('props') or {}) if fo else None),
                                    ('spawn_points', f.get('spawn_points')), ('spawn_count', f.get('spawn_count')),
                                    ('max_spawned_in_world', f.get('max_spawned_in_world')), ('spawn_delay', f.get('spawn_delay')),
                                    ('destroy_spawned_on_stream_out', f.get('destroy_spawned_on_stream_out')),
                                    ('fired_by_direct', f.get('fired_by_direct')), ('fired_by_events', f.get('fired_by_events')),
                                    ('outputs', f.get('outputs')), ('spawned_variable', f.get('spawned_variable'))]))
        rec = blueprint(bp, levels)
        rec = OD([('generated_by', 'AssetTools/work/campaign_characters/campaign_destructibles.py'),
                  ('source', 'manifests/authored.db + cooked StaticMesh sections + compiled particle streams (vs_destructibles helpers)'),
                  ('factory_class', b['factory_class']), ('actor_class', b['actor_class']), ('chapters', b['chapters'])] + list(rec.items())
                 + [('factories', facs)])
        name = bp.split('.')[-1]
        json.dump(rec, open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8'), indent=1, default=str)
        idx[name] = OD([('blueprint', bp), ('file', 'out/campaign_characters/destructibles/%s.json' % name), ('chapters', b['chapters']),
                        ('factories', len(facs)), ('states', [(s['handle'], (s['StateName'] or {}).get('value'), (s['InitialHealth'] or {}).get('value'),
                                                              (s['AutomaticTransitionTime'] or {}).get('value'), len(s['effects']), len(s['links']))
                                                             for p in rec['pieces'] for s in p['states']]),
                        ('meshes', {m: v.get('gltf') for m, v in rec['meshes'].items()})])
        print(name, json.dumps(idx[name]['states'])[:400], '| meshes', len(rec['meshes']), 'ps', len(rec['particle_systems']), 'cues', len(rec['sound_cues']))
    json.dump(OD([('generated_by', 'AssetTools/work/campaign_characters/campaign_destructibles.py'), ('blueprints', idx)]),
              open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), indent=1, default=str)

if __name__ == '__main__':
    main()
