# Targeted authored-evidence pass (2026-10-01) — answers for Gameplay / Rendering / Systems

Machine-readable source of truth: **`AssetTools/manifests/vs_evidence.json`** (75 findings, each
`{id, confidence, source_package, object, class, property, value, handoff, note}` + full supporting dumps:
cue graphs with WAV paths, particle summaries, camera strategies, anim trees, AnimSet notifies, MIC chain).
Regenerate: `AssetTools\bin\py\python.exe AssetTools\run_pipeline.py --only vs_map vs_collision vs_mapfx vs_validate vs_evidence` (~20 s).

Evidence package for the slice: **`MP_IAC_Streets_BASE_m.xxx`** (complete cook of Optimus, Ion Blaster, camera
assets, anim trees, FX, cues); class defaults from **`TransGame.xxx`**; placed map content from **`MP_IAC_Streets_ART_m.xxx`**.
Units: UE units (1 UU = 1 cm), rotators 65536 = 360°. Confidence: CONFIRMED / HIGH CONFIDENCE / PARTIAL / INFERRED / UNKNOWN.

**Effective values.** Cooked objects only serialize properties that differ from their archetype. Cooked exports store
archetype 0, which means "the class default object", and a CDO's parent is its super-class CDO. `effective.py` resolves
this chain, so every value below is the one the object actually has, with the object that authored it.

