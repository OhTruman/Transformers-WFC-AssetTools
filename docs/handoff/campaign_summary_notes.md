## 3. Pending diagnostics (m05 / structure audit / bsp_alignment)

- `m05_bsp_default_faces` and `map_structure_audit` are ray / triangle-grid diagnostics. They export no level data, but they produce the
  default-material face list (input to the campaign texture / material pass) and the playable-space / collision-vs-visible checks.
- On the large chapters they exceed the 10 GB cap or their own 8 GB guard (A1, A3, D2, D3B), or run for over 50 min (A4). So they were
  skipped from D3A onward, as Integration decided.
- **Plan:**
  1. Make the grids bounded: keep oversized triangles (sky dome, light planes, huge BSP polys) out of the uniform grid, test them
     per ray instead (the CLAUDE.md ray-test rule), and use coarser cells for chapter-size bounds.
  2. Gate: Streets and the 10 MP maps byte-identical (m05 / structure-audit outputs) before vs after.
  3. Then run both alone per chapter (`run_stages.cmd <chapter> 10 m05_bsp_default_faces map_structure_audit map_complete`), and
     update each chapter doc.
- `bsp_alignment` (D2_COR: 2,074 more exported than authored BSP triangles, 747 unaccounted nodes) is checked in the same pass.

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
