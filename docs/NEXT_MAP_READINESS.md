# Second MP map after Streets: readiness and generalization probe (2026-10-03)

**Recommendation: `MP_UND_Gorge` ("Gorge", MapId 510).**

The existing Streets pipeline already runs end to end on it: 14 stages, all rc 0, with the transform validator and `vs_validate`
both passing. The recommendation rests on the measured criteria below, not on preference.

**Machine-readable outputs:**
* `manifests/next_map/readiness.json`: per-map criteria (`scripts/wfc/next_map_readiness.py`).
* `manifests/next_map/MP_UND_Gorge_probe.json`: stage runs, peak memory and outputs (`next_map_probe_summary.py`).
* `manifests/next_map/MP_UND_Gorge_validation.json` and `MP_UND_Gorge_transform_validation.json`: validator reports.
* `manifests/mp_next_map_readiness.json`: the earlier weighted ranking (`fe_map_catalog.py`).

## Criteria (all 9 other cooked MP maps measured; counts include BASE plus every streamed level)

**Extraction coverage is not a differentiator.** Every map's cooked dependencies are already extracted: StaticMesh glTF 100%,
Texture2D PNG 99.3–99.5%, SoundNodeWaveEx WAV 100%, and the level's own objects are about 99.9% present in authored.db.

| map | sublevels | geometry (SM MB / BSP MB / SMCA) | lightmaps | new materials | collision vols | movers | destructibles | new particles / cues | special native behaviour vs Streets |
|---|---|---|---|---|---|---|---|---|---|
| Streets (ref) | ART, AUDIO | 11.7 / 0.85 / 1906 | LightMapTexture2D ×81 | — | 71 BlockingVolume | 4 InterpActor + 8 StaticInterpActor | 1 | — | — |
| **Gorge** | ART, AUDIO | 6.5 / 1.0 / 1752 | LightMapTexture2D ×39 (same format) | 25 | 80 BlockingVolume + 28 TnTransformerBlockingVolume | 13 InterpActor (4 hidden objective bases + 9 PHYS_Rotating vent fans), 0 Matinee | 0 | 2 / 32 | TnRadialForceVolume ×9, LensFlareSource ×1, SkeletalMeshActor ×1, PhysicsVolume, PostProcessVolume |
| Berth | ART, AUDIO, **GLB_Audio_m** | 7.1 / 0.86 / 1457 | same | 14 | 55 | 4 | **9** | 3 / 29 | fog volume, 12 placed light actors, SkeletalMeshActor ×4, TnRadialForceVolume ×6, 4 new Kismet classes |
| Molten | ART, AUDIO | 7.7 / 3.2 / 2155 | same | 24 | 156 | 4 | 0 | 2 / 36 | **HmRoomVolume ×9 / HmRoomPortal ×33** (native visibility system) |
| Complex | ART, AUDIO | 7.2 / 1.8 / 1902 | same | 17 | 101 | 7 | 0 | 5 / 41 | **HmRoomVolume ×14 / HmRoomPortal ×34** |
| Rust | ART, AUDIO, GLB_Audio_m | 11.9 / 0.95 / 2205 | **+ HmInterpolatedLightMappedSkeletalMeshComponent** | 35 | 133 | 8 | 0 | 2 / 57 | TnTransformingWorldActor, fog volumes, lens flare |
| Seed | 4 (+ MP_IAC_Global_Art_m, GLB_Audio_m) | larger | same | 35 | — | 16 | 6 | 11 / — | 15 new classes, Kismet ×8 Streets |
| Orbital Debris | ART, AUDIO | similar | same | 27 | — | 18 | 12 | 14 / — | 15 Matinee sequences, 19 new classes |
| Broken Hope / Remnant | ART, AUDIO | larger | + light-mapped skeletal meshes | 42 / 70 | — | 2 / 50 | ~100 | 45 / 32 | Escalation-only (SV), AI waves, 28 / 44 new classes |

**Why Gorge:**
* **Same structure as Streets:** BASE + ART + AUDIO with `_LM` / `_LOC` companions, and no shared extra level.
* **Same lightmap format.**
* **Movers use only mechanisms the pipeline already handles:** hidden objective bases toggled by Kismet, and constant
  `PHYS_Rotating` like the Streets domes.
