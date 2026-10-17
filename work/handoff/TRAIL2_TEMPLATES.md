# Trail2 particle templates (AssetTools, 2026-10-18; read-only)

**For:** Rendering's Trail2 item (copy to Systems).

**Files:** manifest `AssetTools/manifests/particles/trail2_templates.json`, written by `scripts/wfc/trail2_templates.py`.

**Sources:**
- inventory.db / authored.db, with compiled modules from `pstream.py`;
- the MP per-map FX sets `Rebuild/work/render/<MP>/map_fx_runtime.json`;
- ExtractedAssets `VerticalSlice/{Weapons,Characters}` (MP chassis only);
- TransGame CDO refs;
- body notifies and sockets from Integration's merged `Rebuild/src/game/AnimNotifies.inc` + `MeshSockets.inc`.

## Counts

- 65 templates contain a `ParticleModuleTypeDataTrail2` emitter; **46 are referenced by MP**. That's 66 trail emitters and 162 LODs.
- **0 LODs are PARTIAL:**
  - every compiled module list parsed;
  - every distribution is assigned and CONFIRMED;
  - every parameter blob decoded.
- `status` / `partial_reasons` are on every LOD in the json.
- The 19 trail templates not referenced by MP are listed in the json (`mp_referenced` false): Trypticon / Omega / SatGuard / Comet /
  Plasma_Flares beams and similar.

## Engine facts (CONFIRMED: cooked enum and class table)

**No trail source / spawn / taper modules exist in this game's data:**
- The cooked `EParticleModuleId` enum (the compiled module ids) has no trail, spawn-per-unit or taper entry.
- `ParticleModuleTrailSource`, `ParticleModuleTrailSpawn` and `ParticleModuleSpawnPerUnit` exist only as Engine class defaults, with
  **0 cooked instances**.
- `ParticleModuleTrailTaper` doesn't exist in this engine at all.

**What that means:**
- There are no source socket / bone names, source offsets, inherit-rotation flags, spawn-per-unit values or taper method / factor to dump.
- A Trail2 emitter spawns like any sprite emitter, from `RequiredModule.SpawnRate` / BurstList (in the json).
- Its trail follows the emitter, i.e. the component's location. For body notifies that is the notify socket below.
- `bConnectToSource` (the type data) is the only "source" control. With no source module, what it connects to is HIGH: stock UE3
  Trail2 connects the newest particle to the emitter location.

**TypeDataTrail2 fields** (schema; Engine default in brackets):
- TessellationFactor [1], TessellationFactorDistance [0], TessellationStrength [1.0];
- TextureTile [1], Sheets [1], MaxTrailCount [1], MaxParticleInTrailCount [0];
- bConnectToSource [true], bEmitOnlyWhenMoving [true], bEmitterXAxisOrientation, bTilePerParticle, BillboardSettings.

The json records, per field, whether the value is authored, the Engine default, or the type zero.

**Values across the 162 MP LODs:**
- `BillboardSettings`: null (162)
- `MaxParticleInTrailCount`: 100 (156), 0 (6)
- `MaxTrailCount`: 1 (162)
- `Sheets`: 1 (162)
- `TessellationFactor`: 5 (56), 8 (45), 3 (18), 2 (16), 1 (15), 10 (12)
- `TessellationFactorDistance`: 0.0 (162)
- `TessellationStrength`: 1.0 (162)
- `TextureTile`: 1 (162)
- `bConnectToSource`: false (98), true (64)
- `bEmitOnlyWhenMoving`: false (116), true (46)
- `bEmitterXAxisOrientation`: false (162)
- `bTilePerParticle`: false (162)

- **TessellationFactorDistance** is 0 everywhere, so there is no distance tessellation.
- **MaxParticleInTrailCount 0:** 6 LODs (the third LOD of Energon_BlastCap_FX and Drain_Blast_FX, 3 emitters each) leave it unset, so
  it is the type zero. How the engine treats 0 there is UNKNOWN.

## MP templates

Material = `RequiredModule.Material`. Tess = TessellationFactor. Notify sockets: from AnimNotifies.inc, with counts of notify rows.

