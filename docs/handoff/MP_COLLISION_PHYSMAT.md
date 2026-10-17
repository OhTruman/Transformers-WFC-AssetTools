# MP weapon-collision physical materials (package 7, 2026-10-18)

**What it is:** `AssetTools/manifests/maps/<MAP>/collision_weapon_physmat.json`, one per MP map, written by
`scripts/wfc/collision_physmat.py`. Shape agreed with Systems; Gameplay threads the index into the hit result.

**What it describes:** `ExtractedAssets/VerticalSlice/Maps/<MAP>/collision_weapon.glb`, the zero-extent (weapon / hitscan) collision
world. The GLB is unchanged; `glb_sha256` ties the file to the exact GLB it describes.

## Shape

```
{ map, glb, glb_sha256, engine_default_physmat ("ENV_PHYSMAT_p.Metal_PHYSMAT", Engine.DefaultPhysMaterialName),
  physmats: ["", ...],                                   # 0 = none (the engine default applies)
  meshes: { "<glb mesh index>": { name, kind, source_mesh | level | volume, triangles,
                                  runs: [[first_tri, count, physmat_index, rule], ...], coverage_ok } },
  node_overrides: { "<glb node index>": physmat_index },  # replaces the mesh's runs for that node
  node_override_rules: { "<glb node index>": "component_override" | "first_material" },
  hull_nodes_by_owner_class: { "<class> (IsA StaticMeshActor | not a StaticMeshActor)": {nodes, triangles, with_first_material} },
  unresolved: [ { mesh, first_tri, count, rule, material | volume | source_mesh } ],   # these get the engine default
  checks: { meshes, coverage_ok, bsp{level: replayed / glb triangles, positions_match}, triangles, triangles_unresolved, runs_by_rule } }
```

- **Runs:** they cover every triangle of every mesh exactly once (`coverage_ok` on all meshes of all 10 maps). The runtime expands them
  into its per-triangle uint16.
- **Instancing:** nodes share meshes, so runs are per mesh. A node override, if any existed, would replace the mesh's runs for that node.

## Rules (the `rule` field per run)

| rule | source |
|---|---|
| section_material | per-poly mesh: the section material's PhysMaterial through the MIC parent chain (physics.json sections; the triangle order replays vs_physics' primitive walk) |
| body_setup | simple hull: the StaticMesh BodySetup's PhysMaterial |
| hull_default | simple hull without a BodySetup PhysMaterial: the mesh-level run, physmat 0 = engine default. CONFIRMED for every owner that is NOT a StaticMeshActor (StaticMeshCollectionActor members, StaticInterpActor, InterpActor): the resolver has no material fallback for them (RE CAMPAIGN_PROVISIONALS_CLOSED_RE.md a509740, 0x82C88168) |
| first_material (node override) | the same hulls placed by an owner that IsA StaticMeshActor: the first material slot WITH a PhysMaterial (CONFIRMED, same source). Carried in `node_overrides` with `node_override_rules[node] = "first_material"`, because the fallback depends on the owner class, not the mesh |
| bsp_surface_material | BSP: the surface material's PhysMaterial |
| volume | blocking volume: the volume's PhysMaterial (none authored: the 126 that carry the field all say None) |
| none / none (section not decoded in physics.json) | nothing authored -> engine default; listed in `unresolved` |
| unreferenced (no node uses this mesh) | a mesh in the GLB with no node (placement skipped as oversize); never hit |

**BSP check:** vs_map's polygon walk is replayed per level, and the triangles are compared position-for-position with the shipped
BSPCollision mesh. They match on all 10 maps.

## Results (10 MP maps)

**Triangles:** 243,682 weapon-collision triangles.
- **Hull rule (corrected 2026-10-18 per RE a509740):** the 65,842 hull triangles that had a "first material" PhysMaterial now split by
  owner.
  - StaticMeshActor owners keep it: 53 nodes, as node overrides.
  - Every other owner falls to the engine default: 17,191 StaticMeshCollectionActor + 15 mover nodes.
  - Instanced counts are in `hull_nodes_by_owner_class`.
- At mesh level, 51,500 have no authored PhysMaterial: e.g. `DarkEnergonCrystal_MATINST`, `DeadBodies_Mat_INST`, `FogSheet` and
  `EngineMaterials.DefaultMaterial` BSP faces. They are listed in `unresolved` and get the engine default (Metal).

**Physmats used:**
- Metal, Metal_dest, Concrete, Rubber, Water, Water_Coolant, ForceField, ForceField_Blue;
- also `TR_Corruptor_VEH_p.RB_CorruptorBigHitSquib_PHYSMAT` (Seed) and `DES_ORB_Asteroids_p.AsteroidLowFriction_PhysMat` (Debris).

**MP gate:** the only new files are the 10 `collision_weapon_physmat.json`. Every pre-existing manifest hash and every ExtractedAssets
MP file is unchanged (`work/transforming/mp_gate.json`). The D5 campaign version comes later.
