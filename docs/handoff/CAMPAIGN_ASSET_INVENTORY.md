# Campaign asset inventory (read-only listing, 2026-10-16)

For Integration (rebuild-bd), ahead of the full-campaign phase. Sources: `manifests/inventory.db` (every cooked package and export
in `Game Dump/TransGame/CookedXenon`), `manifests/extracted/*.jsonl`, `out/hd/full/selection.json` + `verdicts.json`, the frozen D
pack `out/hd/push_full_snap_20261016_b0-31/pack/hd_index.json`, `ExtractedAssets/maps|movies`, `RE-Workspace/work/script/decomp`.
Nothing was extracted or run for this listing; ExtractedAssets and the Game Dump were only read.

"Campaign package" = a package whose inventory role is `campaign chapter …` (the `A1_…`–`D5_…` packages). Shared standalone packages
(`ENV_`, `TR_`, `WEP_`, `FX_`, `PROP_`, `WL_`, `CINE_` …) are counted separately where it matters. CONFIRMED unless marked.

## 1. Campaign levels in the Game Dump

| chapter | packages | map packages (World) | on disk MB | uncompressed MB | ExtractedAssets/maps actor JSON | streaming sublevels | checkpoints | lightmap textures | nav: NavigationCell / TnReachSpec |
|---|---|---|---|---|---|---|---|---|---|
| A1_IAC | 138 | 50 | 360 | 896 | 50 / 50 | 50 | 26 | 2,154 | 3,415 / 24,448 |
| A2_KON | 151 | 55 | 279 | 715 | 55 / 55 | 55 | 34 | 2,178 | 2,287 / 12,131 |
| A3_COR | 139 | 48 | 271 | 650 | 48 / 48 | 48 | 25 | 2,337 | 1,502 / 9,321 |
| A4_ORB | 123 | 46 | 286 | 686 | 46 / 46 | 46 | 23 | 1,980 | 1,202 / 39,216 |
| A5_TRY | 33 | 14 | 91 | 211 | 14 / 14 | 14 | 4 | 321 | 333 / 1,199 |
| D1_ORB | 153 | 55 | 350 | 880 | 55 / 55 | 55 | 21 | 2,634 | 2,697 / 16,462 |
| D2_COR | 125 | 43 | 255 | 631 | 43 / 43 | 43 | 22 | 2,670 | 1,050 / 29,323 |
| D3A_IAC | 138 | 47 | 288 | 696 | 47 / 47 | 47 | 28 | 1,047 | 3,021 / 18,051 |
| D3B_IAC | 151 | 54 | 237 | 561 | 54 / 54 | 54 | 26 | 810 | 2,245 / 16,452 |
| D5_OME | 16 | 9 | 64 | 155 | 9 / 9 | 8 | 2 | 144 | 123 / 8,581 |
| **total** | **1,167** | **421** | **2,481** | **6,081** | 421 / 421 | 420 | 211 | 16,275 | 17,875 / 175,184 |

- Each chapter has one persistent `*_Base_m` package that streams the other map packages through `LevelStreamingKismet` (for example,
  `A1_IAC_Base_m` streams `A1_IAC_SideAlley_Art_m`). The packages are suffixed `_Art_m`, `_Design/DSN_m`, `_VIG_m`, `_CINE_m` and
  `_Audio_m`, plus `_LM` lightmap and `_LOC_FRA/_int` localisation companions.
- There is no `D4_` package, but `Movies/FMV_d4text_*.bik` exists. D3A/D3B are probably Decepticon chapters 3 and 4 (PROVISIONAL).
- **Map pipeline status: none of the 10 chapters has been through it.** By "map pipeline" I mean the outputs `run_map_pipeline.py`
  produces for MP maps: per-map glTF placement, `materials_glsl`, `lighting.json`, nav, collision and `render_index`.
  `manifests/maps/` and `ExtractedAssets/VerticalSlice/Maps/` hold only the 10 MP maps and the UI levels.
