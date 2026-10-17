# Campaign assets: summary over all 10 chapters (AssetTools, 2026-10-18; read-only)

**Sources:**
- Per chapter: `manifests/campaign/<ch>_assets.json`, from `scripts/wfc/campaign_chapter_assets.py <CH>`. Each chapter ran under
  `run_bounded.py` (6 GB cap) in about 12 s, with a peak under 1 GB.
- Campaign-wide: `manifests/campaign/summary.json`, from `scripts/wfc/campaign_assets_summary.py`.
- A1 detail: `CAMPAIGN_A1_ASSETS.md`. The method and the column meanings are the same for every chapter.
- D3A / D3B are separate chapters (3 / 4). They share the d3 movies, so both rows list them.

## Per chapter

Columns:
- **levels:** level packages, with the `_LM` / `_LOC_int` / `_LOC_FRA` companion counts in brackets.
- **deps:** package dependencies.
- **objects / MB:** distinct objects, an INT build.
- **textures:** "not extr." = textures without a PNG.
- **anim sets:** "psa-only" = present only as raw .psa.
- **materials tr / cand / miss:** translator status (PROVISIONAL definition, A1 doc §3).
- **FX (PARTIAL):** pstream.
- **live w/o actor:** unbound matinee groups that still fire.
- **AI / conv / obj / ckpt:** pawn factories / conversations / objective bank keys / checkpoints.
- **dump gaps:**
  - uncooked streaming levels;
  - content imports unresolved, or resolved only outside the chapter's packages;
  - waves without a file.

| chapter | levels (+LM/INT/FRA) | deps | objects / MB | meshes st / sk | textures (not extr.) | cues / waves | anim sets (psa-only) | materials tr / cand / miss | FX (PARTIAL) | Kismet seq / matinees (live w/o actor) | AI / conv / obj / ckpt | FMV | dump gaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1_IAC | 51 (48/20/20) | 179 | 185,056 / 466.1 | 676 / 137 | 1,528 (18) | 1,821 / 2,604 | 237 (3) | 569 / 416 / 103 | 281 (2) | 475 / 495 (30) | 143 / 72 / 7 / 26 | a1intro, a1outro, a1text_FRA, a1text_INT | 0 |
| A2_KON | 56 (50/23/23) | 179 | 145,859 / 452.9 | 398 / 132 | 1,474 (16) | 1,773 / 2,786 | 240 (4) | 445 / 274 / 101 | 269 (2) | 389 / 359 (2) | 120 / 134 / 8 / 34 | a2outro, a2text_FRA, a2text_INT | 0 |
| A3_COR | 49 (41/25/25) | 178 | 153,444 / 383.2 | 562 / 138 | 1,486 (20) | 1,808 / 2,837 | 214 (3) | 485 / 235 / 94 | 270 (2) | 327 / 457 (33) | 102 / 99 / 12 / 25 | a3outro, a3text_FRA, a3text_INT | 0 |
| A4_ORB | 47 (37/20/20) | 163 | 165,878 / 414.6 | 782 / 133 | 1,570 (17) | 1,755 / 2,752 | 176 (3) | 512 / 320 / 171 | 309 (1) | 326 / 289 (48) | 119 / 95 / 10 / 23 | a4intro, a4text_FRA, a4text_INT | 0 |
| A5_TRY | 15 (11/4/4) | 137 | 62,253 / 204.6 | 323 / 94 | 1,458 (14) | 1,129 / 1,771 | 146 (2) | 426 / 145 / 59 | 237 (1) | 84 / 139 (25) | 29 / 25 / 6 / 4 | a5itext_FRA, a5itext_INT, a5otext_ESN, a5otext_FRA, a5otext_INT, a5outro | 0 |
| D1_ORB | 56 (50/24/24) | 172 | 164,189 / 487.9 | 625 / 130 | 1,765 (18) | 1,643 / 2,546 | 221 (3) | 592 / 395 / 130 | 266 (1) | 381 / 434 (15) | 180 / 61 / 7 / 21 | d1intro, d1itext_FRA, d1outro, d1text_FRA, d1text_INT | 0 |
| D2_COR | 44 (40/21/21) | 149 | 158,861 / 396.8 | 551 / 116 | 1,406 (17) | 1,545 / 2,562 | 166 (2) | 459 / 257 / 93 | 249 (1) | 289 / 319 (20) | 162 / 81 / 10 / 22 | d2outro, d2text_FRA, d2text_INT | 0 |
| D3A_IAC | 48 (45/23/23) | 184 | 171,784 / 402.9 | 597 / 142 | 1,575 (17) | 1,867 / 2,893 | 215 (5) | 594 / 326 / 155 | 300 (1) | 511 / 717 (45) | 228 / 165 / 12 / 28 | d3outro, d3text_FRA, d3text_INT | 0 |
| D3B_IAC | 55 (51/23/23) | 208 | 134,898 / 347.7 | 604 / 143 | 1,610 (19) | 1,976 / 2,828 | 220 (5) | 531 / 286 / 130 | 297 (1) | 370 / 326 (46) | 150 / 118 / 13 / 26 | d3outro, d3text_FRA, d3text_INT | 0 |
| D5_OME | 9 (5/1/1) | 123 | 54,664 / 154.1 | 222 / 86 | 1,358 (16) | 948 / 1,615 | 109 (1) | 351 / 125 / 66 | 208 (1) | 28 / 40 (0) | 30 / 42 / 3 / 2 | d5itext_FRA, d5itext_INT, d5otext_FRA, d5otext_INT, d5outro, d5text_FRA | 0 |

