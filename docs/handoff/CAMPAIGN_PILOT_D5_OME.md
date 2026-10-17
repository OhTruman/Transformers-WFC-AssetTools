# Campaign pilot: D5_OME through the generic map pipeline (2026-10-16, PROVISIONAL)

Integration (rebuild-bd) gave the GO. The final Decepticon chapter (Omega Supreme; 9 map packages, 155 MB uncompressed) went through
`run_map_pipeline.py` unchanged, CPU only, each stage under `run_bounded.py` (6 GB cap, which refuses to start while any PERF_HOLD exists), `hold_wait.cmd` before launch.

**Output root:** `AssetTools/work/campaign_pilot/VerticalSlice/Maps/D5_OME/` (37 MB).
- The one code change is an opt-in output-root override in `vs_common.py`: `WFC_VS_ROOT`. Unset, `VS` is still
  `ExtractedAssets/VerticalSlice`, so MP/Streets outputs are unaffected.
- ExtractedAssets and the Game Dump were not written: no `D5_OME` folder exists and no file under ExtractedAssets/VerticalSlice is
  newer than the run.
- The per-map manifests went to AssetTools `manifests/maps/D5_OME/` and `manifests/next_map/D5_OME_*.json`. These are new files keyed
  by map name; no MP manifest was touched.
- Runners: `work/campaign_pilot/run_d5.cmd` and `run_d5_rest.cmd`. Logs: `logs/D5_OME_pipeline/`.

**Wall time:** about 80 s for the main stages plus about 40 s for the rest. Peak job memory was 2.5 GB (vs_map), so the "about a day"
estimate was far too high.

## 1. What exported

The driver ran 19 of its 32 stages before `validate_smca_transforms` stopped it (see blocker 1). I ran the 10 stages that follow
directly, with the same wrapper. Nine of them passed; `vs_validate` failed (blocker 2). Results:

| output | result |
|---|---|
| level hierarchy | **all 9 map packages** found through authored LevelStreaming: ART, AUDIO, BASE, CINE_LevelIntro, CINE_Outro, DSN, GLB_ART, GLB_AUD, Music |
| `world.glb` (glTF placement) | 1,341 placed meshes (153 unique); 5 without a mesh (blocker 1); BSP 612 triangles (ART only) |
| SMCA transforms | 1,291 / 1,291 exact (319 mirrored, 547 non-uniform), all handled |
| collision | `collision.glb` + pawn/weapon variants; 101 BlockingVolume, 4 TnTeamBlockingVolume |
| lighting | `lighting.json`, `lights.json`, `light_probes.json`, `postprocess.json` (3 PostProcessVolumes, 2 CLUTs), fog COMPLETE |
| lightmaps | `lightmaps.json` + 71 atlas PNGs, `vertex_lightmaps.json`, destructible lightmaps |
| nav | `navigation.json` + `navigation.glb`, COMPLETE (123 NavigationCell, 210 TnTacticalPathNode, 99 TnTacticalAirPathNode, 64 AirPathNode) |
| materials | `materials.json` / `materials_authored.json`: 115 materials (see 4) |
| gameplay / audio / FX | `gameplay.json`, `spawnpoints.json` (1 TnCampaignPlayerStart, 8 weapon, 3 health, 2 ammo factories, 4 objective markers), `audio.json`, `map_fx.json` (67 particle components, 21 systems) |
| physics / destructibles | `physics.json`; 36 TnStaticDestructibleActor (`D5_OME_destructibles.json`) |
| Kismet | `manifests/next_map/D5_OME_kismet.json` (35 startup events; see 3) |
| render index | `render_index.json` (generic): 13 glTF paths, 0 missing |
| structure audit | **PASS** (`manifests/maps/D5_OME/structure_audit.json`) |
| completeness | **INCOMPLETE** (`manifests/maps/D5_OME/completeness.json`): 46 checks: 33 COMPLETE + structure_audit PASS, placed_meshes PARTIAL, 3 AUTHORED (movers, moving scenery, BSP default faces), 2 EXPORTED (map_fx, particles), decals NONE. Missing: loading screen, thumbnail, frontend name, mode compatibility (MP-lobby concepts with no campaign equivalent in the checker). vs_validate FAIL (blocker 2) |

- **`materials_glsl.json` is Rendering's output (matc), not this pipeline's.** For Rendering: `work/campaign_pilot/D5_OME_materials_for_rendering.json`
  lists the 115 materials.
  - 81 have an exported `.mat` file.
  - 69 are already compiled in some Rendering `materials_glsl.json`.
  - So 46 still need a matc pass; 34 of the 115 have no `.mat` file.

## 2. Streaming structure: what the pipeline needs

- The chapter persistent level is `D5_OME_BASE_m` (Kismet, checkpoints, objectives). It streams 8 levels through 8 `LevelStreamingKismet`:
  - art: ART, GLB_ART (sky and backdrop cards);
  - audio: AUDIO, GLB_AUD, Music;
  - design: DSN;
  - cinematics: CINE_LevelIntro, CINE_Outro.
- Here the generic pipeline **already works on the chapter model**. `map_levels()` picks BASE/ART/AUDIO by name, and `vs_map` follows
  the authored LevelStreaming list for the rest, giving all 9. D5 fits because its packages carry the MP-style `_BASE/_ART/_AUDIO`
  names.
