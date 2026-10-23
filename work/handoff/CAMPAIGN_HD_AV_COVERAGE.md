# Campaign HD / material coverage and audio / FMV / dialog presence (AssetTools, 2026-10-23, read-only)

**Scoping for the campaign HD pass.** Nothing was generated.

**Data:**
- `work/campaign_hd/hd_coverage.json` (`hd_coverage.py`)
- `work/campaign_hd/campaign_av_presence.json` (`campaign_av_presence.py`)

## 1. HD coverage

**Packs measured:**
- colour pack D: the shipped `push_full_snap_20261016_b0-31`, 3,505 rows;
- M6 PBR: `push_m6`, 498 rows.

Texture2D only, per chapter manifest (light maps are a separate group).

| chapter | Texture2D | pack D | M6 | also in MP | gap (campaign-only) | gap source Mtexel | materials with textures / all HD / some HD |
|---|---|---|---|---|---|---|---|
| A1_IAC | 1501 | 841 | 204 | 891 | 658 (408) | 75.6 | 512 / 218 / 347 |
| A2_KON | 1442 | 780 | 164 | 784 | 661 (412) | 66.4 | 474 / 157 / 302 |
| A3_COR | 1468 | 826 | 200 | 846 | 640 (406) | 64.1 | 428 / 188 / 311 |
| A4_ORB | 1550 | 878 | 219 | 900 | 670 (423) | 87.6 | 507 / 218 / 364 |
| A5_TRY | 1444 | 754 | 163 | 727 | 688 (457) | 68.6 | 353 / 141 / 241 |
| D1_ORB | 1731 | 1061 | 253 | 979 | 668 (414) | 79.7 | 532 / 241 / 379 |
| D2_COR | 1387 | 753 | 175 | 761 | 633 (404) | 64.1 | 426 / 185 / 295 |
| D3A_IAC | 1550 | 876 | 208 | 887 | 672 (427) | 76.8 | 525 / 214 / 351 |
| D3B_IAC | 1584 | 890 | 189 | 810 | 692 (454) | 66.1 | 503 / 208 / 354 |
| D5_OME | 1344 | 681 | 121 | 587 | 661 (452) | 48.1 | 297 / 131 / 212 |

**Distinct gap across the campaign (textures shared between chapters counted once):**
- 937 textures, of which 623 are campaign-only;
- 165.4 Mtexel of source;
- every gap texture has a PNG.

**Estimated HD output:** about 1.77 GB, PROVISIONAL. That is pack D's median of 10.7 DDS bytes per source texel, applied to the gap.

**Resolution mix** (mostly small textures): 128² 344, 64² 121, 512² 115, 1024² 71, 32² 49, 256² 44, 256×1 35, others.
The full list with sizes and chapters is in `hd_coverage.json` → `distinct_gap`.

## Correction: the real build scope (2026-10-23, later the same day)

The gap above counts every Texture2D without a pack D row. Under pack D's own rules almost all of them stay original:

| of the 937 distinct gap textures | count | outcome |
|---|---|---|
| 64 px or less | 297 | original (pack D rule: Lanczos / kept) |
| pack D verdict KEEP | 86 | original (pack D decision) |
| pack D verdict REMAKE | 96 | original (pack D decision) |
| eye-rejected in pack D (cap None) | 92 | original |
| editor ThumbnailTexture (never used at runtime; cooked inside FX / material packages) | 269 | not applicable |
| TEXTUREGROUP_UI | 85 | original (pack D excludes UI) |
| TEXTUREGROUP_Skybox | 2 | original (pack D excludes skyboxes) |
| **PASS verdict, never eye-reviewed (pack D batches after 31)** | **10** | **the only build work: 2.9 Mtexel** |

- So the campaign is already covered by pack D, apart from 10 textures. The 1.77 GB estimate above does not apply.
- The 10 are listed in `work/campaign_hd/campaign_hd_build_set.json`.
- Those 10 were in pack D's selection, in reviewed batches (all 32 batches were reviewed), with no eye cap, yet they have no pack row. Most likely pack D's build ladder fell back to the original at its automatic gates (PROVISIONAL: the per-texture results went with the deleted `out/hd/push_full` working folder). Rerunning the same deterministic pipeline should reproduce that, so the campaign HD pass adds about nothing under pack D's rules.
- Widening scope (UI 85, skybox 2, 64 px or less 297) would be a policy change, the user's to decide.

## 2. Audio / FMV / dialog presence

Re-verified on disk, not taken from the manifest flags.

| chapter | waves (plain / INT / FRA) | no file | cues | FaceFX | dialog conv / lines (no wave) | FMV mkv / total (MB) |
|---|---|---|---|---|---|---|
| A1_IAC | 2604 (1803 / 1139 / 1177) | 0 | 1821 | 9 ok | 72 / 122 (0) | 4 / 4 (275) |
| A2_KON | 2786 (1958 / 1331 / 1369) | 0 | 1773 | 7 ok | 134 / 241 (0) | 3 / 3 (92) |
| A3_COR | 2837 (2043 / 1198 / 1236) | 0 | 1808 | 5 ok | 99 / 192 (1) | 3 / 3 (101) |
| A4_ORB | 2752 (1972 / 1168 / 1206) | 0 | 1755 | 5 ok | 95 / 201 (0) | 3 / 3 (72) |
| A5_TRY | 1771 (1548 / 416 / 454) | 0 | 1129 | 8 ok | 25 / 50 (0) | 6 / 6 (96) |
| D1_ORB | 2546 (1824 / 1032 / 1070) | 0 | 1643 | 8 ok | 61 / 118 (0) | 5 / 5 (267) |
| D2_COR | 2562 (1829 / 1093 / 1131) | 0 | 1545 | 4 ok | 81 / 175 (0) | 3 / 3 (83) |
| D3A_IAC | 2893 (2033 / 1349 / 1387) | 0 | 1867 | 6 ok | 165 / 241 (0) | 3 / 3 (107) |
| D3B_IAC | 2828 (2014 / 1210 / 1248) | 0 | 1976 | 7 ok | 118 / 179 (0) | 3 / 3 (107) |
| D5_OME | 1615 (1344 / 464 / 502) | 0 | 948 | 7 ok | 42 / 42 (0) | 6 / 6 (119) |

- No INT wave lacks its FRA twin, and the manifests agree with disk everywhere.
- Waves on disk total 1.4–2.3 GB per chapter (uncompressed .wav; chapters share many, so the numbers don't add up).
- **The only gap: one A3 dialog line has no wave** (as recorded in the A3 dialog manifest).
- Subtitle JSON exists for the intro / outro films; the text-card FMVs have none.
