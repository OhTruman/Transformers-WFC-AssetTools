# Slim list refresh (staged; Systems adopts at the package step)

Measured 2026-10-17 13:50. Live `out/package/slim_files.tsv` untouched; refreshed copy `out/package/slim_files.refresh.tsv` (same rows, order, columns, line endings; only the bytes column of keep / xpr rows re-measured). Generator `scripts/wfc/slim_refresh.py` (rerun at the head).

| | value |
|---|---|
| rows | 101031 -> 101031 |
| rows with a changed byte count | 47 |
| rows added | 0 |
| line endings | live: 101021 CRLF + 11 LF-only rows (the LF ones are AssetTools appends of 2026-10-18); refresh: all CRLF |
| rows whose source is missing (kept) | 0 |
| keep / xpr bytes | 12,945,073,330 -> 12,976,812,151 (+31738821) |

## Changed rows

| source | before | after | delta | file mtime |
|---|---|---|---|---|
| `AssetTools/manifests/package/slim_package.json` | 154,012 | 52,139 | -101873 | 2026-10-11 12:09 |
| `Rebuild/data/frontend/graphics_presets.json` | 2,789 | 2,688 | -101 | 2026-10-12 22:51 |
| `Rebuild/data/frontend/pc_strings.int` | 1,991 | 2,471 | +480 | 2026-10-17 12:36 |
| `Rebuild/work/render/MP_ESC_BrokenHope/decals.glb` | 264,584 | 352,104 | +87520 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_ESC_BrokenHope/lighting.json` | 2,735,657 | 2,739,587 | +3930 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_ESC_BrokenHope/map_fx_runtime.json` | 18,879,871 | 21,969,999 | +3090128 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_ESC_BrokenHope/materials_glsl.json` | 3,668,106 | 4,115,972 | +447866 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_ESC_Remnant/decals.glb` | 1,017,648 | 1,247,444 | +229796 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_ESC_Remnant/lighting.json` | 3,246,458 | 3,261,186 | +14728 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_ESC_Remnant/map_fx_runtime.json` | 17,339,559 | 20,275,331 | +2935772 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_ESC_Remnant/materials_glsl.json` | 3,617,651 | 4,065,127 | +447476 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_IAC_Berth/decals.glb` | 167,836 | 182,032 | +14196 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_IAC_Berth/lighting.json` | 2,549,217 | 2,553,710 | +4493 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_IAC_Berth/map_fx_runtime.json` | 14,808,889 | 17,323,246 | +2514357 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_IAC_Berth/materials_glsl.json` | 3,459,466 | 3,904,339 | +444873 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_IAC_Rust/decals.glb` | 182,744 | 210,672 | +27928 | 2026-10-12 21:19 |
| `Rebuild/work/render/MP_IAC_Rust/lighting.json` | 19,343,360 | 19,357,973 | +14613 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_IAC_Rust/map_fx_runtime.json` | 14,788,473 | 17,300,662 | +2512189 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_IAC_Rust/materials_glsl.json` | 4,024,421 | 4,472,014 | +447593 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_IAC_Seed/decals.glb` | 761,680 | 868,624 | +106944 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_IAC_Seed/lighting.json` | 6,708,592 | 6,727,121 | +18529 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_IAC_Seed/map_fx_runtime.json` | 16,062,463 | 18,735,672 | +2673209 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_IAC_Seed/materials_glsl.json` | 3,676,334 | 4,122,776 | +446442 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_IAC_Streets/decals.glb` | 282,252 | 338,444 | +56192 | 2026-10-12 21:19 |
| `Rebuild/work/render/MP_IAC_Streets/lighting.json` | 1,636,949 | 1,643,215 | +6266 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_IAC_Streets/map_fx_runtime.json` | 15,185,767 | 17,760,935 | +2575168 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_IAC_Streets/materials_glsl.json` | 3,474,761 | 3,921,012 | +446251 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_KON_Molten/decals.glb` | 365,976 | 424,624 | +58648 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_KON_Molten/lighting.json` | 2,339,307 | 2,352,885 | +13578 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_KON_Molten/map_fx_runtime.json` | 14,921,840 | 17,447,670 | +2525830 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_KON_Molten/materials_glsl.json` | 3,614,278 | 4,060,417 | +446139 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_ORB_Debris/lighting.json` | 2,730,100 | 2,736,053 | +5953 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_ORB_Debris/map_fx_runtime.json` | 15,938,892 | 18,576,850 | +2637958 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_ORB_Debris/materials_glsl.json` | 3,442,225 | 3,887,549 | +445324 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_UND_Complex/decals.glb` | 195,624 | 256,020 | +60396 | 2026-10-12 21:20 |
| `Rebuild/work/render/MP_UND_Complex/lighting.json` | 1,852,445 | 1,854,832 | +2387 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_UND_Complex/map_fx_runtime.json` | 15,035,796 | 17,582,402 | +2546606 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_UND_Complex/materials_glsl.json` | 3,330,518 | 3,775,435 | +444917 | 2026-10-17 11:29 |
| `Rebuild/work/render/MP_UND_Gorge/decals.glb` | 175,284 | 217,032 | +41748 | 2026-10-12 21:19 |
| `Rebuild/work/render/MP_UND_Gorge/lighting.json` | 15,124,031 | 15,131,006 | +6975 | 2026-10-17 11:18 |
| `Rebuild/work/render/MP_UND_Gorge/map_fx_runtime.json` | 14,822,001 | 17,341,518 | +2519517 | 2026-10-17 13:47 |
| `Rebuild/work/render/MP_UND_Gorge/materials_glsl.json` | 3,292,095 | 3,736,531 | +444436 | 2026-10-17 11:29 |
| `Rebuild/work/render/UI_CampaignLobby/materials_glsl.json` | 2,343,016 | 2,357,260 | +14244 | 2026-10-12 13:28 |
| `Rebuild/work/render/UI_CharacterCustomization/materials_glsl.json` | 2,374,066 | 2,388,670 | +14604 | 2026-10-12 13:24 |
| `Rebuild/work/render/UI_FrontEnd/materials_glsl.json` | 2,473,623 | 2,488,867 | +15244 | 2026-10-12 13:23 |
| `Rebuild/work/render/UI_Lobby/materials_glsl.json` | 2,364,253 | 2,378,929 | +14676 | 2026-10-12 13:27 |
| `Rebuild/work/render/UI_PartyLobby/materials_glsl.json` | 2,368,873 | 2,383,549 | +14676 | 2026-10-12 13:26 |