---------------------------------------------------------------------------------------------------------------
## 1. Vehicle boost presentation

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY / REFERENCE | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 1a | CONFIRMED | Streets_BASE | `TR_Optimus_VEHDEF_p.OptimusTruckForm` / TnTruckFormBlueprint | `BoostFx` | `BoostSocket_L` + `BoostSocket_R` → `FX_Navigation_p.bumble_boost_small1_FX` | Systems |
| 1b | CONFIRMED | 〃 | 〃 | `HoverFX` | 6× `FX_Navigation_p.CarHover_A_01_FX` on `HoverBooster_{L,R}{Front,Back,Back2}` | Systems |
| 1c | CONFIRMED | 〃 | 〃 | `JumpFX` / `RamFX` | `FX_Navigation_p.Jump_FX` on `JumpBoostSocket_{C,L,R}`; `FX_Navigation_p.FX.Truck_ram_FX` on `RamSocket` | Systems |
| 1d | CONFIRMED | 〃 | `TR_Optimus_VEH_p.VH_OptimusPrime_SKEL` / SkeletalMeshSocket | `BoostSocket_L` | bone `L_Robo23_XT`, loc (0,−35,0), rot yaw −16384 (−90°) | Systems |
| 1e | CONFIRMED | 〃 | 〃 | `BoostSocket_R` | bone `R_Robo23_XT`, loc (0,35,0), rot yaw +16384 (+90°) | Systems |
| 1f | CONFIRMED | 〃 | 〃 | `HoverBooster_*` | wheel bones `{L,R}_Wheel0{1,2,3}_XB`, loc (0,∓13,0), rot pitch 32768 yaw ±16384, scale (3,3,3) front / (2,2.5,2.5) back | Systems |
| 1g | CONFIRMED | 〃 | `bumble_boost_small1_FX` / ParticleSystem | emitters (LOD0 RequiredModule) | `thruster` (mesh `Boostermesh_02_STATMESH`, mat `Boostermaterial_02_MAT`, burst 3, 0.5 s, 1 loop, local space); `Particle Emitter_Dup` (sprite, `Basic_Particle_Add_MAT`, burst 1, 0.5 s); `loopcone` (mesh, spawn 3–4/s, **loops forever**); `Particle Emitter_Dup_Dup` (sprite, spawn 20/s, **loops forever**); `Cone_thrust_Dup` (mesh `bulletshape_fx_STAT`, `bumble_boostcone_MAT`, burst 1). LODDistances 0 / 2500. All materials Additive+Unlit | Systems |
| 1h | CONFIRMED | 〃 | `…OptimusTruckForm.HmPlayerVehicleAudioComponent_6670` | Boost* | BoostSound=`Auto_Boost_Start`, BoostSounds.BoostLoops=`Auto_Boost_Loop`, BoostStopSound=`Auto_Boost_End`, BoostWheelsSound=`Auto_Boost_Wheels`, **BoostFadeOutTime 0.15**, **BoostWheelsGroundCheckDelay 0.27**, BoostLandSound (≥0.15 s air → Wheels_Light, ≥2.0 s → Wheels_Heavy), HoverLandSound (same thresholds → Hover_Light/Heavy), EngineFadeOutTime 0.2, SpeedSoundParameter `Optimus_Prime_Speed` | Systems |
| 1i | CONFIRMED | 〃 | `SoundEvents_Vehicles_Trans.Veh_Optimus_Prime_SoundSet` | SoundEventSet | Auto_Boost_Start→`VEH_OPTIMUS_BOOST_START`, _Loop→`_BOOST_LOOP`, _End→`_BOOST_END`, Auto_Boost_Wheels→`_BOOST_WHEELS` (+ jump, land, impact, ram events) | Systems |
| 1j | CONFIRMED | 〃 | `BL_VEH_OPTIMUS_PRIME.VEH_OPTIMUS_BOOST_START` | SoundNodeRoot | −8 dB, Distance 5000–35000, Priority 185, SmartPan PreferPlayer, category `SFX_WET_VEH_MANEUVER`; 5 timed WaveEvents (`WHSH_BOOST_FLARE_LR_03` @0.005 −6 dB, `SYNTH_ENGINE_ACCEL` @0.138 pitch +3, `SYNTH_AIR_RELEASE_04` @0.247 pitch +6, …) — all WAVs resolved | Systems |
| 1k | CONFIRMED | 〃 | `…VEH_OPTIMUS_BOOST_LOOP` | SoundNodeRoot | −12 dB, 5000–35000, **SoundParameter `Optimus_Prime_Speed`**, LoopStart 2.904 / LoopEnd 3.120, category `SFX_WET_VEH_ENGINE`; layers `MECH_OPTIMUS_TIRE_NOISE_02_LP`, `SYNTH_ENERGY_MOD_PAN_LP` −14 dB, `JET_TURBO_WHINE_LP` −8 dB … | Systems |
| 1l | CONFIRMED | 〃 | `VEH_Proxy_p.VEH_Car_ANIMTREE.AmpAnimSwitch_3253` | SelectorProperty | `_VehicleForm._InputState._Boosting`: 0 → **Hovering** state, 1 → **Driving** state (no clip, wheels via SkelControlWheel, Ram sub-switch) | Gameplay |
| 1m | CONFIRMED | 〃 | `HmAnimTransitionWithBlend_7946 / _3724` | TransitionAnim | Hovering→boost transition = **`Nav_HoverToBoost_VEH`** (0.70 s), Driving→hover = `Nav_BoostToHover_VEH` (1.03 s); BlendIn 0.05 / BlendOut 0.10 | Gameplay |
| 1n | INFERRED | 〃 | AmpAnimState semantics | "Default" child | the transition plays when LEAVING the state (HoverToBoost when boost starts) — native | Gameplay |
| 1o | CONFIRMED | 〃 | `TnAccelerationAnimBlend_2889` | Children | Idle/Up/Down=`Nav_Hover_Pose_VEH`, F/B/R/L=`Nav_Hover_{F,B,R,L}_VEH` + additive `ADD_Nav_Hover_VEH`; driven by **acceleration** (weighting law native/UNKNOWN) | Gameplay |
| 1p | CONFIRMED | 〃 | `VEH_SHARED_p.HoverTruck_Physics` / TnHoverCarSimulationBlueprint | effective | **DashSpeed 3000** (CDO 5000), **DashDuration 0.5** (CDO 0.3), **SuspensionRadius 185** (CDO 200), MaxLinearSpeed 1500, MaxLinearAcceleration 3000, JumpLinearSpeed 1200, DriftDuration 0.5; suspension `HoverTruck_Suspension` Damping 4000 RestingLength 250 | Gameplay |
| 1q | CONFIRMED (values) / HIGH CONFIDENCE (use) | 〃 | `VEH_SHARED_p.Truck_Physics` / TnCarPhysicsBlueprint | effective | Mass 2500, MaxSpeed 3000, MaxAcceleration 2500, JumpLinearVelocity (600,0,1400), CoM (−47,0,20), 4 wheels r45 steer 25°, Truck_Suspension Stiffness 120000 Damping 8000. Boost = wheels-down "Driving" mode on this CarBlueprint (1l + wheel-boost sounds); the physics switch itself is native | Gameplay |
| 1r | CONFIRMED | 〃 | `CHR_Transformer_NormSpec_Cust_E_Mat` | parameters | **no** boost/speed parameter in the vehicle master or MIC — boost visuals are particles only | Rendering |
| 1s | CONFIRMED | 〃 | `Optimus_VEH_ANIM` notifies | TnAnimNotify_ToggleVehicleFx | vehicle FX **enabled at 1.800 s** of `Transform_ToVehicle_VEH`, **disabled at 0.000 s** of `Transform_ToRobot_VEH` | Systems |

