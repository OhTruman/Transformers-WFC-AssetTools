# Playtest 2026-10-23 #10 / #13: MP_IAC_Seed collision (AssetTools, read-only)

**For:** Gameplay.

**Data:**
- `work/playtest_20261023/seed_collision.json` (volumes; script `seed_collision.py`);
- `work/playtest_20261023/seed_cylinders.json` (simple hulls vs visuals; script `seed_cylinders.py`).

**Source:** ExtractedAssets VerticalSlice `MP_IAC_Seed/physics.json` (volumes, per-mesh simple collision, per-prop pawn representation).
Coordinates are glTF metres (Y up).

## #10 Tall invisible collision at the central hole

**Two authored BlockingVolumes stack over the map centre** (map centre ≈ (0.66, 8.0, −41.1), the mean of the starts and pickups):

| volume | level | footprint x / z (m) | y (m) | flags |
|---|---|---|---|---|
| `BlockingVolume_7008` | Seed_BASE_m | −10.27…1.40 / −44.82…−29.91 (≈ 12 × 15 m) | **−8.88 → 18.57** | CollideActors, BlockActors, BlockNonZeroExtent, BlockRigidBody, RBCC_BlockingVolume, bWorldGeometry |
| `BlockingVolume_9745` | Seed_ART_m (rotated: Pitch 1120, Roll 2944) | −12.73…−0.07 / −38.68…−26.60 | **16.54 → 38.20** | same |

- Together they form an invisible column about **47 m tall** (y −8.9 → 38.2) over the central area. That fits the user's description of a
  wall rising far above the visible feature, which stops ground and air movement.
- Neither volume is referenced by any Kismet sequence, so both are active for the whole match. Both block NonZeroExtent (pawn and vehicle
  movement), not weapon traces.
- They are authored cooked data. Our pawn collision reproduces them as cooked (CONFIRMED); the original runtime has the same volumes
  (HIGH: UE3 BlockingVolume blocks every actor with these flags).
- **Decision for Gameplay:** keep them as original, or apply a PC adaptation such as capping 9745 / 7008 at the visible top or ignoring
  them for flying vehicles.
- Not the cause: `BlockingVolume_5746` (y 41–102 m, 777 × 414 m) is the map's ceiling cap.
- Other tall pawn-blocking volumes, sorted by distance from the centre, are in `seed_collision.json` → `tall_pawn_blocking_volumes` (40).

## #13 Clip-in on cylindrical props

- Pawn movement collides with each mesh's authored **simple hull** (BodySetup convex / box elements) wherever the mesh sets
  `UseSimpleBoxCollision`, as in UE3 (physics.json `props[].pawn == "simple"`).
- **The hulls are smaller than the visible meshes on 40 of the 132 simple-collision meshes** (inset > 0.25 m on some axis). Cylinder-like
  ones:
  - `ENV_IAC_Orrery_p.StaticMesh.OrreryColumn_STAT` (4 placements): hull about 1.06 m inside the visual on each side of the round axes;
  - `ENV_ORB_D1_Debris_p.Meshes.Pillar01_Debri_STAT` (1): about 1.8 m.
  - Others: `SeederGroundBase_STAT`, `Core_RoutingWallA / B`, `GasChamber_Top(_A)`, `Wall_Side2` / `Wall_BreakOff_sm`, `RectBld`.
  - Full list with hull vs visual extents in `seed_cylinders.json`.
- The original uses the same hulls, so the clip-in is most likely original behaviour (HIGH), not a rebuild bug.
- **Option (PC adaptation, Gameplay's call):** use per-poly (render) collision for pawns on the listed meshes. physics.json already holds
  each mesh's render sections with EnableCollision.
- **Caveat:** the comparison is sorted per-axis extents (axis-order safe), so the insets are indicative per mesh, not exact per side.
