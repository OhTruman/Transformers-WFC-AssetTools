# Production map pipeline: one command per multiplayer map (2026-10-04)

**How to run.** `python scripts/wfc/run_map_pipeline.py <MAP>`, for example `MP_UND_Gorge`.
* **25 stages**, run one at a time. Each stage runs under `run_bounded.py` (Windows Job Object, 6 GB cap). The highest stage peak
  so far is 4.5 GB (`vs_map` on Gorge).
* **Lock-guarded**: `logs/map_pipeline.lock` refuses overlapping pipelines.
* **Refusals:**
  * `MP_IAC_Streets` is refused; it is regenerated in the Streets-specific order given in CLAUDE.md.
  * Maps whose `<MAP>_BASE_m` package is not cooked in the Game Dump are refused.
* **Cross-map overview:** `python scripts/wfc/map_pipeline_summary.py` writes `manifests/maps/pipeline_summary.json`, one row per
  registry map.

## Stages
| # | stage | output |
|---|---|---|
| 1 | `vs_map` | `world.glb`, `props.json`, `map.json`, BSP. Sublevels = name prefix ∪ authored LevelStreaming. |
| 2–4 | `vs_lighting`, `vs_postprocess`, `vs_navigation` | lights (+ all HeightFog), post-process chain + volumes, ReachSpec graph |
| 5–7 | `vs_lightmap` → `m04_lightmap_atlases` → `vs_lightmap` | lightmap bindings, atlas PNGs, rebind |
| 8–9 | `vs_materials`, `vs_props` | MIC chains / masters, authored prop flags |
| 10–11 | `vs_collision`, `vs_physics` | `collision.glb`, pawn / weapon channels (simple / per-poly / none) |
| 12–14 | `vs_gameplay`, `vs_audio`, `vs_mapfx` | starts, clusters, pickups, objectives, Kismet mode rules, Matinee, audio emitters / zones / reverb, decals, particles |
| 15–17 | `m04_inventory`, `validate_smca_transforms`, `vs_validate` | actor inventory; per-component transform proof; GLB checks |
| 18–23 | `m04_bsp`, `m05_bsp_default_faces`, `m04_kismet`, `vs_pickups`, `vs_destructibles`, `vs_surface_audio` | BSP audit, DefaultMaterial face visibility, Kismet graph, pickup factories + decoded pickup FX, destructible state machines, surface → footstep audio |
| 24 | `map_structure_audit` | structural / visual audit (below) |
| 25 | `map_complete` | `manifests/maps/<MAP>/{map_complete,render_index_generic,completeness}.json` |

**Output naming.** Streets keeps its canonical manifest names (`manifests/streets_*.json`). Every other map writes
`manifests/next_map/<MAP>_*.json` (`m03_common.map_out`).

**Level resolution.** `m03_common.map_levels` resolves level names case-insensitively (`MP_IAC_Rust_Art_m`) and adds authored
streaming sublevels:
* Seed: `MP_IAC_Global_Art_m`, `GLB_Audio_m`;
* Debris: the shared `MP_ORB_Art_m` / `MP_ORB_Audio_m`; its own package holds only the BASE level.

`m03_common.bsp_level` picks the level that carries BSP.

## Structural audit (`map_structure_audit.py`): proof beyond file counts
* **Transforms.** Every StaticMeshCollectionActor component node in `world.glb` equals the `props.json` matrix, which is
  component S·R·T × native CachedParentToWorld. This is the Streets collection-actor lesson.
* **Mirrored instances.** For det < 0 nodes the transformed winding opposes the transformed normals. That is consistent with
  glTF 2.0, which requires the renderer to flip the front face.
* **Playable space:**
  * upward-facing pawn-collision triangles are rasterised into a layered 1 m height grid (≤ 48 layers per cell; Gorge's gate
    shafts stack more than 12);
  * the grid is flood-filled from every player start with a conservative step rule (≤ 1.25 m);
  * every start, pickup and objective must sit on reachable floor.
* **Collision vs visible.** Reachable collision floor is compared with render floor. Every blocking prop without a collision
  node must be explained from `physics.json`:
  * no simple collision and no per-poly flag (no pawn collision in UE3 either); or
  * a per-poly shell larger than 2 km (out of play).
* **Also checked:**
  * lightmap binding (`lm_atlas` nodes have `TEXCOORD_1`);
  * DefaultMaterial triangles;
  * movers and mode-gated actors present in `world.glb`;
  * oversized triangles kept out of the grids (sky dome rule).

