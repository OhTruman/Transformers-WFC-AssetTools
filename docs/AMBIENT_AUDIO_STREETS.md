# MP_IAC_Streets ambient audio setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/audio.json`**. Regenerate with
`AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_audio.py` (reads `manifests/authored.db` through `authored.py`;
trigger polygons come from `collision.json`). All 32 cues and **54/54 waves resolve to extracted WAVs**.
Handoff: **Systems** (audio), **Gameplay** (zone triggers / spawn zones). Units: UE units (cm), volumes in dB, mixer reverb in FMOD mB.

## Structure (CONFIRMED)
Everything lives in the streamed sublevel **`MP_IAC_Streets_AUDIO_m`**:
1. **70 emitters** that are always on, all playing cues from the map bank `BL_LVL_MP_IAC_STREETS`:
   * 40 `AmbientSound`: point sources; `AudioComponent.SoundCue` + Location/Rotation/DrawScale.
   * 17 `HmAmbientSoundVolumeEmitter`: the class default `Radius` is 500, scaled per actor by `DrawScale3D`. 7 of them are the
     regional 2D room-tone beds `AMB_*` (all tagged "Steam Room", a copy-paste tag).
   * 13 `HmAmbientSoundLineEmitter`: the class default `LineLength` is 500, scaled per actor (pipes, screens, monitors).
2. **9 Kismet audio zones** (`Main_Sequence`):
   * `SeqEvent_Touch` on a `TriggerVolume` (`bLocalPlayerOnly`, `bClientSideOnly`, `bForceOverlapping`, unlimited triggers, the camera ignored)
     fires `SeqAct_AmbientAudioZone.Enter`.
   * "Scene 0 Begun" then calls `SeqAct_Reverb` (mixer preset) and **START**s the zone sub-sequence.
   * "Scene 0 Ended" **STOP**s the zone sub-sequence.
   * Each sub-sequence runs `SeqAct_PlayPlayerPositionalSound` pools: looping random one-shots, delayed DelayMin–DelayMax s, placed
     DistanceMin/Max = 2000 UU from the player.
   * Editor frames group the zones as EXTERIOR / NEUTRAL / AUTOBOT / DECEPTICON / TRAIN YARD.
3. **Reverb presets**: these are `SoundConfig.SoundMixerProperties.MixerPresets` entries (priority, fade). Their DSP values are in
   `SoundCategories[MASTER_WET].DSPPresets[<preset>]`: Reverb, Echo, filters, EQ and compressor.
4. **Music**: every Streets `TnWorldInfo` has an empty `HmMusicPlayer` (class defaults: SpazTime 5, fades 1 s). MP music is not
   map-authored; it comes from the game mode or native code (UNKNOWN). BASE's WorldInfo sets
   `AnnouncerSoundEventSet = SoundEvents_Dialog.Announcer.CHR_ANNOUNCER_DIALOG`.