* **No destructibles and no Matinee.**
* **The fewest special classes.** The new collision class is a blocking-volume subclass the pipeline already includes.

**Berth is the alternative.** It needs the destructible pipeline (proven on one Streets panel) for 9 barricades, plus fog
volumes and the extra `GLB_Audio_m` level.

**Molten and Complex** depend on the native HmRoom/Portal visibility system, which RE has not characterised.

## Generalization probe on Gorge (done; low risk)
* **How it ran.** Every stage ran through `scripts/wfc/run_bounded.py`: a Windows Job Object with a hard **6 GB** cap, where
  allocations beyond the cap fail inside the child. Peak was **4.52 GB** (`vs_map`); every other stage stayed at or below
  3.2 GB.
* **Where outputs went.** `ExtractedAssets/VerticalSlice/Maps/MP_UND_Gorge/` (57 files, including `world.glb`, collision
  glbs, 36 lightmap PNGs).

| stage | result |
|---|---|
| `vs_map` | ART BSP 657 nodes / 1,824 triangles, 0 skipped polys, 0 validation issues; 1,765 props from 166 unique meshes, **0 missing meshes**; unexported actor classes vs Streets: LensFlareSource ×1, SkeletalMeshActor ×1 |
| `vs_lighting` | 411 lights; cached vs native placement compared on 409, max error 0 |
| `vs_postprocess`, `vs_navigation` | OK (148 nav nodes, 738 reach specs) |
| `m04_lightmap_atlases` + `vs_lightmap` | 12 atlases exported (ART and `_LM`); 1,137 props lightmapped, 0 atlases without PNG |
| `vs_materials` | 136 materials, 0 missing, 31 masters |
| `vs_props`, `vs_collision`, `vs_physics` | OK; TnTransformerBlockingVolume blocks pawns (28), TnRadialForceVolume non-blocking (9) |
| `vs_gameplay` | 97 team starts (51 / 46) + 18 FFA, all clustered; 14 objective volumes with geometry |
| `vs_audio` | 15 emitters, 23 zones, 6 reverb presets, 37 / 37 WAVs |
| `validate_smca_transforms --map MP_UND_Gorge` | **1,752 / 1,752 exact** (390 mirrored), 1,137 lightmapped world nodes, collision glbs carry corrected matrices |
| `vs_validate MP_UND_Gorge` | **44 / 44** |

**Generalization gaps found and fixed:**
1. `vs_lighting`, `vs_postprocess` and `m04_lightmap_atlases` assumed their output folder existed; they now call `makedirs`.
2. `validate_smca_transforms.py` was Streets-only. It now takes `--map`, writes non-Streets reports to `manifests/next_map/`,
   and skips the Streets-only RE scale table instead of failing.
3. `vs_validate.py` was Streets-only. It now takes the map as an argument; non-Streets reports go to `manifests/next_map/`,
   leaving the slice manifests untouched.

The Streets regression after these edits: `vs_validate` 44/44, `validate_m04` 15,918/0, frontend validators 0 failures.

**Not yet generalized (needed before Gorge gets a render index):**
* These scripts hard-code `MAP = 'MP_IAC_Streets'`: `m04_inventory.py`, `m04_kismet.py`, `m04_complete.py`
  (`render_index.json`), `vs_destructibles.py`, `vs_pickups.py`, `vs_surface_audio.py`.
* These Gorge features need RE semantics before faithful rendering or gameplay; the authored data is all present:
  * TnRadialForceVolume: pushes planes, tanks and cars along `ArrowDirection`, with per-instance `ForceStrength` (1500 on the
    sampled volume); IsAffected / HardBlock / Touch logic in `TransGame.TnRadialForceVolume` script;
  * the lens flare (`LensFlareSource`);
  * one `SkeletalMeshActor`.

## Confidence
* **CONFIRMED:** counts and set differences from cooked data; probe results (stage logs and validator reports).
* **HIGH:** the comparative judgment.
* **UNKNOWN:** the runtime semantics of the Gorge-only classes (RE).
