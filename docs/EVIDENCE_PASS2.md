# Targeted evidence pass 2 (2026-10-01): handoff

Machine-readable: **`AssetTools/manifests/vs_evidence_pass2.json`** (43 items with confidence/source/object/value/handoff).
Pass 1 remains valid: `manifests/vs_evidence.json` and `docs/EVIDENCE_TARGETED_PASS.md`.
Regenerate: `run_pipeline.py --only vs_mapfx vs_audio vs_character_materials vs_evidence vs_evidence2`.

## 1. Optimus materials (`ExtractedAssets/VerticalSlice/Characters/Optimus/materials_authored.json`)
* **Wrong robot mesh in the slice (CONFIRMED).** `Optimus_ROBODEF.SkelMesh` = **`RB_OptimusWeaponArm_SKEL`**, the only Optimus robot
  mesh cooked into Streets.
  * `robot.glb` was built from `RB_Optimus_A_SKELMESH`, which is cooked only into campaign design/vignette/cine sublevels.
  * The MP mesh **omits the right forearm/elbow**: 293 vertices weighted to `R_Arm03_Elbow_XB` / `R_ElbowRobo01-02_XT`. That is exactly
    where `WeaponSocket_Primary` mounts the Ion Blaster, so the slice currently draws the forearm and the gun together.
  * Same 106-joint skeleton and bounds, so every robot clip applies unchanged.
  * Material slot order differs: MP slot 0 = `InteriorAlt_Energon_MAT_INST`, slots 1–2 = `RB_OptimusPrime_Cust_Mat_INST_B`.
  * The glTF is already extracted: `content/TR_Optimus_ROBO_p/RB_OptimusWeaponArm_SKEL.gltf`.
  * `ArmBlueprint` = `CP_OptimusArm_SKEL` + `OptimusArm_ROBO_ANIM` (separate arm mesh; when it is shown is native).
* **8 materials:** robot body `Cust_Mat_INST_B`, vehicle body `Cust2_Mat_INST` (both on master `CHR_Transformer_NormSpec_Cust_E_Mat`),
  robot/vehicle `InteriorAlt_Energon_MAT_INST`, robot/vehicle Overshield, robot/vehicle Defrag (energy death).
* **Compiled per-instance static switches**, inferred from the parameters each cooked compiled shader references (HIGH):
| switch | master default | robot body | vehicle body |
|---|---|---|---|
| UseReconstructedNormal | true | **false** (samples DXT1 RGB `Normal_Map` `RB_Optimus_Norm_b`, unpack −1..1) | **true** (`VarienceNormal_XY_Map` = `VH_Optimus_NORM` DXT5, X=A, Y=G) |
| UseSpecPower_S_Curve | false | **true** | **true** |
| UseDiffuseReflection / UseEmissiveReflection | true / true | true / true | true / true |
| Enable_Autobot_Lut / Enable_Decepticon_Lut | false / false | false / false | false / false (customization LUTs not sampled) |
| energon switches | — | undeterminable (same parameter name in every branch); driven at runtime | same |
* **Overshield** instances add 17 parameters (`Overshield_Color` (0, 0.5, 2.0), Intensity 10 robot / 8 vehicle, HexagonTile 28,
  Edge_Min 4 / 5, pan speeds…). **Defrag:** Masked + Unlit, `EdgeEnergyColor` (0, 0.5, 2.0), `LightColor` (0.173, 0.316, 0.384).
  The vehicle Defrag has PhysMaterial `VH_VehicleHull_PHYSMAT`.
* **Texture colour flags:** `Lum_Map` (SpecPwr / DifLum / EnrGlow packed data), `CustClrAlphasMap` and `Grunge_Map` are DXT1 with
  **SRGB = true**. Normal maps are SRGB false with UnpackMin −1.
* **Team/energon colour (CONFIRMED values):**
  * `TnCharacterApplier` binds PrimaryColor → `Cust_Color_A`, SecondaryColor → `Cust_COLOR_B`, team energon → `EnergonColor`.
  * Team colours: `TnFactionTeamAutobots` **(1.25, 0.05, 0.05)**, `TnFactionTeamDecepticons` (0.2, 0.1, 1.5), neutral `TnTeamInfo`
    (0.843, 0.302, 0.029). These equal the master's three switch constants.
  * Optimus character data (SP and MP) authors blank (0,0,0) primary/secondary colours, so the MIC customization values stand (INFERRED).
  * `InteriorAlt_Energon_MAT` bakes its energon colour as constants (red 1.25 / blue 0.2, ×1.75), so it is **not** recoloured at runtime.

