"""Independent review (AssetTools, 2026-10-18; Integration's data-switch rule): integration's live Rebuild/work/render/<map>/materials_glsl.json
vs Rebuild-Systems/work/matB/render/<map>/materials_glsl.json, entry by entry, read-only on both trees. A changed entry is "confined to the
vector-channel pattern" when every changed line equals the live one after normalising: declared type vecN <-> float, broadcasts vecN(x) of a
variable or literal, channel / swizzle extraction (tK).c..., and channel selection (vecN(...)).c; and its info differs only in type_violations.
  python review.py -> materials_glsl_diff.json"""
import json, re, os
R = r'F:\Transformers Rebuild'; HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten', 'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
TYPE = re.compile(r'^(\s*)(?:vec[234]|float) (t\d+) = ')
BCAST = re.compile(r'vec[234]\((t\d+|-?\d+(?:\.\d+)?(?:e-?\d+)?)\)'); CH = re.compile(r'\((t\d+)\)\.[xyzwrgba]{1,4}(?![a-z])')
SEL = re.compile(r'^\((vec[234]\(.*\))\)\.[xyzwrgba];$')
def norm(l):
    m = TYPE.match(l)
    if m: l = m.group(1) + m.group(2) + ' = ' + l[m.end():]
    l = BCAST.sub(r'\1', l); l = CH.sub(r'\1', l)
    head, sep, rhs = l.partition(' = ')
    s = SEL.match(rhs)
    if s: rhs = s.group(1) + ';'
    return head + sep + rhs
per = {}; dch, dad, drm = set(), set(), set(); tv = {}
for mp in MAPS:
    a = json.load(open(R + r'\Rebuild\work\render\%s\materials_glsl.json' % mp, encoding='utf-8'))
    b = json.load(open(R + r'\Rebuild-Systems\work\matB\render\%s\materials_glsl.json' % mp, encoding='utf-8'))
    ch = sorted(k for k in a if k in b and a[k] != b[k]); ad = sorted(set(b) - set(a)); rm = sorted(set(a) - set(b))
    dch |= set(ch); dad |= set(ad); drm |= set(rm); conf, notc = [], []
    for k in ch:
        la, lb = a[k]['glsl'].splitlines(), b[k]['glsl'].splitlines()
        ia, ib = a[k].get('info') or {}, b[k].get('info') or {}
        others = sorted(x for x in set(ia) | set(ib) if x != 'type_violations' and ia.get(x) != ib.get(x))
        ok = len(la) == len(lb) and all(x == y or norm(x) == norm(y) for x, y in zip(la, lb)) and not others
        d = ia.get('type_violations', 0) - ib.get('type_violations', 0) if isinstance(ia.get('type_violations'), int) and isinstance(ib.get('type_violations'), int) else None
        tv[str(d)] = tv.get(str(d), 0) + 1
        if ok: conf.append(k)
        else:
            notc.append({'entry': k, 'other_info_keys_changed': others, 'lines_live': len(la), 'lines_candidate': len(lb),
                         'first_unexplained_diff': next(((x, y) for x, y in zip(la, lb) if x != y and norm(x) != norm(y)), None)})
    per[mp] = {'changed': ch, 'n_changed': len(ch), 'confined_to_pattern': len(conf), 'not_confined': notc, 'added': ad, 'removed': rm}
tot = {'changed_entry_map_pairs': sum(p['n_changed'] for p in per.values()), 'confined': sum(p['confined_to_pattern'] for p in per.values()),
       'not_confined': sum(len(p['not_confined']) for p in per.values()), 'distinct_changed': len(dch), 'distinct_added': len(dad),
       'distinct_removed': len(drm), 'distinct_total_changed_plus_added': len(dch) + len(dad),
       'distinct_not_confined': sorted({x['entry'] for p in per.values() for x in p['not_confined']}),
       'type_violations_delta_live_minus_candidate': tv}
json.dump({'generated_by': 'AssetTools work/matB_review/review.py (independent review)', 'pattern_rule': __doc__.split('A changed entry is ')[1],
           'totals': tot, 'distinct_changed': sorted(dch), 'distinct_added': sorted(dad), 'distinct_removed': sorted(drm), 'per_map': per},
          open(os.path.join(HERE, 'materials_glsl_diff.json'), 'w', encoding='utf-8'), indent=1)
print(json.dumps(tot)); print({m: (p['n_changed'], p['confined_to_pattern'], len(p['not_confined'])) for m, p in per.items()})