- What does exist for every campaign map package is the actor-summary JSON `ExtractedAssets/maps/<pkg>.json` (actor classes and
  streaming list), plus the individual meshes, textures and audio (section 2).
- `run_map_pipeline.py` is built around MP `_BASE/_ART/_AUDIO` triples. It has never been tried on a chapter with 14–55 streamed
  sublevels.

## 2. Asset classes: campaign vs MP (unique object paths)

| class | total unique | in an MP map package | campaign packages only | also in standalone packages | extracted (campaign-used) |
|---|---|---|---|---|---|
| StaticMesh | 2,440 | 934 | 1,468 | 19 | 2,334 / 2,334 |
| SkeletalMesh | 402 | 197 | 199 | 5 | 358 / 358 |
| AnimSet / AnimSequence | 634 / 3,921 | 179 / 2,090 | 449 / 1,804 | 5 / 26 | AnimSet 598 / 599 |
| PhysicsAsset | 190 | 88 | 98 | 1 | – |
| Material / MaterialInstanceConstant | 655 / 2,615 | 310 / 1,319 | 258 / 1,258 | 43 / 20 | `.mat` files: 0 / 570, 1,380 / 2,287 (see 4) |
| ParticleSystem | 544 | 216 | 281 | 35 | not exported as files (MP FX go through Systems) |
| SoundCue / SoundNodeWaveEx | 8,797 / 18,224 | 2,614 / – | 6,008 / – | 136 / – | waves 8,097 / 8,097 |
| FaceFXAsset | 23 | 19 | 3 | – | 22 / 22 |
| Prefab | 123 | 16 | 106 | – | – |
| World (map packages) | 459 | 31 | 421 | – | actor JSON 421 / 421 |
| Kismet `Sequence` / matinee `InterpData` | 3,443 / 3,658 | 241 / 25 | 3,185 / 3,601 | – | not exported |

Other campaign-only content:

- **Characters:** 236 `TR_` packages hold 57 named characters (ROBO/VEH textures, ROBODEF/VEHDEF definitions).
  - None is referenced by an MP map package. MP soldiers come from the customisation packages.
  - 25 are referenced by campaign map packages: Optimus, Megatron, Bumblebee, Ironhide, Ratchet, Starscream, Soundwave, Omega Supreme, Jetfire, Warpath, Barricade, Brawl, Breakdown, Skywarp, Thunder, Laserbeak, Sideswipe, Silverbolt, Air Raid, the brute and the soldier variants.
  - 32 have no map-package reference, so they are presumably loaded at runtime from AI character definitions (PROVISIONAL): Zeta Prime, Trypticon, Shockwave, Starscream boss, Arcee, Jazz, Slipstream, Onslaught, Demolishor, Rumble/Frenzy, the CQC/Corruptor/Spider/Security drone enemies, and others.
- **Weapons:** 103 `WEP_` packages are shared with MP; the 85 WEP_/PROP_ skeletal glTFs are already in the wfc_material overlay.
- **Cinematics:** 45 `CINE_` packages (26 `*_CINE_m` map packages) and 3,601 campaign-only `InterpData`. There are also 54 Bink FMVs
  (chapter intros/outros, text cards, credits); all 54 are already converted to `ExtractedAssets/movies/*.mkv` with subtitle JSON.
- **Voice:** 106 `WL_DX` dialog packages with 8,740 dialog waves, all extracted (`audio_native.jsonl`). Only 22 campaign FaceFX
  assets exist, so most dialog has no lip-sync data.
- **UI:** the campaign lobby (`UI_CampaignLobby`) is already in `ExtractedAssets/VerticalSlice/Maps`. Its textures are UI-group
  textures (section 3).

## 3. HD texture coverage of campaign textures

The full-pass selection was **not** MP-only: `hd_full.py` selected every extracted texture that is decodable and not UI, lightmap,
skybox or editor thumbnail. So the D pack already covers most campaign textures.

