# Campaign render-data gaps: AssetTools deliverables (2026-10-23)

**For:** Rendering (Integration rebuild-84 approved a–e).

**Source:** findings 1–6 of `CAMPAIGN_RENDER_DRYRUN.md`. Every run was CPU-only, one at a time under run_bounded (6 GB).
Nothing in `Rebuild/tools/render` was touched (`git status` is clean).

| gap | deliverable | size | status |
|---|---|---|---|
| #1 inline light maps | `work/campaign_render_dryrun/inline_lightmaps.json` (`inline_lightmaps.py`) | 269 KB | DONE (see below) |
| #2 props_authored path | hunk in `proposed_render_patch.diff` | — | proposed, not applied |
| #3 height fog | `work/handoff/CAMPAIGN_RENDER_GAP3_HEIGHT_FOG.md` | — | cause CONFIRMED; fix proposed |
| #4 campaign material lists | `manifests/campaign/render_materials/<CH>.{json,txt}` (`campaign_materials.py`) | 636 KB | DONE (see below) |
| #5 per-sublevel inputs | `work/campaign_pilot/VerticalSlice/Maps/<CH>/sublevels/<level>/{world.glb, map_fx.json, render_index.json}` + `sublevels/index.json` (`split_sublevels.py`, `verify_split.py`) | 996 MB | DONE, all PASS (see below) |
| #6 VS root | `work/campaign_render_dryrun/proposed_render_patch.diff` | — | proposed, not applied (see below) |

## #1 Inline light maps

- 8,118 inline LightMapTexture2D objects across 10 chapters, listed per package.
- Each level package's umodel call gets only its own `-obj` names.
- Matches the dry run exactly: Intr1_Art 96, Strts0_Design 3, Base 0.

## #3 Height fog

- The campaign authors its fog as `PostProcessVolumeHeightFogComponent`, a subclass of HeightFogComponent: 169 in the campaign, and 1
  in MP_ESC_Remnant.
- `build_lighting` matches the exact class only, so it skips them.
- How the volume gates the fog is UNKNOWN (an RE question).
- MP impact: the fix adds 1 fog layer to Remnant, so gate it to campaign maps or record the change.

## #4 Campaign material lists

- One list per chapter of the materials beyond world.glb (2–454 per chapter), split into:
  - skeletal-mesh slots (extracted glTF names, the scene_materials rule);
  - energy-death (Defrag) instances;
  - runtime-assigned, by referrer class. The largest group is ParticleModuleRequired; the others include TnWeaponMesh, TnTransformer,
    DecalComponent, LensFlare, MaterialInstanceActor and SeqAct_SetMaterial.
- ObjectReferencer-only materials are in the build list (cooked keep-alives, likely spawned at run time); parent-only (compiled through
  their children) and unreferenced materials are recorded in the .json but not listed.
- `.txt` is the build list, one path per line. Chapter membership comes from inventory.db, because authored.db keeps one row per object
  path.

## #5 Per-sublevel inputs

- Approved at about 1.06 GB; actual 996 MB, peak 1.1 GB per chapter.
- 392 sublevel folders across the 10 chapters.
- Records reach a sublevel by their package prefix (component / source / actor path, or props.json (actor, mesh, matrix) for nodes
  without one).
- Checks:
  - Every node, particle component, decal and split render-index record is accounted for, with 0 unassigned in all 10 chapters.
  - `verify_split.py`: every split node's positions, indices and material names are byte-identical to the chapter world.glb, and every
    image URI resolves. PASS on all 10.
- Split files keep the chapter keys and add sibling keys `sublevel` / `split_from`.

## #2 / #6 Proposed patch

- A hunk for #2, plus `WFC_VS_ROOT` for build_lighting / build_map_fx / build_movers / build_render_index / build_materials / ue3obj.
- When unset, the default is the old literal, byte for byte, so MP is unchanged.
- `git apply --check` passes against deed7f1a.
- Not covered by the patch: the M72 fallback filter and energy_death iterate `MP_*` only. Use the #4 lists for those.
