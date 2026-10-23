# AssetTools resume note (2026-10-18)

## 2026-10-23 evening: campaign chain complete (commit 2cabbb4)

- All 10 chapters in out/campaign_render/<CH>/: render data + inputs (collision, physics incl. chapter-root non-unit volumes, floor-level
  bot_nav with fill / mover cells), actors.json (props.bHidden + hidden), destructibles.json, matinee_skeletal.json, checkpoint_spawns,
  postprocess_volumes, transforming actors (world.glb nodes + transforming_actors_gameplay.json in the MP schema), chapter lightmaps
  (package-correct dedupe), extras.actor_path on every world.glb actor node, BASE / streamed units added by add_units.sh.
- Campaign AI: out/campaign_characters (57 bodies, AI weapons with fire blocks, destructibles incl. sentries, spawnables.json).
- Outside-render list: manifests/campaign/campaign_assets_outside_render.tsv (8,678 files, 2.98 GB, 0 missing).
- PENDING: air nav queue (work/campaign_render/air_queue.sh, detached, PERF_HOLD-aware, markers lanes/air_done_<CH>): A2 / A3 redo,
  A4 / D1 / D3A / D2 / D3B at 8 m; files ship as they land (Integration cut rule). After a reboot: powershell -File
  work/campaign_render/resume_lanes.ps1 (relaunches the air queue; lanes are done).
- Tools: run_lane.sh, add_units.sh, add_transforming_actors.py (--rerun-materials, extra_skeletal_actors.json), dedupe_lightmaps.py,
  campaign_nav_fill.py (per-seed, 60 m bound), mp_transforming_actors.py --campaign, check_actor_path.py.

## 2026-10-23 (Integration rebuild-84; Gameplay rebuild-gameplay-b9; Rendering rebuild-rendering-56)

- Escalation horde packaging: 14 bodies + 7 AI weapons in out/escalation_characters (0c1f00e); index copied to
  manifests/escalation/escalation_characters_index.json. Built by work/escalation_characters/build.py.
