# Campaign chapter A1 (A1_IAC): asset manifest (AssetTools, 2026-10-18; read-only)

**Purpose:** campaign background prep. The data goes first; code starts after online MP.

**Files:**
- Manifest: `AssetTools/manifests/campaign/a1_assets.json`.
- Generator: `scripts/wfc/campaign_chapter_assets.py <CH>`. It is reusable per chapter (A2_KON … D5_OME; reads the campaign
  VerticalSlice + `manifests/next_map/<CH>_*.json`). Run it through `run_bounded.py`: A1 took 12 s with a 0.8 GB peak.
- Labels: everything is cooked / authored data (CONFIRMED) except the translator status, whose definition is PROVISIONAL (§3).

## 1. What A1 loads

**Levels:** `A1_IAC_Base_m` (persistent) + 50 streaming sublevels = **51 level packages**, all cooked. The list comes from
`streaming.json`: LevelStreamingKismet + LevelStreamingState, with 26 checkpoints.

**Companions:**
- 48 `_LM` (lightmap) packages.
- 20 `_LOC_int` / 20 `_LOC_FRA` packages, which hold the localized dialog waves. FRA is 3.5 MB.
- An INT build loads level + `_LM` + `_LOC_int`; FRA swaps in `_LOC_FRA`.

**Package dependencies:** 179 (script, ENV / FX / TR / WEP / BL_ / WL_ banks); listed in the json.

**Seek-free cook:**
- Content is inline in the level packages under its source names, so the loaded set is the union of their exports by object path.
- **185,056 distinct objects, 466.1 MB** (cooked export bytes, each object once).
- The level packages hold 914.0 MB together, because objects are duplicated across levels.

## 2. Per class (distinct objects; cooked bytes)

| group | count | MB | status |
|---|---|---|---|
| static meshes | 676 | 34.7 | all extracted (.gltf) |
| skeletal meshes | 137 | 22.3 | all extracted (.gltf) |
| materials (Material / MIC / MITV / Decal) | 1,090 | 2.3* | translator: 569 translated, 416 candidate, 103 missing, 2 engine default, 0 error (§3) |
| textures | 1,528 | 78.0 | 1,510 extracted; **18 not** (15 cube maps, a render target, 2 others) |
| lightmap / shadowmap textures | 1,077 | 32.2 | in the `_LM` companion packages |
| FX templates (ParticleSystem) | 281 | 0.04* | pstream: 279 COMPLETE, **2 PARTIAL** |
| sound cues | 1,821 | 0.1 | every wave they play has a file |
| sound waves | 2,604 | 30.7 | 1,803 plain + 1,139 INT + 1,177 FRA files; every localized wave has its FRA twin |
| anim sets / sequences | 237 / 2,031 | 0.2 / 28.4 | 234 converted (.anim.gltf); **3 only as raw .psa** |
| FaceFX assets | 9 | 1.4 | all extracted (.fxa) |
| physics assets | 53 | 0.0 | — |
| Kismet sequences | 486 | 0.2 | §4 |
| matinee InterpData | 496 | 0.1 | §4 |
| GFx movies | 13 | 1.0 | all extracted |
| shader caches | 147 | 78.4 | Xbox shader bytecode: not usable, not needed |

\* The group's own export only. Emitters, LODs, modules and material expressions are sub-objects; they count in the totals, not here.

## 3. Material translator status (PROVISIONAL definition)

Rendering's translator (material → GLSL) has run only on the MP and UI maps (`Rebuild/work/render/<map>/materials_glsl.json`). For
A1 I derived the status:
- **translated:** the material has GLSL and no error in some MP / UI set. 569.
- **candidate:** not translated itself, but its master Material is the master of a translated material, so the instance only changes
  parameters. 416.
