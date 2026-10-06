"""Per-chassis default EnergonColor (robot + vehicle mesh material) -> manifests/mp_content/energon_defaults.json

  python energon_defaults.py

Rule (RE b0d9b22, notes/TARGETED_PASS5_2026-10-06_energon.md (a)/(c), CONFIRMED script path):
  TnCharacterApplier.ExtractColors: Energon = CD.EnergonColor if it is not (0,0,0,1)/(0,0,0,0), else
  RobotMesh.GetVectorParam('EnergonColor'); MeshComponent.GetVectorParam walks material slots 0..N-1 (after component
  material overrides) and returns the first material (or MIC parent chain) that has the parameter. EnergonColor is never
  team-tinted: an uncustomised character uses exactly this material default; ApplyColorsToMesh then writes it to the meshes.
Lookup per material, as UE3 GetVectorParameterValue: MIC VectorParameterValues override -> Parent ... -> base Material's
MaterialExpressionVectorParameter('EnergonColor').DefaultValue (expressions of called material functions included).
Slots: the character export's resolved skeletal-mesh material slots (character.json robot / vehicle); MP pawns author no
component material overrides (only campaign cutscene SkeletalMeshActors do), so slot materials are final.
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
PARAM = 'EnergonColor'

def expr_default(mat, seen=None):
    """EnergonColor DefaultValue from a Material's expressions (incl. called material functions)"""
    seen = seen or set()
    if mat in seen: return None
    seen.add(mat)
    for (o, c) in A.con().execute("SELECT opath, class FROM objects WHERE opath LIKE ? AND class IN "
                                  "('MaterialExpressionVectorParameter','MaterialExpressionMaterialFunctionCall')", (mat + '.%',)).fetchall():
        v = A.values(o) or {}
        if c == 'MaterialExpressionVectorParameter' and v.get('ParameterName') == PARAM:
            return v.get('DefaultValue'), o
    for (o, c) in A.con().execute("SELECT opath, class FROM objects WHERE opath LIKE ? AND class = 'MaterialExpressionMaterialFunctionCall'",
                                  (mat + '.%',)).fetchall():
        fn = (A.values(o) or {}).get('MaterialFunction')
        if fn:
            r = expr_default(fn, seen)
            if r: return r
    return None

def lookup(mat):
    """(value, source object, chain) or None"""
    chain = []; cur = mat
    while cur and len(chain) < 12:
        chain.append(cur)
        row = A.get(cur); v = A.values(cur) or {}
        if not row: return None, None, chain
        for p in v.get('VectorParameterValues') or []:
            if p.get('ParameterName') == PARAM:
                return p.get('ParameterValue'), cur + '.VectorParameterValues', chain
        if row['class'] == 'Material':
            r = expr_default(cur)
            return (r[0], r[1], chain) if r else (None, None, chain)
        par = v.get('Parent'); cur = par.get('ref') if isinstance(par, dict) else par
    return None, None, chain

def form(rec):
    slots = rec.get('materials') or []
    out = OD([('mesh', rec.get('mesh_object')), ('slots', [])])
    for s in slots:
        m = s.get('material')
        val, src, chain = lookup(m) if m else (None, None, [])
        out['slots'].append(OD([('slot', s.get('slot')), ('material', m), ('EnergonColor', val), ('defined_at', src), ('chain', chain)]))
        if val is not None and 'EnergonColor' not in out:
            out['EnergonColor'] = val; out['from_slot'] = s.get('slot'); out['defined_at'] = src
    out.setdefault('EnergonColor', None)
    return out

def main():
    res = OD()
    for f in sorted(glob.glob(os.path.join(VS, 'Characters', '*', 'character.json'))):
        c = json.load(open(f, encoding='utf-8'))
        if not c.get('chassis_id') or not (c.get('robot') or {}).get('materials'): continue   # non-roster folders
        r = form(c.get('robot') or {}); v = form(c.get('vehicle') or {})
        res[c['chassis_id']] = OD([('iconic_id', c.get('iconic_id')), ('faction', c.get('faction')),
                                   ('energon_default', r['EnergonColor']),
                                   ('vehicle_differs', (v['EnergonColor'] is not None and v['EnergonColor'] != r['EnergonColor'])),
                                   ('robot', r), ('vehicle', v)])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/energon_defaults.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('rule', 'uncustomised character energon = first robot-mesh material slot (MIC chain) defining EnergonColor; never '
                       'team-tinted (RE b0d9b22 TARGETED_PASS5_2026-10-06_energon (a)/(c), CONFIRMED script path). '
                       'Team EnergonColor class defaults are used only by kamikaze-mine fallbacks.'),
              ('usage', 'energon_default = robot value, applied to robot AND vehicle meshes by ApplyColorsToMesh (vehicle FX / boost / '
                        'faction notifies read the same character colour); vehicle.* is the vehicle mesh own material default, for reference'),
              ('chassis', res),
              ('summary', OD([('chassis', len(res)), ('with_energon', sum(1 for x in res.values() if x['energon_default'])),
                              ('vehicle_material_differs', sorted(k for k, x in res.items() if x['vehicle_differs'])),
                              ('missing', sorted(k for k, x in res.items() if not x['energon_default']))]))])
    p = os.path.join(AT, 'manifests', 'mp_content', 'energon_defaults.json')
    json.dump(out, open(p, 'w', encoding='utf-8'), indent=1)
    for k, x in res.items():
        e = x['energon_default']
        print(k, x['iconic_id'], (round(e['R'], 3), round(e['G'], 3), round(e['B'], 3)) if e else None, 'slot', x['robot'].get('from_slot'),
              'veh', ((round(x['vehicle']['EnergonColor']['R'], 3), round(x['vehicle']['EnergonColor']['G'], 3), round(x['vehicle']['EnergonColor']['B'], 3))
                      if x['vehicle']['EnergonColor'] else None))
    print(json.dumps(out['summary']))

if __name__ == '__main__':
    main()
