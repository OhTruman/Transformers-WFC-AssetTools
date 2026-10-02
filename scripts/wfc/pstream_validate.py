"""Cross-check pstream.assign() against surviving TAGGED module exports.

Some cooked packages keep a few ParticleModule exports with full tagged distributions (LookupTable) next to
the compiled LOD stream. For every such export, its ParticleSystem's LOD streams must contain an assigned
entry (same module, same property) with identical values. Any tagged property that only matches a stream
entry assigned to a DIFFERENT property/module counts as a contradiction.

  python pstream_validate.py [package ...]   -> prints totals, writes logs/pstream_validate.json
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, typed_props as tp, pstream as PS  # noqa: E402

CLS2PMI = {'ParticleModuleLifetime': 'PMI_Lifetime', 'ParticleModuleColor': 'PMI_Color', 'ParticleModuleVelocity': 'PMI_Velocity',
           'ParticleModuleRotation': 'PMI_Rotation', 'ParticleModuleSizeMultiplyLife': 'PMI_SizeMultiplyLife',
           'ParticleModuleLocation': 'PMI_Location', 'ParticleModuleLocationPrimitiveCylinder': 'PMI_LocationPrimitiveCylinder',
           'ParticleModuleColorOverLife': 'PMI_ColorOverLife', 'ParticleModuleSize': 'PMI_Size'}

def _vals(v):
    return [round(x, 4) for x in (v.get('LookupTable') or [])] if isinstance(v, dict) else None

def run(pkg):
    p = objtree.package(pkg)
    stats = Counter(); detail = []
    by_ps = {}
    for k, i in p._idx.items():
        c = p.class_name(p.exports[i - 1])
        if c == 'ParticleLODLevel':
            by_ps.setdefault(k.rsplit('.', 2)[0], []).append(i)
    for k, i in p._idx.items():
        c = p.class_name(p.exports[i - 1])
        if c not in CLS2PMI: continue
        ps = k.rsplit('.', 1)[0]
        if ps not in by_ps: continue
        d = tp.simplify(p._tr.read_dict(i))
        entries = []
        for li in by_ps[ps]:
            try:
                a = PS.assign(PS.parse(PS.lod_tail(p, li)))
            except Exception:
                continue
            entries += a['float'] + a['vector']
        for prop, v in d.items():
            tv = _vals(v)
            if not tv: continue
            same = [e for e in entries if e['module'] == CLS2PMI[c] and e['property'] == prop
                    and [round(x, 4) for x in e['dist']['values']] == tv]
            other = [e for e in entries if [round(x, 4) for x in e['dist']['values']] == tv
                     and not (e['module'] == CLS2PMI[c] and e['property'] == prop)]
            cand = [e for e in entries if e['module'] == CLS2PMI[c] and prop in (e.get('property_candidates') or [])
                    and [round(x, 4) for x in e['dist']['values']] == tv]
            key = 'match' if same else ('candidate_match' if cand else ('contradiction' if other else 'absent'))
            stats[(c, prop, key)] += 1
            if key in ('contradiction', 'candidate_match'):
                detail.append({'pkg': pkg, 'module': k, 'prop': prop, 'values': tv[:8], 'result': key,
                               'stream_entries': [(e['module'], e['property'], e.get('property_candidates')) for e in (cand or other)][:4]})
    return stats, detail

if __name__ == '__main__':
    pkgs = sys.argv[1:] or ['A1_IAC_Base_m', 'A2_KON_BASE_m', 'D3A_IAC_Sentinel_DESIGN_m', 'A2_KON_Jailbreak_Vig_m',
                            'A2_KON_DRIVE3_Trans_Art_m', 'A1_IAC_DecoFoyer_Design_m']
    tot = Counter(); det = []
    for pk in pkgs:
        s, d = run(pk); tot.update(s); det += d
    for k, v in sorted(tot.items()): print(k, v)
    out = os.path.join(HERE, '..', '..', 'logs', 'pstream_validate.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'packages': pkgs, 'stats': {'|'.join(k): v for k, v in tot.items()}, 'detail': det}, open(out, 'w'), indent=1)
    print('->', os.path.normpath(out))
