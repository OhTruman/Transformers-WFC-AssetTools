# HD finish plan: D to the end, E (beyond D) for every world surface, Modern maps (2026-10-13, for Integration)

*User decision (relayed): the next playtest waits for "the newer textures" plus full RT. Estimates below are from today's
measurements; anything not measured at scale is marked PROVISIONAL.*

## 1. D pass to the end

| step | left | rate | wall time |
|---|---|---|---|
| colour model (rgt-s, CPU) | ~390 of 917 units of 1024² (~700 textures) | one 12-thread process ~18 units/h on a free CPU (measured 07:42-10:47, shared CPU: ~14/h) | ~22 h; a 2 x 12-thread trial on the free 32-thread CPU (30 min) may cut it to ~15 h (PROVISIONAL: the 2 x 8 test was slower, but V_bake was taking 8 threads then) |
| GPU rows (masks / data / normals, DML) | ~70-250 rows (normals 56, texset normals ~8, some alpha / mask rgb) | 1-90 s per row | 1-2 h; runs alongside the CPU colour model (no conflict); upscaler models use 4-6 GB VRAM in small 128 px tiles |
| builds | batches 13-31 | 20-60 s per unit, 4 threads | keeps pace with the colour model |
| eye review + caps + capped rebuild + pack | 19 batches (13-31) | 45-60 min per batch | 15-19 h of review time, pipelined behind the colour model |

**D complete: ~1.5 days wall time (about 2026-10-15 morning) without long holds.** Frozen snapshot `push_full_snap_<date>_b0-31`.

GPU and TDRs: today's resets (8) all involved DirectML beside GL exes; one (08:54) hit with the sliced SD job and only two GL exes.
The D GPU rows are light (4-6 GB, short dispatches), so running them beside Rendering's single RT exe is a moderate risk. They
are only 1-2 h, so the safest route is a short window without the RT exe.

## 2. E (generative, level 2) for every world surface: days, not weeks

- **Scope**: every colour / TEXSET-colour texture in the D pack, minus those kept original (sky, glow / EMIS / Illum, FX
  gradients, lens flares, cube maps: about 10 %), minus characters and weapons (separate decision). About 1,400 textures, about
  800 units of 1024².
- **Method**: as the Rust pilot. SD 1.5 + ControlNet tile at G2 (denoise 0.40) only, with no G1 / G3 ladder for the full pass.
  Exact lock to D at the original resolution; tint (Masks B) and emissive (Masks R) regions are kept as D. The TEXSET alpha gets
  relief from the E colour's height. Experimental's gates apply.
- **GPU**: measured on Rust at G2, 2048² is ~2 min and 4096² ~9 min, so ~0.55 min per 1024² unit. That gives **~8 GPU hours** for
  everything. It needs ~10.8 GB VRAM and must run without GL / RT exes (TDR finding), so it needs exclusive GPU windows.
- **CPU**: height model + lock + BC encode, ~25 s per texture, so ~10 h, running in parallel.
- **Eye review**: 100 % (Experimental), ~12 h.
- **Pipelining**: E can start now on D batches 0-12 (1,531 rows) and follow each reviewed D batch.
  **E complete: ~2-3 days after D** (overlapping, so about 2026-10-17/18).
- **Per-map order**: Molten, Streets, Gorge, Rust, Debris, then the rest. Exact per-map lists come from Rendering's
  materials_glsl texture slots, as for Rust: 838 bound 2d objects, 254 world (ENV_ / DES_), ~190 colour-like. The VerticalSlice
  materials.json covers only ~170 BSP materials per map, so it is not enough. To do: ask Rendering for the same TSV for Molten,
  Streets, Gorge and Debris.
- **No cut needed** at this size. If GPU windows stay scarce, the cut is the per-map order above, plus the surfaces that fill
  the screen (floors, walls, large architecture), from Rendering's bind census ranked by coverage.

## 3. Modern maps (Systems M6)

- 0 of 490 roughness parents done (work list: SYSTEMS_M6_WORKLIST.json); 15 ORM candidates held.
- Roughness: 1x-PBRify-RoughnessV2 on the final colour, half the colour resolution, mean normalised to Systems' derived target
  per texture, BC4 linear.
- Estimate (PROVISIONAL, not measured at scale): 10-30 s per texture on CPU, so ~3-4 h plus family review sheets (~2 h).
- They come from the final colour, so they run per batch after E (or from D where E is not accepted).
- Rows go in `pack/hd_pbr_index.json`:
  `{key: <parent key>#roughness, tex: <parent object>, role: roughness, dds, format: BC4, space: linear, srgb: false, bytes, from}`.

## 4. Packing

| snapshot | content | when |
|---|---|---|
| `push_full_snap_20261013_b0-12` | D, batches 0-12 (1,531) | done, in package a44aa6db |
| `push_full_snap_<date>_b0-31` | D complete | ~2026-10-15 |
| `push_e_snap_<date>_<maps>` | E rows only (level 2, loaded over a D root by key) + `hd_pbr_index.json` | per milestone (first maps, then all) |

Every snapshot is frozen (never rewritten), byte-checked and stale-checked, and static-checked by Systems before a package.
Level 2 = an E root over a D root: the runtime takes a row from E where its key exists, else from D (Rendering's loader step 6).
