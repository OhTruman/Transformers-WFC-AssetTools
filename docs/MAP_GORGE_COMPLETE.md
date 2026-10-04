# MP_UND_Gorge: second map through the generic pipeline (2026-10-04)

**How to regenerate.** One command: `python scripts/wfc/run_map_pipeline.py MP_UND_Gorge`. It now runs 25 stages (see `docs/MAP_PIPELINE.md`), each under the
6 GB Job Object cap, one at a time and lock-guarded. The peak was 4.54 GB (`vs_map`).

**Determinism.** Regeneration is deterministic: `world.glb`, `collision.glb`, `props.json`, `gameplay.json` and `lightmaps.json`
were byte-identical between two runs.

**Outputs:**
* scene data in `ExtractedAssets/VerticalSlice/Maps/MP_UND_Gorge/` (58 files);
* `manifests/next_map/MP_UND_Gorge_*.json` (inventory, movers, lighting audit, transform validation, `vs_validate`, probe);
* `manifests/maps/MP_UND_Gorge/{map_complete,render_index_generic,completeness}.json`.

**Status.** GEOMETRY + AUTHORED DATA COMPLETE. **This is not a playability claim**: modes, movers, pickups, FX and audio runtime
belong to Gameplay, Rendering and Systems.

## Completeness (`completeness.json`)
| area | result |
|---|---|
| level hierarchy | BASE + ART + AUDIO (from name prefix and authored LevelStreaming) |
| BSP | ART 1,824 triangles, 0 skipped polys, 0 validation issues |
| placed meshes | 1,765 placed / 166 unique, 0 missing |
| collection-actor transforms | **1,752 / 1,752 exact** (translation, rotation, scale, sign, determinant, glTF, bounds); 390 mirrored (det < 0), 420 with a negative axis, 30 with two negative axes (not mirrored), 772 non-uniform |
| collision | `collision.glb` + pawn + weapon; 80 BlockingVolume + 28 TnTransformerBlockingVolume (block pawns), 9 TnRadialForceVolume (non-blocking), 35 triggers |
| lightmaps | 12 atlases, all exported; 1,137 lightmapped world nodes |
| materials | 149 records, 0 missing |
| decals / map FX | 20 decals; 31 particle components across 5 systems (exported) |
| fog | 4 HeightFog, all exported (`lighting.json` `globals.height_fogs`) |
| lights | 411 |
| postprocess | complete |
| movers | 13: 4 hidden objective props (PHYS_Interpolating, Kismet-shown) + 9 vent fans (PHYS_Rotating); no Matinee |
| pickups | 7 ammo crate, 7 health, 1 overshield |
| player starts / objectives | 115 starts (97 team + 18 FFA); 6 objective records |
| mode-hidden state | 21 actors hidden in TDM: 3 domination, 7 KOTH, 2 flag + 1 bomb factories, 2 capture + 2 plant points, 4 Kismet-hidden objective props |
| ambient audio | 9 point, 4 volume and 2 line emitters; 23 zones; 6 reverb presets; 37 / 37 WAVs |
| navigation | 148 nodes, 738 reach specs |
| frontend | name "Gorge" (FRA "Gorge"), thumbnail `MP_Gorge.png`, shared loading screen, modes DM/TDM/CTF/KOTH/EXT/DOM |
| `vs_validate` | 44 / 44 |

**Cross-check.** The same generic generator run on Streets reproduces the validated Streets `render_index` TDM state exactly:
19 = 19 actors, identical names.

## Handoff package classification (all 45 categories, `completeness.json`, 2026-10-04 pass)
Every category the Streets handoff covers is classified. All are COMPLETE, EXPORTED (the renderer simulates them) or AUTHORED
(runtime behaviour):
* level hierarchy and sublevels;
* BSP (1,824 triangles; alignment audit difference 0, 0 unaccounted nodes);
* placed meshes (1,765);
* collection-actor transforms (1,752 / 1,752);
* negative / non-uniform scales: 390 mirrored, 772 non-uniform, winding CONSISTENT;
* materials (149, 0 missing) and material instances (122 MIC + 27 Material, 44 masters);
* textures and lightmaps (12 atlases, 1,137 / 1,137 bound with TEXCOORD_1);
* lights (411; 404 baked, 7 dynamic), fog (4 HeightFog), post-process;
* decals (20), particles (31 components);
* moving scenery (13: 9 rotating vent fans + 4 Kismet-shown objective props);
* collision, blocking volumes (80 + 28 transformer);
* player starts (115), navigation (148 nodes / 738 reach specs, no tactical data);
* pickups (15, with decoded FX), objectives, mode-specific actors (21 hidden in TDM);
* audio emitters (15), zones / reverb (23 / 6), surface audio (all FS_DEFAULT);
* skyline / background geometry (67 props outside the playable bounds + 50 m);
* Kismet references (generated summary: GameplayStarted → 2 GameRuleActive → ToggleHidden ×4 objective props; 48 audio ops);
* destructibles (none on Gorge);
* frontend loading, thumbnail and name.