## 2. Optimus vehicle materials

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 2a | CONFIRMED | Streets_BASE | `TR_Optimus_VEH_p.RB_OptimusPrime_Cust2_Mat_INST` / MIC → `TR_AllShader_p.Release.CHR_Transformer_NormSpec_Cust_E_Mat` | chain | 2 levels; textures Reflection_Map `CHR_Metals_CUBEMAP3D`, Grunge_Map `VH_Optimus_GrungeClr`, CustClrAlphasMap `VH_Optimus_CustAB_AuxGlow`, Lum_Map `VH_Optimus_SpecPwr_DifLum_EnrGlow`, Normal_Map = VarienceNormal_XY_Map = `VH_Optimus_NORM`; scalars/vectors in manifest (Cust_Color_A (0.599,0.016,0.016), Cust_COLOR_B (0,0.117,0.530), Emissive_Intensity 3, ColorBrightness 0.6, PowerDown 0.5 …) | Rendering |
| 2b | CONFIRMED | 〃 | master graph | consumers of `VarienceNormal_XY_Map` | **only outputs A and G** → `AppendVector(A, G)` → `Append(AG, sqrt(1−dot(AG,AG)))` → `UseReconstructedNormal` (default **true**, A-pin) → Normal. `Normal_Map` RGB feeds only the false pin | Rendering |
| 2c | CONFIRMED | 〃 | 〃 | DXT5 alpha usage | alpha = **normal X only**; no node reads A (or R/B) for gloss, specular or masks. The `*2−1` unpack is not a graph node (sampler unpack; Rendering confirmed it in microcode) | Rendering |
| 2d | CONFIRMED | 〃 | 〃 | `UseNeutralEnergonColor` (default **false**) → `UseAutobotEnergonColor` (default **true**) | three same-named `EnergonColor` VectorParameters: Neutral (0.843,0.302,0.029), **Autobot (1.25,0.05,0.05)** ← selected, Decepticon/false (0.2,0.1,1.5). MIC overrides neither switch nor colour | Rendering |
| 2e | CONFIRMED | 〃 | 〃 | energon emissive formula | `(E + E·pow((sin(sin(fractalMaps.R(panned)+Time·energonSpeed))+1)·energonIntensity, energonContrast))·Lum_Map.B·Energon_Intensity`, added to `CustClrAlphasMap.B`-masked emissive, ×`PowerDown`, then UpLight/ScanLines/Overshield switches → Desaturation → EmissiveColor. **Red appears only where `VH_Optimus_SpecPwr_DifLum_EnrGlow` blue > 0** | Rendering |
| 2f | UNKNOWN | — | runtime MID | `EnergonColor` team override | the three parameters share one name, so a runtime `SetVectorParameterValue("EnergonColor")` would override the selected one; whether gameplay does this is native | Rendering / RE |
| 2g | CONFIRMED | Streets_ART | `ENV_ORB_D1_Debris_p.Meshes.column_Base_STAT` / StaticMesh | `FStaticMeshElement[0].Material` | **`ENV_IAC_Deco_1_p.Material.SideSupport_MATINST`** (→ `ENV_NEU_VariantShaders_p.Materials.SideSupport_MATINST` → `ENV_IAC_Shader_p.Material.IAC_Base_Shader_MAT` → `ENV_AllShader_p.Release.ENV_PhongMain_NS_Mat`, all cooked in Streets ART/BASE, 30-node graph present) | Rendering |
| 2h | CONFIRMED | — | AssetTools bug (fixed) | why it "could not compile" | umodel names glTF materials by short name; 4 packages define `SideSupport_MATINST`; `assets.json` resolved it to `ENV_ORB_D1_Debris_p.Materials.SideSupport_MATINST`, which is **not cooked into Streets** (its master is absent). `vs_map.py` now binds sections from the cooked `FStaticMeshElement` array (`smsections.py`); `materials.json` no longer lists the D1 Debris material | Rendering |