| template | trail emitters x LODs | material(s) | Tess | EmitOnlyWhenMoving | ConnectToSource | SpawnRate (LOD0) | notify sockets |
| `Shell_AssaultRifle_FX` (FX_AssaultRifle_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2 | True | True | [50.0] | ShellEject (2), ShellSocket (1) |
| `Tracer_AssaultRifle_FX` (FX_AssaultRifle_p) | 1 x 3 | Trail_Smoke_10_MAT_INST | 5 | False | False | [6.0] |  |
| `Shell_BurstRifle_FX` (FX_BurstRifle_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2 | True | True | [50.0] | ShellEject (1) |
| `Trail_CorruptorMangaRocket_FX` (FX_Corruptor_p) | 1 x 2 | Tracer_MOD_MAT | 1/2 | False | True | [30.0] |  |
| `Magazine_EMPShotgun_FX` (FX_EMPShotgun_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2/5 | True | False/True | [50.0] | MagazineSocket (2) |
| `Magazine_Shotgun_FX` (FX_EMPShotgun_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2/5 | True | True | [50.0] | MagazineSocket (1) |
| `Shell_EMPShotgun_FX` (FX_EMPShotgun_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2/5 | True | False/True | [50.0] | ShellSocket (2) |
| `Trail_EMPShotgun_FX` (FX_EMPShotgun_p) | 3 x 2/2/2 | Trail_Smoke_10_MAT_INST | 10 | False | False | [20.0] |  |
| `Magazine_HeavyMG_FX` (FX_ElectronPulseRifle_p) | 2 x 2/2 | Blaster_Trail_MAT_INST | 2/5 | True | False/True | [50.0] | MagazineSocket (1) |
| `Shell_ElectronPulseRifle_FX` (FX_ElectronPulseRifle_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2/5 | True | False/True | [50.0] | ShellSocket (4) |
| `Exp_Energy_MED_FX` (FX_Explosives_p) | 3 x 3/3/3 | Streak_Mat | 8 | False | False | [3.0] | L_Rocket1 (2), R_Rocket1 (2), C_Rocket1 (1), C_Rocket2 (1), C_Rocket3 (1) |
| `TF_Death_Energy_Med_FX` (FX_Explosives_p) | 3 x 3/3/3 | Streak_Mat | 8 | False | False | [10.0] |  |
| `TF_Death_LRG_FX` (FX_Explosives_p) | 3 x 4/4/4 | Streak_Mat | 8 | False | False | [876.25] |  |
| `TF_Death_MED_FX` (FX_Explosives_p) | 3 x 4/4/4 | Streak_Mat | 8 | False | False | [876.25] | TargetingSocket (1) |
| `Trail_FusionCannon_FX` (FX_FusionCannon_p) | 1 x 3 | Lightning_Anim_03_MAT | 1 | False | True | [10.0] |  |
| `Ammo_GrenadeLauncher_FX` (FX_GrenadeLauncher_p) | 1 x 2 | Blaster_Trail_MAT_INST | 5 | True | False/True | [50.0] | AmmoShell (1) |
| `Tracer_GrenadeLauncher_FX` (FX_GrenadeLauncher_p) | 1 x 2 | Trail_Distort_01_MAT_INST | 5 | False | True | [10.0] |  |
| `Hammer_Trail_DCPT_FX` (FX_Hammer_p) | 1 x 2 | Trail_Distort_01_MAT_INST | 10 | True | True | [5.0] | WeaponTrailSocket (1) |
| `Shell_HeavyPistol_FX` (FX_HeavyPistol_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2 | True | True | [50.0] | ShellEject (1) |
| `Tracer_HomRocket_FX` (FX_HomingRocket_p) | 1 x 3 | Trail_Distort_01_MAT_INST | 5 | False | False | [3.0] |  |
| `Magazine_IonBlaster_FX` (FX_IonBlaster_p) | 1 x 2 | Blaster_Trail_MAT_INST | 2/5 | True | True | [50.0] | MagSocket (1) |
| `Trail_KamikazeMine_FX` (FX_KamikazeMine_p) | 1 x 2 | Trail_Distort_01_MAT_INST | 5 | False | True | [5.0] |  |
| `Energon_BlastCap_FX` (FX_Level_Generic_p) | 3 x 3/3/3 | DefaultParticle, Streak_Mat | 1/5 | False/True | False/True | [10.0] |  |
| `Code_of_Power_FX` (FX_Multiplayer_p) | 2 x 2/2 | Spark_01_MAT_INST | 5 | True | False | [10.0] |  |
| `Drain_Blast_FX` (FX_Multiplayer_p) | 3 x 3/3/3 | DefaultParticle, Streak_Mat | 1/5/8 | False/True | False/True | [10.0] |  |
| `Prime_Target_FX` (FX_Multiplayer_p) | 1 x 2 | Spark_MAT | 5 | True | True | [4.0] |  |
| `WarCry_Buff_01_FX` (FX_Multiplayer_p) | 1 x 2 | Trail_Distort_MOD_01_MAT_INST | 3 | False | False | [60.0] |  |
| `WarCry_Buff_02_FX` (FX_Multiplayer_p) | 2 x 2/2 | Trail_Distort_MOD_01_MAT_INST | 5 | False | False | [20.0] |  |
| `WarCry_Buff_03_FX` (FX_Multiplayer_p) | 3 x 2/2/2 | Trail_Distort_MOD_01_MAT_INST | 5 | False | False | [20.0] |  |
| `Trails_Jet_A_FX` (FX_Navigation_p) | 1 x 2 | Tracer_MOD_MAT | 3 | True | True | [5.0] |  |
| `Trails_Jet_D_FX` (FX_Navigation_p) | 1 x 2 | Tracer_MOD_MAT | 3 | True | True | [5.0] | WingTipSocket_L (8), WingTipSocket_R (8), VaporTrailSocket_L (8), VaporTrailSocket_R (8) |
| `Trail_MangaRocket_Short_FX` (FX_OmegaSupremeAE_p) | 1 x 2 | Trail_Distort_MAT | 1 | False | True | [10.0] |  |
| `A_Plasma_Trail_FX` (FX_PlasmaCannon_p) | 1 x 2 | Spark_01_MAT_INST | 5 | False | True | [10.0] |  |
| `Flashbang_Trail_FX` (FX_PlasmaCannon_p) | 1 x 2 | Spark_01_MAT_INST | 5 | False | True | [10.0] |  |
| `HealGrenade_Trail_FX` (FX_PlasmaCannon_p) | 1 x 2 | Spark_01_MAT_INST | 5 | False | True | [10.0] |  |
| `Trail_PlasmaCannon_Lrg_FX` (FX_PlasmaCannon_p) | 1 x 2 | Tracer_MOD_MAT | 3 | False | True | [10.0] |  |
| `Trail_PlasmaCannon_Med_FX` (FX_PlasmaCannon_p) | 1 x 2 | Tracer_MOD_MAT | 3 | False | True | [10.0] |  |
| `Trail_PlasmaCannon_Sm_FX` (FX_PlasmaCannon_p) | 1 x 3 | Tracer_ADD_MAT | 3 | False | False | [10.0] |  |
| `Trail_PlasmaCannon_Sm_FX` (FX_SatGuard_p) | 1 x 3 | Tracer_ADD_MAT | 3 | False | False | [10.0] |  |
| `Tracer_SniperRifle_FX` (FX_Sniper_p) | 1 x 2 | Tracer_Smoke_MAT | 10 | True | False | [20.0] |  |
| `SwordTrail_Red_FX` (FX_Sword_p) | 1 x 2 | Trail_Blur_MAT | 5 | True | True | [50.0] | WeaponTrailSocket (24) |
| `Trail_TankCannon_FX` (FX_TankCannon_p) | 1 x 3 | Tracer_MOD_MAT | 1 | False | True | [10.0] |  |
| `Trails_Bumblebee_FX` (FX_Transformers_p) | 1 x 2 | Trail_Blur_MAT | 10 | True | True | [5.0] | ElbowSocket_L (58), ElbowSocket_R (58), KneeSideSocket_L (58), KneeSideSocket_R (58), WingLrgSocket_L (58), WingSmSocket_L (58) ... |
| `Trail_Missiles_FX` (FX_Trypticon_p) | 2 x 2/2 | Tracer_ADD_MAT, Tracer_MOD_MAT | 2/3 | False | True | [10.0] |  |
| `Tracer_TurretIon_FX` (FX_TurretIonBlaster_p) | 1 x 2 | Trail_Smoke_01_MAT_INST | 5 | False | False | [20.0] |  |
| `Rocket_Trail_FX` (FX_Weapons_p) | 1 x 2 | Spark_01_MAT_INST | 5 | False | True | [10.0] |  |

## Sockets and bones

`body_notify_attachments` holds each notify row: anim set, sequence, time, socket, attach flag. The top-level `sockets` table gives, for
each socket name used, every TR_ / WEP_ skeletal mesh that defines it, with its bone, offset (UU) and rotation (from MeshSockets.inc).

- The listing isn't narrowed to the meshes that play that AnimSet. Pick the row whose mesh is the pawn or weapon in use.
- Main users:
  - **Trails_Bumblebee_FX:** 483 notify rows on the transform, Nav_Boost and melee clips, across 11 sockets (Elbow / KneeSide / Wing
    sockets and others; full list in the json).
  - **SwordTrail_Red_FX:** 24 rows on `WeaponTrailSocket`, the energon-hammer and shield melee combos.
  - **Trails_Jet_D_FX:** 32 rows.
  - **Shell_*:** fire clips (ShellEject / ShellSocket). **Magazine_*:** reload clips (MagazineSocket).
- Templates with no notify row are spawned by code (projectile / weapon / CDO) or by the map.
- The `referenced_by` field says which: map_fx_runtime:<map>, weapon:<W>, character:<chassis>, TransGame CDO:<class>, anim_notify.
- Every MP template has at least one non-notify reference. The notify rows also include campaign-only TR_ sets.
