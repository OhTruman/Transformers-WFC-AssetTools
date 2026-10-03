# Milestone 03 targeted evidence pass (2026-10-02)

The machine-readable outputs are in `AssetTools/manifests/`. Every important field carries
`source_package / object / class / property / value / origin / confidence`.

**Confidence labels:**
* CONFIRMED AUTHORED DATA
* HIGH CONFIDENCE
* PARTIAL
* UNKNOWN

| Manifest | Builder | Consumer |
|---|---|---|
| `streets_destructibles.json` | `vs_destructibles.py` | Rendering, Gameplay |
| `streets_pickup_factories.json` | `vs_pickups.py` | Gameplay, Systems |
| `streets_pickup_fx.json` | `vs_pickups.py` (+ `pstream.py` decoder) | Systems, Rendering |
| `fineaim_hud.json` | `vs_fineaim_hud.py` (+ `gfxscan.py`, `as2dis.py`) | Rendering/UI |
| `streets_surface_audio.json` | `vs_surface_audio.py` | Systems |
| `vertical_slice_audio_concurrency.json` | `vs_audio_concurrency.py` | Systems |
| `vehicle_audio_loops.json` | `vs_vehicle_loops.py` (+ `fsb4.py`), validated by `validate_vehicle_loops.py` | Systems |

**Regenerate:**
`run_pipeline.py --only pstream_validate vs_destructibles vs_pickups vs_fineaim_hud vs_surface_audio vs_audio_concurrency vs_vehicle_loops validate_vehicle_loops validate_m03`

## New decoders (they make the rest possible)
* **`pstream.py`: WFC compiled particle modules.** Each module's type byte is the cooked enum
  `Engine.ParticleModule.EParticleModuleId` (`PMI_Lifetime=1` … `PMI_SubUVDirect=33`).
  * Distributions sit in a float group followed by a vector group. In each group they are in module order, then property
    order.
  * Two LOD census checks consumed every distribution exactly, with no leftovers: 2,290 LODs in `A1_IAC_Base_m` and 193 in
    `TransGame`.
  * A cross-check against surviving tagged modules matched 12/12.
  * Values are now assigned to **module + property**, not just listed in stream order.
* **`fsb4.py`: FSB4 bank and sample-header reader.**
* **`gfxscan.py` / `as2dis.py`: Scaleform GFX scanner and ActionScript 2 disassembler.**

## 1. Destructible wall panel (`streets_destructibles.json`)
### Object, blueprint and placement
* **Placed actor:** `MP_IAC_Streets_ART_m…TnStaticDestructibleActor_14465`.
  * Class chain: TnStaticDestructibleActor → TnDestructibleActor → HmDestructibleActorBase → Actor.
  * **Location (896, 89968, −352)**, rotation 0, scale 1.
  * Flags: `ForcePawnSeeThrough`, Tag `World`, `bWorldGeometry`, `bCanBeDamaged`.
* **Component:** `HmDestructibleComponent_15287`, Blueprint `DES_IAC_WallPanelSignDSYS_p.WallPanelSign`, BlueprintVersion 203,
  CodeVersion 1.
* **Blueprint variants:** `_Aqua` / `_Blue` exist in campaign levels and are not used in Streets.
* **Blueprint defaults:** DamageAngle 180, AI / radius damage modifiers 1.0, MinRadiusDamageDistanceForModifier 50.
* **Placement (CONFIRMED positions):** it is the **only Streets actor above Z = −50,000**.
  * ~70,000 UU above the play floor; nearest player start 138,859 UU away.
  * A 1:1 rebuild places it, but players cannot reach it (HIGH).
* **Not rendered by the slice:** `props.json` / `map.json` do not contain it; only `physics.json` does.

