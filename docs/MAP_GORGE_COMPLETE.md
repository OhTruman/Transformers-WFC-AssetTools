# MP_UND_Gorge: second map through the generic pipeline (2026-10-04)

**How to regenerate.** One command: `python scripts/wfc/run_map_pipeline.py MP_UND_Gorge`. It runs 17 stages, each under the
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

## Blockers by owner
* **ASSETTOOLS:**
  * one SkeletalMeshActor is not exported to `world.glb` (its mesh and anim are listed in the inventory);
  * the Streets-only render_index enrichments are not generic yet: pickup FX component matrices and destructible states
    (Gorge has none) come from `m04_complete.py`.
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
