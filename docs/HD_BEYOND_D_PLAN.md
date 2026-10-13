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

Format contract (Systems, 2026-10-12), replacing the ORM-in-DXT1 proposal (BC1's shared 5:6:5 endpoints would bleed
roughness / metal / AO into each other):

- **roughness**: BC4, linear. One per source texture: the one feeding the material's SpecularColor, else DiffuseColor.
  Systems' mapping table lists those textures, which is the generator's work list.
- **metal**: a per-material constant from Systems' classification table, not a texture. Only for materials that mix metal and
  non-metal inside one texture: an **ORM in BC7**, linear (R = small-scale AO, G = roughness, B = metal). The metalness
  heuristic stays PROVISIONAL and applies only there.
- **AO**: skipped (the lightmaps and RT AO cover it); only as the R channel of an ORM that exists anyway.
- **height**: BC4, only if parallax is approved later.
- **Index**: sibling rows next to the original texture's row:
  `{"tex": <original texture name>, "role": "roughness" | "orm" | "height", "dds", "format": "BC4" | "BC7", "space": "linear",
  "from": <generator id + version>, "bytes", "srgb": false}`. `bytes` is for Rendering's MEMSTATS column; `srgb: false` duplicates `space` for the loader.
  - I'll add `key` too: the parent row's key plus `#<role>`, so key lookups stay unique and existing keys are unchanged.
- **Without siblings** a material keeps Systems' derived values, so the maps are a per-family improvement measured against the
  derived version.
- **Encoding**: DirectXTex texconv (MIT, already in bin/texconv), BC4_UNORM / BC7_UNORM, DDS DX10 header. BC7 on the CPU is slow
  (`-nogpu`), so the time is measured on the pilot.
- **Rendering** must confirm the loader reads BC4 / BC7 (RGTC / BPTC, DX10 header); today it accepts only DXT1/3/5, A8R8G8B8 and G8,
  and an unknown format makes it ignore the whole pack. So the PBR rows go in a separate index file (`hd_pbr_index.json`; Rendering resolves it by
  (parent object, role)) until the loader accepts them, and can never disable the colour pack.
- **Order**: Systems' matc "pbr" mapping on the existing textures first; then the classification audit sends the work list;
  then the generated maps.
- The renderer had no PBR path; M6 provides it.

## Experimental review (2026-10-12): required before E pilot results count

1. Customisation / faction read: no E inside custom-colour / Energon tint mask regions (TEXSET mask channels) or the rim around EMIS
   glow; those regions gated at mean dE ~ 0. Characters and weapons excluded from E by default (separate eye sheet if ever).
   The pilot reports dE inside each TEXSET mask channel's region; which channel is the tint mask is UNKNOWN to AssetTools (to
   confirm with Systems / Rendering from the matc shader), so the exclusion itself is not implemented yet.
2. Gates (implemented in hd_e_pilot.py at the original resolution, E vs D): |dmean L| <= 1; mean shift <= 3; pixels in colour bins
   D lacks <= 3 %; Lab dE p99 <= 3; spurious new edges <= 0.5 %; seam = wrap step / interior step, E <= max(D, original) x 1.15.
   Still open: UV-island borders from UV0 coverage (no UV data in AssetTools yet); alpha-exact checked after the BC encode (for
   TEXSET the alpha is a normal component and changes on purpose; for alpha-as-mask textures it must stay exact).
   Eye review 100 % for E; seed / strength recorded per row.
3. E installs as a NEW pack root with an atomic switch, never over D rows; D stays shippable (HD: Faithful (D) / Enhanced (E)).
   Pairs and timed runs use a frozen root (out/hd/push_..._snap_<date>), never the live one.
4. M6 maps at HALF the colour resolution; never G8 / RGBA8 fallbacks; each roughness map's mean normalised to Systems' derived
   value per material (spec_power_mean, m6_mapping.json); one height per texture feeds both E micro-normals and M6 height; M6 maps
   per batch from D where E is not accepted. Work list: Systems' SYSTEMS_M6_WORKLIST.json (490 parents, 15 ORM candidates held).

## E pilot v1 results (2026-10-12, detail-map synthesis, no diffusion)

- Set: the 11 colour units MP_IAC_Rust's materials bind that were already packed at D (20 textures with the TEXSET masks).
- v1 (isotropic micro grain at 10 levels): reads as sensor noise. Rejected by eye.
- v2: grime in cavities, wear on raised edges, relief shading from the 1x-PBRify-Height high-pass, faint grain, exact two-step
  lock at the original resolution. E2 passes the gates on 9 of 11 (E1 11 / 11, E3 2 / 11). By eye it adds faint embossed
  micro-structure (panel seams, pitting) and keeps every design; it is NOT the visibly "realistic and new" look the user asked
  for. PBRify height invents small "+" / circuit marks in flat areas.
- Conclusion (PROVISIONAL until the user sees it): the synthesis route is a safe floor; visible realism needs the generative
  route (img2img + structure control), which needs a diffusion stack AssetTools does not have yet.
- Pilot pack: out/hd/push_e_pilot/pack (E2, 20 rows, 125.5 MB), ladder sheets out/hd/push_e_pilot/ladder_sheet_{1,2}.png.

## D pass fix found by the pilot

8 selection rows carry a png path borrowed from a same-named texture in another package (EditorTextureSet, RectBld, Tubes_Road,
IaconTable). Pack keys now come from each row's own dds path (identical for every other row), and TEXSET halves pair by dds path.
Outputs built with the wrong pairing were removed for rebuild (results 733 / 734 / 1434, texnrm 733 / 1936 / 2705); batches 0-2
are unaffected. Eye caps are keyed by png, so such twins share a cap.

## Order

1. D pass completes (colour model about 2026-10-14), its batches are reviewed and packed, and it is installed via an
   Integration announcement with backups and the FILELOG check.
2. E pilot on Rust: about 20 textures, diffusion vs detail-map synthesis, ladder crops, then in-game pairs. The user picks the
   method and strength.
3. E full pass over the HD selection, then the remake pool with the same pipeline. Batches, eye review and the pack work as
   in D. The time estimate comes from the pilot.
4. Modern maps from the final colour, in Systems' format.