### One piece "Base" (piece offset Z −160) and three states (handle = list index)
| handle | role | InitialHealth | AutomaticTransitionTime | effects | exits |
|---|---|---|---|---|---|
| 0 | intact | **20** | – | static mesh `WallPanelSign_Base_STAT`; loop cue `BL_PROP_SIGNS.WALL_PANEL_EMIT_ELEC_LIGHT_HUM_HUGE` | → 1 on `HmGenericDamageDestructionTrigger`, `HmKismetDestructionTrigger`, `HmTouchDestructionTrigger` |
| 1 | destroyed | – | **10 s** | see list below | → 2 on `HmTimerExpiredDestructionTrigger` |
| 2 | settled | – | – | static mesh `Chunk02` | terminal |

State 1 effects:
* static mesh `WallPanelSign_Chunk02_STAT`
* physics chunk `Chunk01_STAT` (velocity (−200, 0, 0), angular (0.6, 0.5, 0), CollisionLifeSpan 999, CollideWithPawns)
* 6 debris chunks `DES_IAC_AirConditioner_p.Debri01_STAT` (speed 1000–1400, angular 10–40, cone 90°, lifespan 3 s,
  spawn volume 300×100×200)
* `FX_Level_Generic_p.FX.Sparks_Sporatic_FX` (terminates on state exit)
* `FX_Explosives_p.FX.TF_Death_Energy_Med_FX`
* cue `BL_PROP_SIGNS.WALL_PANEL_EXPLO`
* a state notification (Kismet `SeqEvent_HmDestructibleStateNotification`)

Other state facts:
* **No separate "damaged" state is authored.** Initial state = handle 0 (HIGH; engine convention).
* No Kismet object references this actor.
* State names are unset (default "State").

### Materials, collision and effects
* **Materials (cooked sections):**
  * Base / Chunk02 use `WallPanelSign_MATINST`.
  * Chunk01 uses `WallPanelSign_EMISSOFF_MATINST` + `DES_IAC_Omega_Cover_p.innerCyberParts_MATINST`.
  * Debris uses `innerCyberParts_MATINST`.
  * Both WallPanelSign MICs sit on `ORB_D1_Base_Shader_MAT` with `Emissive_Color` (0.94, 0.37, 0.21) and pulse rate 0.3.
  * **The emissive-on/off difference is not visible in authored parameters**: their compiled parameter lists are identical.
    It stays UNKNOWN (a static permutation).
* **Collision:** state meshes use template `TextureLightmapMeshTemplate0` (CollideActors / BlockActors / BlockZero/NonZero /
  BlockRigidBody / BlockCameras true, CastShadow true, bCastDynamicShadow false).
* **Particle systems:** fully decoded except one `Orbit` emitter, whose leftovers are listed explicitly.
* **Cues:** full graphs are included.

## 2. Pickup factories (`streets_pickup_factories.json`)
| class | n | RespawnTime | gives | visual | effect components (template, auto-activate, attached) |
|---|---|---|---|---|---|
| TnAmmoCratePickupFactory | 14 | 30 s | TnAmmoCratePickup (WT_Primary / Secondary / Vehicle) | `PROP_NEU_AmmoPickup_STAT`, rotating Yaw 10000 | PickupEffect `Pickup_FX`, **false**, attached |
| TnHealthPickupFactory | 9 | 60 s | TnHealthPickup **AddedHealth 50** | `HealthPickup_FX` (energon-cube mesh emitter) | Custom `HealthPickup_FX` true / attached; PickupEffect `Pickup_FX` false / **not attached** |
| TnOverShieldPickupFactory | 1 | 120 s | TnOverShieldPickup (amount native) | `OvershieldPickup_FX` | Custom `OvershieldPickup_FX` true / attached; PickupEffect `Pickup_FX` false / **not attached** |
| TnGameObjectivePickupFactoryFlag | 2 | 9999999 (inherited) | TnWeaponFlag; `RequiredGameRuleClass` = SingleFlagCTF | – | `Pickup_FX` false, attached |
| TnGameObjectivePickupFactoryBomb | 1 | 9999999 | TnWeaponBomb; ScoreBombingRun, WaitAfterScoreTime 5 | – | `Pickup_FX` false, attached |