## Zones
| zone | trigger | reverb preset | priority | fade in/out s | Room mB | Decay s | RoomHF mB | Reflections/Level mB | Echo delay ms / wet | one-shot pool |
|---|---|---|---|---|---|---|---|---|---|---|
| NEU_BASE | TriggerVolume_9729 | `NEU_BASE` | 183 | 0.25/0.25 | -650 | 2.06 | -700 | -760/-600 | 500 / 0.0 | PP_SMALL_ROOMS 4–9 s |
| AUTO_ROOM_02 | TriggerVolume_8662 | `AUTO_ROOM_02` | 220 | 0.25/0.25 | -900 | 4.81 | -700 | -780/-800 | 207 / 0.158 | PP_OPEN_ROOMS 4–9 s |
| NEU_HALL | TriggerVolume_10361 | `NEU_HALL` | 218 | 0.25/0.25 | -900 | 2.75 | -850 | -600/-600 | 108 / 0.158 | PP_TUNNEL 4–9 s |
| EXTERIOR | TriggerVolume_3727 | `EXTERIOR` | 182 | 0.25/0.25 | -800 | 2.65 | -985 | -900/-600 | 475 / 0.1 | PP_EXTERIOR_EXPLOSIONS 3–8 s, PP_EXTERIOR_ROCKETS 3–8 s |
| TRAIN_TUNNEL | TriggerVolume_3102 | `TRAIN_TUNNEL` | 221 | 0.25/0.25 | -900 | 4.32 | -1400 | -1100/-800 | 108 / 0.089 | PP_TRAIN_TUNNEL 4–9 s |
| NEU_STAIRWELL | TriggerVolume_13344 | `NEU_STAIRWELL` | 222 | 0.25/0.25 | -650 | 3.33 | -800 | -750/-650 | 500 / 0.0 | PP_TUNNEL 5–10 s, PP_SMALL_ROOMS 5–10 s |
| DEC_ROOM_LOWER | TriggerVolume_2182 | `DEC_ROOM_LOWER` | 217 | 0.25/0.25 | -630 | 3.24 | -800 | -750/-600 | 500 / 0.0 | PP_CORRIDORS 4–9 s |
| DEC_ROOM_UPPER | TriggerVolume_5812 | `DEC_ROOM_UPPER` | 223 | 0.25/0.25 | -936 | 3.14 | -887 | -600/-600 | 452 / 0.056 | PP_CORRIDORS 4–9 s |
| AUTO_ROOM_01 | TriggerVolume_6486 | `AUTO_ROOM_01` | 216 | 0.25/0.25 | -850 | 2.35 | -700 | -650/-600 | 500 / 0.0 | PP_MEDIUM_ROOMS 4–9 s |

All presets are prefixed `REVERB_TRANS_MP_STREETS_`. Full Reverb fields (RoomRolloffFactor, DecayHFRatio, ReflectionsDelay, Delay,
Diffusion, Density, HFReference), Echo, EQ, LowPass and Compressor are in `audio.json.reverb_presets`.
`REVERB_TRANS_MP_STREETS_TRAIN_DEPOT` is defined (priority 219, decay 2.65 s) but **no zone uses it**: an orphaned authored preset.

## Emitters (cue, root volume dB, DistanceMin–Max UU, category, waves)
| kind | cue | count | tags | dB | distance | category | waves |
|---|---|---|---|---|---|---|---|
| line | `EMIT_COMPUTER_MONITOR_01` | 5 | Computer Monitor01 | -8 | 1000–5000 | SFX_WET_AMB_3D | 2 |
| line | `EMIT_COMPUTER_MONITOR_02` | 3 | Computer Monitor02 | -8 | 1000–5000 | SFX_WET_AMB_3D | 1 |
| line | `EMIT_HEAT_CORRIDOR` | 1 | Heat Corridor | -18 | 3000–8000 | SFX_WET_AMB_3D | 1 |
| line | `EMIT_LONG_SCREEN` | 1 | Long Screen | 0 | 1500–5000 | SFX_WET_AMB_3D | 1 |
| line | `EMIT_MAGMA_PIPE` | 2 | Magma Tube | 0 | 2200–7000 | SFX_WET_AMB_3D | 1 |
| line | `EMIT_METAL_LIQUID_PIPE` | 1 | Metal Liquid Pipe | -4 | 1800–5500 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_COMPUTER_MONITOR_03` | 1 | Computer Monitor03 | -5 | 1000–5000 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_ENERGON_GENERATOR` | 1 | ENERGON GENERATOR | -3 | 2600–6000 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_ENERGON_LIQUID_CRATERS` | 12 | Energon Liquid Craters | -18 | 1000–5000 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_FLOOD_LIGHTS` | 5 | Flood Light | -13 | 2000–6000 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_FLOURESCENT_LIGHTS` | 13 | Flourescent Lights | -16 | 1000–5000 | SFX_WET_AMB_3D | 1 |
| point | `EMIT_LAMP_POSTS` | 8 | Lamp Posts | 0 | 2000–4000 | SFX_WET_AMB_3D | 1 |
| volume | `AMB_AUTO_CONTROL_ROOM` | 1 | (bed) | -8 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_AUTO_FOYER` | 1 | (bed) | -11 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_AUTO_MAGMA_CHAMBER` | 1 | (bed) | -5 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_DECEPTICON_BASE` | 1 | (bed) | -9 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_EXTERIOR` | 1 | (bed) | -12 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_NEUTRAL_BASE` | 1 | (bed) | -12 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `AMB_TRAIN_YARD` | 1 | (bed) | -12 | 900–4500 | SFX_WET_AMB_2D | 2 |
| volume | `EMIT_ENERGON_VENTS` | 3 | Energon Vents | -3 | 800–2000 | SFX_WET_AMB_3D | 1 |
| volume | `EMIT_FIRE_CHAMBER_LP` | 2 | Fire Chamber | -5 | 2500–9000 | SFX_WET_AMB_3D | 3 |
| volume | `EMIT_MONRAIL_IDLE_LP` | 1 | Monorail Idle | -9 | 1800–9500 | SFX_WET_AMB_3D | 1 |
| volume | `EMIT_ROTATING_MECH_GLOBES` | 3 | Rotating Mech Globes | -10 | 1600–9000 | SFX_WET_AMB_3D | 1 |
| volume | `EMIT_SPINNING_GENERATORS` | 1 | Spinning Generators | -5 | 2000–6000 | SFX_WET_AMB_3D | 1 |

