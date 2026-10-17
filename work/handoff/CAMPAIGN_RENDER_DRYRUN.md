# Campaign render-data dry run: A1 base + 2 largest sublevels (AssetTools, 2026-10-18)

**Purpose:** size the campaign render-data step, as the matc dry run sized the materials.

**Scope:** Rendering's per-map pipeline (`Rebuild/tools/render/build_render_data.ps1` and its Python steps) on `A1_IAC_Base_m` + its two
largest streaming sublevels: `A1_IAC_Intr1_Art_m` (40 MB of exports) and `A1_IAC_Strts0_Design_m` (29 MB).

**How it ran:**
- The ps1 hard-codes `Rebuild/work/render/<map>` and the shared `umodel_out`, so it was **not** run.
- `work/campaign_render_dryrun/driver.py <step>` replays every ps1 step in order, one bounded process each (`run_bounded`, 6 GB cap).
  It imports Rendering's scripts read-only, with no bytecode.
- Outputs went to `work/campaign_render_dryrun/{render/A1_IAC, umodel_out}`. `git status` of Rebuild `tools/render` and `work/render`
  is clean afterwards.
- **Patched, per module:**
  - `VS_MAPS` / `VS` → the campaign VerticalSlice (`AssetTools/work/campaign_pilot/VerticalSlice`), because A1 isn't in ExtractedAssets;
  - `map_packages` / `map_lm_packages` → the 3 packages.
- Nothing else was patched, so other MP-layout assumptions show up below.
- Per-step results: `work/campaign_render_dryrun/steps/*.json` and `*.log`.

## Per step

