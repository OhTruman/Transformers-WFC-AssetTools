# MP_IAC_Streets native-map fidelity follow-up (after geometry fix 8d8195e), 2026-10-03

Sources:
* AssetTools cooked-data analysis (this lane).
* RE notes, read-only: `RE-Workspace/notes/MILESTONE04_STREETS_NATIVE_SCENE.md`, `MILESTONE04_STREETS_RUNTIME_SEMANTICS.md`,
  `MILESTONE03_RENDERING_LIGHTVIS_SHADOW.md`.

Lane boundary: AssetTools does not write to RE-Workspace, so this report lives here.

## 1. Default-material BSP faces (`manifests/streets_bsp_default_faces.json`)
* **Recovered.**
  * 62 BSP surfaces (87 polygon nodes, 202 triangles, 46 subtractive brushes) reference `EngineMaterials.DefaultMaterial`.
  * The reference appears in both the FBspSurf and the cooked FModelElement of the rendering ModelComponents.
  * The source brush Models are cooked as 124-byte stubs without Polys.
  * **Shipped WFC renders these faces with the engine default material wherever they are visible. This is not a lost
    assignment.** CONFIRMED.
* **Occlusion, first pass:** rays along the face normal against the corrected placed meshes, up to 0.64 m.
  * Most faces are not covered by a mesh. Several are very large (up to 8,228 m²); many face down or outward.
* **Play visibility (rerun 2026-10-03, memory-bounded, peak 0.54 GB):**
  * **Method.**
    * Viewpoints: 182 = 123 nav nodes + player starts, at +200 UU eye height.
    * A face counts as seen if any viewpoint on its front side, within 200 m, has an unobstructed line to a face sample.
    * Occluders: the corrected placed meshes plus all other rendered BSP.
    * Not occluders: the sky dome and the 126 unlit light planes / beams.
    * Grid: triangles spanning more than 64 cells are tested on every ray.
  * **84 of 87 default-material nodes are never visible from any viewpoint.** HIGH; this is a lower bound because players
    also jump and drive.
  * **3 nodes are partly visible:**

    | node | brush | area | normal | seen from |
    |---|---|---|---|---|
    | 572 | `BRUSH_9457` | 33 m² | wall, +Y | 23 m away, at (35842, −38592, −70848) |
    | 498 | `BRUSH_11694` | 10 m² | ceiling, −Z | 22 m away, at (13504, −35712, −69120) |
    | 265 | `BRUSH_2106` | 2,831 m² | floor, +Z | only at a grazing angle (eye 2.8 m above the plane, 110 m away), centre (17006, −64183, −71680) |

    * Samples covered by meshes: 1 of 8 (node 265), 2 of 5 (nodes 572 and 498).
  * Shipped WFC draws these visible parts with `EngineMaterials.DefaultMaterial` too, so they are not a rebuild defect.
  * Rendering should match this, not substitute a material.
  * They are the right spots for Experimental to compare against original footage.
* **Handoffs:**
  * Rendering: draw them with DefaultMaterial, not a guessed material.

## 2. StaticMeshCollectionActor per-component state beyond the transform
Census of all 1,906 SMCA components. Archetype: `Engine.Default__StaticMeshActor.StaticMeshComponent0`.
* **No authored visibility or draw rules:** no component authors `HiddenGame`, `CullDistance`, a min/max draw distance or a
  forced LOD. CONFIRMED.
* **LOD:** every one of the 1,952 placed meshes is cooked with a single LOD (one consistent FStaticMeshElement run), so there
  is no LOD switching. HIGH.
* **Visible-state flags already exported in `props_authored.json`:**

  | flag | components |
  |---|---|
  | `bAcceptsLights`=false + empty LightingChannels (unlit/emissive light planes, beams) | 126 |
  | `CastShadow`=false | 146 |
  | `bAcceptsDecals`=false (decals must not project on them) | 98 |
  | material overrides | 566 |
  | collision fully off | 252 |
  | lightmap resolution override | 124 |
* **Mirroring:** 478 instances with det < 0 need front-face reversal; the glTF rule covers it. There is no other
  mirroring-related state.
* **Rendering check:** decal receivers honour `bAcceptsDecals`, and the 126 unlit components get no light.

## 3. Moving world actors
* **Domes:** `StaticInterpActor_15810 / 7381 / 8114`, PHYS_Rotating, RotationRate yaw 2730 (= 15.0°/s) from map start.
  CONFIRMED (authored; RE stock physics).