Pickup sounds:
* Ammo: `BL_HUD_INTERFACE.HEALTH_PU_AMMO`
* Health: `HEALTH_PU_ENERGON`
* Overshield: `OVERSHIELD_POWER_UP`
* Plus a `PickupObtainedDialog` event each.

State machine:
* It is **UnrealScript** (decompiled by RE): TnPickupFactory `SetPickupVisible` / `SetPickupHidden` / `IsReadyToPickup` /
  `GiveTo` / `TakePickUp` / `GetRespawnTime`, and state `Pickup`. TnHealthPickupFactory overrides `SetPickupVisible`.
* **Correction (2026-10-03):** this pass first called these functions native stubs because their exports are only 50–144
  bytes. That was wrong.

**Beam activation (CONFIRMED; RE `MILESTONE04_STREETS_PICKUP_OBJECTIVE_PRESENTATION.md` §1, script decompilation):**
* `SetPickupVisible` → `PickupEffect.ActivateSystem()`; `SetPickupHidden` → `PickupEffect.DeactivateSystem()`.
* `InitializePickup` calls `SetPickupVisible` at begin play. So the `Pickup_FX` beam, although authored
  `bAutoActivate=false`, is **on whenever an attached factory is available** and off while taken or Sleeping.

| factory | beam |
|---|---|
| ammo crates (14) | on while available, every mode; off when taken; on again after the 30 s respawn |
| flag factories (2) | CTF only; otherwise Disabled (hidden, no collision). Each round only the defending team's factory is available (beam on); the other sleeps (beam off). Taken → Sleeping; returned → available immediately |
| bomb factory (1) | EXT only; otherwise Disabled. After a score it returns after `WaitAfterScoreTime` 5.0 s; other returns are immediate |
| health / overshield `Pickup_FX` (10) | never drawn: not in the `Components` array, so never attached |

* The health and overshield `CustomPickupEffect` follows the same visible/hidden path: shown while available, hidden on
  pickup, back after `RespawnTime`.
* `ShouldDisplayHighlightFx` = true on `TnAmmoCratePickupFactory` and `TnWeaponPickupFactory` (inherited by flag/bomb).

**TDM pickup state** (the vertical-slice mode; DM is identical). CONFIRMED: RE script decompilation plus the authored
`RequiredGameRuleClass`.

| factories | TDM state | drawn in TDM |
|---|---|---|
| ammo crates (14) | active: crate mesh + `Pickup_FX` beam while available, 30 s respawn | 14 meshes + 14 beams |
| health (9) | active: `HealthPickup_FX` while available, 60 s respawn | 9 effects |
| overshield (1) | active: `OvershieldPickup_FX` while available, 120 s respawn | 1 effect |
| flag factories (2) | **Disabled**: actor hidden, `SetCollision(false, false)`, no touch | 0 |
| bomb factory (1) | **Disabled** (same) | 0 |
| health/overshield `Pickup_FX` copies (10) | never attached | 0 |

* Drawn in TDM: **24 pickup effect components** (14 beams + 9 health + 1 overshield) and 14 ammo crate meshes.
* Machine-readable: `render_index.json` `tdm_render_state`, `pickup_fx_components` (`drawn_in_tdm` = 24) and
  `pickup_factory_visuals`.
* Machine-readable: the `state_behaviour.beam_activation` section of `streets_pickup_factories.json`, and
  `render_index.json` `pickup_fx_components`.

## 3. Pickup FX (`streets_pickup_fx.json`): **27 / 9 / 1 confirmed**
* **The particle systems are cooked in `TransGame`**, not in the Streets packages.
* **"Weapon pickup effect" is `FX_Pickups_p.FX.Pickup_FX`**:
  * 14 ammo + 9 health + 1 overshield + 2 flag + 1 bomb = **27 components**.
  * It is a highlight light beam with `bAutoActivate=false`. Script activates it whenever the factory is available (see
    the beam-activation rule in §2).
  * The 10 copies on health/overshield factories are not attached.