| step (ps1 order) | result | wall | peak RAM | output |
|---|---|---|---|---|
| 1a umodel `_LM` atlases | OK for the 2 sublevel `_LM`s (87 PNG); `A1_IAC_Base_m_LM` has **0 exports**, so umodel exits 1 (benign) | 0.3 s | — | 8.5 MB umodel_out |
| 1b umodel inline light maps | **FAILS as written**: see finding 1. 99 inline LightMapTexture2D exported with the per-package workaround | 1.2 s | 1.0 GB | (in umodel_out) |
| 2 build_lighting | runs. 2,274 light-map records (Intr1 2,161, Strts0 113), 99 atlases, 39 vertex-lit components, 207 lights. **component_flags empty** (finding 2), **fogs empty** (finding 3) | 6.5 s | 2.8 GB | lighting.json 2.4 MB, bsp.glb 48 KB, decals.glb 1.4 MB, lvv_0.bin 2.3 MB, 99 light-map PNG |
| 3 build_materials (+ the 480 extra list entries: 112 MP character, 54 weapon, 141 FX library, 58 defrag, 54 ability, fx / ui lists) | runs. **938 / 941 compile**; the 3 errors are the known DecalMaterial roots. **Only 452 of the 604 materials of these 3 levels are attempted** (finding 4) | **1,683 s (28 min)** | **4.13 GB** | materials_glsl.json 6.0 MB, tex/ 72 |
| build_fog_volumes | runs; 0 volumes (correct: A1's 2 FogVolumes are in A1_IAC_Armory_m) | 0.8 s | 0.3 GB | 39 B |
| beast_probes | runs; 12 volumes | 0.4 s | — | 2.6 MB |
| 4 build_movers | runs | 0.5 s | 0.1 GB | 200 KB |
| build_map_fx | runs; 268 systems, 1,265 instances, 40 destructible mesh components, for the **whole chapter** (finding 5) | 67 s | 1.0 GB | 31 MB |
| build_render_index | "ships a runtime render_index.json (used as is)": the campaign VerticalSlice's file for the whole chapter; nothing written | 0.1 s | — | — |
| build_scene_floatprops | runs | 1.2 s | 0.3 GB | 3 KB |
| 5 build_hud / build_anim_choosers | run (map-independent) | 1.3 / 0.4 s | 0.3 GB | `_ui` |

**Total:** about 29.5 min wall, 28 of it in build_materials; 53 MB of render data + 8.5 MB umodel export. MP Gorge's render dir is 94 MB,
for scale.

## Findings (what breaks or silently degrades on campaign)

1. **Inline light-map export fails on multi-sublevel maps.**
   - The ps1 passes all inline LightMapTexture2D names (`build_lighting --list-inline`) as `-obj=` to every level package, and umodel
     aborts at the first object not in that package (rc 1, nothing exported).
   - MP maps get away with it because their inline light maps sit in one package. A1: 96 in Intr1_Art, 3 in Strts0_Design, so all 3
     calls fail.
   - Fix: per-package `-obj` lists, as `driver.py inline_umodel` does.
2. **Component render flags are silently dropped.**
   - `build_lighting.py` line 102 hard-codes `ExtractedAssets/VerticalSlice/Maps/<map>/props_authored.json` (not `VS_MAPS`). The campaign
     file lives elsewhere, so the read returns `{}`.
   - So `component_flags` (hidden / no-light / no-shadow / dynamic-shadow) is empty for A1. MP Gorge carries hundreds of these entries.
   - Fix: read it through VS_MAPS.
3. **Height fog not picked up.** `lighting.json` `fogs` is `[]`, but Intr1_Art_m has 3 `PostProcessVolumeHeightFog`. Cause UNKNOWN
   (not traced); for Rendering.
4. **Map materials come from world.glb only.** The 152 materials of these levels that aren't compiled are none of them in world.glb:
   - 67 parent MICs (compiled through their children, so harmless);
   - 54 referenced only by ObjectReferencers;
   - 27 unreferenced;
   - runtime-assigned ones: TnTransformer / form blueprints / skeletal components 23, TnWeaponMesh 14, StaticMeshComponents outside world.glb
     14, particle 5, SeqAct_SetMaterial 2, MaterialInstanceActor 2, TnHealingAura 2.

   Campaign-only characters and props need their own material lists:
   - `character_materials.py` reads the MP roster (`mp_characters.json`);
   - `energy_death_materials.py` lists `MP_*` maps only.
5. **The per-map model has no streaming sublevels.**
   - `world.glb`, `map_fx.json` and `render_index.json` are per chapter (all 51 sublevels), while `map_packages` gives the cooked
     packages.
   - With 3 packages the material step finds 486 world materials "missing from this map". Its M72 fallback then loads about 46 other
     packages (the other A1 sublevels, other chapters, 3 MP maps), which is where the 28 min and 4.1 GB go.
   - Two options: run per chapter with all 51 level packages (one big Repo; RAM likely at or above the 6 GB cap, PROVISIONAL estimate), or
     split the inputs per streaming sublevel. The second needs per-sublevel world.glb / map_fx / render_index, which AssetTools can
     produce: the campaign VS already tags nodes by sublevel.
6. **Loaders assume the MP layout:**
   - `VS_MAPS` / `VS` are hard-coded to ExtractedAssets in 6 scripts (build_lighting, build_materials, build_movers, build_map_fx,
     build_render_index, beast_probes via ue3obj);
   - `map_packages` falls back to `<map>_ART_m` / `<map>_BASE_m` when the map has no map.json there;
   - build_materials' M72 fallback filter and energy_death iterate `MP_*` only.
   - Campaign needs a VS root parameter (or env var, like build_render_index's `WFC_ASSETTOOLS_MANIFESTS`).
7. **What ran clean as-is:** light-map binding and atlases (given the inline fix), BSP / decals rebuild, light list, post-process, fog
   volumes, beast probes, movers, map FX, matinee float props, HUD and anim choosers. 938 / 941 of the attempted materials compile; the
   3 errors are the DecalMaterial roots, sized in the matc dry run.

## Sizing for the campaign phase

**Code changes in the pipeline:**
- per-package inline `-obj`;
- `props_authored` via VS_MAPS;
- a VS-root parameter;
- campaign character / energy-death / runtime-material lists;
- the height-fog read.

**A decision:** chapter-wide runs vs per-sublevel inputs. Per-sublevel needs AssetTools to split world.glb / map_fx / render_index.

**Materials are the cost:** about 28 min and 4 GB for 3 of A1's 51 levels, almost all of it in loading fallback packages. A chapter-wide
Repo should cut the fallback but needs the RAM. Translator gaps are as sized: 38, plus DecalMaterial roots.