- **Not yet handled (needed for the larger chapters):**
  1. **Per-sublevel load state.** All 9 levels are merged into one world with everything visible. The chapters load and unload sublevels
     from Kismet (`SeqAct_SetStreamingState` / LevelStreamingKismet; A1 has 50, A2 55). The runtime needs a sublevel tag on every node
     (the per-prop `sublevel` field exists in `props.json`) and the streaming volumes / Kismet calls that switch them.
  2. **Package naming.** The other chapters name their persistent level `*_Base_m` / `*_BASE_m` (handled case-insensitively), but most
     have no `<CHAPTER>_ART_m` or `_AUDIO_m`. Their art is in `A1_IAC_SideAlley_Art_m` etc., reached only through the streaming list.
     That works today, but `bsp_level()` falls back to "the level with the most BSP triangles" and per-section lightmaps / BSP need
     handling per sublevel. To check on a 50-sublevel chapter.
  3. **Scale.** D5 is the smallest chapter (1,341 props). A1 has about 4,500 static mesh actors and collection actors over 50
     sublevels; peak memory should stay under the 6 GB cap but is unmeasured.
  4. **Cinematic sublevels.** CINE_LevelIntro / CINE_Outro are merged as normal geometry. They should be tagged and stay hidden outside
     their matinee.

## 3. Blockers for D5_OME

1. **5 props with no mesh** (validate_smca_transforms FAIL, which stops the driver). All 5 are `GLB_ART` StaticMeshCollection
   components carrying sky/FX materials: LightRaysV2Orange ×3, IaconNightGlowl, FireSky. Their StaticMesh reference does not
   resolve (`mesh not extracted`). This is data-side, and visually they are light-ray / sky cards. The fix would be to resolve the mesh
   import or skip mesh-less components in the validator; that is a code change, not made.
2. **`vs_validate` is MP-slice specific.** It crashes on `robot non-empty` (`vs_validate.py:147`; the check expects the MP robot
   preview), so 0 of its checks ran. A campaign variant needs to skip the MP-only checks. Not changed.
3. **Kismet** (counts from the inventory and `D5_OME_kismet.json`): BASE has 5 Sequences.
   - **Startup:** 4 SeqEvent_GameplayStarted and 31 SequenceActivated.
   - **Flow:** 29 RemoteEvent/ActivateRemoteEvent; checkpoints via SeqAct_SetActiveCheckpoint ×2; objectives via
     SeqAct_TnSetCurrentObjective ×4.
   - **Chapter-specific actions:** TnSeqAct_SetOmegaStage ×3, TnSeqEvent_OmegaStatus, SeqAct_TnCorruptOmegaBattery ×4 (with 5
     TnInteractCorruptOmegaBattery actors), TnSeqAct_MissionComplete ×2, SeqAct_TnPawnFactory ×30 (enemy spawns),
     SeqAct_TnAiMoveToActor ×24, SeqAct_MoviePlayer ×2 (FMVs).
   - **Decomp gaps:** custom classes with no file in the RE decomp, matched by file name (PROVISIONAL):
     - Kismet and interaction: TnSeqAct_MissionComplete, TnSeqEvent_Interact, TnSeqEvent_OmegaStatus, SeqAct_TnAiMoveToActor,
       TnInteractCorruptOmegaBattery, TnInteractButton, TnInteractEmote, TnInteractPathNode, TnMountableTurret(IonicDisplacer/Rocket).
     - Actors: TnStaticDestructibleActor, TnCollectableAchievementItemDecepticon, TnAssetReferencesCampaign.
     - Sound: HmSoundEvent, HmSoundParameter, HmAnimNotify_Sound, HmDialogCharacter.
   - The other ~60 Tn/Hm classes used here (TnInteractAction*, SetOmegaStage, PawnFactory, …) have a decomp file.
4. **Matinee:**
   - **Counts:** 40 InterpData driven by 40 SeqAct_Interp, with 24 InterpGroupDirector (cutscene camera cuts), 27 CameraActor,
     77 InterpTrackAnimControl, 66 InterpTrackSound, 27 InterpTrackEvent and 13 InterpTrackFaceFX.
   - **Linked actors:** SeqAct_Interp drives 39 SkeletalMeshActorMAT, 24 cameras, 24 emitters, 9 HmSkeletalMeshActor and 8
     InterpActor. 47 movers are PHYS_Interpolating.
   - **Minimum player:** a matinee player with move, anim, sound, event and director tracks.
5. **FaceFX / dialog:** 7 FaceFXAsset, 13 InterpTrackFaceFX, 165 HmAnimNotify_Dialog, 21 HmSoundEventDialogGroup, 10
   HmDialogCharacter, 9 HmDialogEventManager, 948 SoundCues across the 9 packages.
   - Lip-sync exists only for the cutscene FaceFX tracks.
   - In-game dialog is driven by anim notifies and dialog groups.
6. **Characters:** TnSeqVar_Character ×52 and SeqAct_TnPawnFactory ×30. The Omega Supreme encounter and the enemy waves need the
   AI and character-definition runtime.

## Next (needs an Integration decision)

- A ~20-line campaign mode in `validate_smca_transforms` and `vs_validate`: skip mesh-less components and MP-only checks. Streets would
  stay byte-identical (generic-fix rule).
- A sublevel tag on `world.glb` nodes.
- Then one large chapter (A1_IAC, 50 sublevels) as the scale test.

## Diagnostics rerun (2026-10-17)

- **m05** over all BSP levels (tiled): 36 default-material faces ({'exposed': 35, 'partial': 1}), 1 visible in play (532 m2).
- **Structure audit** at a 2 m cell: PASS.
