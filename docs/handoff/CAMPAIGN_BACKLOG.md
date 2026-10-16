# Campaign-phase backlog (AssetTools)

Order set by Integration (2026-10-16). Each fix is generic: MP / Streets outputs must stay byte-identical, proven before and after.

1. **Pickup-factory discovery for campaign chapters.**
   - A1_IAC: `vs_pickups` finds 0 of the 47 factories that `spawnpoints.json` lists (21 weapon, 20 ammo, 5 health, 1 overshield).
     Campaign factories sit in the design sublevels; the stage needs to look through every exported sublevel.
2. **Tag parser fix** (authored.db mis-parses some components' tags).
   - A1_IAC: 1,211 components lose their StaticMesh (657 in HGHWY2_Art, 547 in HGHWY3_Art, 7 in Strts0_End_Art). Their property
     names come out as unrelated names (e.g. `Wave_Alpha_Pan_Speed_1407`), which looks like a name-table / tag-size desync.
   - The detector runs over the 10 MP maps first. If any MP component is affected, this moves up to package 6 (Streets byte-identical
     except the recovered components), and the detector joins the validator.
3. **m05_bsp_default_faces and map_structure_audit grids.** Both exceed the 10 GB chapter cap on A1_IAC (MemoryError in their ray /
   triangle grids). Fix them with oversized-triangle exclusion / coarser cells (Streets byte-identical as the gate), then rerun both
   alone on every finished chapter. The default-material face list feeds the campaign texture / material pass.
4. **matc pass for campaign materials** (Rendering, when they have a gap): D5_OME 46 of 115; A1_IAC 269 of 524.
   - Lists: `work/campaign_pilot/<MAP>_materials_for_rendering.json`.
5. **Player-start ground check.** A1_IAC's start has no ground within 6 m (the nearest is 236 m below). Recheck after item 2.

Chapters still to run, in size order: A5_TRY, D3B_IAC, D2_COR, A3_COR, A4_ORB, D3A_IAC, A2_KON, D1_ORB. Done: D5_OME, A1_IAC.
