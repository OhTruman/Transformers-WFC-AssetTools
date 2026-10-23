"""PC adaptation (Gameplay / Integration 2026-10-23: the Remnant horde slid along a SquareLightPlane at x = 149.0 on its perch exit):
light cards (ENV_IAC_LightSources_p LightPlanes meshes, *LightPlane* names) out of the PAWN collision. Their component collision flags are
not authored (inherited from Default__StaticMeshActor.StaticMeshComponent0: CollideActors / BlockActors true), the mesh has no simple
collision and one collision-enabled section, so per-poly pawn collision is what the data gives; the same cards are authored non-colliding
on most maps (Streets 69 / 69 'none'). Whether the original blocks here is UNKNOWN (UE3 per-poly checks may be one-sided). Weapon collision
is unchanged.

Base = the shipping overlay (work/overlay_20261023g) when it holds the map, else live ExtractedAssets. Writes the adapted collision_pawn.glb +
physics.json to out/pc_adapt/_candidates/lightcards/VerticalSlice/Maps/<MAP>/ (props[].pawn -> 'none' with pc_adaptation).
    python drop_light_cards.py <MAP> [...]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, accessor  # noqa: E402
OVG = os.path.join(AT, 'work', 'overlay_20261023g', 'VerticalSlice', 'Maps')
OUT = os.path.join(AT, 'out', 'pc_adapt', '_candidates', 'lightcards', 'VerticalSlice', 'Maps')
NOTE = 'light card out of pawn collision (PC adaptation; inherited default flags; Gameplay / Integration 2026-10-23)'

def is_card(m): return bool(m) and ('.LightPlanes.' in m or 'LightPlane' in m.split('.')[-1])

def one(mp):
    B = os.path.join(OVG, mp) if os.path.exists(os.path.join(OVG, mp, 'collision_pawn.glb')) else os.path.join(ROOT, 'VerticalSlice', 'Maps', mp)
    bj, bb = read_glb(os.path.join(B, 'collision_pawn.glb')); g = GLB('AssetTools drop_light_cards (%s)' % mp); cache = {}; dropped = 0; kept = 0
    for n in bj['nodes']:
        mi = n.get('mesh')
        if mi is None: continue
        if is_card((n.get('extras') or {}).get('mesh')): dropped += 1; continue
        if mi not in cache:
            prims = []
            for pr in bj['meshes'][mi]['primitives']:
                P = accessor(bj, bb, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(bj, bb, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            cache[mi] = g.mesh(bj['meshes'][mi].get('name', ''), prims)
        g.node(dict(n, mesh=cache[mi])); kept += 1
    od = os.path.join(OUT, mp); os.makedirs(od, exist_ok=True); g.write(os.path.join(od, 'collision_pawn.glb'))
    ph = json.load(open(os.path.join(B, 'physics.json'), encoding='utf-8')); sw = 0
    for r in ph['props']:
        if is_card(r.get('mesh')) and r.get('pawn') != 'none':
            r['pc_adaptation_light_card'] = {'pawn_original': r['pawn'], 'reason': NOTE}; r['pawn'] = 'none'; sw += 1
    pa = ph.get('pc_adaptation') or {}; pa['light_cards'] = {'note': NOTE, 'placements': sw}; ph['pc_adaptation'] = pa
    json.dump(ph, open(os.path.join(od, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(mp, 'base', 'overlay g' if B.startswith(OVG) else 'live', 'collision nodes kept', kept, 'dropped', dropped, '| physics props switched', sw)

if __name__ == '__main__':
    for m in sys.argv[1:]: one(m)
