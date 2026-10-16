import sys, json, sqlite3, importlib.util, collections, os
sys.path.insert(0, 'scripts/wfc')
def load(path, name):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
old = load(sys.argv[1], 'pstream_old'); new = load('scripts/wfc/pstream.py', 'pstream_new')
c = sqlite3.connect('manifests/inventory.db')
role = {p: r for p, r in c.execute('select package, role from packages')}
sysmap = {}
for p, op in c.execute("select package, opath from exports where class='ParticleSystem'"):
    if 'multiplayer map' in role.get(p, ''): sysmap.setdefault(op, p)
stats = collections.Counter(); gained = []; other_diff = []; orbit_lods = 0; orbit_complete = 0; example = None
for ps, pk in sorted(sysmap.items()):
    try: a = old.system(ps, pk); b = new.system(ps, pk)
    except Exception as ex: stats['decode error'] += 1; continue
    stats['systems'] += 1
    for ea, eb in zip(a.get('emitters', []), b.get('emitters', [])):
        for la, lb in zip(ea['lods'], eb['lods']):
            stats['lods'] += 1
            J = lambda o: json.dumps(o, sort_keys=True)
            if J(la) == J(lb): stats['lods identical'] += 1; continue
            def nov(L):
                L = json.loads(J(L))
                for m in L.get('compiled_modules', []): m.pop('props', None) if m['module'] == 'PMI_VelocityOverLife' else None
                return J(L)
            if nov(la) == nov(lb): stats['lods changed: only props.Absolute added to VelocityOverLife'] += 1; continue
            ma = {m['index']: m for m in la.get('compiled_modules', [])}; mb = {m['index']: m for m in lb.get('compiled_modules', [])}
            has_orbit = any(m['module'] == 'PMI_Orbit' for m in mb.values())
            orbit_lods += has_orbit; orbit_complete += bool(has_orbit and lb.get('assignment_complete'))
            # what changed: allowed = VoL props, Orbit/later modules gaining distributions, assignment_complete, unassigned list
            for i, m in mb.items():
                x = ma.get(i)
                if m['module'] == 'PMI_VelocityOverLife' and any(d['property'] == 'VelOverLife' for d in m['distributions']) \
                        and not any(d['property'] == 'VelOverLife' for d in x['distributions']):
                    gained.append({'system': ps, 'emitter': eb.get('name'), 'lod': lb.get('level'), 'VelOverLife': next(d for d in m['distributions'] if d['property'] == 'VelOverLife')})
                    if ps.endswith('Squib_HomRocket_01_FX') and eb.get('name') == 'Embers_Dup_Dup' and lb.get('level') in (0, None):
                        example = {'before': x, 'after': m}
                strip = lambda mm: {k: v for k, v in mm.items() if k not in ('distributions', 'props')}
                if J(strip(m)) != J(strip(x)): other_diff.append((ps, eb.get('name'), i, 'module fields'))
                elif J(m['distributions']) != J(x['distributions']) and x['distributions']:
                    other_diff.append((ps, eb.get('name'), i, 'existing distributions changed'))
            ka = {k: v for k, v in la.items() if k not in ('compiled_modules', 'assignment_complete', 'unassigned_distributions')}
            kb = {k: v for k, v in lb.items() if k not in ('compiled_modules', 'assignment_complete', 'unassigned_distributions')}
            if J(ka) != J(kb): other_diff.append((ps, eb.get('name'), None, 'lod fields'))
            stats['lods changed: Orbit assignment (curves added to modules after Orbit)'] += 1
vol_props_only = 0
out = {'generated_by': 'scratchpad vol_proof.py (old vs new scripts/wfc/pstream.py)', 'scope': 'every ParticleSystem exported by an MP map package (inventory.db)',
       'stats': dict(stats), 'orbit_lods': orbit_lods, 'orbit_lods_now_complete': orbit_complete,
       'emitter_lods_gaining_VelOverLife': len(gained), 'emitters_gaining_VelOverLife': len({(g['system'], g['emitter']) for g in gained}),
       'systems_gaining': sorted({g['system'] for g in gained}), 'unexpected_changes': other_diff, 'example_Squib_HomRocket_01_FX_Embers_Dup_Dup': example, 'gained': gained}
json.dump(out, open('work/fx_vol/vol_before_after.json', 'w'), indent=1)
print({k: v for k, v in out.items() if k in ('stats', 'orbit_lods', 'orbit_lods_now_complete', 'emitter_lods_gaining_VelOverLife', 'emitters_gaining_VelOverLife', 'systems_gaining')})
print('unexpected', len(other_diff), other_diff[:5])
