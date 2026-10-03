# MP_IAC_Streets: complete authored map (Milestone 04, 2026-10-02)

**Entry point:** `AssetTools/manifests/mp_iac_streets_complete.json` (hierarchy, extents, counts, rebuild comparison, causes,
links). Every focused manifest below keeps per-record provenance (package / object / class / property / value / confidence).

**Regenerate:**
1. `run_pipeline.py --only m04_lightmap_atlases m04_bsp m04_inventory m04_kismet m04_complete validate_m04`
2. After any change to `lightmaps.json`, also run `vs_lightmap.py` then `--only vs_map vs_collision vs_physics vs_validate`.

## Geometry fix (2026-10-03): StaticMeshCollectionActor component transforms
**Root cause:** reported by ReverseEngineering (`RE-Workspace/notes/MILESTONE04_STREETS_NATIVE_SCENE.md`,
`notes/data/streets_smca_component_scale.json`). `vs_map.py` placed the 1,906 SMCA members with the serialized
CachedParentToWorld only. The engine also applies the component `S(Scale*Scale3D) * R * T`.

**Fix:** `M = component_matrix(cd) @ CachedParentToWorld`. The fix flows into `props.json`, `world.glb`, `collision.glb`,
`collision_pawn.glb`, `collision_weapon.glb`, `physics.json`, `map.json`, `render_index.json` and the M04 manifests.

**Transform validation (`validate_smca_transforms.py`, `manifests/streets_transform_validation.json`):** 1,906 components
checked against an independent recomputation (native parent re-read, component values through the archetype chain) and the
RE table.
* 1,906/1,906 exact matches; 0 mismatches in translation, rotation, scale, sign, determinant, glTF matrix or bounds.
* RE table agreement: 1,906/1,906.
* 1,672 components changed versus the pre-fix export.
* 478 are mirrored (det < 0); 4 have two negative axes, which is not mirroring.
* All three collision GLBs carry the corrected matrices, with 0 stale pre-fix matrices.
* Lightmap bindings are unchanged (1,755 SMCA bindings identical; `world.glb` has 1,794 lightmapped nodes).
* All 46 non-SMCA placements are unchanged.

**Before/after audit (`manifests/streets_transform_fix_audit.json`):**
* `CityBackdrop_STAT` ×2: 1.0 → 0.41.
* `SquareLightPlane_STAT` up to 13.88×.
* `Cratestack_Debri_01` up to 18.5× / (14.7, 14.7, 27.1).
* `Saucer_8192` → (0.07, 0.07, 0.035).
* `OmegaCeilingDome` → 0.086.
* Mirrored wall and support halves: `Wall_Top_Straight` (−1, 1, 1), `SideSuppPillar` (−0.78, 0.78, 0.78).
* By family: `ENV_CORE_InroomWall_C` 92, `SquareLightPlane` 69, `ArchTop01` 63, `CurveWall_7168` 63, `GS_SupportB` 62,
  `SideSuppPillar` 61.

**Bounds:** the authored world bounds excluding sky and backdrop are now 842 × 929 × 843 m. Playable bounds are unchanged.

**Caveat:** this fixes a structural export defect. It does not by itself make the map visually 1:1.

## Identity and hierarchy (CONFIRMED)
| package | role | streaming | actors (+BSP comps) | components |
|---|---|---|---|---|
| `MP_IAC_Streets_BASE_m` | persistent level: starts, pickups, objectives, volumes, Kismet, movers, WorldInfo | persistent | 224 | 268 |
| `MP_IAC_Streets_ART_m` | art: static meshes, BSP, lights, decals, emitters, fog, destructible | `LevelStreamingKismet_8751` | 794 (incl. 422 ModelComponents) | 2365 |
| `MP_IAC_Streets_AUDIO_m` | ambient audio, audio zones, reverb Kismet | `LevelStreamingKismet_12838` | 84 | 51 |

**Levels and streaming:**
* The default `LevelStreamingState` lists both sublevels `LevelVisible=true`.
* No Kismet streaming actions exist, so all three levels coexist for the whole match.
* Streaming levels carry no level transform.
* Hierarchy closure: every referenced level resolves.

**Companions:**
* `MP_IAC_Streets_ART_m_LM` (78 lightmap textures)
* `MP_IAC_Streets_Base_m_LM` (3)
* `MP_IAC_Streets_BASE_m_LOC_{int,FRA}`
* Cue bank `BL_LVL_MP_IAC_STREETS`