* **SkyBeam:** `SeqAct_Interp_3464`, looping, 9.0022 s.
  * Driven actors: `StaticInterpActor_5249` (dome half), `_13497` and `_10471` (LightBeam cones).
  * InterpTrackMove, IMF_RelativeToInitial, quaternion interpolation, CIM_CurveAuto.
  * Euler keys: 0 s (0, 0, 0) → 4.5 s (19.40°, 3.78°, −10.60°) → 9.0 s (0, 0, 0).
  * Translation ≤ 0.008 UU (negligible).
  * Started by SeqEvent_GameplayStarted → RemoteEvent "StartBeam". CONFIRMED.
* **Static:** `StaticInterpActor_12825` and `_8037` have no track. CONFIRMED.
* **Domination totems:** AnimSet `NEU_EnergonTotem_ANM` with `EnergonTotem_StandBy`, `_DeActivate`,
  `EnergonTotemAUT_Activate`, `EnergonTotemDEC_Activate`.
  * Visible only in DOM; hidden elsewhere, with the idle animation still started. Per RE script decompilation.
* **KOTH zones:** the active-zone visual is the template component `ActiveMeshComponent0` = `FX_Mesh_p.Mesh.pTorus1_STAT`
  (glTF extracted).
  * The level cooks no instance of it; it is created from the class template at spawn.
  * Shown only for the active zone in KOTH.
  * The ring is placed with the zone transform, including DrawScale3D (1, 1, 2), so it stands twice as tall. Material
    `FX_Materials_p.MatInst.CaptureZone_Reverse_MAT_INST`.
* **Collision:** hidden InterpActors still collide (stock UE3).
* **In `render_index.json` (2026-10-03):**
  * the 3 totems and 5 KOTH rings are listed under `not_in_world_glb (authored renderables)`, with glTF paths, UE + glTF
    matrices and visible modes;
  * domes and SkyBeam actors are under `authored_render_state`;
  * motion data is in `manifests/streets_movers.json`.

## 4. LightsVisibilitiesVolume: purpose now known (RE)
* A baked light-visibility octree queried only by light-environment updates at the owner's bounds origin: pawns, vehicles,
  pickups, totems.
* It has no effect on culling, BSP, static meshes, particles or static lighting.
* Outside the volume, baked lights get visibility 0 for dynamic objects.
* Visible impact: character, vehicle and pickup lighting and shadow fading only. It does not change world geometry.
* AssetTools' earlier "semantics UNKNOWN" is superseded.

## 5. Mode-dependent visual state for the slice mode (TDM / DM)
Per RE runtime semantics plus authored Kismet:

| actor | TDM / DM state |
|---|---|
| 4 objective-base InterpActors | **hidden** (still collide) |
| 3 domination totems | **hidden** |
| 5 KOTH zones | **hidden** |
| 2 flag factories + 1 bomb factory | **Disabled** (hidden + no collision) |
| capture / plant points | inert |
| ammo / health / overshield factories | active |

**In `render_index.json` (2026-10-03):**
* `mode_visual_state`: per-class visibility for DM/TDM/CTF/EXT/DOM/KOTH, with mechanism, collision and actor lists.
* `tdm_render_state`: the 19 actors to hide in the slice (4 bases, 3 totems, 5 KOTH zones, 2 flag + 1 bomb factories, 4
  capture/plant points).
* `pickup_factory_visuals`: 14 ammo crate meshes (placement PROVISIONAL), 10 health/overshield particle meshes (approximate
  matrices), flag/bomb resting visual UNKNOWN.
* `pickup_fx_components`: all 37 pickup effects with draw rules.
  * The `Pickup_FX` beam is switched on whenever its factory is available (`SetPickupVisible` → `ActivateSystem`, RE script).
  * The 10 health/overshield copies are never attached.
  * 24 effects are drawn in TDM.
* The destructible wall panel (outside the play space) is listed with all 3 states. State meshes are CONFIRMED; spawned
  chunk/debris placement is PROVISIONAL.

Rendering and Gameplay should consume these sections rather than re-deriving the table.

## 6. Map-wide visibility, culling and streaming
* No CullDistanceVolume, occlusion, portal or precomputed-visibility actor exists in Streets.
* No BSP portal flag is set.
* No Kismet streaming exists; the default LevelStreamingState makes ART and AUDIO visible.
* No component is HiddenGame.
* Apart from the mode-gated actors in §5, everything extracted is visible in normal play. CONFIRMED (authored).