## 3. Fine aim

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 3a | CONFIRMED | Streets_BASE | `CAM_Strategies_p.Truck_Optimus_CAMSET` | Strategies | robot (OverTheShoulder type) → `OverTheShoulder_STRATEGY`; hovering → `HoverTruck_Optimus_STRATEGY`; driving (boost) → `Truck_Optimus_STRATEGY`; TransformToRobo → OverTheShoulder; TransformToVehicle → HoverTruck | Gameplay |
| 3b | CONFIRMED | TransGame / Streets_BASE | `TransContent.Default__TnWeapon*` | `WeaponPCS`, `HasFineAimScope` | **Ion Blaster: none** → only `TnPCS_FineAim` is active when fine-aiming. BurstRifle → TnPCS_BurstRifle; HeavyPistol → TnPCS_HeavyPistol + scope; SniperRifle → TnPCS_SniperRifle + scope | Gameplay |
| 3c | CONFIRMED | Streets_BASE | `OverTheShoulder_STRATEGY.TnFovCameraBehavior_1013` | DefaultFOV / FOVsByPCS | default **80° / smooth 0.4 s**; FineAim **45° / 0.1 s** (Ion Blaster); HeavyPistol|BurstRifle+FineAim 30°; Sniper+FineAim 20°; Hovering+FineAim 45°; FocusingOnPOI 50° / 0.5 s | Gameplay |
| 3d | CONFIRMED | 〃 | `…TnLocationOffsetCameraBehavior_15999` | orbit distance | **DefaultOrbitDistance 800 UU (8 m)**; only Sniper/HeavyPistol/BurstRifle+FineAim → 100. Ion Blaster fine aim keeps 800 | Gameplay |
| 3e | CONFIRMED | 〃 | `…TnOrbitRotationCameraBehavior_13237` | look speeds | default Yaw 50 / Pitch 25, FineAim **Yaw 25 / Pitch 12.5** (×0.5), Sniper+FA 6.5/3.25, HeavyPistol|Burst+FA 9.375/4.6875; RampSpeedMultiplier 2.5, RampTime 0.4, RampZone 0.7, SpeedTransitionTime 0.5, Low/HighSensitivityMultiplier 0.8/1.5, MaxInputChange 1.0, PitchRange ±75 | Gameplay |
| 3f | CONFIRMED | 〃 | `…TnScreenSpaceOffsetByPitchCameraBehavior_3741` | offset curves | default 3 keys over pitch −75…+75: (150,300,150) / (150,300,−35) / (150,300,150), SmoothTime 0.3; Sniper/Burst/HeavyPistol+FA X=350, smooth 0.1; Hovering+FA middle key (−25,300,−100). X/Y/Z = fwd/right/up INFERRED | Gameplay |
| 3g | CONFIRMED | 〃 | `…HmOffsetAnchorPointRelativeToActorCameraBehavior_836` | Offset | (0,0,200) UU pivot above the actor | Gameplay |
| 3h | CONFIRMED | 〃 | `OverTheShoulder_STRATEGY` | TransitionTime | 1.5 s (0 when coming from GuidedMissile) | Gameplay |
| 3i | CONFIRMED (value) / HIGH CONFIDENCE (use) | TransGame | `Default__TnFineAimManager` | `_GroundSpeedMultiplier`, `_TargetSnapTimeout` | **0.5**, 1.0 s | Gameplay |
| 3j | CONFIRMED | Streets_BASE | `WEP_IonBlaster_p.IonBlaster_WEPDATA` (MultiplayerData) | fine-aim | FineAimSpreadModifier 0.5; FineAimTargetFocusParams DOF (kernel 8, focus 1000, max near 0.6 / far 1.0); RecoilCameraParams FOV +0.085, pitch 0.1°, 0.05 s, delay 0.25; PerShotSpread 0.08–0.18, +0.005/shot, cooldown 2 s; GroundSpeedMultiplier 1.0 | Gameplay |
| 3k | CONFIRMED | Coalesced.ini | `Xe-TransInput.ini` | bindings | `XboxTypeS_LeftTrigger = "FineAim \| Boost"`; `FineAim = "FineAim \| OnRelease StopFineAim"`; `Boost = "StartBoost \| OnRelease StopBoost"`; PC `RightMouseButton = "ToggleFineAim \| Boost"`; HmPlayerInput MouseCameraSensitivityX/Y 0.00114286, MouseOrbitRotation…Low/High 0.03/0.2, DeadZone 0.25; LookRightScale 300, LookUpScale −250, MouseSensitivity 15 | Gameplay |

