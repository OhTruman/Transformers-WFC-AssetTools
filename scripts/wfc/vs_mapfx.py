"""Authored decal / particle-emitter records for a map (default MP_IAC_Streets).

Every DecalComponent and ParticleSystemComponent exported natively by the map's
packages (not cooked copies of library assets) is emitted with:
  * owner actor (class, name, sublevel) and the actor's authored props
  * the component's EFFECTIVE props (own tags merged over its archetype chain;
    effective.py) with the authoring object of each value
  * world transform: UE row-vector matrix (component_matrix @ actor_matrix, the same
    convention as vs_map.py) + glTF matrix
  * decals: material chain summary (matgraph.mic_chain) and blend/lighting of the root
  * particles: particles.py summary of the Template (emitters, required modules,
    materials, raw native distribution tables)
Output: ExtractedAssets/VerticalSlice/Maps/<map>/map_fx.json

Provenance: tagged props CONFIRMED; transforms CONFIRMED (same code path as props.json);
native particle module tables PARTIAL (see particles.py).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, effective, particles, matgraph  # noqa: E402
from vs_common import ue_to_gltf_matrix, VS  # noqa: E402
from vs_map import actor_matrix, component_matrix, sublevels, MAP  # noqa: E402

def _l(v):
    """typed_props struct dicts -> the list form vs_map's matrix helpers expect."""
    if isinstance(v, dict):
        for keys in (('X', 'Y', 'Z'), ('Pitch', 'Yaw', 'Roll')):
            if all(k in v for k in keys): return [v[k] for k in keys]
    return v

def _xf(d):
    return {k: _l(v) for k, v in d.items()} if isinstance(d, dict) else {}

def prefab_instances(p):
    """{placed actor opath: {'prefab_instance', 'template_prefab', 'archetype'}} from each PrefabInstance's
    native ArchetypeToInstanceMap (i32 count, then (archetype idx, instance idx) pairs after the tags)."""
    import struct
    out = {}
    for i, e in enumerate(p.exports):
        if p.class_name(e) != 'PrefabInstance': continue
        try:
            tags, used = p._tr.read_object(i + 1)
            d = objtree.tp.to_dict(tags)
            raw = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
            n = struct.unpack_from('>i', raw, 0)[0]
            for k in range(max(0, min(n, 4096))):
                a, b = struct.unpack_from('>2i', raw, 4 + 8 * k)
                if b > 0:
                    out[p.object_path(b)] = {'prefab_instance': p.object_path(i + 1),
                                             'template_prefab': objtree.tp.simplify(d.get('TemplatePrefab')),
                                             'archetype': p.object_path(a) if a > 0 else (p.full_path(a) if a else None)}
        except Exception:
            continue
    return out

KINDS = {'DecalComponent': 'decal', 'ParticleSystemComponent': 'particle'}

def main():
    out = {'map': MAP, 'decals': [], 'particle_components': [], 'particle_systems': {}, 'decal_materials': {},
           'provenance': __doc__.split('Provenance:')[1].strip()}
    for pk in sublevels():
        p = objtree.package(pk)
        prefab_of = prefab_instances(p)
        for i, e in enumerate(p.exports):
            cls = p.class_name(e)
            if cls not in KINDS: continue
            op = p.object_path(i + 1)
            if not op.startswith(pk + '.'): continue                # cooked library copy, not placed in this map
            owner_i = e['outer']
            owner = p.object_path(owner_i) if owner_i > 0 else None
            owner_cls = p.class_name(p.exports[owner_i - 1]) if owner_i > 0 else None
            try: ad = objtree.tp.simplify(p._tr.read_dict(owner_i)) if owner_i > 0 else {}
            except Exception as ex: ad = {'__error__': str(ex)}
            eff = effective.effective(op, pk)
            cv = {k: v['value'] for k, v in eff.items()}
            src = {k: v['from'] for k, v in eff.items()}
            M = component_matrix(_xf(cv)) @ actor_matrix(_xf(ad))
            rec = {'sublevel': pk, 'component': op, 'class': cls, 'owner': owner, 'owner_class': owner_cls,
                   'prefab': prefab_of.get(owner),
                   'owner_props': {k: v for k, v in ad.items() if k in ('Location', 'Rotation', 'DrawScale', 'DrawScale3D',
                                   'Tag', 'Group', 'Base', 'bHidden', 'bStatic', 'bNoDelete', 'Layer', 'bCurrentlyActive')},
                   'props': cv, 'prop_source': src,
                   'ue_matrix': M.tolist(), 'gltf_matrix': ue_to_gltf_matrix(M)}
            if cls == 'DecalComponent':
                mat = cv.get('DecalMaterial')
                if mat and mat not in out['decal_materials']:
                    ch = matgraph.mic_chain(mat, pk)
                    out['decal_materials'][mat] = [{'object': c['object'], 'class': c.get('class'), 'package': c.get('package'),
                                                    'props': {k: v for k, v in (c.get('props') or {}).items()
                                                              if k not in ('ExpressionTree', 'ReferencedTextureGuids')}}
                                                   for c in ch]
                out['decals'].append(rec)
            else:
                t = cv.get('Template')
                if t and t not in out['particle_systems']:
                    try: out['particle_systems'][t] = particles.summarize(t, pk if t.lower() in p._idx else None)
                    except Exception as ex: out['particle_systems'][t] = {'error': str(ex)}
                out['particle_components'].append(rec)
    out['counts'] = {'decals': len(out['decals']), 'particle_components': len(out['particle_components']),
                     'particle_systems': len(out['particle_systems']), 'decal_materials': len(out['decal_materials'])}
    path = os.path.join(VS, 'Maps', MAP, 'map_fx.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts']), '->', path)

if __name__ == '__main__':
    main()
