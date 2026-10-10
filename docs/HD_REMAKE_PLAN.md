# HD texture remake pass - plan (draft for review)

*User decision 2026-10-09: textures that stay pixelated / soft after the faithful upscale ("REMAKE", listed in
`manifests/hd/remake_candidates.json`) get a remake pass after the full pack: "almost identical to the original but just with
added details that weren't there because it was too pixelated to have the detail". This is the only place where added detail is
approved. Not started; this is the plan.*

## Principle: re-synthesis inside a hard lock

1. **Generate** a higher-resolution version guided by the original (image-to-image with structure conditioning), so the model
   draws plausible fine detail (scratches, grain, rivets, wear) where the original pixels could not hold it.
2. **Lock** the result to the original exactly as the faithful pack does: iterative back-projection so that the result,
   area-downsampled to the original size, equals the (deblocked) original. Colours, layout, shapes, markings and every
   pattern visible at the original resolution therefore stay the artist's; only sub-pixel detail is new.
3. **Gate**: the same lock / tone checks as the pack, plus a native-size comparison sheet reviewed by eye per texture class;
   anything that changes what the texture reads as (material, design, markings) is rejected and stays on the plain HD / original.

## Per texture type

| type | approach |
|---|---|
| grunge / painted metal / concrete (most REMAKE candidates) | img2img at low denoise with a tile / structure condition, then the lock |
| decals, text, logos, UI-like markings | no diffusion: vectorise the shapes (OpenCV contours, Apache-2.0) and re-render crisp at 2x / 4x; colours sampled from the original; then the lock |
| team-paint / glow / alpha-as-data masks | kept exact (thresholded, re-rasterised edges), never generated |
| normal maps | derived from the remade colour + the original normal (height integration, as in the Modern maps), then the lock |

## Candidate tools (redistributable outputs only; no NC licences)

| tool / model | licence | notes |
|---|---|---|
| FLUX.1-schnell | Apache-2.0 | strong image model; img2img via diffusers. FLUX.1-dev is non-commercial: excluded |
| Stable Diffusion XL base + refiner | CreativeML Open RAIL++-M | outputs may be redistributed; the use-restriction list must be passed on with the pack credits |
| ControlNet tile (SD 1.5 / SDXL variants) | per model (OpenRAIL / Apache); check each | structure conditioning for texture re-synthesis |
| diffusers | Apache-2.0 | inference library |
| OpenCV | Apache-2.0 | contours / vectorising for decals |
| torch-directml | MIT | already installed; DirectML on the RX 7900 XTX |

Each model's licence, source URL and sha256 go into `bin/hdmodels/models.json` and the pack's `CREDITS.txt`, as for the upscalers.

## Cost / risk

- DirectML is much slower than CUDA for diffusion; a pilot on ~20 REMAKE textures first measures seconds per texture and the
  visual result. GPU time is scheduled through Integration (gaps / overnight), like the upscale runs.
- Disk: models 5-25 GB under `AssetTools/bin/hdmodels` (F:, 500+ GB free). Nothing on C: (1.9 GB free).
- Risk: diffusion drifts in style even at low denoise; the lock bounds colours / layout, and the eye review catches "reads as a
  different material". Rejected textures keep the faithful HD (or the original).

## Order

1. Full faithful pack finishes; PASS / REMAKE verdicts by eye per class.
2. Remake pilot: ~20 REMAKE textures across types, 2 tool options, comparison sheets for the user.
3. User picks; full remake pass over the REMAKE list; same index (the remade texture replaces the original in `hd_index.json`).