The agreement percentage is a diagnostic. UE3 simple collision hulls are coarser than render meshes and blocking-volume tops
are walkable, so 100 % is not expected.

## Map-specific exceptions (explicit, data-driven)
* **Streets** keeps its hand-written Kismet summary (`m04_kismet.STREETS_SUMMARY`) and its destructible interpretation and
  placement prose. Other maps get generated summaries and computed placement verdicts.
* **Streets transform report.** `validate_smca_transforms` before/after comparison needs `--before <pre-fix slice>`. A plain
  rerun drops those fields, so the committed Streets report is kept.

## Generic fixes in this pass (Streets regenerated and compared byte for byte)
* **`vs_map`:**
  * when the cooked component does not serialize `StaticMesh`, the effective archetype-chain values are filled in
    (Rust: 6 `Ceiling_Arch_STAT` components with `Scale3D` Y 0.75 on the archetype);
  * when `authored.db`'s `extracted` path is stale, the content path is used.
* **`validate_smca_transforms`** reads native parents from every exported sublevel. Seed's streamed `MP_IAC_Global_Art_m`
  components were otherwise unvalidated; their transforms were already correct.
* **`m04_inventory`** and the M03–M05 scripts take the map as a positional argument and use case-resolved and streamed levels.
* **`vs_gameplay`**: Escalation maps have no spawn clusters, so the nearest-cluster inference is skipped.
* **`vs_destructibles`**: prefab-instance destructibles (Escalation loot crates) take their Blueprint and Pieces from the
  archetype, and missing objects are skipped safely.

**Regression results.**
* Streets `vs_map` outputs are byte-identical. `collision.glb` is first written by `vs_map` and then replaced by
  `vs_collision`, so the canonical file was restored.
* `streets_kismet`, `future_hud_handoff`, `streets_bsp_audit`, `streets_bsp_default_faces`, `streets_pickup_*`,
  `streets_surface_audio` and `streets_destructibles` are byte-identical to the pre-change run.
* `validate_m04` passes with 0 failures.

## Every cooked multiplayer map through the pipeline (`manifests/maps/pipeline_summary.json`)
The registry has 13 maps. **10 are cooked** in the dump: Streets plus 9 maps run by the generic pipeline. **Fortress, Havoc and
Tranquillity are not cooked** (registry `cooked=false`); the pipeline refuses them.

| map | props | BSP tris | lights | particle comps | decals | movers | destructibles | structure audit | starts on walk graph |
|---|---|---|---|---|---|---|---|---|---|
| Gorge | 1,765 | 1,824 | 411 | 31 | 20 | 13 | 0 | PASS | 115/115 |
| Seed | 2,630 | 5,368 | 317 | 39 | 25 | 16 | 3 | PASS | 102/102 |
| Berth | 1,490 | 1,580 | 297 | 23 | 14 | 4 | 9 | PASS | 120/120 |
| Complex | 1,909 | 5,189 | 152 | 42 | 30 | 7 | 0 | PASS | 96/96 |
| Rust | 2,215 | 1,267 | 348 | 30 | 17 | 8 | 0 | PASS | 109/109 |
| Debris | 1,689 | 304 | 121 | 21 | 0 | 18 | 6 | PASS | 50/50 |
| Molten | 2,159 | 10,834 | 302 | 75 | 24 | 4 | 0 | PASS | 76/76 |
| BrokenHope (Escalation) | 2,430 | 4,040 | 303 | 42 | 22 | 2 | 50 | PASS | 4/4 |
| Remnant (Escalation) | 4,312 | 10,712 | 172 | 77 | 18 | 24 | 47 | PASS | 4/4 |
| Streets (own order; generic cross-check) | 1,952 | 2,460 | 268 | 45 | 25 | 12 | 1 | PASS | 84/84 |

Every map reports **GEOMETRY + AUTHORED DATA COMPLETE** with 0 ASSETTOOLS blockers. The highest stage peak was 4.54 GB.
Escalation maps also carry 35 TnSurvivalGenerator and 12–18 TnTransformingWorldActor. The transforming actors are spawned from
glTF via `render_index_generic`; Escalation gameplay semantics belong to RE / Gameplay.

**Additional generic fixes found by the full run** (Streets regenerated and compared):
* `vs_lighting`, `vs_postprocess`, `vs_audio`, `vs_gameplay`, `vs_navigation` and `vs_physics` use
  `vs_common.map_sublevels`, which adds the streamed levels. Before this, Debris had 0 lights; it now has 121.