## 4. Fast robot movement

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 4a | CONFIRMED | Streets_BASE | `TR_Optimus_ROBODEF_p.Optimus_ROBODEF` / TnTransformer | speeds | **BaseGroundSpeed 1400**, AccelRate 12000, AirSpeed 1200, AirControl 0.4, TerminalVelocity 6000; (TnTransformer CDO) BaseEyeHeight 150, Mass 100 | Gameplay |
| 4b | HIGH CONFIDENCE | TransGame | `Default__TnPawn._BaseGroundSpeed` (600), `_SpeedMultiplierFactors` | runtime model | ground speed = blueprint base × multipliers (weapon GroundSpeedMultiplier 1.0, fine aim 0.5). The rebuild's 5.5 m/s (`TnPlayerPawn.GroundSpeed 550`) is a pawn CDO default that the blueprint very likely replaces. **The native assignment is not decompiled.** | Gameplay / RE |
| 4c | CONFIRMED | Streets_BASE | `Robot_ANIMTREE.TnVelocityAnimBlend_10449` | MinSpeed / MaxSpeed | **450 → 1200 UU/s**: Walking = `Nav_StrafeWalk_{F,B,L,R}`, Jogging = `Nav_StrafeJog_{F,B,L,R}` (Turret variants for two-handed guns); synch group "Strafers"; `TnVelocitySwitch` Idle/Moving above it | Gameplay |
| 4d | HIGH CONFIDENCE | robot.glb | foot-plant measurement | clip speeds | walk ≈ **4.5 m/s**, jog F/L/R ≈ **12.2–12.8 m/s** (jog B 8.9) = the 450/1200 endpoints. **There is no run/sprint clip or node**: the "fast state" is the jog set at ≥ 12 m/s; at 5.5 m/s the blend is ~13 % jog | Gameplay |
| 4e | CONFIRMED | 〃 | `TR_Acrobatics_p.SharedAcrobatics` | effective | JumpHeight **500**, DoubleJumpHeight 450, HoverJumpHeight 500, HoverDuration 7, HoverAirSpeed 500, **DodgeSpeed 3000, DodgeTime 0.5**, RammedSpeed 5000, noise radii; LandingAnims thresholds (MinHeight/MinSpeed 1200/1200, 1000/1200, 4500/0, 500/0, 250/0) | Gameplay |
| 4f | CONFIRMED | 〃 | `Robot_ANIMTREE…TnAcrobaticsSlotLogic_10124` | Dodge/Jump/Hover/Skid/Rammed | dodge = **`Nav_Boost_{F,B,L,R}`** (0.5 s, blend 0.2/0.2); notifies: `FOLEY_JUMPJETS_BOOST` / `FS_DEFAULT_JUMP_CHARGED` @0, `DashPulse_1_FX` on `BoosterSocket_L` @0.012 / `_R` @0.021, trail FX on wing/elbow/knee sockets | Gameplay / Systems |
| 4g | CONFIRMED (values) / UNKNOWN (semantics) | 〃 | `TR_Acrobatics_p.TruckTransformerMomentum` | OnGround / InAir | {Forward 7, Neutral 3, Backward 1} / {100, 100, 5} | Gameplay / RE |
| 4h | UNKNOWN | — | — | activation | no authored "sprint" input, state or threshold; speed alone drives the blend. Boost (LT) only acts in vehicle form; robot "boost" = dodge | Gameplay |