The `AMB_*` beds are 2-layer looping 4-channel beds: an `_LR` wave plus an `_LSRS` wave whose front pans are set to −96 dB, so it plays from the rears only.
They use SmartPan, RolloffFactor 3 and RearAttenuation −2 dB; the per-cue pitch offsets are in `audio.json.cues`.

## Validation
* 70/70 emitters and 9/9 zones resolve, with 0 missing cues and 54/54 WAVs.
* All 9 trigger volumes have world polygons (6–32 faces). The Exterior volume is **non-convex**, so use ray-parity point tests, not half-spaces.
* **Player starts:** of 84, 76 lie in exactly one zone, **0 in two zones**, and 8 lie in gaps.
  * By zone: DEC_UPPER 14, DEC_LOWER 13, NEU_BASE 13, AUTO_02 12, EXTERIOR 9, AUTO_01 8, TRAIN_TUNNEL 6, NEU_HALL 1.
  * The zones are authored as a partition.
* The `authored.db` cue graphs agree with the direct package reader (BOOST_START root and waves identical). The cross-check
  exposed a `vs_evidence.py` bug: WaveEvents with several child waves were truncated to the first. Fixed; 7 such events exist in the slice cues.

## Inferred / unknown (native)
* INFERRED: entering a zone ends the previously active zone's scene, so exactly one reverb and pool is active at a time. A player who
  spawns inside a volume enters it at once (`bForceOverlapping`); a player in a gap starts with no zone reverb.
* INFERRED: volume-emitter box half-extents = Radius × DrawScale × DrawScale3D; line length = LineLength × DrawScale3D.X. How the
  native code positions the sound on the shape (nearest point to the listener) is unknown.
* INFERRED: `SoundNodeWaveEvent` with several children picks a random variant (class default `LastWaveNode −1`). Its class default
  pans Center/BackL/BackR/LFE to −96 dB, so wave events are front-stereo unless they override that.
* UNKNOWN: the bit meaning of `DSPEffectConfig`. Raw values: MASTER_WET 280, Master 32, DX_WET_PA 261, DX_DRY_RADIO 128, several categories 8.
  `DX_WET_LOPASS = 8` suggests bit 3 = LowPass.
* UNKNOWN: MP music selection and playback (no map data).
