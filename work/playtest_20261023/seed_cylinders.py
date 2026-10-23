"""Playtest 2026-10-23 #13 (MP_IAC_Seed clip-in on cylindrical props), read-only.

Per mesh placed in Seed whose pawn collision is the authored simple hull (physics.json props[].pawn == 'simple'): the union of the
BodySetup convex / box elements (mesh space, UE cm) vs the render mesh bounds (the extracted glTF's POSITION min / max, metres,
umodel axes). Compared as sorted per-axis EXTENTS (sign / axis-order safe): where the visual extent exceeds the hull's, the player
cylinder can enter the visible surface by up to (visual - hull) / 2 per side. Writes seed_cylinders.json here.
"""
import json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
EA = r'F:\Transformers Rebuild\ExtractedAssets'
VS = os.path.join(EA, 'VerticalSlice', 'Maps', 'MP_IAC_Seed')

def gltf_extent(mesh):
    f = os.path.join(EA, 'content', *mesh.split('.')) + '.gltf'
    if not os.path.exists(f): return None
    j = json.load(open(f, encoding='utf-8'))
    lo, hi = [1e9] * 3, [-1e9] * 3
    for m in j.get('meshes') or []:
        for p in m.get('primitives') or []:
            a = j['accessors'][p['attributes']['POSITION']]
            if 'min' in a: lo = [min(x, y) for x, y in zip(lo, a['min'])]; hi = [max(x, y) for x, y in zip(hi, a['max'])]
    return [h - l for l, h in zip(lo, hi)] if lo[0] < 1e9 else None

def main():
    ph = json.load(open(os.path.join(VS, 'physics.json'), encoding='utf-8'))
    use = Counter(p['mesh'] for p in ph['props'] if p.get('pawn') == 'simple' and p.get('mesh'))
    rows = []
    for mesh, n in use.items():
        rec = ph['meshes'].get(mesh) or {}
        el = (rec.get('simple') or {}).get('elements') or {}
        boxes = [e['elem_box'] for e in el.get('convex') or []] + [e.get('elem_box') for e in el.get('boxes') or [] if e.get('elem_box')]
        if not boxes: continue
        lo = [min(b[i] for b in boxes) for i in range(3)]; hi = [max(b[3 + i] for b in boxes) for i in range(3)]
        hull = sorted(0.01 * (h - l) for l, h in zip(lo, hi))
        vis = gltf_extent(mesh)
        if not vis: continue
        vis = sorted(vis)
        inset = [round((v - h) / 2, 3) for v, h in zip(vis, hull)]
        rows.append({'mesh': mesh, 'placements': n, 'cylinder_like': bool(re.search(r'cylind|pipe|tank|pillar|column|canister|barrel|silo|support', mesh, re.I)),
                     'hull_elements': len(boxes), 'hull_extent_m (sorted)': [round(x, 3) for x in hull],
                     'visual_extent_m (sorted)': [round(x, 3) for x in vis], 'max_inset_per_side_m': max(inset), 'inset_per_axis_m': inset})
    rows.sort(key=lambda r: -r['max_inset_per_side_m'])
    json.dump({'map': 'MP_IAC_Seed', 'meshes_with_simple_pawn_collision': len(rows), 'rows': rows},
              open(os.path.join(HERE, 'seed_cylinders.json'), 'w', encoding='utf-8'), indent=1)
    print('meshes with simple pawn collision', len(rows), '| inset > 0.25 m:', sum(r['max_inset_per_side_m'] > 0.25 for r in rows),
          '| of which cylinder-like:', sum(r['max_inset_per_side_m'] > 0.25 and r['cylinder_like'] for r in rows))
    for r in rows[:15]: print(' ', r['mesh'], 'x%d' % r['placements'], 'cyl' if r['cylinder_like'] else '', 'inset', r['inset_per_axis_m'], 'hull', r['hull_extent_m (sorted)'], 'vis', r['visual_extent_m (sorted)'])

if __name__ == '__main__':
    main()