## 5. Transformation presentation

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 5a | CONFIRMED | Streets_BASE | `Optimus_ROBO_ANIM` `Transform_ToVehicle_ROBO` (2.0 s, 60 frames) | Notifies | @0.125 HmAnimNotify_Sound **`BL_TRANSFORM.OPTIMUS_BOT2VEH`**; @0.880 ToggleHidden **Hide** | Gameplay / Systems |
| 5b | CONFIRMED | 〃 | `Optimus_VEH_ANIM` `Transform_ToVehicle_VEH` (2.0 s) | Notifies | @0.396 ToggleHidden **Unhide** (enum default 0); @1.800 ToggleVehicleFx **Enable** (enum default 0) | Gameplay |
| 5c | CONFIRMED | 〃 | `Transform_ToRobot_ROBO` (1.167 s) | Notifies | @0.000 Sound **`BL_TRANSFORM.OPTIMUS_VEH2BOT`**; @0.098 ToggleHidden **Unhide** | Gameplay / Systems |
| 5d | CONFIRMED | 〃 | `Transform_ToRobot_VEH` (1.167 s) | Notifies | @0.000 ToggleVehicleFx **Disable**; @0.663 ToggleHidden **Hide** | Gameplay |
| 5e | HIGH CONFIDENCE | derived | visibility timeline | | robot→vehicle: both visible **0.396–0.880 s**; vehicle→robot: both visible **0.098–0.663 s**. Replaces `kTransformHandoffFrac=0.5`. (Simultaneous clip start inferred from identical authored lengths) | Gameplay |
| 5f | CONFIRMED (corrected) | 〃 | `BL_TRANSFORM.OPTIMUS_BOT2VEH` | cue | −4 dB, Distance 1500–15000, category `SFX_WET_COMBAT_TRANS`; events `TRANS_OPTIMUS_TO_VEH_SERVOS` @0 −6 dB, `TRANS_OPTIMUS_TO_VEH` @0.152, `MECH_TRUCK_LAND_HEAVY_01/02/03` (random variants) @0.642 −9 dB, `WHSH_BOOST_FLARE…` @1.440 (VEH2BOT and VEH_SUPER_BOOST_TRUCK in manifest) | Systems |
| 5g | CONFIRMED | TransGame | `Default__TnTransformation` | _BlendInTime / _BlendOutTime | 0.115 / 0.25 | Gameplay |
| 5h | CONFIRMED (value) / INFERRED (meaning) | TransGame | `Default__TnPawn` | `_RestoreWeaponTransformFractionRemaining` | **0.75**: weapon restored when 75 % of the vehicle→robot transform remains. No weapon hide/restore notify exists in any Optimus clip; the weapon is attached to the robot mesh and hides with it (5a) | Gameplay |
| 5i | HIGH CONFIDENCE | robot.glb | `Transform_ToVehicle_ROBO` root | root motion | `C_Root_Reference_XR` rises 0.849 m (up to 0.519 m forward mid-clip); `ToRobot_ROBO` none; vehicle clips none (TranslationScale 0); vehicle `C_Reference_XR` 1.5 m in transform clips vs 0.6 m in hover/boost clips | Gameplay |
| 5j | CONFIRMED | — | clip timing | | glB clip lengths = (NumFrames−1)/30 (1.967 / 1.133 s); authored SequenceLength = NumFrames/30 (2.0 / 1.167 s); notify times are in authored seconds | Gameplay |

