# HD full pass: plan (draft 2026-10-11, for Integration)

User order (relayed by Integration 2026-10-11): M1 Gorge 4K -> **HD textures** -> M5 frame gen / upscaling -> RT.
User: "Upgraded / upscaled textures is the next highest priority so we can play the game at higher fidelity. [Textures that fail]
can be remade safely but with more detail if [they're] missing stuff." Remake pass approved; eye review mandatory.

## Starting point (CONFIRMED, from out/hd/full/verdicts.json, out/hd/pack/hd_index.json)
- 3,918 textures in the M4 selection: PASS 2,247 / REMAKE 1,556 / KEEP 115.
  - colour 1,355 PASS / 323 REMAKE; data (masks, TEXSET) 556 / 968; normal 336 / 265; KEEP 112 data + 3 colour.
- Shipped pack (3f410a1, optional in M3): 2,244 rows, 2x, 4,054 MB DDS.
- REMAKE reasons: 1,069 "blend mostly Lanczos" (the models added little), 212 "no faithful upscale" (gate; being re-measured by the
  errata, which has 72/212 done and 36 PASS candidates so far), ~470 "detail gain just under 1.25", 102 custom-colour / aux-glow masks.
- REMAKE by original max side: <=64 px 26, 128 171, 256 187, 512 714, 1024 408, 2048 50.
- M4b remake pilot (20 textures): 8 automatic candidates, 5 rejected by eye -> 3 accepted. The automatic checks miss defects, so
  the eye review gate is required.

## Method per texture class
| class | upscale | remake (when the upscale fails or loses detail) |
|---|---|---|
| colour (diffuse, TEXSET Color) | Rust push pilot winner (gen4x / +mid-band / none), drift gate (SSIM >= 0.80, shift <= 3, new colours <= 3 %) | edge-guided / direct model variants (hd_remake), anchored to the original by back-projection; layout, motifs and palette kept; no redrawn logos |
| normal | 4x-Normal-RG0-BC1, renormalised; +normal-detail boost if the pilot shows it in game | height-derived (from colour luminance) micro-detail only, whiteout blend; original base kept |
| data / masks (TEXSET Masks + NormY alpha, spec, emissive) | 4x-PBRify-RPLKSRd-V3 per channel, straight alpha | constant channels copied; custom-colour / aux-glow masks: Lanczos + edge snap (masks must keep exact region edges) |
| tiny (<= 64 px), KEEP | Lanczos or kept | none (no visible gain) |

The resolution factor is 4x capped at 4096² (Integration VRAM guard), else 2x. Which variant wins (look vs cost) is the user's
choice from the Rust in-game sheet.

## Eye review
- Close-up sheets: 8 textures per sheet, original | HD at 6x on the busiest 48 px spot, plus a full-texture thumbnail.
- Throughput (PROVISIONAL, from the remake pilot and M4 showcase): about 100–150 textures/hour of review.
- Scope: every REMAKE result (~1,556, minus the errata wins) and every 4x colour/normal on the screen-visible list; PASS 2x textures
  already shipped are spot-checked at 1 in 10.
- About 2,000 textures to review, so roughly 15–20 review hours spread over the run. A reject means a second variant, or keep the
  2x / original.

## VRAM budget
- The 2x pack is 4,054 MB on disk for all maps. A full 4x set would be about 4x that (~16 GB), so not everything goes 4x.
- The budget is per map: the Rust MEMSTATS per variant (from the pilot) gives the real total texture MB in game. Proposal: 4x only
  for screen-visible textures (ranked by world area per map, plus characters / weapons); everything else stays 2x. Target per-map
  total TBD from MEMSTATS, with headroom for M5 / RT. The RX 7900 XTX has 24 GB.

## Timeline (PROVISIONAL; GPU timings to be measured by the Rust pilot)
0. Now (M1 open, CPU any time outside TIMED holds, GPU in gaps): finish the errata (CPU) and the Rust pilot -> user choice of variant.
1. GPU main track once M1 closes: model outputs for all 3,918. Estimate ~5 s per 1024² at 4x, so ~6–10 GPU hours, run in resumable
   shards with hold checks.
2. CPU build / gates / remake variants in parallel shards.
3. Eye review in batches as results land; the pack and index are written only for reviewed textures.
4. Integration announcement -> install to the HD pack (backup of 3f410a1), FILELOG check in game on Streets / Gorge / Rust.
Rough total: 3–5 days of wall time, depending on GPU gaps and review pace.

## Decisions (Integration 2026-10-11: plan approved as drafted)
- VRAM: <= 8 GB of textures per map in game (MEMSTATS), with Rendering's compressed upload (BC7 / S3TC sRGB) for HD-on. If 4x on
  the screen-visible set exceeds 8 GB, narrow the 4x set; do not raise the budget.
- 4x only for screen-visible textures plus characters and weapons.
- Install keeps 3f410a1 as a backup; FILELOG check on Streets / Gorge / Rust.

## User decision (relayed by Integration 2026-10-11): variant C, "I want the most amount of details"
Rust pilot (hd_push.py, in-game sheets out/hd/push_pilot/ingame): A 4x / B +mid-band / C +normal detail all cost the same VRAM
(3,265 MB vs 1,432 MB off, uncompressed sRGB upload); C is the most visible on lit surfaces.

### Method (replaces the per-class table above where they differ)
- Every texture: the 4x model output, anchored to the original (low-frequency back-projection); then the ladder
  **D -> C -> B -> A -> original**: the strongest level that passes the drift gate (SSIM >= 0.80, mean shift <= 3, new colours <= 3 %)
  and the full-resolution `broken_blocks` gate = 0 is used. TEXSET Color / Masks pairs always take the same level.
  D only if the user approves it from a C vs D sheet; until then the top is C.
- Models: colour 4x-Textures-GTAV-rgt-s (**CPU**: DirectML corrupts interior tiles), masks / alpha 4x-PBRify-RPLKSRd-V3 and
  normals 4x-Normal-RG0-BC1 on DirectML (verified clean).
- 4x up to 4096² (originals up to 1024), 2x for 2048 originals.
- Remake pool (1,470 = 1,556 REMAKE - 86 errata wins): the same ladder. Where it falls to the original, the M4 remake variants
  (hd_remake: edge / height / direct) are tried at the highest level that passes. Eye review decides, as for all textures.
- Eye review: mandatory for every texture that enters the pack (close-up sheets, original | chosen level, 8 per sheet);
  reject -> next lower level or original. EYE_REJECT list in the generator, never hand edits.
- VRAM: <= 8 GB per map, assumes Rendering's compressed sRGB upload (Rendering estimate: C, 4x full Rust ~3.3 GB).

### D prototype (Integration: "more mid-band and relief than C, same layout / motifs / palette, still gated")
- Luminance-only mid band (gain 1.0 vs C's 0.6, sigma 3 orig px) plus a fine band (sigma 1 orig px, gain 0.5); chroma unchanged,
  so the palette holds. Normal relief base x1.6 (C 1.25), micro 0.30 (C 0.15).
- Run on the Rust pilot set when the M1 slots end (CPU build ~20 min); texture sheets + eye review; Rendering's in-game C vs D
  captures for the user.

### Timeline (PROVISIONAL; measured pilot rates)
| step | rate | full pass |
|---|---|---|
| colour model on CPU (12 of 32 threads) | ~230 s / 1024², 55 s / 512² (6 threads, pilot) | ~1,700 colour textures: ~25-45 h CPU |
| first: DirectML retest of the colour model at 144 px tiles (edge tiles were correct) | if clean: ~10x faster | ~4-6 h GPU instead |
| masks / normals on DirectML | 1-4 s each | ~2 h GPU |
| build (anchor, ladder, gates, BC encode) | ~25 s / texture (4 levels) | ~3,800 textures: ~26 h CPU, ~9 h in 3 shards |
| eye review | ~100-150 / h | ~3,800 textures (all levels changed): ~25-35 h, in batches as builds land |
| install + FILELOG (Streets / Gorge / Rust) | | ~0.5 day |
Wall time with gaps and holds: about 4-6 days after the M1 slots end, if the DirectML retest is clean. If it isn't (CPU colour model),
about 6-8 days. Everything is resumable and hold-aware; an announced PERF HOLD = all runners stopped.

### Approved (Integration 2026-10-11), with conditions
1. The DirectML colour retest (scripts/wfc/hd_dml_retest.py, 144 px tiles) counts as clean only if broken_blocks == 0 AND sampled
   interior tiles match a CPU run (mean |diff| <= 1.0), on >= 20 colour textures of mixed sizes (256 / 512 / 1024 / 2048).
2. Eye review is mandatory per texture; progress goes to Integration once per completed batch.
Starts when the M1 slots end (PERF_HOLD cleared).

### Results 2026-10-12 (after the M1 slots)
- DirectML retest at 144 px tiles: **NOT CLEAN** (stopped at 13 of 20 once the rule could no longer pass): 3 clean, 10 with broken
  blocks (256 px 5/5, 512 px 4/6, 1024 px 1/2). Every sampled interior tile matched the CPU (mean |diff| 0.0); the corrupt tile is the
  top-left corner tile (128 px input, no padding), seen by eye on k 61 / 1872 / 2397. DML is also only ~2x faster than CPU (101 s vs
  ~228 s per 1024², `aten::roll` falls back to CPU), so the colour model stays on **CPU** (timeline row "6-8 days").
- D prototype on the Rust pilot: D on 26 of 37 textures (8 fall to C, 1 B, 2 A); texture-space eye review passed (layout, motifs and
  palette kept). Rendering's C vs D in-game captures (`_cd` runs, compressed sRGB upload build): same VRAM (1,566 MB, 36 HD); sheets
  out/hd/push_pilot/ingame_cd (`hd_push.py ingame cd`).

## Open
- D vs C (user, from the Rust C vs D sheet).
- hd_pbr does not fit: there is no renderer PBR path (reported earlier).
