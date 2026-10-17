# AssetTools disk sweep: listing only (2026-10-18, 15:3x; nothing deleted)

**Context:** the user ordered a sweep of old builds to free F:. AssetTools/out is the package source, so this is a list for Integration
to approve deletions by name.

**What counts as a reference:**
- `out/package/slim_files.refresh.tsv` sources;
- build_slim's defaults (`--hd` = `AssetTools/out/hd/pack`);
- Systems' `build_slim.json` (hd_source, hd_pbr, overlay);
- the junctions in Rebuild-Systems/Rebuild/Experimental (scanned 3 levels deep);
- text references in Rebuild / Systems / Experimental tools and docs and in AssetTools scripts / docs.

## Keep: live package or pipeline inputs

| path | size | referenced by |
|---|---|---|
| `out/hd/push_full_snap_20261016_b0-31` | 22 G | build_slim `hd_source` (pack D, labelled); junction `Rebuild-Systems/work/hd_dev_full/content` -> its `pack/content` |
| `out/hd/pack` | 6.2 G | build_slim default `--hd`; 3,702 rows of the refresh tsv |
| `out/hd/push_m6` | 577 M | build_slim `hd_pbr`; junction `Rebuild-Systems/work/hd_dev_full/m6` -> its `pack/m6` |
| `out/dds` | 1.8 G | 6,044 rows of the refresh tsv (`out/dds/content` 5,090, `out/dds/VerticalSlice` 954) |
| `out/package/slim_files.tsv`, `slim_files.refresh.tsv`, `xpr_twins.tsv`, `run_manifest.*` | 38 M | the package step (Systems adopts the refresh) |
| `work/gltf_wfcmat` | 1.2 M | build_slim `overlay` |
| `out/movies` | 609 M | `manifests/movies/movies_webm_manifest.json` (converted FMVs; not superseded) |
| `out/abilities`, `out/lens_flares`, `out/campaign_textures`, `out/campaign_anims` | 16 M | today's handoffs (Decoy, lens flares, campaign gaps) |
| `work/campaign_pilot` | 2.9 G | the campaign VerticalSlice every campaign manifest reads |

## Superseded: deletion candidates (approve by name)

| path | size | why superseded | refs |
|---|---|---|---|
| `out/hd/push_full_snap_20261014_b0-15` | **11 G** | older snapshot of the same full pass (batches 0–15); the 2026-10-16 snapshot (b0–31) is the shipped pack D | none |
| `out/hd/v2`, `v2_bc7`, `v3`, `v3_4x`, `v4`, `v4_bc7`, `v5`, `v5_bc7` | 1.05 G | HD trial rounds of 10-09 / 10-10, before the full pass | only their own generator scripts (hd_v4.py) |
| `out/hd/dml_retest` | 81 M | DirectML retest of 10-12 (memory: rgt-s on DML broken; CPU chosen) | its script only |
| `out/hd/pbr_sample`, `pbr_sample_v2` | 34 M | PBR samples of 10-09; push_m6 is the PBR pack | its script only |
| `out/hd/content` | 105 M | early dev-layout output of 10-09 | none |
| `out/hd/compare`, `remake_thumbs`, `_pilot_sheet_*.png` | 10 M | review sheets of 10-09 / 10-10 | none |
| `out/bot_nav` | 705 M | bot-nav dry runs of 10-10 (dry0–dry5, cmp, logs); the real outputs are in VerticalSlice / manifests | none |
| `out/package/slim_files.tsv.bak_20261018`, `.bak_20261018b` | 37 M | backups of today's two tsv appends; delete after Systems builds package 7 from the refresh | none |
| `work/mapfx_dryrun` | 173 M | build_map_fx dry run; Integration's baseline for the map_fx regen gate. **Delete after that gate passes** | Integration's gate |
| `work/campaign_render_dryrun` (render/, umodel_out/) | 62 M | dry-run outputs; the doc, driver and step logs are committed | none |

**Clear candidates now:** ≈ 13.2 G (the 10-14 snapshot, the trial rounds, DML / PBR samples, early content and sheets, the bot_nav
dry runs).
**After package 7 / the regen gate:** +0.27 G.

## Needs a decision, not superseded by anything in the pipeline

| path | size | what it is |
|---|---|---|
| `out/hd/full` | **41 G** | the full HD pass's working tree: `_hdpng` 8.6 G, `enc` 8.6 G, `out_animevideov3_x2` 15 G, `out_4x-PBRify-RPLKSRd-V3` 6.4 G. The shipped packs are snapshots of it. Deleting it saves 41 G but loses resumability: a new batch or errata pass would regenerate hours of GPU / CPU work. Referenced by hd_full.py / hd_push.py / hd_verdicts.py and HD_FULL_PASS_PLAN.md. Keep while pack D may still get errata; deletable once the HD lane is closed (M4 frozen). |
| `out/hd/push_e_full` / `push_e_gen` / `push_e_pilot` | 6.0 G / 493 M / 203 M | the HD remake ("E") experiment: pilot 20 rows, G4 A/B (MILESTONES_09c 10:56 / 19:20: "E-4x-G3 = the real overhaul", sheet sent to the user). Input to the later M4b remake / M6 Modern work, not superseded. |
| `work/models` | 3.4 G | SD1.5 + ControlNet-tile weights (the E remake generator). Re-downloadable, but needed for any M4b / M6 run. |
| `out/loc_fsb` | 205 M | localized FSB banks from loc_fsb_banks.py (int / FRA); not in the package tsv; consumer not confirmed |
