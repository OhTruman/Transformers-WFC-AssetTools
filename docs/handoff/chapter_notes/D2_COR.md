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