* **`Pickup_FX`:** one mesh emitter, `LightBeam_WepPickup_STAT`, material `LightVolume_WepPickup_MAT` (additive, unlit,
  two-sided).
  * Local space, LODDistances 0 / 10000.
  * Spawn rate: LOD0 2/s, LOD1 0.4/s. Lifetime: LOD0 3.0 s, LOD1 0.6 s.
  * StartSize uniform (1.5, 3, 1.5)…(2, 5, 2).
  * StartColor (0.5, 0.4, 0.15), StartAlpha 0.5.
  * Sphere location: radius 1, velocity scale 1, offset (0, 0, −10).
  * Alpha-over-life curve 0→1→0 (21 samples).
  * Size-multiply-life curve.
  * Velocity uniform ±5.
  * MeshRotation (−0.25, 0, 0).
* **`HealthPickup_FX`:** GlowMut, GlowADD and an energon-cube mesh emitter.
  * The mesh is `PROP_NEU_EnergonCube_STAT`: one burst particle, Lifetime 0 (never expires), StartSize 0.85,
    rotation rate 0…0.1, Z offset +200.
  * GlowMut spawns 1–2/s, Lifetime 1.0…0.75, size 300…500, colour (0, 0.5, 1); LOD1 colour (1, 0.3, 1).
  * LODDistances 0 / 15000.
* **`OvershieldPickup_FX`:** same structure.
  * Mesh `PROP_NEU_Overshield_STAT`, spawn 1–2/s, StartSize 0.7, rotation rate (0, 0, 0.1), Z +190.
  * Glows are blue (0, 0.3, 1).
* **Every LOD of all three systems decodes completely** (validated).
* **Distribution layout rules** (constant / uniform / curve headers) are in `distribution_layout`.
* **PARTIAL:**
  * The health/overshield mesh emitters set `bOverrideMaterial=true` with no RequiredModule material. The only authored
    material is the mesh section material; native fallback is UNKNOWN.
  * Raw flag bytes per module are kept but not interpreted.

## 4. Fine Aim HUD (`fineaim_hud.json`)
The reticle stays the same under Fine Aim; only its prongs tighten.

* **HUD movie:** `TnHUD.HudMovie = UI_GFxHud_p.Hud_GFX_1` (`content/UI_GFxHud_p/Hud_GFX.gfx`, 1120×720, 30 fps).
* **Ion Blaster reticle = `mc_crosshairIonBlaster`.**
  * The weapon-change handler selects it by class name `TnWeaponIonBlaster` (`SetWeaponCrosshair(2)`).
  * It has three prongs at 0° / 120° / 240°, art `Hud_GFX_I190.png` (30×12 px).
  * Centre of stage. It spins in from 60° over 0.3 s when the weapon changes.
* **No special Fine Aim reticle for the Ion Blaster (CONFIRMED).** In `NotifyFineAimChanged(1)`:
  * Only HeavyPistol, BurstRifle and SniperRifle show a scope (short / medium / long).
  * Every other weapon gets `hideScope()`.
  * The crosshair is neither hidden nor replaced.
  * TnWeaponIonBlaster leaves `HasFineAimScope` false and `ReticuleType` = WRT_Default; HeavyPistol and SniperRifle set the
    scope flag to true.
* **Visible Fine Aim change: the prongs move inward.**
  * Prong offset = spread × −300 px, eased 0.2 s.
  * Ion Blaster `FineAimSpreadModifier` = 0.5. The value feeding this is native (HIGH).
* **Target tint:** friend 0x50B5D5, enemy 0xFF3333, none white (0.2 s).
* **Visibility:** the ammo panel hides the crosshair when ReserveAmmo == −2 or ReserveCapacity < 0.
* **Callback wiring:** `TnHudDataObserverCurrentWeaponAndAim` (SavedWeaponClass, SavedAimType kHudStandardAim / kHudFineAim)
  → `NotifyCurrentWeaponChanged` / `NotifyFineAimChanged` (HIGH: the native call site is not authored).
  * The `NotifyWeaponReticuleTypeChanged` binding has **no handler** in this movie.

## 5. Streets surface audio (`streets_surface_audio.json`)
* **All Streets surfaces map to one identical footstep table, so there is no surface-specific robot footstep audio on this
  map (CONFIRMED).**
