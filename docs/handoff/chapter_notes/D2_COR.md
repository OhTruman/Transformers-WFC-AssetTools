**Starts with no floor below (backlog 5 follow-up, 2026-10-17): verdict per actor.**
- Ruled out for this chapter: every D2 level is exported, so no streaming sublevel is missing, and no mover sits in any of these
  columns (within 40 m horizontally, at any height).
- All verdicts are PROVISIONAL because they read reachFlags 2 as R_FLY.

**Shaft cluster** at glTF (1100, -315, 1250): **truly air, by design.** Floor is about 60 m above and about 220 m below.
- `TnCampaignPlayerStart_3993` and `TnCampaignPlayerStart_9817`: auxiliary spawn points of the two checkpoints below.
- `Checkpoint_14292` ("Berserker"; restart sets OBJ9 "Destroy the Energon Bridge").
- `Checkpoint_14650` ("Uncaged Power").
- Each has 9-11 fly-only reach specs. Their 3 walk specs each link only these four starts to each other, so every way out is flying.

**`Checkpoint_11675`** ("Drop Ship Entrance"): **truly air, by design.**
- It has no paths. Its only neighbours (about 10 m away) are `TnCampaignPlayerStart_8098` / `_9089`, both fly-only.
- Its restart sets OBJ1 "Destroy the Autobot Dropship" and fires the dropship scene (hatches, side doors, vignettes). Nothing in it
  teleports or attaches the player.
- The nearest dropship actor is 160 m away.

**The 3 unclassified starts (2026-10-18, corrected the same day): one site, "Guardian Chamber"** (`Checkpoint_8567` + its auxiliary
`TnCampaignPlayerStart_3766` / `_9617`, glTF ≈ (1050, −250, 1112), in D2_COR_Chamber_Design_m / Chamber_Art_m).

**Verdict: elevated spawns over a real floor; level data, NOT an export gap.**
- **The floor exists** in both world.glb and collision_pawn.glb: `ENV_CORE_InroomRndTunnel_A_STAT` (StaticMeshCollectionActor_9905,
  walkable, normal y 0.98) at y ≈ −259.9.
  - The two starts are about 11.3 m above it; the checkpoint is about 13 m above a support-pillar top.
  - The audit's seed search looks only 3 m below a start, so they were off the walk graph.
- The ground node `TnTacticalPathNode_3036` stands 1.79 m above the same floor, a normal grounded height.
- Their reach specs are mostly fly-only (3766: 4 of 6, 9617: 4 of 6, 8567: 3 of 4). The walk specs link only the three and the ground
  node.
- The triage now has a category for this, `elevated_above_floor` (walkable floor 3–30 m below).

**Correction:** the first version of this note said "missing floor". That came from a layer list I printed only partly and a vertex-box
search that misses large triangles whose vertices lie outside the box. Triangle containment under each start finds the floor.