## Campaign-wide totals

**Summed over chapters** (objects shared between chapters count once per chapter):
- 430 level packages; 1,396,886 objects; 3,710.8 MB.
- 5,340 static + 1,251 skeletal meshes; 15,230 textures.
- 16,265 cues / 25,194 waves; 1,944 anim sets; 8,861 materials; 2,686 FX.
- 3,180 Kismet sequences; 3,575 matinees; 1,263 AI factories.
- 892 conversations; 88 objective keys; 211 checkpoints.

**Distinct across the campaign** (each object once):

| group | count | MB |
|---|---|---|
| static meshes | 2,334 | 129.9 |
| skeletal meshes | 358 | 75.2 |
| materials | 2,865 | 6.4 |
| textures | 3,473 | 195.2 |
| lightmap textures | 8,194 | 240.9 |
| fx templates | 528 | 0.1 |
| sound cues | 7,911 | 0.5 |
| sound waves | 8,097 | 108.3 |
| anim sets | 599 | 0.5 |
| anim sequences | 3,686 | 70.9 |
| facefx | 22 | 3.1 |
| physics assets | 165 | 0.0 |
| kismet sequences | 3,189 | 2.2 |
| matinee data | 3,601 | 0.6 |
| gfx movies | 13 | 1.0 |
| shader caches | 1,037 | 545.5 |

Materials, distinct: 1,098 translated, 1,291 candidate, 472 missing, 4 engine default. The candidates sit on 94 masters and the missing ones on 296.

PARTIAL FX, distinct: `FX_H2H_p.FX.H2H_Punch01_FX` (10 chapters); `FX_Transformers_p.FX.Transforming_Impact_Sm_FX` (2 chapters); `FX_Plasma_Flares_p.FX.PowerCell_Voltage_FX` (1 chapter). The first two are the open SubUVDirect [SubUVPosition, SubUVSize] order. **PowerCell_Voltage_FX is a different, new case.** In
`ParticleSpriteEmitter_5839.ParticleLODLevel_14559`, one float constant curve (15 values) and one vector constant curve (10 values) are
left over: none of the LOD's compiled modules (Lifetime, Size, Velocity, LocationPrimitiveCylinder, Color, SubUV, ColorScaleOverLife)
claims them. UNKNOWN; for RE.

## Dump gaps

**None in any chapter:**
- All 430 streaming levels are cooked.
- 0 content imports are unresolved, and 0 resolve only outside the chapter's packages.
- Every wave a cue plays has a file, and every localized wave has INT + FRA twins.

**Our extraction gaps** (every chapter, same kind):
- Textures without a PNG: mostly TextureCube, plus render targets and a few others.
- A few anim sets only as raw .psa.
- 1–2 PARTIAL FX per chapter.

## Material translator dry run (sizes the campaign material work)

**Method:** `work/matc_dryrun/dryrun.py <CH>` imports Rendering's `Rebuild/tools/render/matc.py` read-only.
- It set no-bytecode; no file under `Rebuild/` changed (checked).
- The texture resolver is a stub that never exports or decodes.
- Results are in `work/matc_dryrun/<CH>.json` + `aggregate.txt`.
- Each material compiles once, in the first chapter that loads it, against that chapter's level packages + build_materials.py's
  fallback packages.
- matc.py has no `--check` flag; this is the equivalent: `MatCompiler(...).build()`, keeping only success or the CompileError.

**Control:** 237 materials already translated in the MP sets were compiled the same way: **237 / 237 clean**, so the harness
reproduces the live build's results.

**Result over the 1,763 campaign materials not yet translated (1,291 candidate + 472 missing):**

| result | count | what it needs |
|---|---|---|
| **clean** | **1,725** (all 1,291 candidates + 434 of the missing) | nothing new: it compiles with today's translator (363 distinct masters) |
| new expression node | 23 | 5 node classes (below) |
| no master | 12 | translator accepts only `Material` as the chain root; these root at a **`DecalMaterial`** (7 decal masters + 5 instances) |
| ShaderCode HLSL function | 3 | `ddy` (Hologram_Post_MAT + its MATINST), `acos` (DarkEnergonCrystal_FloorCrack_Emiss_MAT) |

**New nodes:**

| expression class | materials | where |
|---|---|---|
| `MaterialExpressionLensFlareIntensity` | 11 | ENV_NEU_LensflareTest_p flares, ORB_LensFlare_BASE |
| `MaterialExpressionDdx` | 4 | TR_OmegaSupreme_Mat + 3 Omega Supreme instances |
| `MaterialExpressionIf` | 4 | FX Splash_Big_Clip (2 masters + 2 instances) |
| `MaterialExpressionLensFlareOcclusion` | 3 | flare_radialBlur (A1 / base / Zeta) |
| `MaterialExpressionCameraWorldPosition` | 1 | CybertronPenumber_MAT (orbit matte) |

**Sizing:**
- 97.8 % of the outstanding campaign materials compile today.
- The remaining 38 come down to:
  - 5 new expression nodes;
  - DecalMaterial accepted as a master;
  - 2 HLSL functions (`ddy`, `acos`) in the ShaderCode translator.
- The lens-flare nodes (14 materials) also need the lens-flare component path that feeds them.

**Caveats:**
- A clean compile means the graph translates. It doesn't prove the output looks right; visual review is still needed.
- Textures were stubbed, so missing texture files (the cube maps above) don't show here.
- The 6 notes "RandomSeed = 0 (first atlas variant; seed source UNKNOWN)" are the translator's existing PROVISIONAL note.