- **missing:** the master has never been seen by the translator. 103 materials on 72 masters.
  - Top masters: DarkEnergon_Spread (5), CHR_DestructiblePieces (5), Smoke_FadeCloseParent (4), Ring_Base (4), Collectibles (4),
    CHR_Transformer_Hologram (4), SatMouthLaser (3), HealBubble2 (3), EnergonTank PanningEmissive (2), Hologram_Post (2),
    IAC_SkyDome2_PARENT (2), ENV_Bridge_Lock (2).
  - Full list with `master` per row in the json.
- **engine_default:** EngineMaterials.*. 2.

## 4. Gameplay data (from the per-chapter manifests already in `manifests/next_map/`)

**Kismet** (`A1_IAC_kismet.json`): 475 Sequence objects; 16,658 Kismet objects across 51 levels.

**Matinee** (`A1_IAC_matinee.json`):
- 495 InterpData, 1,633 groups (89 without a bound actor).
- **30 unbound groups are `live_without_actor`:** they have event / sound / dialog tracks, so they still fire (RE `CAMPAIGN_PROVISIONALS_CLOSED_RE.md`).

**AI** (`A1_IAC_pawn_factories.json`):
- 143 pawn factories: 135 TnActorFactoryAI + 8 SentryAI.
- Top archetypes:
  - Soldier_MachineGun_Decepticon 35, Soldier_Jet_Decepticon 24, Soldier_MachineGun_Autobot 13, Soldier_Jet_Autobot 11, Rocket_Dec 10,
    Sniper_Dec 9, Jet_Dec_Defender 8, Car_Dec 8, Protector_Dec 6;
  - turrets: RepairSentry 4, WarshipHomingRocket 4;
  - Titan_Aut 3, StarScream_Boss 2, Brute_Dec 2, Titan_Dec 2, Car_Aut 1, Rocket_Aut 1.

**Dialog** (`A1_IAC_dialog.json`):
- 72 conversations, 122 lines.
- Every line has a wave and a bound speaker; 131 waves have INT subtitles, 115 have FaceFX.

**Objectives** (`A1_IAC_objectives.json`):
- 7 bank keys, A1_OBJ1–7, with INT and FRA text (texts in the json).
- 14 setters; 7 of them are whitespace no-ops.

**Checkpoints:** 26 (tag, display order and streaming state in the json). "2 - Balcony (Art Only)" is an authored art-only checkpoint.

**Movies:** FMV_a1intro (94.1 s), FMV_a1outro (81.5 s), FMV_a1text_INT / FRA (28.1 s), converted in `out/movies`.

## 5. Gaps

**The dump lacks nothing for A1:**
- All 51 streaming levels are cooked.
- 0 content imports are unresolved, and 0 resolve only in packages A1 doesn't load.
- The remaining imports (15,987) are script / native class references (Core, Engine, HM_Engine, TransGame, TransContent, GFxUI,
  WinDrv), not content.

**Our extraction lacks** (fixable on our side; not dump gaps):
- 18 textures without a PNG: the CubeMaps (CHR_Metals A/B Center, CHR_Metals_CUBEMAP / 3D, ENV_Desaturated_Glass, ENV_Glass,
  ENV_Metals, ENV_WarmStreaks, Iacon_Halls, Iacon_Streets, IaconCity, StreetStreet, Iac_streets_cube, Glass_Blue_CUBE, FluidCubemap),
  `UI_Interacts_p.Center_Screen_R2T` (a render target, no pixels), `FX_Textures_p.Textures.Drop_CLR` and
  `ENV_IAC_Interior_1_p.Materials.Interior_Spacers_BUMP`.
- 3 anim sets only as raw `.psa`, not yet converted: `TR_LightSmall_ANM_p.Interact_ROBO_ANIM`, `VIG_Run_ANIM`, `VIG_Scanning_ANIM`.
- 2 PARTIAL FX templates (4 PROVISIONAL distributions each: SubUVDirect SubUVPosition / SubUVSize, the known open order): `FX_H2H_p.FX.H2H_Punch01_FX`,
  `FX_Transformers_p.FX.Transforming_Impact_Sm_FX`.
- Translator: 103 materials on 72 masters the translator hasn't seen (§3).