- Slim refresh staged: +161 escalation rows, +16 out/campaign_anims rows (the boss tank's robot set), + 6 lens_flares rows
  (f8bdf55). The live tsv is untouched; the refresh has 101,214 rows.
- CeremonialStaffHolo HUM / HUM_CHARGED: SILENT AS COOKED (the wave events have no ChildNodes).
- Playtest 2026-10-23, all sent:
  - #4: package 6 carries hd_pbr_index.json and all 498 m6 files;
  - #10 / #13: work/handoff/PLAYTEST_20261023_SEED_COLLISION.md (22bb058);
  - #14: work/handoff/PLAYTEST_20261023_WATER.md (3e6e4d0).
- Seed PC adaptation (Integration decision): out/pc_adapt/MP_IAC_Seed (9745 dropped, per-poly pawn collision on 40 meshes, nav and air
  nav rebuilt; bot_nav / bot_nav_air got an optional --overlay, no-change proof done). Frozen overlays work/overlay_20261023 (87 files,
  adopted by Systems) and the superset overlay_20261023b (90 files, + Seed nav; Systems asked to switch). Gameplay dev pickup:
  WFC_OVERLAY_ROOT. Open: Gameplay re-test of the centre strand (offered a clearance-clipped nav).
- Campaign render gaps a–e DONE (work/handoff/CAMPAIGN_RENDER_GAPS_20261023.md): inline LM lists, fog cause, material lists, per-sublevel
  split (392 folders, 996 MB, PASS), proposed tools/render patch (not applied).
- Gameplay #18 raised collision (38985d9): audit hull_float_audit.py (nav-first, world.glb probe) on all 10 versus maps; 266 raised
  simple-hull placements switched to per-poly + nav rebuilt in out/pc_adapt/<MAP>; volumes list-only (Integration). Gameplay-confirmed
  placements in work/playtest_20261023/gameplay_confirmed.json. Frozen overlay work/overlay_20261023c (135 files, all 10 maps),
  adopted by Systems refresh.sh; Gameplay uses WFC_OVERLAY_ROOT. Doc work/handoff/PLAYTEST_20261023_RAISED_COLLISION.md.
- Escalation spawn points: escalation_geometry zones[].spawn_points (9ca9a9e). Slim refresh + bot_skill.json (101,215 rows).
- Campaign scoping (df3d56e): HD gap 937 textures / ~1.77 GB PROVISIONAL; audio / FMV / dialog complete (1 A3 line without wave).
  Doc work/handoff/CAMPAIGN_HD_AV_COVERAGE.md. Remnant volume fog params sent to Rendering.
- Gameplay three-arm test: adapted collision ships for all 10 maps; rebuilt navs regress (per-poly broken floors expose cracks the hulls
  span; same bot_nav code). Overlay work/overlay_20261023d (114 files; rebuilt nav only BrokenHope / Remnant / Seed) supersedes c.
  Seed nav v3 candidate out/pc_adapt/_candidates/seed_nav_v3 (shipped collision + #13 hulls), awaiting Gameplay's A/B.
  Berth fall-through: not a collision hole.
- Campaign HD closed (covered by pack D). Confirmation of the 10 (out/hd/campaign_push_20261023): 1 eye-passed row,
  ENV_statue01_NORM, waits for the next pack-D snapshot (work/campaign_hd/confirm10_eye.json). New opt-in envs: hd_push
  WFC_HD_PUSH_ROOT, hd_torch WFC_HD_DEVICE.
- Overlays: e (Seed nav v3) then f (Debris / Gorge broken floors back on hulls) = the shipping set (work/overlay_20261023f;
  Systems refresh.sh). Streets stuck candidates out/pc_adapt/_candidates/overlay_f_streets_revert{A,B} await Gameplay's A/B.
- Campaign render (work/campaign_render/campaign_render.py; out/campaign_render/<CH>/<Sublevel without _m>/ + chapter.json):
  D5_OME done on the integration head; A1_IAC done, lighting + materials rerun on the head running (--force). D5 collision / nav
  inputs (campaign_collision.py). InitialStreamingState for RE (manifests/campaign/initial_streaming_state.json).
- Escalation: weapon_pickups + spawn_points in escalation_geometry; bot_nav_escalation.json v2 (original NavigationCell mesh + all
  TnReachSpec links; 1 piece, every on-mesh spawn point reaches the starts) + blockers / coverage / air; escalation_weapons.json;
  horde chassis in roster_package.json; 10-chapter INT subtitle sidecars (manifests/campaign/*_loc_int_subtitles.json).
- Later 2026-10-23: overlay g (f + Streets SideSupp01 / GiantPillar on hulls) = shipping set. A1 rerun on the head: 0 compile errors;
  work/campaign_render/relpaths.py post-pass (unit-relative paths, both chapters). ESC nav v3 (escalation_bot_nav_v3.py: typed
  reach-spec links, versus_only merge) + lower_nav_cells.py (original cells were at pawn-centre height, +1.75 m; lowered, authored
  heights kept) + air navs rebuilt. D5 campaign bot_nav.json / bot_nav_air.json (campaign_bot_nav.py) at out/campaign_render/D5_OME/;
  D5_OME_BASE/vbake = Rendering's RT calibration copy. Kismet seq_inputs / seq_outputs / inputs_disabled for all chapters (m04_kismet,
  campaign only; run with WFC_VS_ROOT=work/campaign_pilot/VerticalSlice or map_levels sees only base / art / audio).
- Next: stand by (Gameplay's runs on ESC v3 / D5; next campaign chapter when asked: campaign_collision.py, campaign_bot_nav.py).

- **Integration session:** now rebuild-07 (same owner as rebuild-9c). Gameplay is rebuild-gameplay-0a. The machine rebooted at 05:41;
  the queue was resumed and finished.
- **Done 2026-10-18:**
  - Campaign verdict with airborne starts exempt (00e4619; A4 PASS PROVISIONAL, D2 ATTENTION).
  - Streaming runtime doc revised with the six RE corrections; streaming.json gained `fully_static` and `checkpoints` (7b48fc7).
  - Matinee export for all 10 chapters + CAMPAIGN_MATINEE_SCHEMA.md; MP no-change proof (b86d0f0).
  - Dialog manifest for all 10 chapters + CAMPAIGN_DIALOG_SCHEMA.md (be27815):
    - per-language subtitles from the cooked packages (`dialog_subtitles.py` -> work/dialog/subtitles.json);
    - pawn factories gained spawn_delay;
    - matinee and Kismet docs corrected per RE.
  - Frontend CDO table: work/frontend_online_cdo_values.md (e2a345e).
  - Objectives export + CAMPAIGN_OBJECTIVES_SCHEMA.md (5bad171, 492ca79).
  - CAMPAIGN_DATA_INDEX.md, generated by campaign_data_index.py (2ced22e). Rerun it after any export changes.
  - Package 7 transforming actors (38406dc):
    - outputs: 4 GLBs in manifests/maps/transforming_actors/ and mp_transforming_actors.json with meshes / drivers / nav (generator
      mp_transforming_actors.py + transforming_glb.py);
    - gates: MP identical, and the 2026-10-17 keys unchanged;
    - bridge collision is switched by Kismet ChangeCollision (Gameplay told).
  - Cleanups (35515af):
    - the 52 "unextracted" dialog waves exist as _LOC twins; the exporter now resolves them;
    - D2 Guardian Chamber starts = missing floor (UNKNOWN; follow-up offered).
  - FaceFX: Trypticon paragraph (79ef99a); proof prefers the _LOC/int wave (7f17f67).
- **Done 2026-10-17:** all committed and pushed on assettools/checkpoint.
  - Backlog 5 starts / walk graph: d84baf2, c9d7bce. The 6 no_floor_below starts are airborne by design (verdicts in
    chapter_notes A4_ORB / D2_COR). on_mover narrowed to 3 m (b43afb3).
  - Skeletal world-actor collision (TnTransformingWorldActor PhysicsAsset boxes at the reference pose, `skel_collision.py`), campaign
    only:
    - Code 237489f. MP structure_audit identical on all 10 MP maps (`work/skelcol/proof.json`).
    - Chapters rerun (b419dfe): A1 ATTENTION -> PASS. Before / after in `work/skelcol/chapter_changes.json`.
  - MP_TRANSFORMING_ACTORS.md: 32 MP doors / bridges for Gameplay's fidelity check (46c0d0b).
  - FaceFX reference CSVs regenerated with RE's native product rule; old ones kept as `*_nlerp.csv`; hook spec updated (e41d3b4).
  - Pawn factories (f350205), FaceFX rest pose (ae600dd), hold watchdog (1b70368, 3d1cc87).
- **Hold watchdog test (PASS, 2026-10-17, A2_KON map_complete via run_stages.cmd).** Log lines from
  `work/campaign_pilot/A2_KON_stages.log`:
  ```
  run_bounded: rc=76  wall=3.0s  peak_job_memory=1.39 GB  cap=10.0 GB  cmd=scripts\wfc\map_complete.py A2_KON  INTERRUPTED by PERF_HOLD at 2026-10-17 04:14:29 (F:\Transformers Rebuild\AssetTools\work\PERF_HOLD): outputs may be partial, rerun the stage
  map_complete interrupted by PERF_HOLD  4:14:29.36, waiting for 60 s without a hold
  run_bounded: rc=0  wall=9.2s  peak_job_memory=1.39 GB  cap=10.0 GB  cmd=scripts\wfc\map_complete.py A2_KON
  map_complete rc 0  4:16:08.71
  ```
- **Done later on 2026-10-18:**
  - D2 Guardian Chamber: the floor exists; the starts are elevated spawns (`elevated_above_floor`, exempt) (0baed93, 7f80fc2).
  - Movies: 54 WebM in out/movies (gitignored); manifest + subtitle JSON in manifests/movies (2c23b15). The old ExtractedAssets subtitles
    are 10x early.
  - Physmat: MP weapon world (2c1d9ba); campaign weapon + pawn worlds (85f80a6).
  - pstream: option A (7eb8b5e) and option B (09a0feb), the compiled parameter blob, 2,736 of 2,736 LODs. Rendering regenerates
    map_fx_runtime.json.
- **Open:**
  - Standing by for Systems' package-7 build data list (overlay files, material sets).
  - Integration will ask for a rerun of `work/matB_review/review.py` on the frozen live tree before the material (B) switch.
- **2026-10-18 handoffs (all committed):**
  - package-7 slim audit (`work/handoff/PACKAGE7_SLIM_AUDIT.md`; the pc_strings.int row appended to the tsv);
  - Gorge / Rust reference frames;
  - Decoy Trap assets (`decoy_trap_assets.py`);
  - Trail2 templates (`trail2_templates.py`);
  - campaign chapter assets for all 10 chapters (`campaign_chapter_assets.py <CH>` + `campaign_assets_summary.py`), plus the matc dry
    run (`work/matc_dryrun/`: 1,725 / 1,763 clean);
  - campaign data gaps closed into `out/campaign_{textures,anims}` (`CAMPAIGN_DATA_GAPS_CLOSED.md`);
  - pstream now assigns by each record's own distribution base index (regression over all cooked LODs: identical; PowerCell fixed);
  - (B) frozen-arm verification: `work/matB_review/verify_frozen.py`, PASS at 10:59; rerun if the arm changes.
  - door interpolated light maps (`interp_lightmaps.py`), MP lens flares (`lens_flares.py`), campaign render dry run
    (`work/campaign_render_dryrun/`, CAMPAIGN_RENDER_DRYRUN.md), BrokenHope versus nav (`work/bot_nav_versus/run.py` ->
    manifests/maps/MP_ESC_BrokenHope/bot_nav_versus.json).
  - Open findings, campaign phase: skel_collision poses TnTransformingWorldActor boxes from the reference skeleton (3.8-5.7 m off on
    bridges); vs_audio reverb_presets misses non-AmbientAudioZone reverbs + prefix only for MP_IAC_ (parked; MP audio.json change
    needs Integration's go). authored.db SoundMixerPresetName is fine (12-byte rows carry no PresetName).
- **RE provisionals parts 1-2 applied:**
  - physmat hull fallback only for StaticMeshActor owners, as node overrides (83b669d);
  - matinee live_without_actor, objectives whitespace_noop (94c758e).
  - The 10 MP physmat rows were appended to out/package/slim_files.tsv (backup .bak_20261018). Update their byte counts whenever the
    physmat files are regenerated.
- **pstream state (2026-10-18):**
  - All 2,736 MP LODs decode the parameter blob and assign every distribution (31,842 CONFIRMED, 4 PROVISIONAL for SubUVDirect).
  - Sphere and Cylinder floats are base-class-first (VelocityScale first): RE 178abb0, pstream 3470a25.
  - The census-sized blocks are named by RE (e9d39dd).
  - The airborne exemption rests on reachFlags 2 = R_FLY: PROVISIONAL until RE confirms the enum.
  - Matinee: 165 groups are unresolved (empty variables in the cook), listed in CAMPAIGN_MATINEE_SCHEMA.md §3b.
  - Trypticon's low jaw-voice correlation is not explained by the blend rule (product and nlerp differ <= 0.47 deg).
  - The FaceFX bone-blend visual check stays parked until Gameplay's hook.
- **Rules:**
  - Campaign runners: `work/campaign_pilot/run_stages.cmd` sets WFC_AUDIT_CELL=2. A 1 m audit exceeds the 10 GB cap.
  - Check `*/work/PERF_HOLD` before any interpreter. While a hold is on: no python, node or py_compile; editor and shell builtins only.
- **Nothing is running.**