## Extents (CONFIRMED)
* **Authored geometry, excluding the sky dome and city backdrop:** 841 × 802 × 686 m.
* **Sky dome (`SpaceDome_STATMESH`):** 14.4 km across. Backdrops: `CityBackdrop_STAT` ×2, ~1.2 km wide.
* **Playable footprint (player starts):** 379 × 370 m, with 21 m vertical spread.
* **Outlier:** the destructible wall panel sits ~700 m above the play floor.
* **Regions and spaces:** 9 authored audio zones (the only authored region partition), 12 spawn clusters, 5 KOTH zones,
  3 domination points, 2 CTF bases, 2 bomb sites.

## Complete counts
| item | count |
|---|---|
| placed actors | 680 (+422 BSP ModelComponents) |
| components | 2684 |
| BSP | 889 nodes / 427 surfaces / 1420 points / 2460 triangles / 540 render elements |
| static-mesh components | 1952 placed (171 unique meshes) + destructible state meshes + editor camera mesh |
| skeletal (domination totems) | 3 |
| movers | 12 (3 rotating domes, 5 SkyBeam/dome StaticInterpActors, 4 hidden objective bases) |
| destructibles | 1 |
| decals | 25 |
| lights | 182 point, 83 spot, 2 directional, 1 sky |
| baked lighting | 1795 texture-lightmapped components, 28 vertex (1D), 133 none |
| lightmap atlases | 63 coefficient textures (81 PNG) |
| FX | 45 particle components (8 level steam + 37 pickup) + 2 destructible FX factories |
| audio | 40 point + 13 line + 17 volume emitters, 9 zones, 10 reverb presets, 32 cues, 11 positional one-shot pools |
| pickups | 14 ammo, 9 health, 1 overshield |
| starts | 60 team + 24 FFA |
| objectives | 2 flag factories, 1 bomb factory, 2 capture points, 2 bomb plant points, 3 domination points, 5 KOTH zones |
| volumes | 71 blocking, 20 trigger, 4 forced-dir, 12 spawn clusters |
| prefabs | 16 instances / 35 members, all resolved to slice data |
| Kismet | BASE startup + SkyBeam Matinee + EXT/CTF unhide; AUDIO 9 zones, 11 positional sounds, 18 activations |

## Current rebuild vs original (`streets_rebuild_diff.json`)
* **Sources:** slice exports plus the Rendering lane's renderer-dump audit, read-only, dated 2026-10-02 12:58.
* **Visible authored render items:** 2,566, comprising:
  * 2,025 static/skeletal/particle/decal components
  * 540 BSP elements
  * 1 destructible
* **Breakdown of those items:**
  * **97.66% present and matching.** 36 of these have materials Rendering could not verify.
  * **1.91% missing or not drawn:** 45 particle components, 3 totems, the destructible.
  * **0.43% wrong state or material:**
    * 4 objective bases drawn in every mode; they are authored hidden.
    * 3 rotating domes drawn static.
    * 3 SkyBeam Matinee actors drawn static.
    * 1 material incorrect (`DeadBodies_Mat_INST`).
* **Geometry is complete:**
  * BSP 2460/2460 triangles; every polygon node is rendered or invisible.
  * 1952/1952 meshes.
  * 0 rebuild-only extras.

### Why it reads as a small test area
It is **not** missing geometry or sublevels. The measurable gaps are all presentation and state:
* **No FX and no ambient audio:**
  * 45 FX components aren't drawn.
  * 70 ambient sound actors, 9 zones and 11 one-shot pools existed only as data at M03.
* **Frozen environment motion:** rotating domes at 15 °/s and the SkyBeam 9 s loop are static.
* **Mode-hidden props shown:** the objective bases appear in every mode.
* **Missing animated totems.**
* **Lighting gaps:**
  * 360 of 540 BSP elements carry no static light interactions (authored).
  * `LightsVisibilitiesVolume` is not implemented.
  * AssetTools' own lightmap binding was incomplete: 39 actor-placed meshes and 9 coefficient atlases. **Fixed in this pass;
    `world.glb` now carries 1,794 lightmapped nodes.**

The authored playable footprint is genuinely about 380 m square.

## `render_index.json` (in `ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/`)
This is the full-map render index, generated by `m04_complete.py` and not tracked in git. Every glTF path it names exists
(`validate_m04.py`).

