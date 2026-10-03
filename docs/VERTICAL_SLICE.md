# WFC vertical slice — loading guide for the C++ reconstruction

Entry point: **`AssetTools/manifests/vertical_slice.json`** (all paths relative to `ExtractedAssets/`).
Rebuild: `AssetTools\bin\py\python.exe AssetTools\run_pipeline.py --only vs_map vs_character vs_weapon vs_validate` (~25 s).
Validation: `AssetTools/manifests/vertical_slice_validation.json` — 44 programmatic checks, 0 failures.
Preview renders (software-rasterised from the GLBs): `ExtractedAssets/VerticalSlice/_previews/`.

## Conventions (all slice files agree)
* glTF 2.0 / GLB, **Y-up, metres, right-handed**. `v_gltf = 0.01 * (x, z, y)_UE` (same as umodel's mesh export).
* UE transforms converted as `G = C·Mᵀ·C⁻¹`, `C = diag(0.01·swapYZ, 1)`; `props.json` also keeps the raw UE matrix.
* Textures are referenced by relative URI into `ExtractedAssets/content/...` (not duplicated), except the
  baked character textures in `Characters/Optimus/textures/`.
* glTF materials are a **PBR approximation**; the authoritative description is in `extras.wfc_material`
  + the per-bundle material JSON (roles: `base_color, normal, specular, emissive, mask, opacity, reflection`,
  each with `file`, `channels`, `role_source` = `param_name+graph` | `graph` | `name` | `cubemap`).

## Player character — `VerticalSlice/Characters/Optimus/`
| file | content |
|---|---|
| `robot.glb` | `RB_Optimus_A_SKELMESH`, 106 joints, 11.5k tris, 4.41 m, **75 clips** |
| `vehicle.glb` | `VH_OptimusPrime_SKEL`, 69 joints, 11.7k tris, **13 clips** |
| `character.json` | sockets (38, e.g. `WeaponSocket_Primary`), materials, clip catalogue, compatible sets, sounds |
| `textures/` | bakes of the customization shader (base colour / emissive / specular) |

* Robot and vehicle are **separate skeletons** (no shared bone names). Transformation: play
  `Transform_ToVehicle_ROBO` on the robot, swap to the vehicle mesh with `Transform_ToVehicle_VEH`
  (reverse: `Transform_ToRobot_VEH` → `Transform_ToRobot_ROBO`). The robot clip's end pose is truck-shaped
  (2.49 m tall vs the vehicle mesh's 2.44 m). `Transform_ToRobot_VEH` parks 3 vehicle bones
  (`C_Robo04/05/10_XT`) ~40 m away to hide them — authored, not an error.
* Clips carry `extras.category` (idle, walk, run, turn, jump, fall, land, boost_dodge, aim, fire, reload, equip,
  melee, hit_reaction, death, transform_*, vehicle_*) and `extras.additive` (`ADD_*` = delta poses).
* Compatibility was proven per AnimSet by track coverage **and bone-length proportions**
  (`animcompat.py`): 100 full-body robot sets / 2 vehicle sets accepted; 211 / 75 name-similar sets rejected
  (e.g. LightMedium `Shared_ROBO_ANIM`: 97.6% names match but 16% bone-length error).
* Firing: no body "fire" clip exists — the weapon plays `IonBlaster_Fire`; the body uses procedural
  SpineRecoil/RightHandRecoil (weapon.json) + the 9-way `Shooting_Aim_*` aim-offset grid.
* Sounds come from the game's own cue banks: `BL_TRANSFORM.OPTIMUS_BOT2VEH/VEH2BOT`,
  `BL_VEH_OPTIMUS_PRIME.*` (18), `BL_FS_LRG_BOT.*` (18 footstep/land/jump). Every wave resolves to a WAV.

## Weapon — `VerticalSlice/Weapons/IonBlaster/`
`weapon.glb` (34-bone skinned mesh, 8 clips: Fire/Equip/Drop/Idle/Reload…), `weapon.json`: authored
`TnWeaponIonBlaster` → `IonBlaster_WEPMESH` + `IonBlaster_WEPDATA`: event→cue→WAV (`WP_Fire` =
`BL_WPN_GUN_ION_BLASTER.SHOOT`, tail, low-ammo, dry-fire, fine-aim), event→anim, recoil, heat,
damage 15 instant-hit, 0.065 s interval, clip 50 / max 250, range 30000 uu, HUD icons (4), magazine mesh,
FX particle-system references (not converted), tracer material, impact decal.

## Map — `VerticalSlice/Maps/MP_IAC_Streets/`
| file | content |
|---|---|
| `world.glb` | level BSP (2,460 tris, 10 materials) + **1,952 placed props** (214 unique meshes instanced as nodes) |
| `collision.glb` | solid BSP + 71 BlockingVolume convex hulls |
| `props.json` | per prop: class, sub-level, mesh object, glTF, material overrides, UE + glTF matrix, collide/block |
| `collision.json` | all 101 volumes (blocking flag, world polygons), prop collision flags |
| `spawnpoints.json` | 60 team + 24 FFA starts, pickups (ammo 14, health 9, overshield 1), flag/bomb/domination/KOTH points, spawn clusters, triggers — with full properties |
| `lights.json`, `materials.json`, `map.json` | lights (1 actor; lighting is baked), resolved materials, summary |

* Sub-levels: `MP_IAC_Streets_BASE_m` (persistent: gameplay, volumes) streams `_ART_m` (geometry) and `_AUDIO_m`.
* All 84 player starts have ground ≤ 6 m below (median 0.84 m); 19 stand on invisible BlockingVolumes
  (matches their authored `Base` property) — load `collision.glb`, not only `world.glb`.
* Static-mesh simple collision bodies were not extracted: use the render mesh where `block` is true.

### Slice game mode: TDM pickup / objective state (added 2026-10-03, CONFIRMED)
The slice runs **TDM** (Civil War; DM is identical for these actors). Sources: the authored `RequiredGameRuleClass` and
Kismet, plus RE script decompilation (read-only `RE-Workspace/notes/MILESTONE04_STREETS_*`).

| actors | TDM state |
|---|---|
| ammo crates (14) | active: `PROP_NEU_AmmoPickup_STAT` mesh + `Pickup_FX` beam while available; respawn 30 s |
| health (9) | active: `HealthPickup_FX` while available; respawn 60 s |
| overshield (1) | active: `OvershieldPickup_FX` while available; respawn 120 s |
| flag (2) / bomb (1) factories | **Disabled**: hidden, no collision, no touch |
| health/overshield `Pickup_FX` copies (10) | never attached: do not draw |
| objective bases (4 InterpActors in `world.glb`) | **hidden**, still collide |
| domination totems (3), KOTH zones (5) | **hidden** |

* Drawn in TDM: 24 pickup effects + 14 crate meshes.
* A pickup's mesh and effect show while it is available and hide from pickup until `RespawnTime`. `SetPickupVisible` /
  `SetPickupHidden` drive this.
* Load from `render_index.json`: `tdm_render_state`, `pickup_fx_components`, `pickup_factory_visuals`.

## Known gaps / fallbacks
* Lightmaps / baked lighting not extracted → use a simple directional + ambient light.
* Particle systems, decals (25, listed with material + transform), emitters (8) are references only.
* Glass / fog / light-ray materials (23 of 164 map materials) have no base texture → constant fallback.
* Character colours are an approximation of the customization shader; reflection cubemaps not exported.
* KingOfTheHill zones have no brush (use their location; radius in props if present).

## Targeted evidence pass additions (2026-10-01)
* **`AssetTools/manifests/vs_evidence.json`**: answers for the open fidelity questions (boost FX/sockets/cues/anim
  switch, vehicle material chain + normal alpha + energon branch, fine-aim camera bands/bindings, robot speed/blend/
  dodge, transformation notifies/visibility/cues, map FX). Human summary: `docs/EVIDENCE_TARGETED_PASS.md`.
* **`Maps/MP_IAC_Streets/map_fx.json`**: 25 decals + 45 particle components (8 level emitters incl. the prefab vent
  `Emitter_5707`, 37 pickup/objective FX) with effective component props, prefab provenance, UE + glTF matrices,
  decal material chains, particle-system summaries.
* **`props.json` `section_materials`**: per-prop section materials read from the cooked `FStaticMeshElement`
  array (authoritative; 1952/1952). `world.glb` materials now use them (the `SideSupport_MATINST` short-name collision is fixed).
* Pipeline: `vs_map → vs_collision → vs_mapfx → … → vs_validate → vs_evidence` (`run_pipeline.py`). `vs_lightmap.py`
  remains a manual step (it joins against `props.json`).
* Superseded gap notes above: lightmaps ARE extracted (`vs_lightmap.py`, `lightmaps.json`); decals/emitters now have full
  authored records; particle systems have module data via `particles.py` (module role by order = PARTIAL).
* **`Maps/MP_IAC_Streets/audio.json`** (from `authored.db`): 70 ambient emitters, 9 Kismet audio zones (trigger polygons, reverb
  preset with full MASTER_WET DSP, one-shot pools), 32 cue graphs, 54/54 WAVs, player-start zone check. See `docs/AMBIENT_AUDIO_STREETS.md`.
* **`Maps/MP_IAC_Streets/lighting.json`** (from `authored.db`): all 268 lights (182 point, 83 spot, 2 directional, sky) with effective
  props and native placement, fog, channel analysis, character light environments, world post settings. Supersedes `lights.json`.
  **Colour correction:** cooked FColor is B,G,R,A; fog = RGB (116,91,234), dominant light = (117,117,255). See `docs/LIGHTING_STREETS.md`.
* **`Maps/MP_IAC_Streets/postprocess.json` + `postprocess_clut.png`**: scene chain (MotionBlur → Uber, world settings), governing BASE
  settings (bloom 0.1, distance DOF far 0.6 / 40000, motion blur off, CLUT), CLUT fit (keeps ~29% saturation), hologram + HUD chains.
  See `docs/POSTPROCESS_STREETS.md`.
* **`Maps/MP_IAC_Streets/physics.json` + `collision_pawn.glb` / `collision_weapon.glb`**: UE3 per-trace collision (authored simple hulls
  for 1667 props, per-poly for 25; volume and prop flags per trace type), physical materials, world physics (gravity -2940, RB x0.66,
  1/60 s, KillZ -75000), movers, destructible, Optimus PhysicsAssets. 18x lighter than collision.glb with identical spawn grounding.
  See `docs/PHYSICS_STREETS.md`.
* **`Maps/MP_IAC_Streets/gameplay.json`**: 6 modes (DM/TDM/CTF/KOTH/EXT/DOM with playlists, limits, rule classes), 60 team (30/30) + 24 FFA
  starts, 12 single-team spawn clusters, pickups with respawn/payload, objectives per mode with volumes, BASE Kismet (sky beam,
  EXT/CTF-only objective bases). See `docs/GAMEPLAY_STREETS.md`.
* **`Maps/MP_IAC_Streets/navigation.json` + `navigation.glb`**: the authored path network (123 nav points, 426 ReachSpecs). It is
  fragmented (40 islands, largest 8) because Streets has no PathNodes/cover/nav mesh/tactical data: no usable authored AI navigation.
  See `docs/NAVIGATION_STREETS.md`.
* **`Maps/MP_IAC_Streets/materials_authored.json`**: 176 materials / 48 masters with MIC chains, effective parameters (through
  MaterialFunctions), static-switch defaults, compiled-resource parameter names (114/115 TextureSet instances compile the TextureSet
  branch), TextureSets, texture files, dead overrides. See `docs/MATERIALS_STREETS.md`.
