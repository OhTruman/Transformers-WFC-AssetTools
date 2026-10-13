# Beyond D: level E, generative remake, Modern maps (plan, draft for review)

*User decision 2026-10-12 (relayed by Integration, verbatim): "Yes it can go beyond faithful! I want the game to look realistic
and new." Also "Yes the brand new textures should be the default" (the HD pack ships on, originals selectable).
Scope from Integration: the D pass finishes first and is not interrupted; plan docs first; no runs until the D colour model
is done.*

What stays fixed in everything below: **designs, layouts, shapes, markings and palette** of the original art. What may now
change: **surface detail** the original never had (micro-structure, wear, grime, relief), including material realism.

## 1. Level E (pilot on the Rust set)

D is the strongest *faithful* level: it boosts detail the 4x model recovered, but it adds nothing. E adds detail.

### Approach: generative detail inside a soft lock

1. **Input** is the D result (or the eye-capped level, if a texture was capped below D), not the original, so E builds on the
   reviewed HD.
2. **Generate.** Image-to-image at low to medium denoise with a structure condition (tile / edge ControlNet) and a short
   material prompt per texture class (painted metal, concrete, rubber, glass...). The model draws scratches, pitting, grime,
   seams and grain at 4x scale.
3. **Soft lock.** This replaces D's hard lock. The result, area-downsampled to 1/4 of its size (the original resolution) and
   blurred, must match the original within a tolerance. This is not an exact match like D's back-projection. Low frequencies
   (layout, shapes, palette) therefore stay the artist's, and everything finer may be new.
4. **Relief.** For TEXSET / normal maps, E's added detail gets matching relief: a height map from the E colour (the hd_pbr
   PBRify height model), turned into micro normals, added on top of the D normal. The original normal stays the base.

### Alternative to compare in the pilot: detail-map synthesis (no diffusion)

The texture is classed by material from its colour and name. CC0 exemplar detail layers (for example ambientCG materials:
micro-normal, grime and wear masks) are tiled at the texture's world scale and blended: grime in cavities, wear on edges,
both found from the normal / height map. This is cheaper, deterministic and never invents shapes, but looks more
"procedural". The pilot shows both.

### Ladder and gates

- Ladder crops: `orig | D | E1 | E2 | E3`, where E1-E3 are increasing generative strength (denoise / lock tolerance), at the
  busiest spot plus one flat spot. Flat spots are where added detail shows most.
- **Kept gates:**
  - layout: edge map at the original resolution, E vs original;
  - palette: per-region mean colour and hue histogram, E vs original;
  - alpha / mask channels exact;
  - `broken_blocks` on the model output.
- **Relaxed gate:** drift / SSIM to the D result (expected to fall; it no longer fails a texture).
- **New gate:** tiling seams. E must wrap like the original: tile-wrapped generation or a seam check on the four edges.
- Kept original, as in D: glow / EMIS, FX gradients, clouds, cube maps, decals / text (crisp vector re-render instead; see 2).
- Eye review stays mandatory.

### Pilot

- **Set:** the textures MP_IAC_Rust actually loads (Rendering's FILELOG for Rust) intersected with the HD selection, about 20
  across classes (painted metal, concrete, grates, TEXSET pairs, one normal, one decal). UNKNOWN until the FILELOG list is in
  hand.
- **Outputs:**
  - ladder crops for the user (via Integration);
  - in-game full-frame 2560x1440 pairs, D vs E, separate files, from Rendering, with E installed only in a pilot root
    (`out/hd/push_e_pilot/pack`, passed via WFC_HD_ROOT), never in ExtractedAssets.
- **Measure:** seconds per texture on DirectML (diffusion is much slower on DML than CUDA), VRAM, and the pass time for the
  full set.
- **Budget:** E keeps D's resolution and formats (DXT1 / DXT5), so per-map texture memory stays under the 8 GB limit.

## 2. Remake pool with added detail

`manifests/hd/remake_candidates.json` lists 1,556 textures (`hd_full.py index`). Integration quotes 1,470; the difference is
probably the KEEP / tiny exclusions. To verify against the full selection before the run.

The earlier HD_REMAKE_PLAN allowed only *restored* detail under a hard lock. The change: the remake pool uses the E pipeline,
with the hard lock replaced by the soft lock, so it may add detail.

| type | approach |
|---|---|
| grunge / painted metal / concrete | E (img2img with a structure condition) + soft lock |
| decals, text, logos, markings | no diffusion: vectorise (OpenCV contours) and re-render crisp; may then get an E wear pass, masked off the marking itself |
| team-paint / glow / alpha-as-data masks | exact (thresholded, re-rasterised edges); never generated |
| normal maps | from the remade colour (height -> micro normal) on top of the original normal |

- Gates as in E: layout, palette and alpha kept, drift relaxed, seam check added, plus eye review per class.
- Tools and licences as in HD_REMAKE_PLAN:
  - FLUX.1-schnell (Apache-2.0);
  - SDXL (OpenRAIL++-M; the use restrictions are passed on in CREDITS);
  - ControlNet tile per model licence;
  - no NC models.
- Each model's licence and sha256 goes in `bin/hdmodels/models.json`.

## 3. Modern materials (Systems M6): roughness / metal / AO / height

`scripts/wfc/hd_pbr.py` already makes a sample from the HD albedo:
- height: PBRify-Height (CC0);
- roughness: PBRify-RoughnessV2 (CC0);
- AO: multi-scale cavity from height;
- metalness: a PROVISIONAL heuristic, because no redistributable generator exists.

The next pass after E runs it per texture on the **final** colour (E where accepted, else the eye-capped D), so the maps
match what ships.

Open with Systems before any run (their renderer path decides the format):
- Packing. The proposal is ORM in one DXT1 (R = AO, G = roughness, B = metal) per colour texture, with height kept separate
  (G8 or DXT5 alpha) only if their path uses parallax. This is about 0.5 byte per texel extra; it needs a VRAM check against
  the 8 GB per map.
- Index: sibling rows in `hd_index.json` (`role: orm / height`, same key prefix). Existing keys are not renamed.
- The metalness heuristic stays PROVISIONAL until Systems or the user accepts it on in-game shots.
- The renderer has no PBR path today, as reported earlier; M6 must provide it.

## Order

1. D pass completes (colour model about 2026-10-14), its batches are reviewed and packed, and it is installed via an
   Integration announcement with backups and the FILELOG check.
2. E pilot on Rust: about 20 textures, diffusion vs detail-map synthesis, ladder crops, then in-game pairs. The user picks the
   method and strength.
3. E full pass over the HD selection, then the remake pool with the same pipeline. Batches, eye review and the pack work as
   in D. The time estimate comes from the pilot.
4. Modern maps from the final colour, in Systems' format.