| section | contents | confidence |
|---|---|---|
| `layers` | `world.glb` (BSP + 1,952 meshes), `lightmaps.json`, `map_fx.json`, `lighting.json`, `postprocess.json`, `audio.json` | CONFIRMED |
| `not_in_world_glb (authored renderables)` | **3 domination totems** (`NEU_EnergonTotem_SKEL` + anim, matrices, template `PointMesh0`, DOM only) | CONFIRMED |
| | **5 KOTH active-zone rings** (`FX_Mesh_p.Mesh.pTorus1_STAT` from template `ActiveMeshComponent0`, zone transform incl. DrawScale3D (1, 1, 2), material `CaptureZone_Reverse_MAT_INST`, KOTH active zone only) | CONFIRMED |
| | **destructible** intact mesh + all 3 states | state meshes CONFIRMED (piece × actor); spawned meshes PROVISIONAL |
| `authored_render_state` | 4 hidden objective bases (CTF/EXT only); rotating domes and SkyBeam movers | CONFIRMED |
| `mode_visual_state` / `tdm_render_state` | visibility per class across DM/TDM/CTF/EXT/DOM/KOTH; **19 actors hidden in TDM** | CONFIRMED |
| `pickup_factory_visuals` | 27 factories: 14 ammo crate meshes | PROVISIONAL placement (attach offset native) |
| | 10 health/overshield particle meshes | PROVISIONAL approximate matrix (particle-driven motion) |
| | 3 flag/bomb at-rest visuals | UNKNOWN |
| `pickup_fx_components` | all 37 pickup effects with matrices, attach and activation state, draw rule; 27 drawn when available, 24 in TDM | CONFIRMED (beam rule from RE script) |

Further detail:
* **Destructible states:**
  * 0 = intact (`Base`, health 20)
  * 1 = destroyed (`Chunk02` + spawned `Chunk01` physics chunk + 6 debris, 10 s)
  * 2 = settled (`Chunk02`)
* **Mode-gated actors hidden in TDM:**
  * 4 objective bases (still collide)
  * 3 totems
  * 5 KOTH zones
  * 2 flag + 1 bomb factories (Disabled: no draw, no collision)
  * 4 capture/plant points (no visual)
* **Pickup beam:** script activates it whenever the factory is available, although it is authored `bAutoActivate=false`.
  The 10 `Pickup_FX` copies on health/overshield factories are never attached.

## Handoffs
* **RENDERING:**
  * `world.glb` + `render_index.json` (see the section above):
    * totems, KOTH rings, destructible states, pickup meshes, pickup effects;
    * per-mode visibility: apply `tdm_render_state` for the slice;
    * authored hidden/mover states.
  * Lightmaps: `lightmaps.json` (1,794 bindings, all three coefficient atlases as PNG) and `streets_lighting_audit.json`
    (vertex-1D list and no-light list).
  * BSP: `streets_bsp_audit.json`.
  * Decals, FX, lighting, post: `map_fx.json`, `streets_pickup_fx.json`, `lighting.json`, `postprocess.json`.
  * Materials: 36 unverified and 1 wrong are listed in the diff. The vector-channel translator issue is left to Rendering.
* **GAMEPLAY:**
  * Collision and physics: `physics.json`, `collision_pawn.glb` / `collision_weapon.glb`; 71 blocking volumes.
  * Movers that collide: the 3 rotating domes have bBlockActors=true; the SkyBeam actors block.
  * Placement and spawning: `gameplay.json` / `spawnpoints.json` (starts, clusters, objectives, modes).
  * Pickups and the destructible: `streets_pickup_factories.json`, `streets_destructibles.json`.
  * Mode logic: `streets_kismet.json` (EXT/CTF unhide, startup).
  * Bounds: the `extents` section of the complete manifest.
* **SYSTEMS:**
  * `audio.json` covers 70 emitters, 9 zones and reverb.
  * `streets_kismet.json` `audio_ops` covers 11 positional one-shot pools with delay ranges and 9 zone/reverb pairs.
  * Pickup and destructible audio/FX are in the M03 manifests.
  * Mover audio: none authored.
* **EXPERIMENTAL:** the `counts`, `extents` and `current_rebuild_comparison` sections of `mp_iac_streets_complete.json`;
  validation targets in `validate_m04.py` (15,918 checks) and
  `validate_smca_transforms.py` (1,906 components).
* **FUTURE HUD:** `future_hud_handoff.json`:
  * HUD and scoreboard movies.
  * Objective marker types and `UI_HudMarkers_p` materials.
  * Capture colours and announcer events.
  * 39 objective/score GFx symbols.
  * No radar or minimap assets exist.

## Still unknown or partial
* **Resolved since M04** (RE, read-only notes):
  * LightsVisibilitiesVolume: a baked light-visibility octree for light environments only.
  * Domination totems: visible only in DOM.
  * Objective marker class: hard-coded per objective class.
  * Pickup beam activation: script.
* **UNKNOWN:**
  * Flag/bomb factory at-rest visual (no PickupFactoryMesh authored).
  * Native attach offset of the ammo crate mesh.
  * Composition order of the destructible's spawned chunk/debris.
* **PROVISIONAL:**
  * Ammo crate mesh placed at the factory origin.
  * Health/overshield particle-mesh approximate matrices.
  * Destructible spawn matrices.
* **PARTIAL:** 36 materials that Rendering could not verify.
