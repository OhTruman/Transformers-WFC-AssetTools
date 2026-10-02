# MP_IAC_Streets collision & physics setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/physics.json`**, plus two new collision worlds:
* **`collision_pawn.glb`**: what blocks pawn and vehicle movement (non-zero-extent traces).
* **`collision_weapon.glb`**: what blocks hitscan and line checks (zero-extent traces).

The existing `collision.glb` is unchanged (render geometry of every blocking prop, applied to both trace types).
Regenerate: `AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_physics.py` (after `vs_map`/`vs_collision`).
Handoff: **Gameplay** (movement and collision), **Systems** (weapons and impacts). Units: UE units unless stated; glB in glTF metres.

## Recommendation for Gameplay/Systems
Load `collision_pawn.glb` for movement and `collision_weapon.glb` for hitscan instead of `collision.glb`:
* **18× lighter:** 101k triangles vs 1.85M.
* **Same grounding:** all 84 player starts ground within 6 m, median drop 0.84 m, identical to `collision.glb`.
* **Authored shapes:** 1,667 props use their authored simple hulls, as UE3 does.
* **Per-trace correctness, two cases:**
  * `StaticMeshActor_11055` (`GroundVent_STAT`) blocks weapon traces but **not** the player; `collision.glb` blocks the player there.
  * 37 BlockingVolumes and the 4 forced-direction volumes block the player but **not** weapon fire.

## Collision representation (rules: stock UE3, HIGH CONFIDENCE; flags and geometry CONFIRMED)
* A placed component collides only if `CollideActors && BlockActors && Block{Zero,NonZero}Extent`.
* **Non-zero-extent (pawns):** if `UseSimpleBoxCollision` and the mesh's `RB_BodySetup.AggGeom` has geometry, use the simple hulls.
  Otherwise use per-poly collision over sections whose cooked `FStaticMeshElement.EnableCollision` is set.
* **Zero-extent (weapons):** the same, with `UseSimpleLineCollision`. Rigid bodies use `UseSimpleRigidBodyCollision`.
* No Streets mesh overrides the `UseSimple*` flags (StaticMesh defaults: all true), and no section disables collision.

| | simple | per-poly | none |
|---|---|---|---|
| props for pawns | 1667 | 25 | 260 |
| props for weapons | 1668 | 25 | 259 |
| props for rigid bodies | 1633 | 25 | 294 |

* **171 meshes, 147 with authored simple collision** (convex hulls with authored `FaceTriData` triangles, plus boxes, spheres and sphyls).
  The 10 meshes without it, which use per-poly: street lines, decal logo, blast ring, statues, AA-gun base, window screen, coolant hole.
* **Hull validation (140 meshes):** median bounding-box mismatch against the render mesh is 1.2% of the diagonal (p90 4.6%).
  The larger differences are partial collision inside the render mesh (dome, road bends). Only 5 hulls extend more than 5% past the
  render bounds (max 19%, a crater).
* Component flag mix: 1,658 props fully block; 259 are non-colliding (decorative); 34 block but not rigid bodies;
  1 (`GroundVent_STAT`) has `BlockNonZeroExtent = false`.

## Volumes
| class | count | blocks pawns | blocks weapons | notes |
|---|---|---|---|---|
| BlockingVolume | 34 | yes | yes | `BlockZeroExtent` authored true |
| BlockingVolume | 37 | yes | **no** | `BlockZeroExtent` unset (default false) |
| TnForcedDirVolume | 4 | yes (`bBlockPawns`) | no | **ExitSpeed 1500**, ArrowDirection (0,0,−1), RBChannel Untitled4: push-down volumes |
| TriggerVolume | 20 | no | no | 10 gameplay (BASE) + 10 audio zones (AUDIO) |
| BSP solid | 2,460 tris | yes | yes | level Model, non-PF_NotSolid surfaces |

## Physical materials (resolved through material → parent chains)
| PhysicalMaterial | uses (sections) | Friction | Restitution | other |
|---|---|---|---|---|
| `ENV_PHYSMAT_p.Metal_PHYSMAT` | 1957 | 0.5 | 0.1 | LinearDamping 0.01, AudioOcclusion −6 dB / 0.5 s |
| `ENV_PHYSMAT_p.ForceField_PHYSMAT` | 84 | **0.7** | **0.3** | |
| `Water_Coolant_PHYSMAT` / `Rubber_PHYSMAT` / `Water_PHYSMAT` | 6 / 3 / 2 | 0.5 | 0.1 | |

BSP surfaces: 120 Metal, 6 ForceField, 1 Rubber, 1 Water, and 38 materials with no PhysMaterial (engine default).
The `TnPhysicalMaterialProperty` sub-objects carry no authored values: impact FX and sounds key off the PhysicalMaterial identity
(native; UNKNOWN mapping).

## World physics (governing BASE TnWorldInfo; CONFIRMED)
* DefaultGravityZ **−2940** UU/s² and RBPhysicsGravityScaling **0.66**, so rigid bodies fall at −1940.
* PhysicsSceneTiming: fixed time step **1/60 s**, MaxSubSteps **5**; MaxPhysicsDeltaTime 1/3 s.
* **KillZ −75000** (BASE override; ART/AUDIO keep the stock −262143); StallZ 1e6.

## Movers and destructibles
* 4 `InterpActor` (PHYS_Interpolating, bStopOnEncroach): objective bases `Base_A`/`Base_D` and two `RepairNodeB` props.
  All are **non-colliding**, driven by BASE Kismet.
* 1 `TnStaticDestructibleActor` (bCanBeDamaged) with `HmDestructibleComponent`: blueprint
  `DES_IAC_WallPanelSignDSYS_p.WallPanelSign` (version 203), 1 piece.

## Slice characters
* **Optimus robot:** pawn cylinder radius 200 / height 200.
  * PhysicsAsset `RB_Optimus_A_PHYSSYS` (ragdoll): **19 bodies, 18 constraints**. Shapes, bones and limits are in json.
  * PhysMaterial `RB_Optimus_PHYSMAT`: **Friction 5.0**, Restitution 0.2, AngularDamping 5.0.
* **Optimus truck:** PhysicsAsset `VH_Optimus_PHYSSYS` with 1 body on `C_Reference_XR`: a 28-vertex convex hull (box ≈ −310..338 × ±154 × −35..185)
  plus a box 326×452×248 centred at (452, 0, 91), at the front of the truck (likely the ram).
  * PhysMaterial `VEH_Truck_PHYSMAT`: **Friction 0.2**, Restitution 0.05, AnisoFrictionDir (1,0,0), AngularDamping 0.2.
  * Hover and car tuning is in `vs_evidence.json` (`HoverTruck_Physics`, `Truck_Physics`).

## Reader fix made during this pass
Matrices nested inside structs (e.g. `KAggregateGeom.BoxElems[].TM`) were still in the cooked (W,X,Y,Z) row order. `authored.py` now
reorders Matrix values recursively by declared schema type; this changed no previously published output.