## 6. Map fidelity (`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/map_fx.json`)

| # | CONFIDENCE | SOURCE PACKAGE | OBJECT / CLASS | PROPERTY | RECOVERED VALUE | HANDOFF |
|---|---|---|---|---|---|---|
| 6a | CONFIRMED | Streets_ART | 25 × DecalActor / DecalComponent | effective props + transform | DecalMaterial, Width/Height (e.g. 900×900), Thickness 10, FarPlane, Tile, DepthBias −0.0002, Orientation, Hit{Location,Normal,Tangent,Binormal}, DecalReceivers (component refs), bStaticDecal, projection flags; UE + glTF matrices (translation matches props.json exactly) | Rendering |
| 6b | CONFIRMED | 〃 | 4 decal materials | BlendMode / LightingModel | `landmark_{Dchevrons,dcorner,corner,chevrons}_clr_Mat` — all **Additive + Unlit** (10/6/5/4 uses) | Rendering |
| 6c | CONFIRMED | 〃 | 8 × Emitter / ParticleSystemComponent | Template / InstanceParameters | all `FX_Level_Generic_p.FX.Steam_Sm_FX` (emitter `Smoke_Dup`, `Steam_Mat`); per-emitter **`SteamColor`**: (106,17,255) ×2, (124,17,255), (111,26,253), (100,17,255), (101,18,254), prefab vent (33,167,239), one with no override | Systems |
| 6d | CONFIRMED | 〃 | `PrefabInstance_4340` | native ArchetypeToInstanceMap | `ENV_IAC_Deco_PFB_p.SteamVentFX.SteamVentFX_Arc0 → Emitter_5707`: the prefab vent **is one of the 8** (no 9th emitter) | Rendering / Systems |
| 6e | CONFIRMED | Streets_BASE | 37 pickup/objective ParticleSystemComponents | Template | AmmoCrate ×14 `Pickup_FX`; Health ×9 `HealthPickup_FX` + ×9 `Pickup_FX`; Flag ×2, Bomb ×1, OverShield `Pickup_FX` + `OvershieldPickup_FX` (previously omitted relationships) | Systems |
| 6f | CONFIRMED | Streets_ART/BASE | all 171 StaticMeshes | FStaticMeshElement | `props.json` now carries `section_materials` for **1952/1952** props; 5 slots that umodel left `dummy_material_N` are bound (e.g. `stain_long_STAT` → `stains_01_CLR_MatINST_BAT`, `InteriorDoor_STAT` → `InteriorDoorLock_MATINST`, D1 debris break faces → `ENV_cboard_CLR_Mat`, a real textured material) | Rendering |

---------------------------------------------------------------------------------------------------------------
## Still requires native RE (not authored in cooked data)
1. Blueprint → pawn ground-speed assignment (`BaseGroundSpeed 1400` vs `GroundSpeed 550`) and the `_SpeedMultiplierFactors` product (4b).
2. Hover↔Driving physics switch on boost: confirm the CarBlueprint is simulated while `_Boosting` (1q).
3. AmpAnimState "Default" transition edge semantics (1n); TnAccelerationAnimBlend weighting law (1o).
4. `_RestoreWeaponTransformFractionRemaining` usage and weapon holster/unholster during transforms (5h).
5. TnTransformerMomentumBlueprint semantics (4g); dodge trigger (input / double-tap) and DodgeSpeed application.
6. Runtime team override of `EnergonColor` (2f); FOV axis (horizontal vs vertical) for TnFovCameraBehavior (3c).
7. Particle module identity inside WFC's compiled per-LOD stream (values exact; roles by order only).

**Correction (audio pass):** `vs_evidence.py` previously kept only the first child of each `SoundNodeWaveEvent`; 7 events in the
slice cues have several variant waves (e.g. `OPTIMUS_BOT2VEH` @0.642: `MECH_TRUCK_LAND_HEAVY_01/02/03`). `wave_events[].variants`
now lists them all.