Of the 3,429 unique Texture2D objects exported by campaign packages:

| status | count | by max side |
|---|---|---|
| in the frozen D pack | **2,490** | 128: 415 · 256: 246 · 512: 1,263 · 1024: 529 · 2048+: 37 |
| kept original by eye (glow / FX / sky / logo) | 202 | 128: 41 · 256: 45 · 512: 62 · 1024: 42 · 2048+: 12 |
| KEEP verdict (no visible gain) | 90 | ≤64: 4 · 128: 2 · 256: 2 · 512: 49 · 1024: 32 · 2048+: 1 |
| ≤ 64 px (kept) | 27 | ≤64: 27 |
| excluded by design: UI group | 346 | mostly 128–256 |
| excluded by design: editor `ThumbnailTexture` (never drawn) | 269 | 128 |
| excluded by design: skybox | 2 | – |
| not decodable by the pass (PF_A8R8G8B8 colour) | 1 | 256 |
| not extracted | 2 | `ENV_IAC_Interior_1_p.Materials.Interior_Spacers_BUMP`, `FX_Textures_p.Textures.Drop_CLR` |

- The 265 textures that appear *only* in campaign packages are all editor thumbnails.
- **New D work the campaign needs: about 3 textures** (the 2 unextracted plus the A8R8G8B8 one), unless the user wants UI textures in
  HD; those 346 would be a separate decision.
- The open D-side work is per-level: lightmaps (16,275 `LightMapTexture2D` in campaign packages) are excluded from HD like the MP ones.

## 4. Known blockers (numbers only; no attempt made)

1. **Kismet:** 127,556 Kismet objects in campaign packages, across 177 classes.
   - Most common: SeqVar_Object 40,646, RemoteEvent 10,314 / ActivateRemoteEvent 10,204, SeqAct_Interp 3,644, Toggle 3,127,
     Touch 3,116, TnSeqVar_Character 2,863.
   - 40 of the classes are High Moon custom (`Tn`/`Hm`). The RE decomp has a file for 29 of those, so 11 have none.
   - Stock UE3 classes without a decomp file (Gate, Switch, SetStreamingState, FlushLevelStreaming, ToggleCinematicMode, …) have known
     engine semantics but still need a runtime.
   - Campaign progression runs entirely through these: checkpoints (211), streaming (420 sublevels) and remote events.
2. **Matinee cinematics:** 3,601 campaign-only InterpData (3,644 SeqAct_Interp). They drive in-engine cutscenes, camera moves and
   level events, and nothing in our pipeline plays matinee yet.
3. **Materials:** 570 parent Materials and 907 MaterialInstanceConstants used by the campaign have no exported `.mat` file. Whether
   Rendering's matc compiles straight from the authored DB (as for MP) or needs the files is UNKNOWN; to confirm with Rendering.
   ParticleSystems: 316 used by the campaign beyond MP.
4. **Voice / lip-sync:** dialog audio is complete (8,740 waves), but 22 FaceFX assets cover only a fraction of the lines. The trigger
   path (Kismet `PlaySound` / Tn dialog actions) is part of item 1.
5. **Characters:** 32 of the 57 characters are spawned without a map-package reference. Bosses and AI definitions (`TR_AiCharacterDefinition_p`)
   need the AI and character-definition runtime, which is not part of the MP slice.
6. **Map pipeline scale:** 421 map packages, 6.1 GB uncompressed, against 10 MP maps of about 120 MB each. `run_map_pipeline.py`
   expects one BASE/ART/AUDIO set and has a 6 GB job cap per stage. Chapters need a streaming-aware variant: one chapter, bounded, as a
   pilot first.

## ETA

This inventory: done (this file). A campaign map-pipeline pilot on one chapter (D5_OME is the smallest: 9 map packages, 155 MB) is
not started and needs an Integration go-ahead. Estimate: about a day of CPU work for the streaming-aware variant, PROVISIONAL.
