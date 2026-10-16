# Campaign pilot: A1_IAC through the generic map pipeline (2026-10-16, PROVISIONAL)

The first Autobot chapter (Iacon), the scale test after D5_OME. Same rules: CPU only; every stage under `run_bounded.py`, which refuses
to start while any PERF_HOLD exists, with `hold_wait.cmd` before each launch. Integration set a 10 GB per-stage cap for this chapter
(the default stays 6 GB). Outputs are under `AssetTools/work/campaign_pilot/VerticalSlice/Maps/A1_IAC/` via `WFC_VS_ROOT`
(32 files, 409 MB, plus 1,048 lightmap atlas PNGs); ExtractedAssets and the Game Dump were not written. Per-map manifests:
`manifests/maps/A1_IAC/`, `manifests/next_map/A1_IAC_*`.
Runners: `work/campaign_pilot/run_campaign.cmd A1_IAC 10`, `run_campaign_rest.cmd`, `run_stages.cmd`. Logs: `logs/A1_IAC_pipeline/`.

## 1. Stages (wall time, peak job memory; cap 10 GB)

| # | stage | wall | peak GB | result |
|---|---|---|---|---|
| 1 | vs_map | 351 s | 5.79 | OK: 51 levels (persistent + 50 streamed) |
| 2 | vs_lighting | 43 s | 1.41 | OK |
| 3 | vs_light_probes | 0.6 s | 0.93 | OK |
| 4 | vs_postprocess | 2.5 s | 1.51 | OK |
| 5 | vs_navigation | 9.9 s | 0.88 | OK: 7,849 nodes, 24,448 edges |
| 6–8 | vs_lightmap / m04_lightmap_atlases / vs_lightmap | 4.3 + 39.6 + 4.3 s | 1.02 | OK: 1,048 atlases |
| 9 | vs_vertex_lightmaps | 3.5 s | 1.44 | OK |
| 10 | vs_vertex_remap | 0.5 s | 0.89 | OK |
| 11 | vs_map (re-run) | 316 s | 5.89 | OK |
| 12 | vs_materials | 7.1 s | 3.53 | OK: 524 materials |
| 13 | vs_props | 14.2 s | 3.44 | OK |
| 14 | vs_collision | 1.1 s | 0.89 | OK |
| 15 | vs_physics | 49 s | 1.93 | OK |
| 16–18 | vs_gameplay / vs_audio / vs_mapfx | 5.6 / 2.8 / 4.9 s | 1.68 | OK |
| 19 | m04_inventory | 94 s | 3.49 | OK |
| 20 | validate_smca_transforms (campaign mode) | 12.4 s | 2.28 | OK: 1,211 mesh-less components skipped (see 3.1) |
| 21 | vs_validate (campaign mode) | 25.9 s | 4.63 | 43 of 44 checks pass; the player-start check fails (see 3.2) |
| 22 | m04_bsp | 2.5 s | 1.85 | OK: 6,865 BSP triangles |
| 23 | **m05_bsp_default_faces** | 56 s | **10.00** | **CAP HIT** (MemoryError in its occlusion ray grid). Integration decision: skipped for campaign chapters, **m05 pending** (grid fix later, Streets byte-identical as the gate) |
| 24 | m04_kismet | 4.2 s | 0.85 | OK |
| 25 | vs_pickups | 1.8 s | 0.91 | OK |
| 26 | vs_destructibles | 140 s | 2.34 | OK after a speed fix: the first run was killed at 33 min (see 2) |
| 27 | vs_surface_audio | 3.4 s | 1.02 | OK |
| 28 | **map_structure_audit** | 215 s | **10.00** | **CAP HIT** (MemoryError in its triangle grid, `add_tris`). Integration decision: skipped like m05, **structure audit pending** |
| 29 | map_complete | 14 s | 3.05 | OK after a speed fix: the first run took 1,418 s (see 2) |
| 30 | map_render_index | 8.2 s | 2.71 | OK |
| 31 | vs_streaming (new) | 1.7 s | 1.22 | OK |

Wall time for a clean run now: **about 22 min**. The largest stage is vs_map at 5.9 GB, well under the 10 GB cap. Only the two
ray-grid diagnostics (m05, structure audit) exceed it.

## 2. Speed fixes made on the way (generic; MP outputs proven unchanged)

- **vs_destructibles: 2.4 s → 0.16 s per actor.** A1 has 1,040 destructibles (D5 has 36). Per actor, the stage re-read every slice
  JSON (214 MB here), ran a full-table `LIKE` scan for blueprint variants, and re-scanned every placed actor's location. All three are
  now memoised once per run, with the same results. Streets `streets_destructibles.json` is byte-identical between the old and new code
  (sha256 d5a76091…).
- **map_complete: 1,418 s → 14 s.** For each PhysicsVolume it called `A.get()` on the actor's path in every sublevel (51 here); each
  miss fell back to a `COLLATE NOCASE` query that cannot use the index, i.e. a full-table scan. It now builds one case-insensitive set of
  the levels' objects. Old code vs new code on all 10 MP maps: 51 / 51 output files byte-identical (originals restored afterwards).

## 3. What exported, and the findings

Completeness: **INCOMPLETE**. Of 46 checks:
- 29 are COMPLETE.
- 3 are EXPORTED (decals 73, map_fx: 1,265 particle components / 115 systems, particles).
- 3 are AUTHORED (movers 1,090, of which 1,046 interpolating and 2 matinee; moving scenery; BSP default faces = m05 pending).
- 1 is PARTIAL (placed meshes).
- 1 is NONE (pickups; see 3.3).
- 1 is UNVALIDATED (negative / non-uniform scales: 4,822 mirrored, 7,250 non-uniform; the winding check sits in the pending
  structure audit).
