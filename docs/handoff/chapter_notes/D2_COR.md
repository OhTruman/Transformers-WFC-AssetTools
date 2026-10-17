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

**The 3 unclassified starts (2026-10-18): one site, "Guardian Chamber"** (`Checkpoint_8567` + its auxiliary
`TnCampaignPlayerStart_3766` / `_9617`, glTF ≈ (1050, −250, 1112), in D2_COR_Chamber_Design_m / Chamber_Art_m).

**Verdict: UNKNOWN, a missing floor; NOT level design.**

**Evidence that the original had floor there:**
- `TnTacticalPathNode_3036`, a *ground* tactical node, sits 1.7 m from the checkpoint and 4.7 m below it (y ≈ −258.4).
- The two starts have walk reach specs to the checkpoint, and the checkpoint has a walk spec out of the cluster. So it is not an
  airborne cluster.

**What our export has:**
- Neither world.glb nor collision_pawn.glb has any geometry within 15 m horizontally between y −273 and −246, except pillar tops
  (`SideSuppPillar_STAT`) and walls starting at y ≈ −262 and lower. There is no BSP there.

**Ruled out:**
- No InterpActor / matinee mover passes under the site: all D2 Move tracks were checked.
- No destructible, skeletal floor or spawned pawn is there. The two SkeletalMeshActors 22 m away are COR_InteriorDoor.
- No prop within 80 m failed to export. Both Chamber levels are exported.

**Code / data item:** the Guardian Chamber floor slab at y ≈ −259 (resting on the support pillars) is absent from the export. Next step:
look for the floor mesh in the cooked Chamber packages (props_missing_mesh, an unhandled actor class, or a component the exporter
skips).