## 2. Boost, Hover Dash, Ram/Nitro (separate mechanics)
| | Boost (normal) | Hover Dash | Ram / Nitro |
|---|---|---|---|
| input | LT `FineAim \| Boost` → StartBoost/StopBoost (vehicle) | native trigger | `VehicleSpecialMove` (RB / LShift) → truck Ram (`_RamState`, `_NitroTimeRemaining`) |
| physics | Driving (wheels) mode on `Truck_Physics` (MaxSpeed 3000, accel 2500) while `_Boosting` (HIGH) | `HoverTruck_Physics` **DashSpeed 3000, DashDuration 0.5** (class default 5000 / 0.3); cooldown base native | damage 175 players / 300 AI (robots and vehicles), ExtraRamZVelocity 7000; nitro duration/speed/steering/cooldown native (only ×1.0 modifiers) |
| anim | `Nav_HoverToBoost_VEH` / `Nav_BoostToHover_VEH`, blend 0.05/0.1 | none authored | Ram state names `Transform_RamIn/Out_VEH`, **which exist nowhere in the cook** → no ram animation |
| FX | `bumble_boost_small1_FX` on `BoostSocket_L/R` (bones `L/R_Robo23_XT`, ±35 UU, yaw ±90°) | no dash FX property | `FX_Navigation_p.FX.Truck_ram_FX` on `RamSocket` (C_Body_XB (380,0,−40), scale (1,1.5,1.5)) |
| audio | BOOST_START / _LOOP (speed parameter) / _END / _WHEELS; fade 0.15 s, wheel ground check 0.27 s | none | RAM_BOOST_START (−8 dB), RAM_NITRO_START (−5 dB), TRUCK_RAM_IMPACT (3 variants), TRUCK_RAM_ALERT (−15 dB looping) |
| material | none | none | none |
NitroForceFeedback: 0.1875 for 3.0 s (linear increase). It may hint at a ~3 s nitro, but that is not a gameplay value.

## 3. Transformation
Unchanged from pass 1 (`vs_evidence.json` Q5), republished as P3.
* **Sounds:** BOT2VEH at 0.125 s; VEH2BOT at 0.0 s.
* **Visibility:** robot→vehicle, both meshes visible 0.396–0.880 s; vehicle→robot, both visible 0.098–0.663 s.
* **Vehicle FX:** enabled at 1.8 s; disabled at 0.0 s.
* **Weapon:** restored when 0.75 of the transform remains.
* **Blend:** in 0.115 / out 0.25.
* **Movement:** robot root rises 0.85 m.
* **Effects:** none authored beyond these notifies and toggles. `TransformFailedSound = BL_TRANS_POWER.TRANSFORM_DISABLED`.

## 4. Fine aim
Pass 1 values (FOV 80→45 at 0.1 s, orbit 800 kept, look 50/25 → 25/12.5, ground speed ×0.5, LT binding) plus authored **sounds**:
`WP_StartFineAim` → `BL_WPN_GUN_PULSE_RIFLE.FINE_AIM_START` (−15 dB) and `WP_EndFineAim` → `FINE_AIM_END` (−18 dB). Both are gun and
robot movement foley variants; all WAVs resolved.

## 5. Fast robot movement
Pass 1 values (BaseGroundSpeed 1400; walk→jog blend 450→1200 UU/s; clips natural 4.5 / 12.5 m/s; dodge = Nav_Boost_*).
Not authored: any sprint state or input, and speed-based play-rate (foot-slip) scaling. At 14 m/s the jog clips would slip about 10%
unless native code scales them.

## 6. Map effects
* **Exactly 8 level emitters.** The prefab vent is `Emitter_5707` (one of the 8), not a 9th.
* All use `FX_Level_Generic_p.FX.Steam_Sm_FX`:
  * One looping emitter, spawn 2–3/s, 3 LODs, LODDistances 0/1000/50000.
  * Material `Steam_Mat`: translucent, unlit, smoke textures, depth-biased alpha 500.
  * Per-emitter `SteamColor`: violet (100–124, 17–26, 253–255) ×6, the prefab vent cyan (33, 167, 239), one default.
* Transforms are in `map_fx.json`.
* Each emitter sits 2–15 m from an energon-vent or energon-crater ambient sound (spatial pairing; no authored link).
* **Pickup effects (added 2026-10-03):** pass 2 covered only the 8 level emitters.
  * The 37 pickup effect components are decoded in `manifests/streets_pickup_fx.json` (M03).
  * TDM state (vertical-slice mode, CONFIRMED): **24 drawn** while their factory is available, plus 14 ammo crate meshes:
    * 14 ammo-crate `Pickup_FX` beams;
    * 9 `HealthPickup_FX`;
    * 1 `OvershieldPickup_FX`.
  * Not drawn in TDM:
    * flag/bomb factories, Disabled outside CTF/EXT;
    * the 10 health/overshield `Pickup_FX` copies, never attached.
  * Tables: `docs/EVIDENCE_M03.md` §2, `docs/GAMEPLAY_STREETS.md`, `docs/MAP_STREETS_COMPLETE.md`; machine-readable in
    `render_index.json`.

## Also in this checkpoint
* **Props pass stopped on request.** `vs_props.py` and `props_authored.json` are kept, validated (171/171 meshes: LOD0 triangles = cooked
  sections; glTF inside authored Bounds), and are not in the pipeline. They record the spinning `DecoSphereHalf01` props
  (PHYS_Rotating, 15°/s) and the sky-beam rig hierarchy. Existing prop placement was **not** changed.
* **Tooling:** `vs_materials.py` refactored to a reusable `describe()`, plus compiled static-switch inference
  (`static_switches_compiled`); `vs_character_materials.py`; `vs_evidence2.py`.
