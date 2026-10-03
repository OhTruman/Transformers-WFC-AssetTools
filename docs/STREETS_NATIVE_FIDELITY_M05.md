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
* **Play visibility (any player viewpoint): UNKNOWN.**
  * The nav-viewpoint ray test was stopped by Claude Code under low system memory: the uniform grid indexed the 14 km sky
    dome / 700 m light planes.
  * Rerun only on request, with oversized triangles tested directly.
* **Handoffs:**
  * Rendering: draw them with DefaultMaterial, not a guessed material.
  * AssetTools: finish the play-visibility pass.

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
* **Collision:** hidden InterpActors still collide (stock UE3).

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

`render_index.json` lists the mode-gated actors. Rendering and Gameplay must apply the table.

## 6. Map-wide visibility, culling and streaming
* No CullDistanceVolume, occlusion, portal or precomputed-visibility actor exists in Streets.
* No BSP portal flag is set.
* No Kismet streaming exists; the default LevelStreamingState makes ART and AUDIO visible.
* No component is HiddenGame.
* Apart from the mode-gated actors in §5, everything extracted is visible in normal play. CONFIRMED (authored).
