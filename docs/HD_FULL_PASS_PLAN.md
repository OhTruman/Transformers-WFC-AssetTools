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

## Open
- The variant choice (user, from the Rust in-game sheet; Integration sends it).
- hd_pbr does not fit: there is no renderer PBR path (reported earlier).
