# Campaign data gaps: closed on our side (AssetTools, 2026-10-18)

**Scope:** Integration's item on our extraction gaps from `CAMPAIGN_ASSETS_SUMMARY.md` (the dump itself lacks nothing). ExtractedAssets is
read-only for this lane, so every new file goes under `AssetTools/out/` (gitignored, local), with manifests in `manifests/campaign/`.

## Per chapter

| chapter | textures without PNG | → cube faces | → 2D PNG | runtime-only | psa-only anim sets | → converted | no data | PARTIAL FX before → after |
|---|---|---|---|---|---|---|---|---|
| A1_IAC | 18 | 15 | 2 | 1 | 3 | 3 | 0 | 2 → 0 |
| A2_KON | 16 | 14 | 1 | 1 | 4 | 3 | 1 | 2 → 0 |
| A3_COR | 20 | 17 | 2 | 1 | 3 | 3 | 0 | 2 → 0 |
| A4_ORB | 17 | 14 | 2 | 1 | 3 | 3 | 0 | 1 → 0 |
| A5_TRY | 14 | 11 | 2 | 1 | 2 | 2 | 0 | 1 → 0 |
| D1_ORB | 18 | 15 | 2 | 1 | 3 | 3 | 0 | 1 → 0 |
| D2_COR | 17 | 15 | 1 | 1 | 2 | 2 | 0 | 1 → 0 |
| D3A_IAC | 17 | 14 | 2 | 1 | 5 | 5 | 0 | 1 → 0 |
| D3B_IAC | 19 | 16 | 2 | 1 | 5 | 5 | 0 | 1 → 0 |
| D5_OME | 16 | 13 | 2 | 1 | 1 | 1 | 0 | 1 → 0 |

Totals (distinct across chapters):
- 20 textures: 17 cube maps + 2 Texture2D decoded, 1 runtime-only.
- 9 anim sets: 8 converted, 1 without data.
- PARTIAL FX: 3 → 0.

## 1. Textures (`scripts/wfc/campaign_texture_gaps.py` → `manifests/campaign/texture_gaps.json`, files in `out/campaign_textures/`)

- **17 TextureCube → six faces each** (`<name>_f0..f5.png` = +X −X +Y −Y +Z −Z, UE3 order).
  - Decoded from the cooked Xbox data with Rendering's `Rebuild/tools/render/xbox_texture.decode_cube`, imported read-only with no
    bytecode. It is the decoder `build_materials.py` uses for MP cube maps.
  - The manifest gives edge size, format and per-face sha256.
  - Visual spot check: faces are coherent environment maps.
- **2 Texture2D** (`Interior_Spacers_BUMP`, `Drop_CLR`): top mip decoded via `read_mip_chain` / `decode_mip`. umodel had skipped them.
- **1 TextureRenderTarget2D** (`UI_Interacts_p.Center_Screen_R2T`): **runtime-only**, rendered at runtime, so there are no pixels in the
  cook. Recorded, not decoded.

## 2. Anim sets (`scripts/wfc/campaign_anim_gaps.py` → `manifests/campaign/anim_gaps.json`, files in `out/campaign_anims/`)

**Cause:** these AnimSets share their object name with an AnimSet in another package, e.g. `TR_LightSmall_ANM_p.VIG_Run_ANIM` and
`TR_LightMedium_ANM_p.VIG_Run_ANIM`.
- `assets.json` lists both `.psa` files for the record, and `psa2gltf.main` converts only the first, the other package's.
- So this package's own `.psa` was never converted. All 8 differ from their namesakes (md5).

**Fix:** `psa2gltf.convert` takes an optional output path (default unchanged). Each `.psa` is converted with the same conventions:
umodel glTF axes, rest pose and hierarchy from the AnimSet's preview skeletal mesh.

**Results:**
- **8 converted:**
  - `TR_LightSmall_ANM_p`: Interact (13 sequences), VIG_A2 (3), VIG_D1 (1), VIG_D3 (1), VIG_Jump (3), VIG_Run (2), VIG_Scanning (2);
    84 bones.
  - `TR_SoldierTankDec_ROBO_p.Shared_ROBO_ANIM`: 37 sequences, 26 bones.
- **1 has no data:** `TR_HeavyMedium_ANM_p.Melee_SingleHanded_ROBO_ANIM` is cooked with TrackBoneNames only. It has no Sequences property
  and no AnimSequence exports (one 892-byte export in A2_KON_IntroPits_Vig_m). The one matinee group listing it (Bailiff) also lists
  VIG_PointAt_ANIM and VIG_Brute_GuardStaff_ANIM. There is nothing to convert.

**Per-chassis glb tracks:**
- These sets drive campaign vignette / matinee actors (LightSmall vignette robots, the Decepticon tank soldier), not the MP chassis whose
  `robot.glb` files live in ExtractedAssets/VerticalSlice.
- They're delivered as standalone `.anim.gltf`, bound by AnimSet name like the other campaign sets.
- Folding them into a chassis glb would mean writing ExtractedAssets, which needs Integration's go and is a campaign-phase step.

## 3. FX

- **SubUVDirect:** RE resolved the order (update runner case 0x21: k→payload CONFIRMED; naming by class declaration order, HIGH).
  `pstream.py` now names it in MODULE_DISTS.
  - `H2H_Punch01_FX` (all 10 chapters) and `Transforming_Impact_Sm_FX` (A1, A2) are COMPLETE.
  - No stored manifest carried the old provisional label (checked).
- **`PowerCell_Voltage_FX` (A3): COMPLETE**, through a decoder fix rather than a per-LOD rule.
  - RE (CONFIRMED in both runners): each compiled module record carries its own float / vector distribution base index, and the runner
    reads distribution k at base + k without counting records.
  - In the cooked LOD tail they sit in the 7 bytes before each 10-byte record block, as u16 LE (float at +0, vector at +2).
  - `pstream.assign` now assigns by base index. The old sequential pass stays as `assign_sequential`, for regression checks only.
  - **Regression over all 7,350 parsed cooked LODs** (`work/pstream_id0/assign_regression.py`): 7,348 / 7,348 previously complete LODs
    are identical (owner, module, property, distribution, confidence). The only change is PowerCell, incomplete → complete.
  - So no MP or campaign output that uses pstream changes anywhere else. One LOD fails to parse; that predates this change.
  - In PowerCell, Color / SubUV / ColorScaleOverLife had each been shifted by one entry under the sequential pass. Its id-0 record (a
    LocationPrimitiveCylinder object, no compiled ModuleId) owns float[2] / vector[2] by its own base index (CONFIRMED). They are named
    VelocityScale = 0.022 and StartLocation = (0, 0, −400) by base-class order (property_confidence HIGH).
  - The 12 other id-0 Cylinder LODs own no entries (their base equals the next record's).

## Not changed

- No translator changes: the 38 translator gaps stay sized for the campaign phase.
- No MP output was regenerated.
