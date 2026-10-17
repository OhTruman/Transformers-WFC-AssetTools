# Package 7: slim-list audit (AssetTools, 2026-10-18; read-only)

**Scope:** `AssetTools/out/package/slim_files.tsv` (Oct 11 + the 10 physmat rows appended today), checked against what the game
actually opens. The tsv was NOT regenerated: Systems owns the package step.

**Script and data:** `AssetTools/work/package7_audit/audit.py`, which writes `PACKAGE7_SLIM_AUDIT.json` (every file list) and
`non_hd_missing_split.json`.

## Inputs and method

**Opened files:** the newest WFC_FILELOG set, `Rebuild-Systems/work/verify_af4d0731/{Streets, Gorge, Debris, hd_runtime/Streets}/filelog.txt`
(Systems' slim-package run of 2026-10-17 04:2x, package `playtest_slim_af4d0731` mounted as `X:`).
- There is no 5fc2e552 log set in the Systems or Experimental work trees, so af4d0731 is the newest available.
- Loads added since af4d0731 are checked explicitly on disk (§3).

**Path mapping:**
- `X:/Transformers Rebuild/<path>` -> the source path;
- the run's private `bin/` -> `Rebuild/build/release-slim/bin`;
- `<name>.xpr` -> `<name>` (tsv rows with action `xpr` ship compressed).

**Per-map generalization:** the logs cover 3 maps, so every path naming Streets / Gorge / Debris is generalized to all 10 MP maps (the
same loader reads the same per-map file names) and kept where the file exists.

**Totals:**
- tsv: 101,030 rows, of which 51,792 are keep / xpr (12.95 GB).
- Logs: 6,951 distinct opened files; 7,056 after generalization.

## 1. Opened files NOT in the tsv: 25 files, 21.3 MB

| file | count | note |
|---|---|---|
| `Rebuild/work/render/<MP map>/fog_volumes.json` | 10 | new render data |
| `Rebuild/work/render/<map>/materials_pbr.json` | 13 | 10 MP + UI_FrontEnd / UI_Lobby / UI_PartyLobby |
| `ExtractedAssets/VerticalSlice/Weapons/EmpShotgun/weapon.json` | 1 | |
| `Rebuild/build/release-slim/bin/wfc_characters.ini` | 1 | bin tree file not in the tsv's bin rows |

The af4d0731 package DID contain these, since the run opened them from `X:`. So build_slim must currently add them some other way.
Systems, please check whether they come from your own additions or should be tsv rows.

**Shipped beside the tsv, by design** (build_slim.json `hd` / `hd_pbr`): 4,005 opened files under `AssetTools/out/hd/`, i.e. the HD pack D
(21.7 GB per the run report) plus the M6 `hd_pbr` overlay. They're not counted as missing.

**Opened files the tsv marks drop:** 0.

## 2. tsv rows that no longer exist / changed size

- **Source gone:** 0 rows.
- **Size changed since Oct 11:** 46 rows, +26.1 MB net.
  - 44 under `Rebuild/work/render`: each map's `lighting.json`, `map_fx_runtime.json` (regenerated today) and `materials_glsl.json`
    (after the (A) switch).
  - `Rebuild/data/frontend/graphics_presets.json`: 2,789 -> 2,688 bytes.
  - `AssetTools/manifests/package/slim_package.json` (the manifest's own summary).
  - The rows' byte counts are stale; the files are present.

## 3. New loads named by Integration (checked on disk; the logs predate some of them)

| item | on disk | in tsv |
|---|---|---|
| 10 × `collision_weapon_physmat.json` | yes | yes (appended today, current sizes) |
| `Rebuild/work/render/<map>/{map_fx_runtime, materials_glsl, lighting}.json` | yes | yes, sizes stale (§2) |
| `Rebuild/data/frontend/pc_strings.int` (2026-10-17) | yes | **NO** |
| `AssetTools/manifests/mp_content/mp_characters.json` | yes | yes (unchanged) |
| `AssetTools/out/hd/push_m6/pack/hd_pbr_index.json` | yes | not in the tsv: part of the `hd_pbr` side source |
| campaign `<chapter>_objectives.json` | yes | not in the tsv; the MP package does not load them (campaign HUD later) |
| `lighting.json` with `fogs` | the current files | listed, sizes stale; the companion `fog_volumes.json` is missing (§1) |

## Summary for the package step

- **Add:** 26 rows. The 25 opened-but-unlisted files from §1, plus `Rebuild/data/frontend/pc_strings.int`. That's about 21.3 MB.
- **Refresh:** byte counts on 46 rows (+26.1 MB).
- **Remove:** nothing.
- **Side sources:** HD pack D and the M6 `hd_pbr` overlay stay outside the tsv, as build_slim.json already does.
- A full regen of `package_manifest.py` would pick all of this up, since it walks the source trees. It's Systems' call when.