## Structural audit (`manifests/maps/MP_UND_Gorge/structure_audit.json`): PASS
* **Transforms.** 0 of 1,752 collection nodes differ from the S·R·T × CachedParentToWorld matrix.
* **Mirrored.** det < 0 triangles oppose their normals 286,931 to 82, as glTF requires.
* **Playable space.**
  * The 1 m walk graph from the starts covers 259,430 m² of floor layers. Bounds: x −233…−11 m, z −225…221 m, floor
    −27.8…38.4 m.
  * All 115 starts, 15 / 15 pickups and 17 / 17 objectives are on reachable floor. KillZ (−7,500 UU) is authored on the
    AUDIO WorldInfo.
* **Collision vs visible.**
  * 83.6 % of reachable collision floor has render floor, excluding volume tops. Simple hulls are coarser than render meshes.
  * All 7 blocking components without a collision node are explained: 3 meshes with no collision (EnergyFence_04 ×2,
    TunnelPipe edge glow) and 4 per-poly shells larger than 2 km (BlueNebulae cards, FogVolume cubes at Y +601 m / −233 m,
    out of play).
* **DefaultMaterial BSP faces.** 560 triangles, **0 visible in play**. Streets has 3.
* **Actors.** 13 / 13 movers and 8 / 8 mode-gated targets are in `world.glb`. The one SkeletalMeshActor (a WEP_ShortSword
  prop) is spawned from glTF via `render_index_generic`.

## What differs from Streets
* **Larger and more vertical.** 411 vs 268 lights, 115 vs 84 starts, two-storey gate shafts, a canyon layout with 4 HeightFogs.
* **No destructibles** (Streets has one, out of play) and **no Matinee**. Movers are 9 rotating fans (PHYS_Rotating) plus the 4
  objective bases.
* **9 TnRadialForceVolumes** (jump / force pads). Their runtime force is RE-owned.
* **0 DefaultMaterial faces visible in play** (Streets: 3).
* **Same pipeline, no custom code.** Streets keeps its own hand-validated order and render index (`m04_complete`). Gorge's
  render index is `render_index_generic.json`. It now also carries pickup FX component data, destructible state meshes and
  skeletal / transforming actors. The generic destructible matrices reproduce Streets' validated ones exactly.

## Blockers by owner
* **ASSETTOOLS:** none. The skeletal actor is spawnable from `render_index_generic`, and pickup FX and destructible
  enrichments are generic now.
* **RE:**
  * TnRadialForceVolume runtime force (×9; per-instance ForceStrength and ArrowDirection are authored);
  * LensFlareSource semantics.
* **RENDERING:** particles (31), decals (20), height fog (4), lens flare (1).
* **GAMEPLAY:** mover runtime (13), mode gating per `mode_visual_state`, pickup state machines (RE P2).
* **SYSTEMS:** ambient zones and reverb from `audio.json`.
* **FRONTEND:** none; the registry entry is complete.

## Generic pipeline fixes made during this pass (Streets outputs unchanged)
* `vs_map.sublevels()` adds authored LevelStreaming packages to the name-prefix set. Streets and Gorge are unchanged; Seed gains
  `MP_IAC_Global_Art_m` and `GLB_Audio_m`; the UI lobbies gain the streamed customization room.
* `vs_lighting` exports every HeightFog (`globals.height_fogs`); the existing `height_fog` key is kept. Streets' `lighting.json`
  is otherwise byte-identical.
* `m04_inventory`, `vs_validate` and `validate_smca_transforms` take a map; non-Streets reports go to `manifests/next_map/`.
* Output folders are created by the stages that need them.
* New: `run_map_pipeline.py`, `map_complete.py`, `run_bounded.py`.
