# Asset extraction - first pass report (2026-09-30)

Game: Transformers: War for Cybertron, Xbox 360 dump (owned copy). Game Dump verified untouched
(all mtimes predate the work; every file in `Xbox360TOC.txt` matches its MD5).
Full pipeline re-run from scratch: **164 s** (`run_pipeline.py`), all steps rc=0.

## 1. Files scanned
2,512 files, 7.0 GB.

## 2. Extensions / formats
`.xxx` 2438 (UE3 packages) · `.bik` 54 (Bink 1) · `.txt` 13 (12 subtitle cue lists + TOC) ·
`Coalesced.ini/.int/.FRA` 3 (obfuscated ini bundles) · `.xex` 1 · `.manifest` 1 (XMNP) · 2 extensionless `PIRS` STFS containers.

## 3. Engine/package format
UE3, FileVersion 511 / Licensee 144, Engine 3428, Cooker 113, big-endian. 918 packages LZO-compressed
(flag 2), 1520 uncompressed. WFC-specific: extra summary int32, 45-byte export entries with conditional
tail, 4-byte bools. No TFC/external caches: all texture, audio and mesh data is inside packages, with
copies duplicated per map. 2.76 M exports; **44,596 unique assets** after dedup by original object path.
Details: `FORMAT_NOTES.md`.

## 4. Map packages
459 packages contain a World: campaign chapters A1–A5 / D1–D5 split into Base/Art/Design/Audio/Vig/Cine
sub-levels (+ `_LM` lightmap and `_LOC_int/_LOC_FRA` companions), and 13 multiplayer map groups
(MP_ESC_BrokenHope, MP_ESC_Remnant, MP_IAC_Berth/Rust/Seed/Streets/Global, MP_KON_Molten, MP_ORB_*,
MP_UND_Complex/Gorge). Map metadata covers 108,542 actors (0 unparsed): 13,015 static-mesh,
6,194 skeletal-mesh, 7,077 particle and 1,296 sound-cue references, with transforms and prefab archetypes.

## 5. Textures
5,265 unique Texture2D + 18 TextureCube → **5,049 PNG** extracted (correct Xbox untiling verified).
207 have no mip data in any cooked copy (mostly editor icons); 18 cubemaps are unsupported.
16k LightMapTexture2D were deliberately skipped (`-nolightmap`).

## 6. Meshes / animation
- 2,441 static meshes → **2,439 glTF**
- 402 skeletal meshes → **401 glTF** (skinned, real material names)
- 634 AnimSets (3,921 sequences) → **632 PSA + 632 glTF animation files** (4,165 animation clips), validated against the rest pose
- 190 PhysicsAssets and 544 ParticleSystems: metadata/references only
- 24 FaceFX → 22 `.fxa`

## 7. Audio
`SoundNodeWaveEx` = FMOD **FSB4** with XMA2 inside. 18,225 unique waves → **14,480 FSB + WAV**.
The 3,745 not extracted are payload-less dialog stubs. There are 8,797 SoundCues and 360 HmSoundEvents (references only).
Movies: 54 Bink → MKV (H.264 + all FLAC tracks), with subtitles as JSON.

## 8. Tools that work
- UE Viewer/umodel 1590 (`-game=trans`): package loading, LZO, texture untile/decode, static/skeletal glTF, PSA, MIC `.mat`, Scaleform `.gfx`, FaceFX
- vgmstream: FSB4/XMA2 → WAV, 0 failures
- ffmpeg: Bink 1 video and audio, 0 failures

## 9. Tools that fail / partially fail, and why
- **umodel, dialog/music audio:** writes zero-filled `.unk`. The FSB4 sits 0x8000-aligned inside the export, and umodel reads from the start of the zero padding → replaced by `sounds.py` (offset/size are in the export's last 8 bytes).
- **umodel, glTF animation:** not available from the CLI ("viewer only") → `.psa` + `psa2gltf.py`.
- **umodel, base Material:** skipped ("empty parameters") → links come from properties instead.
- **umodel, TextureCube:** no exporter.
- **umodel, `-obj=` handling:** names with spaces break the response file, and one unknown name aborts the whole run → handled in `extract.py`.
- **umodel, `-save`:** copies packages byte-for-byte; it does not decompress.
- **python-lzo:** no wheel for 3.12 → replaced by `lzallright`.
- **Decrypticon/TFGamesUtil** (community Coalesced tools): not used; the key was re-derived instead.

## 10. Scripts/tools created
`AssetTools/run_pipeline.py`, `setup_tools.ps1`, and in `scripts/wfc/`: `ue3pkg.py`, `props.py`, `inventory.py`,
`extract.py`, `sounds.py`, `build_db.py`, `psa2gltf.py`, `maps.py`, `coalesced.py`, `movies.py`, `high_value.py`.

## 11. Manifests/databases
`manifests/assets.json` (44,596 assets) · `inventory.db` (SQLite: files/packages/exports/imports/deps) ·
`files.json` · `packages.json` · `packages/<pkg>.json` (2,438 full tables) · `summary.json` · `maps.json` ·
`high_value.json` · `config_report.json` · `extracted/*.jsonl` (object → output mapping) + `*_status.json`.

## 12. Extracted so far (ExtractedAssets, ~13.5 GB)
- **Content:** 5,049 PNG textures · 2,439 static + 401 skeletal glTF · 632 PSA + 632 anim glTF ·
  14,480 FSB + 14,480 WAV · 1,596 MIC `.mat` · 38 `.gfx` · 22 `.fxa`
- **Maps:** 459 map JSON files
- **Config/localization:** 60 decoded ini/int/FRA files + JSON
- **Movies:** 54 MKV + 12 subtitle JSON

## 13. Unknown / remaining
- BSP level geometry (`Model`/`BRUSH`; ~100 per map) is not exported
- StaticMeshCollectionActor transforms (native data)
- TextureCube (18)
- Base Material expression graphs → shader reconstruction
- Lightmaps (skipped)
- PhysicsAsset / RB_BodySetup collision shapes
- ParticleSystem emitter data
- SoundCue/HmSoundEvent graphs → wave mapping (refs captured, graph semantics not)
- Bink audio track layout (10 mono tracks: channels vs languages)
- `PIRS` containers (nxeart, system update): low value, not unpacked
- 207 textures and 3,745 dialog waves have no data in the dump

## 14. Next highest-value target
**Map geometry: BSP `Model` export plus StaticMeshCollectionActor transforms.** Multiplayer maps
average about 100 BRUSH actors each, and their walls and floors are BSP. Without it the scene JSON places
props in empty space. umodel has no BSP exporter, so this needs a native `UModel` (Points/Vectors/Nodes/Surfs/Verts)
parser → glTF per level, which `ue3pkg.py`/`props.py` are already positioned for.
