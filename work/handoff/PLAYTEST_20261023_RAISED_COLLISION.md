# Gameplay #18: authored pawn collision standing above the visible floor (AssetTools, 2026-10-23)

**For:** Gameplay (BOTTEST) and Systems (package). Decided by Integration rebuild-84.

**Method** (`work/playtest_20261023/hull_float_audit.py`; per-map data in `hull_float/<MAP>.json`):
- Every bot_nav surface sample (1 m grid) is attributed to the simple hull or volume top that supplies it, using the nav cell's height range ± 0.4 m.
- The visible render geometry (world.glb, hidden_game excluded) is probed straight down from it.
- **raised:** the visible floor is 0.5–5 m below, and nothing visible covers the spot within 0.6 m above.
- **large:** the visible floor is ≥ 5 m below (overhang edge or catwalk; probable false positives). Listed only.
- **Gameplay-confirmed:** `probe_positions.py` at Gameplay's robot feet positions (`gameplay_confirmed.json`, 12 placements). This adds Gorge SMCA_8751 CanyonFloor_B (1.11 m) and Debris SMCA_7038 PipeFloorRing (12.4 m, a hull filling a ring's hole). The Rust position stood 1.71 m above BSP floor, so that bot was airborne; not static data.

**Adaptation** (`pc_adapt_raised.py`):
- Raised and confirmed **simple-hull** placements switch to per-poly render collision, per placement; then bot_nav and bot_nav_air are rebuilt (`--overlay`).
- **Volumes with raised tops are kept authored and listed only** (Integration: adapted case by case on Gameplay's call).
- Output goes to `out/pc_adapt/<MAP>/`. The live ExtractedAssets files are unchanged (sha-checked on every map).
- Frozen overlay superset: `work/overlay_20261023c` (135 files, 199.8 MB, all 10 maps; supersedes 20261023b).

| map | simple hulls switched (of which Gameplay-confirmed) | raised m² on hulls | volumes listed (raised m²) |
|---|---|---|---|
| MP_ESC_BrokenHope | 8 (0) | 215 | 3 (325) |
| MP_ESC_Remnant | 4 (0) | 13 | 2 (30) |
| MP_IAC_Berth | 17 (0) | 70 | 4 (140) |
| MP_IAC_Rust | 29 (0) | 780 | 0 (0) |
| MP_IAC_Seed | 9 (0) | 435 | 0 (0) |
| MP_IAC_Streets | 40 (0) | 978 | 8 (101) |
| MP_KON_Molten | 11 (0) | 52 | 8 (22) |
| MP_ORB_Debris | 101 (8) | 4565 | 22 (942) |
| MP_UND_Complex | 24 (0) | 957 | 1 (4) |
| MP_UND_Gorge | 23 (4) | 186 | 3 (712) |

## MP_ESC_BrokenHope

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| BlockingVolume_13818 | BlockingVolume | 217 | 0.95 / 2.41 | 0 | list only (authored) |
| StaticMeshCollectionActor_10585 | ENV_CORE_CanyonFloor_A_STAT | 77 | 0.84 / 1.0 | 0 | per-poly |
| BlockingVolume_12476 | BlockingVolume | 73 | 0.87 / 2.1 | 0 | list only (authored) |
| StaticMeshCollectionActor_3463 | Dec_StepsFront_STAT | 46 | 0.61 / 0.77 | 0 | per-poly |
| BlockingVolume_10635 | BlockingVolume | 35 | 0.73 / 1.38 | 0 | list only (authored) |
| StaticMeshCollectionActor_3463 | Dec_StepsFront_STAT | 34 | 0.58 / 0.66 | 0 | per-poly |
| StaticMeshCollectionActor_3463 | Dec_StepsFront_STAT | 17 | 0.61 / 0.75 | 0 | per-poly |
| StaticMeshCollectionActor_11656 | Dec_StepsFront_STAT | 15 | 0.61 / 0.74 | 0 | per-poly |
| StaticMeshCollectionActor_3463 | Dec_StepsFront_STAT | 12 | 0.61 / 0.73 | 0 | per-poly |
| StaticMeshCollectionActor_3463 | Dec_StepsFront_STAT | 12 | 0.61 / 0.73 | 0 | per-poly |
| StaticMeshCollectionActor_10300 | ENV_CORE_InroomWall4Tunel_A_STAT | 2 | 0.65 / 0.77 | 0 | per-poly |

Large-gap only (overhang / catwalk, list only): BlockingVolume_10727 BlockingVolume (1 m²)

## MP_ESC_Remnant

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| BlockingVolume_6759 | BlockingVolume | 17 | 0.98 / 1.57 | 0 | list only (authored) |
| BlockingVolume_15798 | BlockingVolume | 13 | 0.58 / 1.11 | 0 | list only (authored) |
| StaticMeshCollectionActor_3455 | FloatingDebri_3072x4096_STAT | 8 | 0.55 / 0.68 | 0 | per-poly |
| StaticMeshCollectionActor_6980 | damageChunk_STAT | 3 | 0.9 / 1.26 | 0 | per-poly |
| StaticMeshCollectionActor_14845 | damageChunk_STAT | 1 | 0.79 / 0.79 | 0 | per-poly |
| StaticMeshCollectionActor_15028 | damageChunk_STAT | 1 | 0.74 / 0.74 | 0 | per-poly |

## MP_IAC_Berth

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| BlockingVolume_2074 | BlockingVolume | 39 | 3.28 / 4.75 | 40 | list only (authored) |
| BlockingVolume_15720 | BlockingVolume | 36 | 3.45 / 4.99 | 24 | list only (authored) |
| BlockingVolume_5152 | BlockingVolume | 33 | 3.44 / 4.77 | 35 | list only (authored) |
| BlockingVolume_7981 | BlockingVolume | 32 | 2.8 / 4.91 | 16 | list only (authored) |
| StaticMeshCollectionActor_15111 | HalfArchSideNub_STAT | 23 | 0.84 / 2.43 | 0 | per-poly |
| StaticMeshCollectionActor_4425 | HalfArchSideNub_STAT | 12 | 0.74 / 1.21 | 0 | per-poly |
| StaticMeshCollectionActor_1082 | HalfArchSideNub_STAT | 10 | 0.76 / 1.31 | 0 | per-poly |
| StaticMeshCollectionActor_1875 | ENV_CORE_PlatformPillar_A_STAT | 4 | 1.04 / 3.4 | 0 | per-poly |
| StaticMeshCollectionActor_6879 | HalfArchSideNub_STAT | 3 | 0.64 / 0.83 | 0 | per-poly |
| StaticMeshCollectionActor_15567 | Big3_Building3Trim_1792x1024x768_STAT | 3 | 2.05 / 2.09 | 0 | per-poly |
| StaticMeshCollectionActor_198 | Big3_Building3Trim_1792x1024x768_STAT | 2 | 1.64 / 2.09 | 1 | per-poly |
| StaticMeshCollectionActor_1875 | ENV_CORE_PlatformPillar_A_STAT | 2 | 1.3 / 2.05 | 0 | per-poly |
| StaticMeshCollectionActor_9696 | DoorWayCap_STAT | 2 | 1.82 / 1.89 | 0 | per-poly |
| StaticMeshCollectionActor_1875 | ENV_CORE_PlatformPillar_A_STAT | 2 | 0.67 / 0.8 | 0 | per-poly |
| StaticMeshCollectionActor_15567 | Big3_Building3Trim_1792x1024x768_STAT | 1 | 0.82 / 0.82 | 1 | per-poly |
| StaticMeshCollectionActor_5505 | ENV_CORE_PlatformPillar_A_STAT | 1 | 0.53 / 0.53 | 0 | per-poly |
| StaticMeshCollectionActor_1875 | ENV_CORE_PlatformPillar_A_STAT | 1 | 2.91 / 2.91 | 0 | per-poly |
| StaticMeshCollectionActor_5505 | ENV_CORE_PlatformPillar_A_STAT | 1 | 4.52 / 4.52 | 0 | per-poly |
| StaticMeshCollectionActor_5872 | PROP_IAC_SideSupp01_STAT | 1 | 1.86 / 1.86 | 0 | per-poly |
| StaticMeshCollectionActor_1082 | HalfArchSideNub_STAT | 1 | 0.64 / 0.64 | 0 | per-poly |
| StaticMeshCollectionActor_1875 | ENV_CORE_PlatformPillar_A_STAT | 1 | 0.53 / 0.53 | 0 | per-poly |

Large-gap only (overhang / catwalk, list only): BlockingVolume_12025 BlockingVolume (1 m²)

## MP_IAC_Rust

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_5741 | FloorTrim_Straight_01_STAT | 73 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_8734 | FloorTrim_Straight_01_STAT | 73 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_2398 | FloorTrim_Straight_01_STAT | 72 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_8734 | FloorTrim_Straight_01_STAT | 72 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_8734 | FloorTrim_Straight_01_STAT | 72 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_10439 | FloorTrim_Straight_01_STAT | 71 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_5741 | FloorTrim_Straight_01_STAT | 68 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_6801 | GroundChunk_Ramp2_STAT | 41 | 0.95 / 2.16 | 0 | per-poly |
| StaticMeshCollectionActor_6801 | GroundChunk_Ramp2_STAT | 40 | 1.08 / 2.16 | 0 | per-poly |
| StaticMeshCollectionActor_6801 | GroundChunk_Ramp2_STAT | 39 | 0.99 / 2.16 | 0 | per-poly |
| StaticMeshCollectionActor_6801 | GroundChunk_Ramp2_STAT | 39 | 0.97 / 2.16 | 0 | per-poly |
| StaticMeshCollectionActor_6801 | GroundChunk_Ramp2_STAT | 38 | 0.92 / 2.16 | 0 | per-poly |
| StaticMeshCollectionActor_2398 | FloorTrim_Straight_01_STAT | 25 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_5741 | FloorTrim_Straight_01_STAT | 18 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_8498 | PROP_NEU_MachinePress_A_STAT | 7 | 1.7 / 1.94 | 0 | per-poly |
| StaticMeshCollectionActor_6333 | ArchSupportTipBroken_STAT | 5 | 1.9 / 3.0 | 4 | per-poly |
| StaticMeshCollectionActor_8972 | GroundVent_STAT | 4 | 3.47 / 4.04 | 6 | per-poly |
| StaticMeshCollectionActor_9367 | Arch_4096_STAT | 4 | 0.74 / 4.89 | 2 | per-poly |
| StaticMeshCollectionActor_3497 | ENV_UND_CanyonWall_C_STAT | 4 | 0.93 / 0.93 | 0 | per-poly |
| StaticMeshCollectionActor_9281 | Arch_4096_STAT | 2 | 0.54 / 0.54 | 4 | per-poly |
| StaticMeshCollectionActor_9281 | Arch_4096_STAT | 2 | 0.91 / 1.28 | 4 | per-poly |
| StaticMeshCollectionActor_9367 | Arch_4096_STAT | 2 | 0.54 / 0.54 | 4 | per-poly |
| StaticMeshCollectionActor_11711 | Terminal_Door_STAT | 2 | 0.73 / 0.73 | 0 | per-poly |
| StaticMeshCollectionActor_8498 | Crate_V2_STAT | 2 | 4.78 / 4.78 | 0 | per-poly |
| StaticMeshCollectionActor_9281 | Arch_4096_STAT | 1 | 3.8 / 3.8 | 4 | per-poly |
| StaticMeshCollectionActor_9367 | Arch_4096_STAT | 1 | 1.1 / 1.1 | 3 | per-poly |
| StaticMeshCollectionActor_11132 | modPlatform_Trim_1024_STAT | 1 | 0.65 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_12869 | Crate_V2_STAT | 1 | 0.65 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_4019 | Crate_STAT | 1 | 4.81 / 4.81 | 0 | per-poly |

Large-gap only (overhang / catwalk, list only): StaticMeshCollectionActor_15581 GroundVent_STAT (8 m²), StaticMeshCollectionActor_9281 Arch_4096_STAT (4 m²), StaticMeshCollectionActor_9367 Arch_4096_STAT (4 m²), StaticMeshCollectionActor_12869 Crate_V2_STAT (1 m²), StaticMeshCollectionActor_8498 Crate_V2_STAT (1 m²)

## MP_IAC_Seed

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_9851 | GroundChunk_Sink_STAT | 128 | 0.69 / 1.58 | 8 | per-poly |
| StaticMeshCollectionActor_7974 | GroundChunk_Sink_STAT | 105 | 0.86 / 1.54 | 2 | per-poly |
| StaticMeshCollectionActor_8335 | GroundChunk_Ramp2_STAT | 32 | 0.87 / 1.56 | 0 | per-poly |
| StaticMeshCollectionActor_2293 | GroundChunk_Ramp2_STAT | 29 | 0.96 / 1.72 | 0 | per-poly |
| StaticMeshCollectionActor_2071 | GroundChunk_Ramp2_STAT | 25 | 0.96 / 1.42 | 0 | per-poly |
| StaticMeshCollectionActor_2293 | GroundChunk_Ramp2_STAT | 24 | 0.74 / 1.76 | 0 | per-poly |
| StaticMeshCollectionActor_12197 | modPlatform_Straight_2048_STAT | 16 | 0.6 / 0.6 | 0 | per-poly |
| StaticMeshCollectionActor_12197 | modPlatform_Straight_2048_STAT | 15 | 0.57 / 0.57 | 0 | per-poly |
| StaticMeshCollectionActor_12918 | CoolantStepCurve_STAT | 13 | 0.61 / 0.76 | 0 | per-poly |
| StaticMeshCollectionActor_15039 | CoolantStepCurve_STAT | 12 | 0.6 / 0.79 | 0 | per-poly |
| StaticMeshCollectionActor_8335 | GroundChunk_Ramp2_STAT | 9 | 0.74 / 1.42 | 0 | per-poly |
| StaticMeshCollectionActor_15641 | Wall_Side2_STAT | 9 | 1.31 / 1.76 | 0 | per-poly |
| StaticMeshCollectionActor_15039 | CoolantStepCurve_STAT | 5 | 0.57 / 0.68 | 0 | per-poly |
| StaticMeshCollectionActor_16055 | column_Base_STAT | 4 | 4.21 / 4.34 | 0 | per-poly |
| StaticMeshCollectionActor_14727 | Scrappage3_STAT | 3 | 0.7 / 0.81 | 0 | per-poly |
| StaticMeshCollectionActor_15039 | CoolantStepCurve_STAT | 3 | 0.56 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_12918 | CoolantStepCurve_STAT | 2 | 0.56 / 0.57 | 0 | per-poly |
| StaticMeshCollectionActor_12918 | CoolantStepCurve_STAT | 1 | 0.71 / 0.71 | 0 | per-poly |

## MP_IAC_Streets

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_4284 | ENV_CraterFlat_STAT | 194 | 0.91 / 3.53 | 0 | per-poly |
| StaticMeshCollectionActor_11477 | ENV_CraterUpNoRing_STAT | 115 | 1.16 / 1.59 | 0 | per-poly |
| StaticMeshCollectionActor_12089 | modPlatform_Straight_2048_STAT | 114 | 0.65 / 1.67 | 0 | per-poly |
| StaticMeshCollectionActor_12153 | ENV_CraterUpNoRing_STAT | 106 | 0.72 / 1.22 | 0 | per-poly |
| StaticMeshCollectionActor_7270 | stairsDestuction_single_STAT | 49 | 0.79 / 2.09 | 0 | per-poly |
| StaticMeshCollectionActor_12987 | craterDebris_STAT | 44 | 0.72 / 2.84 | 0 | per-poly |
| StaticMeshCollectionActor_7116 | ENV_CraterUpNoRing_STAT | 43 | 0.93 / 1.31 | 0 | per-poly |
| StaticMeshCollectionActor_12944 | ENV_CraterUpNoRing_STAT | 42 | 0.91 / 1.25 | 0 | per-poly |
| StaticMeshCollectionActor_11932 | Building_ONE_Base_STAT | 42 | 0.95 / 1.25 | 0 | per-poly |
| StaticMeshCollectionActor_12089 | modPlatform_Straight_2048_STAT | 39 | 0.65 / 2.76 | 0 | per-poly |
| StaticMeshCollectionActor_7252 | CanyonFloor_B_Destroy_STAT | 39 | 1.02 / 2.89 | 0 | per-poly |
| StaticMeshCollectionActor_7252 | CanyonFloor_B_Destroy_STAT | 31 | 2.68 / 3.21 | 0 | per-poly |
| StaticMeshCollectionActor_4824 | ENV_CORE_InroomWall_C_STAT | 30 | 0.71 / 1.09 | 0 | per-poly |
| BlockingVolume_2781 | BlockingVolume | 29 | 0.55 / 0.59 | 0 | list only (authored) |
| BlockingVolume_725 | BlockingVolume | 25 | 2.87 / 2.87 | 0 | list only (authored) |
| BlockingVolume_8426 | BlockingVolume | 23 | 3.07 / 4.99 | 47 | list only (authored) |
| StaticMeshCollectionActor_11477 | ENV_CraterUpNoRing_STAT | 17 | 0.72 / 1.86 | 0 | per-poly |
| BlockingVolume_7015 | BlockingVolume | 14 | 0.59 / 1.23 | 4 | list only (authored) |
| StaticMeshCollectionActor_11250 | ArchTop01_STAT | 8 | 0.52 / 0.52 | 0 | per-poly |
| StaticMeshCollectionActor_11477 | BridgeSupport_01_STAT | 8 | 2.13 / 2.93 | 0 | per-poly |
| StaticMeshCollectionActor_11768 | Debris2_STAT | 7 | 0.59 / 0.67 | 0 | per-poly |
| StaticMeshCollectionActor_12987 | Debris2_STAT | 7 | 0.67 / 0.74 | 0 | per-poly |
| StaticMeshCollectionActor_12944 | Prop_NEU_CitySigns_10_STAT | 6 | 1.26 / 1.83 | 3 | per-poly |
| StaticMeshCollectionActor_12745 | Debris2_STAT | 5 | 0.62 / 0.67 | 0 | per-poly |
| StaticMeshCollectionActor_6173 | Iacon_Trim_01_Corner_A_STAT | 4 | 1.21 / 4.61 | 0 | per-poly |
| BlockingVolume_5272 | BlockingVolume | 4 | 1.29 / 1.37 | 244 | list only (authored) |
| StaticMeshCollectionActor_1341 | CurveWall_7168_STAT | 3 | 0.5 / 0.55 | 0 | per-poly |
| StaticMeshCollectionActor_10306 | PowerTube_Metal_03_STAT | 3 | 0.74 / 0.79 | 0 | per-poly |
| StaticMeshCollectionActor_12987 | craterDebris_STAT | 3 | 1.43 / 1.49 | 0 | per-poly |
| BlockingVolume_6291 | BlockingVolume | 3 | 3.12 / 4.96 | 6 | list only (authored) |
| StaticMeshCollectionActor_1341 | CurveWall_7168_STAT | 2 | 0.5 / 0.5 | 0 | per-poly |
| StaticMeshCollectionActor_9818 | PROP_ORB_GiantPillar_STAT | 2 | 0.74 / 0.91 | 0 | per-poly |
| StaticMeshCollectionActor_14438 | PROP_ORB_GiantPillar_STAT | 2 | 2.21 / 2.59 | 0 | per-poly |
| BlockingVolume_15829 | BlockingVolume | 2 | 0.96 / 1.13 | 0 | list only (authored) |
| StaticMeshCollectionActor_1341 | CurveWall_7168_STAT | 1 | 0.5 / 0.5 | 0 | per-poly |
| StaticMeshCollectionActor_1341 | CurveWall_7168_STAT | 1 | 0.61 / 0.61 | 0 | per-poly |
| StaticMeshCollectionActor_1908 | CurveWall_7168_STAT | 1 | 0.61 / 0.61 | 0 | per-poly |
| StaticMeshCollectionActor_1908 | CurveWall_7168_STAT | 1 | 0.61 / 0.61 | 0 | per-poly |
| StaticMeshCollectionActor_1908 | CurveWall_7168_STAT | 1 | 0.61 / 0.61 | 0 | per-poly |
| StaticMeshCollectionActor_1325 | DecoSphereHalf01_STAT | 1 | 0.67 / 0.67 | 0 | per-poly |
| StaticMeshCollectionActor_1325 | DecoSphereHalf01_STAT | 1 | 0.71 / 0.71 | 0 | per-poly |
| StaticMeshCollectionActor_10455 | Big3_Building3Piece2_3584x2048x1792_STAT | 1 | 0.54 / 0.54 | 0 | per-poly |
| StaticMeshCollectionActor_9818 | PROP_ORB_GiantPillar_STAT | 1 | 0.57 / 0.57 | 0 | per-poly |
| StaticMeshCollectionActor_11150 | PROP_IAC_SideSupp01_STAT | 1 | 0.68 / 0.68 | 0 | per-poly |
| StaticMeshCollectionActor_13491 | ENV_CraterUpNoRing_STAT | 1 | 0.5 / 0.5 | 0 | per-poly |
| StaticMeshCollectionActor_11150 | PROP_IAC_SideSupp01_STAT | 1 | 0.65 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_11145 | ENV_CORE_InroomWall_C_STAT | 1 | 0.52 / 0.52 | 0 | per-poly |
| BlockingVolume_6959 | BlockingVolume | 1 | 0.98 / 0.98 | 0 | list only (authored) |

Large-gap only (overhang / catwalk, list only): StaticMeshCollectionActor_1325 PROP_IAC_SideSupp01_STAT (2 m²)

## MP_KON_Molten

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_8183 | FloatingDebri_4096x6144_STAT | 14 | 1.02 / 2.96 | 5 | per-poly |
| StaticMeshCollectionActor_16111 | FloatingDebri_4096x6144_STAT | 9 | 0.85 / 1.61 | 11 | per-poly |
| BlockingVolume_14742 | BlockingVolume | 7 | 0.79 / 0.99 | 5 | list only (authored) |
| StaticMeshCollectionActor_10071 | FloatingDebri_4096x6144_STAT | 6 | 0.6 / 0.94 | 0 | per-poly |
| StaticMeshCollectionActor_8183 | FloatingDebri_3072x4096_B_STAT | 6 | 1.13 / 2.59 | 0 | per-poly |
| StaticMeshCollectionActor_8183 | FloatingDebri_4096x6144_STAT | 5 | 0.83 / 1.19 | 5 | per-poly |
| BlockingVolume_16038 | BlockingVolume | 4 | 1.16 / 1.73 | 0 | list only (authored) |
| BlockingVolume_2697 | BlockingVolume | 4 | 0.67 / 0.7 | 0 | list only (authored) |
| StaticMeshCollectionActor_16111 | FloatingDebri_3072x4096_B_STAT | 3 | 0.91 / 1.45 | 2 | per-poly |
| BlockingVolume_6858 | BlockingVolume | 3 | 0.83 / 1.79 | 0 | list only (authored) |
| StaticMeshCollectionActor_16111 | FloatingDebri_4096x6144_STAT | 2 | 0.68 / 0.74 | 8 | per-poly |
| StaticMeshCollectionActor_9730 | FloatingDebri_4096x6144_STAT | 2 | 0.81 / 1.09 | 4 | per-poly |
| StaticMeshCollectionActor_11800 | Saucer_8192_STAT | 2 | 2.47 / 2.92 | 0 | per-poly |
| StaticMeshCollectionActor_10071 | ENV_CORE_CliffWall_B_STAT | 2 | 0.74 / 0.76 | 0 | per-poly |
| StaticMeshCollectionActor_10095 | Crate_V2_STAT | 1 | 0.83 / 0.83 | 0 | per-poly |
| BlockingVolume_9059 | BlockingVolume | 1 | 0.78 / 0.78 | 2 | list only (authored) |
| BlockingVolume_14475 | BlockingVolume | 1 | 0.89 / 0.89 | 1 | list only (authored) |
| BlockingVolume_11059 | BlockingVolume | 1 | 0.65 / 0.65 | 0 | list only (authored) |
| BlockingVolume_10034 | BlockingVolume | 1 | 0.64 / 0.64 | 0 | list only (authored) |

Large-gap only (overhang / catwalk, list only): StaticMeshCollectionActor_16111 FloatingDebri_Lcorner_B_STAT (6 m²), StaticMeshCollectionActor_16111 FloatingDebri_4096x6144_STAT (6 m²), BlockingVolume_13205 BlockingVolume (4 m²), BlockingVolume_3306 BlockingVolume (3 m²), BlockingVolume_14766 BlockingVolume (3 m²), BlockingVolume_4177 BlockingVolume (3 m²), StaticMeshCollectionActor_9730 FloatingDebri_Lcorner_B_STAT (2 m²), BlockingVolume_15641 BlockingVolume (1 m²), StaticMeshCollectionActor_9730 FloatingDebri_Lcorner_B_STAT (1 m²), BlockingVolume_4940 BlockingVolume (1 m²), BlockingVolume_8266 BlockingVolume (1 m²)

## MP_ORB_Debris

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_8804 | ENV_COR_BossBottomDisc_STAT | 1546 | 1.46 / 1.63 | 0 | per-poly |
| StaticMeshCollectionActor_2340 | ENV_COR_BossBottomDisc_STAT | 772 | 1.06 / 1.07 | 0 | per-poly |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | 767 | 0.61 / 0.73 | 0 | per-poly |
| BlockingVolume_9211 | BlockingVolume | 216 | 0.73 / 1.98 | 0 | list only (authored) |
| StaticMeshCollectionActor_2870 | Mini_Cable_Hang01_STAT | 141 | 1.74 / 4.89 | 32 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorAEdge_STAT | 122 | 1.0 / 4.47 | 1 | per-poly |
| BlockingVolume_7035 | BlockingVolume | 113 | 0.96 / 3.34 | 4 | list only (authored) |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorAEdge_STAT | 104 | 0.99 / 2.16 | 0 | per-poly |
| BlockingVolume_4353 | BlockingVolume | 104 | 1.14 / 4.57 | 0 | list only (authored) |
| BlockingVolume_10751 | BlockingVolume | 97 | 0.88 / 4.69 | 15 | list only (authored) |
| StaticMeshCollectionActor_3343 | ArchSupportBroken_STAT | 71 | 0.67 / 1.28 | 0 | per-poly |
| BlockingVolume_12486 | BlockingVolume | 65 | 0.65 / 1.01 | 0 | list only (authored) |
| StaticMeshCollectionActor_10335 | ArchSupportBroken_STAT | 59 | 0.73 / 1.23 | 0 | per-poly |
| BlockingVolume_15133 | BlockingVolume | 58 | 0.54 / 1.38 | 0 | list only (authored) |
| StaticMeshCollectionActor_1236 | damageChunk_STAT | 46 | 0.97 / 1.9 | 2 | per-poly |
| BlockingVolume_1139 | BlockingVolume | 46 | 0.59 / 3.29 | 11 | list only (authored) |
| StaticMeshCollectionActor_3783 | PROP_MegatronShipWing_STAT | 43 | 0.71 / 4.9 | 10 | per-poly |
| BlockingVolume_3921 | BlockingVolume | 42 | 0.78 / 2.19 | 0 | list only (authored) |
| BlockingVolume_9092 | BlockingVolume | 40 | 0.79 / 2.56 | 0 | list only (authored) |
| StaticMeshCollectionActor_6694 | PROP_MegatronShipWing_STAT | 39 | 0.69 / 1.9 | 14 | per-poly |
| StaticMeshCollectionActor_10904 | CanyonFloor_B_Destroy_STAT | 38 | 0.76 / 1.25 | 0 | per-poly |
| BlockingVolume_331 | BlockingVolume | 37 | 3.33 / 3.45 | 2 | list only (authored) |
| BlockingVolume_9768 | BlockingVolume | 37 | 0.65 / 1.75 | 0 | list only (authored) |
| StaticMeshCollectionActor_10904 | CanyonFloor_B_Destroy_STAT | 35 | 0.77 / 1.3 | 0 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 30 | 1.19 / 1.61 | 0 | per-poly |
| StaticMeshCollectionActor_10335 | TubeDebris_07_STAT | 29 | 1.91 / 4.2 | 2 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 29 | 1.16 / 1.52 | 0 | per-poly |
| StaticMeshCollectionActor_290 | damageChunk_STAT | 27 | 0.98 / 1.58 | 0 | per-poly |
| BlockingVolume_2483 | BlockingVolume | 27 | 1.23 / 1.8 | 1 | list only (authored) |
| StaticMeshCollectionActor_4966 | hoh_ClosedWallFlat_Interior_alt_STAT | 25 | 1.11 / 1.89 | 0 | per-poly |
| StaticMeshCollectionActor_4966 | hoh_ClosedWallFlat_Interior_alt_STAT | 24 | 1.14 / 2.52 | 0 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 23 | 1.18 / 1.56 | 0 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 23 | 1.27 / 1.54 | 0 | per-poly |
| StaticMeshCollectionActor_10870 | hoh_ClosedWallFlat_Interior_alt_STAT | 22 | 1.04 / 2.0 | 0 | per-poly |
| StaticMeshCollectionActor_4811 | coreRing_STAT | 22 | 1.2 / 1.56 | 0 | per-poly |
| StaticMeshCollectionActor_4811 | coreRing_STAT | 21 | 1.27 / 1.61 | 0 | per-poly |
| StaticMeshCollectionActor_5730 | hoh_ClosedWallFlat_Interior_alt_STAT | 21 | 1.18 / 1.99 | 0 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 21 | 1.29 / 1.6 | 0 | per-poly |
| StaticMeshCollectionActor_14610 | coreRing_STAT | 20 | 1.24 / 1.58 | 0 | per-poly |
| BlockingVolume_4583 | BlockingVolume | 17 | 0.71 / 1.25 | 0 | list only (authored) |
| StaticMeshCollectionActor_4586 | ENV_ORB_SliceUpperD_STAT | 16 | 0.83 / 2.74 | 2 | per-poly |
| StaticMeshCollectionActor_10209 | PowerTube_Metal_03_STAT | 15 | 0.91 / 3.37 | 1 | per-poly |
| StaticMeshCollectionActor_10904 | TubeDebris_07_STAT | 15 | 0.87 / 3.56 | 1 | per-poly |
| StaticMeshCollectionActor_12024 | TubeDebris_07_STAT | 14 | 0.6 / 3.62 | 0 | per-poly |
| StaticMeshCollectionActor_15187 | ENV_ORB_SliceUpperD_STAT | 13 | 0.7 / 1.69 | 10 | per-poly |
| StaticMeshCollectionActor_4586 | ENV_ORB_SliceUpperD_STAT | 13 | 1.1 / 4.23 | 4 | per-poly |
| StaticMeshCollectionActor_4586 | damageChunk_STAT | 13 | 0.76 / 1.35 | 2 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorBEnd_STAT | 13 | 0.73 / 2.9 | 0 | per-poly |
| StaticMeshCollectionActor_5145 | ENV_ORB_SliceUpperD_STAT | 12 | 0.74 / 2.3 | 5 | per-poly |
| StaticMeshCollectionActor_12024 | TubeDebris_07_STAT | 12 | 0.56 / 2.87 | 0 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorBEnd_STAT | 12 | 0.77 / 1.41 | 0 | per-poly |
| StaticMeshCollectionActor_9710 | TunnelPipeA_Debri_B_STAT | 12 | 0.83 / 1.74 | 0 | per-poly |
| BlockingVolume_6923 | BlockingVolume | 12 | 0.73 / 1.3 | 0 | list only (authored) |
| StaticMeshCollectionActor_12024 | ENV_ORB_SliceUpperD_STAT | 11 | 0.92 / 3.42 | 9 | per-poly |
| StaticMeshCollectionActor_4586 | ENV_ORB_SliceUpperD_STAT | 11 | 0.77 / 2.25 | 2 | per-poly |
| StaticMeshCollectionActor_1236 | PowerTube_Metal_03_STAT | 11 | 1.89 / 2.02 | 0 | per-poly |
| StaticMeshCollectionActor_7579 | Ship_FloorPanel_01_Destory_STAT | 11 | 0.86 / 1.76 | 0 | per-poly |
| BlockingVolume_12921 | BlockingVolume | 11 | 1.43 / 1.81 | 9 | list only (authored) |
| StaticMeshCollectionActor_1774 | ENV_ORB_SliceUpperD_STAT | 10 | 0.74 / 1.87 | 10 | per-poly |
| StaticMeshCollectionActor_9315 | ElevatorPodBase02_STAT | 9 | 1.99 / 2.17 | 0 | per-poly |
| StaticMeshCollectionActor_3105 | ElevatorPodBase02_STAT | 9 | 1.98 / 2.06 | 0 | per-poly |
| StaticMeshCollectionActor_3419 | CanyonFloor_B_Destroy_STAT | 9 | 0.65 / 0.74 | 0 | per-poly |
| StaticMeshCollectionActor_9710 | TunnelPipeA_Debri_STAT | 9 | 3.82 / 4.93 | 0 | per-poly |
| StaticMeshCollectionActor_1774 | ENV_ORB_SliceUpperD_STAT | 8 | 0.71 / 0.93 | 10 | per-poly |
| StaticMeshCollectionActor_5145 | ENV_ORB_SliceUpperD_STAT | 8 | 0.68 / 1.58 | 3 | per-poly |
| StaticMeshCollectionActor_705 | TubeJoint_Road_REG_STAT | 8 | 0.77 / 0.77 | 0 | per-poly |
| StaticMeshCollectionActor_8803 | TubeDebris_07_STAT | 8 | 1.11 / 2.39 | 0 | per-poly |
| StaticMeshCollectionActor_9710 | CanyonFloor_B_Destroy_STAT | 8 | 0.84 / 0.94 | 0 | per-poly |
| StaticMeshCollectionActor_7579 | Ship_FloorPanel_01_Destory_STAT | 8 | 1.26 / 1.8 | 0 | per-poly |
| StaticMeshCollectionActor_10209 | MiniCables_01_STAT | 7 | 1.15 / 1.91 | 15 | per-poly |
| StaticMeshCollectionActor_15156 | DebrisFloor_01_STAT | 7 | 1.76 / 2.49 | 2 | per-poly |
| StaticMeshCollectionActor_15156 | DebrisFloor_01_STAT | 6 | 0.73 / 0.73 | 16 | per-poly |
| StaticMeshCollectionActor_4586 | ENV_ORB_SliceUpperD_STAT | 6 | 0.8 / 1.64 | 3 | per-poly |
| StaticMeshCollectionActor_705 | TubeJoint_Road_REG_STAT | 6 | 0.7 / 0.77 | 0 | per-poly |
| StaticMeshCollectionActor_10269 | TubeDebris_01_STAT | 6 | 0.84 / 1.17 | 0 | per-poly |
| BlockingVolume_530 | BlockingVolume | 6 | 0.89 / 2.2 | 0 | list only (authored) |
| StaticMeshCollectionActor_3012 | DebrisFloor_01_STAT | 5 | 0.72 / 0.72 | 17 | per-poly |
| StaticMeshCollectionActor_15187 | ENV_ORB_SliceOuter2_STAT | 5 | 1.29 / 2.3 | 2 | per-poly |
| StaticMeshCollectionActor_92 | TubeDebris_07_STAT | 5 | 1.17 / 2.33 | 0 | per-poly |
| StaticMeshCollectionActor_8803 | TubeDebris_07_STAT | 5 | 0.99 / 1.02 | 0 | per-poly |
| StaticMeshCollectionActor_12024 | TubeDebris_01_STAT | 5 | 0.9 / 1.33 | 0 | per-poly |
| StaticMeshCollectionActor_3012 | DebrisFloor_01_STAT | 5 | 0.72 / 0.72 | 0 | per-poly |
| StaticMeshCollectionActor_3343 | DecoSphereHalf01_STAT | 5 | 1.18 / 1.94 | 0 | per-poly |
| StaticMeshCollectionActor_10335 | DecoSphereHalf01_STAT | 5 | 0.64 / 2.15 | 0 | per-poly |
| StaticMeshCollectionActor_15187 | ENV_ORB_SliceOuter2_STAT | 4 | 1.81 / 2.59 | 1 | per-poly |
| StaticMeshCollectionActor_12024 | TubeDebris_01_STAT | 4 | 0.95 / 1.55 | 0 | per-poly |
| StaticMeshCollectionActor_10335 | Mini_Cable_Hang01_STAT | 4 | 1.95 / 2.38 | 0 | per-poly |
| StaticMeshCollectionActor_6686 | ENV_COR_BossBottomDisc_STAT | 4 | 1.03 / 1.06 | 0 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorBEnd_STAT | 4 | 1.65 / 3.09 | 0 | per-poly |
| StaticMeshCollectionActor_7579 | Ship_FloorPanel_01_Destory_STAT | 4 | 0.59 / 0.89 | 0 | per-poly |
| BlockingVolume_7649 | BlockingVolume | 4 | 2.72 / 3.44 | 2 | list only (authored) |
| StaticMeshCollectionActor_10269 | TubeDebris_07_STAT | 3 | 1.5 / 2.1 | 2 | per-poly |
| StaticMeshCollectionActor_5145 | ENV_ORB_SliceUpperE_STAT | 3 | 0.53 / 3.5 | 0 | per-poly |
| StaticMeshCollectionActor_4586 | damageChunk_STAT | 3 | 0.69 / 0.73 | 0 | per-poly |
| StaticMeshCollectionActor_3419 | CanyonFloor_B_Destroy_STAT | 3 | 0.55 / 0.7 | 0 | per-poly |
| StaticMeshCollectionActor_15537 | PowerTube_Metal_03_STAT | 3 | 1.03 / 4.65 | 0 | per-poly |
| BlockingVolume_5211 | BlockingVolume | 3 | 0.95 / 1.01 | 2 | list only (authored) |
| BlockingVolume_10684 | BlockingVolume | 3 | 0.71 / 4.51 | 2 | list only (authored) |
| StaticMeshCollectionActor_92 | TubeDebris_07_STAT | 2 | 0.97 / 1.16 | 0 | per-poly |
| StaticMeshCollectionActor_9148 | TubeDebris_01_STAT | 2 | 0.89 / 1.24 | 0 | per-poly |
| StaticMeshCollectionActor_290 | TubeDebris_06_STAT | 2 | 0.61 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_15156 | DebrisFloor_01_STAT | 2 | 1.93 / 2.01 | 0 | per-poly |
| StaticMeshCollectionActor_15156 | DebrisFloor_01_STAT | 2 | 0.73 / 0.73 | 0 | per-poly |
| StaticMeshCollectionActor_4586 | damageChunk_STAT | 2 | 0.73 / 0.77 | 0 | per-poly |
| StaticMeshCollectionActor_13240 | TubeDebris_07_STAT | 2 | 0.96 / 1.12 | 0 | per-poly |
| StaticMeshCollectionActor_6902 | damageChunk_STAT | 2 | 0.61 / 0.61 | 0 | per-poly |
| StaticMeshCollectionActor_3419 | CanyonFloor_B_Destroy_STAT | 2 | 0.64 / 0.68 | 0 | per-poly |
| BlockingVolume_13503 | BlockingVolume | 2 | 2.04 / 2.2 | 14 | list only (authored) |
| StaticMeshCollectionActor_8803 | TubeDebris_01_STAT | 1 | 0.53 / 0.53 | 0 | per-poly |
| StaticMeshCollectionActor_92 | damageChunk_STAT | 1 | 0.64 / 0.64 | 0 | per-poly |
| StaticMeshCollectionActor_9148 | TubeDebris_07_STAT | 1 | 0.56 / 0.56 | 0 | per-poly |
| StaticMeshCollectionActor_8803 | TubeDebris_07_STAT | 1 | 1.76 / 1.76 | 0 | per-poly |
| StaticMeshCollectionActor_8803 | TubeDebris_07_STAT | 1 | 3.8 / 3.8 | 0 | per-poly |
| StaticMeshCollectionActor_12806 | Mini_Cable_Hang01_STAT | 1 | 0.64 / 0.64 | 0 | per-poly |
| StaticMeshCollectionActor_10209 | PowerTube_Metal_03_STAT | 1 | 0.77 / 0.77 | 0 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorBEdge1_STAT | 1 | 1.78 / 1.78 | 0 | per-poly |
| StaticMeshCollectionActor_13512 | ENV_ORB_SliceFloorBEdge1_STAT | 1 | 0.63 / 0.63 | 0 | per-poly |
| StaticMeshCollectionActor_7579 | Ship_FloorPanel_01_Destory_STAT | 1 | 0.5 / 0.5 | 0 | per-poly |
| StaticMeshCollectionActor_7579 | Ship_FloorPanel_01_Destory_STAT | 1 | 0.59 / 0.59 | 0 | per-poly |
| StaticMeshCollectionActor_2696 | Ship_FloorPanel_01_Destory_STAT | 1 | 0.51 / 0.51 | 0 | per-poly |
| BlockingVolume_15018 | BlockingVolume | 1 | 2.24 / 2.24 | 15 | list only (authored) |
| BlockingVolume_4605 | BlockingVolume | 1 | 0.54 / 0.54 | 0 | list only (authored) |
| StaticMeshCollectionActor_8804 | ENV_COR_BossBottomDisc_STAT | — | 1.51 (Gameplay position [-223.2, 133.0, 55.8]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_8804 | ENV_COR_BossBottomDisc_STAT | — | 1.51 (Gameplay position [-221.3, 133.0, 54.8]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_7038 | ENV_CORE_PipeFloorRing_A_STAT | — | 12.41 (Gameplay position [72.8, 124.7, -80.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | — | 0.72 (Gameplay position [-164.8, 133.4, -155.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | — | 0.67 (Gameplay position [-169.1, 133.4, -160.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | — | 0.66 (Gameplay position [-165.9, 133.4, -165.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | — | 0.71 (Gameplay position [-163.1, 133.4, -158.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_3557 | ENV_COR_BossBottomDisc_STAT | — | 0.69 (Gameplay position [-162.5, 133.4, -162.0]) | — | per-poly (confirmed) |

Large-gap only (overhang / catwalk, list only): StaticMeshCollectionActor_12426 ENV_ORB_SliceWall_STAT (1 m²)

## MP_UND_Complex

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| StaticMeshCollectionActor_5767 | ENV_CORE_CanyonJunkPillar_C_STAT | 123 | 1.5 / 3.7 | 0 | per-poly |
| StaticMeshCollectionActor_13735 | DamagedOmegaBridge_STAT | 111 | 0.59 / 0.96 | 0 | per-poly |
| StaticMeshCollectionActor_14947 | ENV_CORE_CanyonJunkPillar_C_STAT | 107 | 1.19 / 4.93 | 4 | per-poly |
| StaticMeshCollectionActor_3733 | DamagedOmegaBridge_STAT | 96 | 0.59 / 0.89 | 0 | per-poly |
| StaticMeshCollectionActor_14947 | ENV_CORE_CanyonJunkPillar_C_STAT | 92 | 1.72 / 3.65 | 3 | per-poly |
| StaticMeshCollectionActor_9797 | ENV_CORE_CanyonDeco_B_STAT | 86 | 2.97 / 4.95 | 86 | per-poly |
| StaticMeshCollectionActor_3733 | DamagedOmegaBridge_STAT | 86 | 0.59 / 1.02 | 0 | per-poly |
| StaticMeshCollectionActor_6868 | ENV_CORE_CanyonJunkPillar_C_STAT | 83 | 1.25 / 2.64 | 0 | per-poly |
| StaticMeshCollectionActor_13735 | DamagedOmegaBridge_STAT | 65 | 0.61 / 1.11 | 0 | per-poly |
| StaticMeshCollectionActor_3733 | craterDebris_STAT | 18 | 0.58 / 1.24 | 0 | per-poly |
| StaticMeshCollectionActor_6438 | ENV_CORE_CanyonJunkPillar_C_STAT | 12 | 0.69 / 0.91 | 0 | per-poly |
| StaticMeshCollectionActor_13735 | ENV_CORE_CanyonJunkPillar_B_STAT | 11 | 0.85 / 2.19 | 2 | per-poly |
| StaticMeshCollectionActor_13735 | craterDebris_STAT | 11 | 0.79 / 1.45 | 0 | per-poly |
| StaticMeshCollectionActor_13735 | craterDebris_STAT | 9 | 0.57 / 1.94 | 6 | per-poly |
| StaticMeshCollectionActor_13735 | craterDebris_STAT | 9 | 0.63 / 1.63 | 4 | per-poly |
| StaticMeshCollectionActor_1232 | ENV_CORE_CanyonJunkPillar_B_STAT | 8 | 0.8 / 1.39 | 0 | per-poly |
| StaticMeshCollectionActor_15941 | Dec_Leg_Short_STAT | 8 | 0.58 / 0.86 | 0 | per-poly |
| StaticMeshCollectionActor_11870 | Dec_Leg_Short_STAT | 8 | 0.73 / 0.89 | 0 | per-poly |
| StaticMeshCollectionActor_3733 | Debris2_STAT | 5 | 0.57 / 0.59 | 0 | per-poly |
| BlockingVolume_16267 | BlockingVolume | 4 | 4.6 / 4.87 | 0 | list only (authored) |
| StaticMeshCollectionActor_3733 | Debris2_STAT | 3 | 0.59 / 0.6 | 0 | per-poly |
| StaticMeshCollectionActor_3733 | ENV_CORE_CanyonFloor_NColide_STAT | 3 | 0.65 / 0.65 | 0 | per-poly |
| StaticMeshCollectionActor_4225 | ENV_CORE_GatePlatform_A_STAT | 1 | 3.14 / 3.14 | 5 | per-poly |
| StaticMeshCollectionActor_4225 | ENV_CORE_GatePlatform_A_STAT | 1 | 4.15 / 4.15 | 4 | per-poly |
| StaticMeshCollectionActor_3560 | MRColumnA_STAT | 1 | 0.89 / 0.89 | 0 | per-poly |

Large-gap only (overhang / catwalk, list only): BlockingVolume_14421 BlockingVolume (21 m²), BlockingVolume_1749 BlockingVolume (18 m²), BlockingVolume_11300 BlockingVolume (3 m²), BlockingVolume_11083 BlockingVolume (2 m²)

## MP_UND_Gorge

| actor | kind / mesh | raised m² | gap median / max (m) | large m² | action |
|---|---|---|---|---|---|
| BlockingVolume_11019 | BlockingVolume | 709 | 1.05 / 4.89 | 70 | list only (authored) |
| StaticMeshCollectionActor_9642 | ENV_CORE_CanyonWall_A_STAT | 28 | 1.14 / 1.39 | 0 | per-poly |
| StaticMeshCollectionActor_9642 | ENV_CORE_CanyonWall_A_STAT | 25 | 1.14 / 1.39 | 0 | per-poly |
| StaticMeshCollectionActor_9642 | ENV_CORE_CanyonWall_A_STAT | 25 | 1.14 / 1.39 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 18 | 3.16 / 3.16 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 14 | 3.16 / 3.16 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 11 | 3.16 / 3.16 | 0 | per-poly |
| StaticMeshCollectionActor_9642 | ENV_CORE_CanyonWall_A_STAT | 9 | 0.7 / 1.29 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 9 | 3.16 / 3.16 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 8 | 0.87 / 1.65 | 0 | per-poly |
| StaticMeshCollectionActor_8658 | ENV_CORE_PlatformPillar_A_STAT | 7 | 0.85 / 1.64 | 0 | per-poly |
| StaticMeshCollectionActor_10353 | ENV_CORE_PlatformPillar_A_STAT | 6 | 0.85 / 1.27 | 0 | per-poly |
| StaticMeshCollectionActor_5692 | ENV_CORE_PlatformPillar_A_STAT | 6 | 0.85 / 1.27 | 0 | per-poly |
| StaticMeshCollectionActor_12114 | ENV_CORE_GatePlatform_D_STAT | 4 | 1.72 / 1.77 | 35 | per-poly |
| StaticMeshCollectionActor_4668 | ENV_CORE_GatePlatform_D_STAT | 4 | 1.71 / 1.76 | 35 | per-poly |
| StaticMeshCollectionActor_15433 | ENV_CORE_PlatformPillar_A_STAT | 4 | 0.8 / 0.88 | 0 | per-poly |
| StaticMeshCollectionActor_1960 | ENV_CORE_PlatformPillar_A_STAT | 2 | 4.67 / 4.74 | 1 | per-poly |
| StaticMeshCollectionActor_5692 | ENV_CORE_PlatformPillar_A_STAT | 2 | 0.77 / 0.79 | 0 | per-poly |
| BlockingVolume_5770 | BlockingVolume | 2 | 0.61 / 0.61 | 0 | list only (authored) |
| StaticMeshCollectionActor_8751 | ENV_CORE_GatePlatform_2A_STAT | 1 | 0.5 / 0.5 | 28 | per-poly |
| StaticMeshCollectionActor_15601 | ENV_CORE_GatePlatform_2A_STAT | 1 | 0.69 / 0.69 | 25 | per-poly |
| StaticMeshCollectionActor_15601 | ENV_CORE_GatePlatform_2A_STAT | 1 | 0.63 / 0.63 | 22 | per-poly |
| StaticMeshCollectionActor_13260 | ENV_CORE_GatePlatform_2A_STAT | 1 | 0.7 / 0.7 | 21 | per-poly |
| BlockingVolume_6343 | BlockingVolume | 1 | 3.68 / 3.68 | 0 | list only (authored) |
| StaticMeshCollectionActor_8751 | ENV_CORE_CanyonFloor_B_STAT | — | 1.11 (Gameplay position [-68.1, -4.0, -55.0]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_5692 | ENV_CORE_PlatformPillar_A_STAT | — | 0.66 (Gameplay position [-57.3, 12.2, -123.7]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_5692 | ENV_CORE_PlatformPillar_A_STAT | — | 0.66 (Gameplay position [-57.5, 12.2, -123.7]) | — | per-poly (confirmed) |
| StaticMeshCollectionActor_5692 | ENV_CORE_PlatformPillar_A_STAT | — | 1.4 (Gameplay position [-57.1, 12.9, -120.6]) | — | per-poly (confirmed) |

Large-gap only (overhang / catwalk, list only): BlockingVolume_4553 BlockingVolume (2 m²)
