# Original-frame references for Gorge haze / Rust fog (AssetTools, 2026-10-18; read-only search)

**Question (Integration):** is there any shipped image showing MP_UND_Gorge's far-canyon haze or MP_IAC_Rust's interior fog as the
original renderer drew it?

**Answer:** one in-engine render per map, the map-select thumbnail. Rust's shows interior fog. Gorge's shows an interior pipe area with
haze, but NOT the far canyon, so there is no shipped reference for the far-canyon haze.

## Hits

| map | package / texture | size | kind | copy |
|---|---|---|---|---|
| MP_UND_Gorge | `UI_LevelThumbnails_p.MP_Gorge` | 512 × 256 RGB, 171,110 B | in-engine render (map-select thumbnail; `frontend_maps.json` binds it to MP_UND_Gorge_BASE_m) | `refs/MP_UND_Gorge_thumbnail_UI_LevelThumbnails_p.png` |
| MP_IAC_Rust | `UI_LevelThumbnails_p.MP_Rust` | 512 × 256 RGB, 155,120 B | in-engine render (map-select thumbnail; bound to MP_IAC_Rust_BASE_m) | `refs/MP_IAC_Rust_thumbnail_UI_LevelThumbnails_p.png` |

**Caveats:**
- Small and block-compressed in the cook. How they were captured (camera, post settings) is UNKNOWN. Use them for haze colour and density
  read, not exact values.
- The camera positions aren't recorded anywhere, so a matching rebuild frame has to be found by eye.
- Gorge thumbnail: dark interior with blue-grey haze toward the back wall; no sky or canyon.
- Rust thumbnail: warm grey haze over the far arches and the Decepticon disc, with light motes.

## Searched, no hit

- **Loading screen:** `UI_GFxLoading_p` (LoadScreen / LoadScreenAlpha GFx). Only UI elements: a 1024 × 256 strip, icons, white or
  alpha masks. No map image.
- **Lobby:** `UI_GFxLobbies_p.MapImage1/2` are 32 × 32 placeholders; the lobby uses the thumbnails above.
- **Front end:** `UI_GFxFrontEnd_p`: logos only.
- **Extras gallery:** `UI_ExtrasContent_p` (Iacon / Kaon / Core / Orbital 01–15, 1024 × 512, plus character and weapon sheets). All
  concept art, painted or sketched, at area level; none is identifiable as Gorge or Rust.
- **Movies** (converted WebM set; frames sampled every 6 s):
  - `FMV_intro`: pre-rendered CG of Cybertron and the war, no MP map.
  - `TF_LoadingScreen_INT`: a spinner on black.
  - `TF_InitialStartup`: logos and legal text.
  - The campaign FMVs aren't MP.
- **Texture names:** inventory.db Texture2D names containing gorge / rust / loading / thumb / preview / mapimage / levelshot. Apart from
  the thumbnails, only material textures (rust decals) and particle-system editor thumbnails.
- **Other:** no achievement or splash textures with map imagery exist in the cooked set.
