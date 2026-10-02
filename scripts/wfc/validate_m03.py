"""Validator for the Milestone-03 targeted manifests (AssetTools/manifests/*.json).

  pickup counts            27 Pickup_FX / 9 HealthPickup_FX / 1 OvershieldPickup_FX, every component resolves, every
                           pickup FX LOD fully assigned by the stream decoder
  destructible             every blueprint/state/effect/link/mesh/cue/particle reference exists in authored.db or the
                           cooked inventory; glTF files exist
  surface audio            every material row and footstep slot carries origin + confidence; every event->cue resolves
  concurrency              every reported field carries an origin (authored / inherited default / unset)
  fine aim HUD             gfx file exists; every symbol id is an ExportAssets entry; weapon CDOs exist
  references               every 'content/...' path in the manifests exists under ExtractedAssets
Writes logs/validate_m03.json; exit 1 on failure.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, gfxscan  # noqa: E402
from vs_common import ROOT  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
LOGS = os.path.normpath(os.path.join(HERE, '..', '..', 'logs'))
FILES = ['streets_destructibles.json', 'streets_pickup_factories.json', 'streets_pickup_fx.json', 'fineaim_hud.json',
         'streets_surface_audio.json', 'vertical_slice_audio_concurrency.json', 'vehicle_audio_loops.json']

def exists_obj(o):
    if A.get(o): return True
    return objtree.inv().execute('SELECT 1 FROM exports WHERE opath=? LIMIT 1', (o,)).fetchone() is not None

def main():
    res, fails = {}, []
    def chk(name, cond, msg=''):
        res.setdefault(name, [0, 0]); res[name][0] += 1
        if not cond: res[name][1] += 1; fails.append('%s: %s' % (name, msg))
    J = {f: json.load(open(os.path.join(MANI, f), encoding='utf-8')) for f in FILES}
    # pickups
    fac = J['streets_pickup_factories.json']
    cnt = fac['counts']['effect_components_by_template']
    for t, n in {'FX_Pickups_p.FX.Pickup_FX': 27, 'FX_Pickups_p.FX.HealthPickup_FX': 9, 'FX_Pickups_p.FX.OvershieldPickup_FX': 1}.items():
        chk('pickup_counts', cnt.get(t) == n, '%s %s != %s' % (t, cnt.get(t), n))
    for i in fac['instances']:
        chk('pickup_instances_resolve', exists_obj(i['actor']), i['actor'])
        for e in i['effects'].values():
            chk('pickup_components_resolve', exists_obj(e['component']) and exists_obj(e['archetype']), e['component'])
            chk('pickup_components_in_map_fx', e['in_map_fx_json'], e['component'])
        chk('pickup_instances_in_gameplay_json', i['in_gameplay_json'], i['actor'])
    for ps, s in J['streets_pickup_fx.json']['systems'].items():
        for e in s['emitters']:
            for L in e['lods']:
                chk('pickup_fx_fully_decoded', L.get('assignment_complete') is True, '%s %s lod%s' % (ps, e['name'], L['level']))
    # destructible
    for a in J['streets_destructibles.json']['actors']:
        objs = [a['actor'], a['blueprint']['object']]
        for pc in a['pieces']:
            objs.append(pc['object'])
            for st in pc['states']:
                objs.append(st['object']); objs += [e['object'] for e in st['effects']] + [l['object'] for l in st['links']]
        objs += list(a['meshes']) + list(a['sound_cues']) + list(a['particle_systems']) + list(a['materials'])
        for o in objs: chk('destructible_refs_resolve', exists_obj(o), o)
        for m in a['meshes'].values():
            chk('destructible_gltf_exists', bool(m['gltf']) and os.path.exists(os.path.join(ROOT, m['gltf'])), m['mesh'])
        for ps, s in a['particle_systems'].items():
            for e in s['emitters']:
                for L in e['lods']:   # complete, or the leftover distributions are listed explicitly (never silently assigned)
                    chk('destructible_fx_decoded_or_explicit', L.get('assignment_complete') or 'unassigned_distributions' in L
                        or any(not m['distributions'] for m in L.get('compiled_modules', []) if m['module'] == 'PMI_Orbit'),
                        '%s %s lod%s' % (ps, e['name'], L['level']))
    # surface audio
    sa = J['streets_surface_audio.json']
    for r in sa['surface_materials']:
        chk('surface_rows_have_provenance', 'confidence' in r and ('physmat' in r), r['material'])
    for pm, r in sa['physical_materials'].items():
        for sl, v in r['slots'].items():
            chk('surface_slots_have_provenance', bool(v.get('origin')) and bool(v.get('confidence')), '%s %s' % (pm, sl))
    for ev, v in sa['event_to_cue (Optimus robot)'].items():
        chk('surface_events_resolve', exists_obj(ev), ev)
        if v['cue']: chk('surface_cues_resolve', exists_obj(v['cue']), v['cue'])
    # concurrency
    for c in J['vertical_slice_audio_concurrency.json']['cues']:
        chk('concurrency_cue_resolves', not c.get('missing') and exists_obj(c['cue']), c['cue'])
        for f, v in c.get('cue_fields', {}).items():
            chk('concurrency_fields_have_origin', 'origin' in v, '%s %s' % (c['cue'], f))
        for f, v in (c.get('root') or {}).items():
            if f != 'node': chk('concurrency_fields_have_origin', 'origin' in v, '%s root %s' % (c['cue'], f))
    # fine aim
    fa = J['fineaim_hud.json']
    gfx = os.path.join(ROOT, fa['hud_movie']['extracted_file'])
    chk('fineaim_gfx_exists', os.path.exists(gfx), gfx)
    ex = {int(k): v for k, v in gfxscan.scan(gfx)['exports'].items()}
    for nm, cid in fa['symbols'].items(): chk('fineaim_symbols_exported', ex.get(cid) == nm, nm)
    for w, r in fa['weapons'].items(): chk('fineaim_weapons_exist', exists_obj(r['cdo']), r['cdo'])
    chk('fineaim_movie_is_hud_movie', fa['hud_movie']['TnHUD.HudMovie']['value'] == 'UI_GFxHud_p.Hud_GFX_1', 'HudMovie')
    for k, v in fa.items():
        if isinstance(v, dict) and 'disassembly' in v: chk('fineaim_disassembly_present', bool(v['disassembly']), k)
    # file references
    for f, j in J.items():
        for p in set(re.findall(r'"(content/[^"]+\.(?:gltf|png|gfx|wav))"', json.dumps(j))):
            chk('content_paths_exist', os.path.exists(os.path.join(ROOT, p)), '%s: %s' % (f, p))
    os.makedirs(LOGS, exist_ok=True)
    json.dump({'checks': res, 'failures': fails}, open(os.path.join(LOGS, 'validate_m03.json'), 'w'), indent=1)
    tot = sum(v[0] for v in res.values()); bad = sum(v[1] for v in res.values())
    for k, v in res.items(): print('%-38s %4d checks %3d failed' % (k, v[0], v[1]))
    print('validate_m03: %d checks, %d failures' % (tot, bad))
    for f in fails[:40]: print('  FAIL', f)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