* **Physical materials:**
  * 176 materials: 120 → `Metal_PHYSMAT`, 6 → `ForceField_PHYSMAT` (no property object), 1 → `Water_PHYSMAT`,
    1 → `Rubber_PHYSMAT`, 48 → none (engine fallback `DefaultPhysMaterialName = Metal_PHYSMAT`).
  * 2 BlockingVolumes override to Metal.
  * No `SeqAct_SetFootstepMaterialOverride` in Streets.
* **Footstep table:** every `TnPhysicalMaterialProperty.FootstepSounds` (and the HmFootstepComponent defaults) gives
  `FS_DEFAULT_*`. Unset slots fall back to `TnPawn.FootstepComp0.Default*Sound`, which are the same events.
* **Event → cue (`SoundEvents.CHR_OPTIMUS`):**
  * walk → `BL_FS_LRG_BOT.FS_WALK_DEFAULT`
  * run → `FS_RUN_DEFAULT`
  * scuff → `FS_SCUFF_DEFAULT`
  * jump → `FS_JUMP`
  * land → `FS_LAND_DEFAULT`
  * hard land → `FS_LAND_HARD`
  * charged jump → `FS_JUMP_CHARGED`
  * high-fall land → `FS_LAND_HIGH_FALL`
  * jog / crouch / dash-land are **unmapped** (silent).
* **Robot-size distinction is per character event set:** LRG_BOT ×16, MED_BOT ×14, SML_BOT ×7, BRUTE ×6.
* **Cue graphs:** WaveEvent variants, volumes and pitch are included.

## 6. Cue concurrency (`vertical_slice_audio_concurrency.json`)
* **Scope:** 140 cues.
* **Cue fields:**
  * `MaxConcurrentPlayCount`: authored on 67, inherited CDO 5 on 73.
  * `InstanceLimiting`: authored on 7 (kKillNewest); all others inherit kKillFarthest.
  * Root `Priority`: authored on 129.
* **Examples:**
  * Footsteps / jump / land: max 3, priorities 25–75, category SFX_WET_NAV.
  * Vehicle engine loops: max 5 (inherited), priority 200.
  * Boost wheels and vehicle death: max 1.
  * Dry fire: max 1.
* **ChannelCountMixerPreset:** "None" on every category used by the slice.
* **Schema-absent (UNKNOWN, native):** per-owner vs global counting, virtualization, steal fade, non-dialog retrigger delay,
  priority-based stealing.

## 7. Vehicle FSB loops (`vehicle_audio_loops.json`, validator 728/728)
* **Scope:** 39 waves reached from the Optimus vehicle audio component.
* **Format:** every one is a single-sample XMA FSB4 bank at 24/36/48 kHz.
* **Header loop data (CONFIRMED):** `loopstart = 0`, `loopend = N−1`, no LOOP_* mode bit. Census: all 1,929 FSB4 samples in
  three packages share this form.
* **The sample-header loop region is the whole sample.** No wave carries custom loop points.
* **Cue-level loops:** 7 waves are looped by their WaveEvent (`bLooping`): `AUTO_OPTIMUS_ENGINE_MID_LR_LP`,
  `AUTO_OPTIMUS_IDLE_LR_LP`, `AUTO_OPTIMUS_ENGINE_BOOST_LR_LP`, `SYNTH_ENERGY_MOD_PAN_LP`, `JET_TURBO_WHINE_LP`,
  `MECH_OPTIMUS_TIRE_NOISE_02_LP`, `MECH_TIRE_SQUEAL_HEAVY_LP`.
* **Start / loop / end roles** come from the component slot (e.g. BoostSound START, BoostLoops LOOP, BoostStopSound END).
* **Cue-root `LoopStart/LoopEnd` floats** are listed only in a field marked "NOT the loop authority".

## 8. Inventory audit (P7)
* All 27 factories are in `gameplay.json`, and all 37 effect components are in `map_fx.json`.
* The wall panel is missing from the rendered slice manifests (see 1).