- 2 are ATTENTION (playable space, collision vs visible: both computed by the pending structure audit).
- 1 is NOT RUN (structure audit).
- 1 is NOT RUN / FAIL (vs_validate 43/44).
- 4 are MISSING: the MP-lobby metadata (loading screen, thumbnail, frontend name, mode compatibility).

The chapter as exported:
- **51 levels:** the persistent level, 24 art, 21 design, 2 audio, 1 music and 1 cinematic (`A1_IAC_Thumper_Cine_m`); the "other"
  one is GLB_Audio_m.
- **24,287 placed static meshes** (2,613 unique), 6,865 BSP triangles, 149 lights, 2,115 volumes, 1,216 emitters and 73 decals.
- **Gameplay points:** 1 TnCampaignPlayerStart, 129 TnMatineePreviewSpawnPoint, 54 objective markers, 421 TriggerVolume,
  21 weapon, 20 ammo, 5 health and 1 overshield pickup factory.
- **Streaming** (`streaming.json`):
  - 23 authored LevelStreamingStates; the initial state is `LevelStart`. Each sublevel is in at least one state.
  - 20 `SeqAct_SetStreamingState` switch them, fired by RemoteEvents (listed per state).
  - 26 checkpoint references restore a state; 2 flush actions.
  - 23,094 world.glb nodes are tagged with their sublevel. 227 are ambiguous (an actor name that occurs in several sublevels, listed
    with every candidate).

### 3.1 Parser bug: 1,211 components lose their mesh (HGHWY2 / HGHWY3)

- **How many:** 657 of 2,017 components in `A1_IAC_HGHWY2_Art_m`, 547 of 1,580 in `A1_IAC_HGHWY3_Art_m` and 7 of 667 in
  `A1_IAC_Strts0_End_Art_m` have no StaticMesh. These are the D5 "mesh-less props" again, but in volume.
- **The tags are mis-parsed in `authored.db`.** A component's properties come out under unrelated names, for example
  `"Wave_Alpha_Pan_Speed_1407"` and `"_DialogEventManager_1430"`, so StaticMesh, transform overrides and materials do not resolve.
  This looks like a name-table / tag-size desync in the parser for these packages.
- **Effect:** about 5 % of the chapter's placed meshes are missing from world.glb. That is a large hole along the highway sections.
- **Next (Integration's order):** run the same detector over the 10 MP maps (count per map), fix the parser with Streets byte-identical
  except recovered components, and add the detector to the validator.

### 3.2 Player-start check

The only TnCampaignPlayerStart (`TnCampaignPlayerStart_10303`) has no ground within 6 m. The nearest ground below is 236 m down.
- Possible causes: the floor is in the mesh-less HGHWY components (3.1), or the chapter starts on a moving / matinee platform.
- To recheck after the parser fix. PROVISIONAL.

### 3.3 Pickups NONE

`vs_pickups` finds 0 pickup factories, although `spawnpoints.json` lists 47 (21 weapon, 20 ammo, 5 health, 1 overshield). The pickups
check looks for the MP factory set and appears to look only in BASE/ART; campaign factories sit in the design sublevels. A generic fix
is needed (not made).

## 4. Blockers for A1_IAC (counts from the 51 exported levels)

1. **Kismet:** 16,440 Kismet objects across 117 classes; 37 are High Moon custom.
   - **Custom classes with no RE decomp file** (by file name, PROVISIONAL): TnSeqAct_ActivateTogethernessVolume, TnSeqEvent_Interact,
     TnSeqAct_MissionComplete, TnSeqAct_DownRevive, SeqAct_TnAiMoveToActor, SeqAct_TnAssignTacticalVolume, SeqAct_TnAiUseTurret,
     TnSeqEvent_Downed (8).
   - **Volume of work:** 143 SeqAct_TnPawnFactory (enemy spawns), 193 TnSeqVar_Character, 26 Checkpoint, 20 SetStreamingState,
     5 FlushLevelStreaming.
2. **Matinee:** 496 InterpData / 491 SeqAct_Interp, 71 director groups, 33 CameraActor; 2 matinee movers; 129 matinee preview spawn points.
3. **FaceFX / dialog:** 14 FaceFXAsset and 12 InterpTrackFaceFX (cutscene lip-sync only); 452 HmAnimNotify_Dialog, 56 dialog groups,
   2,881 SoundCues.
4. **Materials for Rendering** (`work/campaign_pilot/A1_IAC_materials_for_rendering.json`): 524 materials.
   - 297 have an exported `.mat` file.
   - 255 are already compiled in some Rendering `materials_glsl.json`.
   - So **269 need a matc pass**, and 227 have no `.mat` file.
5. **Parser bug** (3.1): 1,211 components.
6. **Pending diagnostics:** m05_bsp_default_faces and map_structure_audit both exceed 10 GB in their ray / triangle grids. The fix
   (oversized-triangle exclusion / coarser cells, Streets byte-identical) comes after the chapters, then a rerun of both alone.

## 5. Next

Per Integration: the VelocityOverLife decode, then the parser detector over the MP maps, then the next chapter in size order:
A5_TRY (211 MB), D3B_IAC, D2_COR, A3_COR, A4_ORB, D3A_IAC, A2_KON, D1_ORB. The rules stay: stop at the 10 GB cap or after an hour.
