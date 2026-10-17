## 3. Diagnostics (done 2026-10-16 / 17; table in section 1b)

- **m05 (default-material BSP faces):**
  - Ran over **all BSP levels per chapter** (`WFC_M05_ALL_LEVELS`), with tile-local obstacle grids (`WFC_M05_TILE=256`).
  - The MP path is unchanged: the single-level untiled default matches the gate on all 10 MP maps, Streets included, and tiled
    output equals untiled on Gorge and BrokenHope.
  - Every chapter is under the 10 GB cap. D1_ORB m05 took 82 min (10,048 faces), the only stage over an hour.
- **Structure audit:** at a 2 m cell (`WFC_AUDIT_CELL=2`; the MP default stays 1 m). **All 10 chapters PASS** (2026-10-17): mesh-less blocking
  components are now explained (no StaticMesh, nothing to collide with). A2's StaticMeshCollectionActor_10261 is explained (meshes without
  collision, as in UE3). The walk-graph checks are empty in the campaign (no MP player starts).
- **bsp_alignment: COMPLETE on all 10 chapters** (m04_bsp key-search fix: D2_COR_TNL3_Art_m's 212 ModelComponents were unparsed
  because the tag stream's 'None' index equals the model export index there).

## 4. Provisional items

- **A2_KON Courtyard:** 125 components without a mesh, all in `A2_KON_Courtyard_Art_m`. They parse clean and have no StaticMesh even
  through the archetype chain, so it's not the parser bug; possibly references stripped at cook time. Eye check in game later.
- **Other genuinely empty components:** A3 9, D1 20, D2 12, D3A 2, same pattern.
- **A1_IAC player start:** 236 m above ground even with every mesh present; likely an airborne / matinee start. D2_COR: 15 of 30
  starts grounded. The approved fix is a campaign-mode relaxation of the ground check; the MP rule stays.
- **Kismet classes "without decomp":** matched by file name only. Some may be native or have a differently named decomp file; RE
  should confirm the list in section 2.
- **Streaming states:** authored data is exported (states, checkpoints, SetStreamingState triggers), but load / visibility order at
  runtime is not proven. CINE sublevels are tagged hidden-outside-matinee as an export-side default.

## 5. Recommended order of work for the campaign phase

The geometry, lighting, nav, collision, audio placement and streaming data now exist for all 10 chapters. What stops any level from
being playable is runtime behaviour, so the order follows what unblocks the most levels:

1. **Level streaming runtime** (Gameplay / Rendering), using `streaming.json`: the persistent level + named streaming states, the
   initial state, SetStreamingState from RemoteEvents, and checkpoint restore. Every chapter needs it before anything past its first
   area is reachable (200 SetStreamingState, 211 checkpoints).
2. **Core Kismet set**: RemoteEvent / ActivateRemoteEvent, Toggle, Gate, Delay, Touch, plus the custom classes used by all chapters:
   `TnSeqAct_MissionComplete`, `TnSeqEvent_Interact` (all 10), `SeqAct_TnAiMoveToActor`, `TnSeqAct_ActivateTogethernessVolume` (9).
   RE first confirms which of the 15 listed classes really lack a decomp.
3. **Pickup-factory discovery** (AssetTools backlog 1; 377 factories, small fix). Weapons, ammo and health matter in every chapter.
4. **Pawn factories / AI** (1,263 SeqAct_TnPawnFactory, 2,863 character vars): enemies spawn through Kismet. This is the largest
   behaviour item and needs the AI / character-definition runtime.
5. **Matinee player** (3,605 InterpData): needed for intros / outros and scripted movers (1,046+ interpolating movers in A1 alone).
   Until it exists, the CINE sublevels stay hidden and chapters can start at their first checkpoint.
6. **Materials:** a matc pass for the 1,112 uncompiled materials (Rendering; list in
   `work/campaign_pilot/ALL_materials_needing_matc.json`). Without it they fall back to the generic material; HD textures already
   cover them.
7. **Dialog:** in-game dialog via anim notifies (3,702) and dialog groups; FaceFX lip-sync only for cutscenes (121 tracks).

**First level to bring up: D5_OME** (9 levels, 1 streaming state, 1,407 Kismet objects, 13 pickups, 46 materials to compile). It is
the smallest complete chapter and exercises each system once. **Then A5_TRY** (15 levels, 4 states), then the large chapters.

**AssetTools next:** the grid fix (section 3), then pickup discovery (backlog 1), then the player-start relaxation (backlog 5).