* `vs_validate` checks BSP > 0, because completeness against authored data is the `m04_bsp` audit (Debris has 304 triangles).
* `vs_navigation` is now deterministic. It used set iteration that varied with `PYTHONHASHSEED`, a pre-existing issue. Streets'
  `navigation.json` is semantically identical; only key order inside one histogram changed.

## Why non-Streets maps look wrong (2026-10-05 investigation)
Every cooked map's geometry, collision, materials and lightmap bindings are complete (structure audit PASS). The visible
problems trace to four data or consumption gaps. Three of them are now closed on the data side.

**1. No per-map `render_index.json` → no pickup crates, domination totems, KOTH rings or destructibles (AssetTools: FIXED).**
* The renderer's `loadMapProps` reads `Maps/<MAP>/render_index.json`, and only Streets had one (from `m04_complete.py`).
* New stage 28, `map_render_index.py`, writes the same sections for every map:
  * `pickup_factory_visuals`;
  * `not_in_world_glb (authored renderables)` with every destructible state mesh;
  * `pickup_fx_components`, `mode_visual_state`, `tdm_render_state`.
* Cross-checked on Streets against the validated index: 27 / 27 pickup visuals and 9 / 9 renderables with identical
  matrices, and an identical TDM hidden set. The Streets file itself is never written.

**2. Vertex-baked lighting dropped → black / unlit props (data FIXED; RENDERER must consume it).**
* 50–635 components per map use LMT_1D per-vertex lightmaps (Rust 635, Gorge 561, Seed 257).
* Their sample colours carry a 4th byte of 0 instead of 254/255 (Streets, Debris). The renderer's decoder requires ≥ 250 and
  so drops all of them; Rendering's `work/render` data has 0 samples on 8 maps.
* New stage `vs_vertex_lightmaps.py` writes `Maps/<MAP>/vertex_lightmaps.json` in the renderer's own record schema (`count`,
  `samples_hex`, `scales`):
  * **byte-identical to Rendering's decode on Streets** (28 / 28);
  * sample count equals the mesh LOD0 vertex count on 99.6 % of components (the exceptions are flagged).
* **Update, 01:10.** Rendering M20/M21 (commit 309facc, 00:38) independently fixed the FColor channel order. Its render data now
  loads every sample. The two independent decoders agree byte for byte on all components (Gorge 561, Rust 635, Seed 257,
  Remnant 58, Streets 28). This gap is **closed**, and AssetTools' file remains as the cross-check.

**3. Colour grade authored on a PostProcessVolume → washed-out maps (data FIXED; RENDERER must apply it).**
* 8 of 9 non-Streets maps author no WorldInfo CLUT. Their grade, a CLUT (`ENV_Cluts_p.clut_mp40` / `desaturation40_CLR`) plus
  Scene_HighLights 1.2–1.5, sits on a PostProcessVolume that contains every player start.
* Berth has both a world CLUT and a volume grade.
* `vs_postprocess` now decodes each volume CLUT (`postprocess_clut_<volume>.png`) and its scene tone. `completeness.json`
  `postprocess.volumes` records coverage (player starts inside).
* **Still open at 01:10.** Rendering's render data applies no CLUT and a neutral tone on 7 maps (Gorge, Seed, Complex, Rust,
  Molten, BrokenHope, Remnant). Berth and Debris load their world CLUT; Berth's volume grade is not applied either.

**4. Streamed shared levels ignored by some stages (AssetTools: FIXED).**
* `vs_lightmap` found levels by name prefix only. Debris's art lives in the streamed `MP_ORB_Art_m`, so it bound 13
  lightmapped props instead of 1,561.
* `vs_lightmap` now adds the `map.json` sublevels and resolves `_Art_m` lightmap packages case-insensitively. Streets'
  `lightmaps.json` is byte-identical.

**Also added:** per-map `hazard_volumes.json` (pain and kill PhysicsVolumes plus KillZ), which Gameplay must apply:
* Gorge: 1 instant-kill volume;
* Remnant: 26 AI-kill DynamicPhysicsVolumes plus 1 suicide volume;
* Debris: 6 volumes at 75/s; Seed and Complex: 2 volumes each at 25/s.

**Readiness:** `manifests/maps/readiness_matrix.json` and `docs/MAP_READINESS_MATRIX.md`, generated by
`map_readiness_matrix.py`, give per-map and per-area verdicts with evidence and consumer actions. They also include read-only
observations of what the Rendering lane's render data currently loads.
