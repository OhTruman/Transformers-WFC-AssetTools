# Campaign-phase backlog (AssetTools)

Order set by Integration (2026-10-16). Each fix is generic: MP / Streets outputs must stay byte-identical, proven before and after.

1. **Pickup-factory discovery for campaign chapters: DONE 2026-10-17.** 377 / 377 placed factories exported (`gameplay.json` pickups and
   `<chapter>_pickup_factories.json`), with weapon class, pickup mesh and sublevel; MP output identical (gate `work/pickupfix/proof.json`).
   Finding: the MP Escalation maps (BrokenHope 17, Remnant 16) also have TnWeaponPickupFactory that `gameplay.json` omits
   (MP left unchanged by rule). **Package 7 (Integration decision 2026-10-17):** in `scripts/wfc/vs_gameplay.py` and `vs_pickups.py`, let
   the weapon-factory classes apply to MP too (replace `is_campaign(MAP)` in the class lists; the BASE-level search stays for MP), then run
   `python scripts/wfc/run_bounded.py --cap-gb 10 -- scripts/wfc/vs_gameplay.py MP_ESC_BrokenHope` (then `vs_pickups.py`, `map_complete.py`,
   `map_render_index.py`; the same for MP_ESC_Remnant). Files that change: `ExtractedAssets/VerticalSlice/Maps/MP_ESC_{BrokenHope,Remnant}/
   gameplay.json` and `render_index.json`, `AssetTools/manifests/next_map/MP_ESC_{BrokenHope,Remnant}_pickup_factories.json` / `_pickup_fx.json`,
   `manifests/maps/MP_ESC_{BrokenHope,Remnant}/map_complete.json` / `completeness.json`. The other 8 MP maps have no weapon factories, so they are unchanged.
   - A1_IAC: `vs_pickups` finds 0 of the 47 factories that `spawnpoints.json` lists (21 weapon, 20 ammo, 5 health, 1 overshield).
     Campaign factories sit in the design sublevels; the stage needs to look through every exported sublevel.
2. **Tag parser fix** - DONE 2026-10-16 (f384c7b): authored.db rows re-parsed, MP runtime unchanged, campaign meshes / lights recovered. (authored.db mis-parses some components' tags).
   - A1_IAC: 1,211 components lose their StaticMesh (657 in HGHWY2_Art, 547 in HGHWY3_Art, 7 in Strts0_End_Art). Their property
     names come out as unrelated names (e.g. `Wave_Alpha_Pan_Speed_1407`), which looks like a name-table / tag-size desync.
   - The detector runs over the 10 MP maps first. If any MP component is affected, this moves up to package 6 (Streets byte-identical
     except the recovered components), and the detector joins the validator.
3. **m05_bsp_default_faces and map_structure_audit grids, plus bsp_alignment** (D2_COR: 2,074 more exported than authored BSP
   triangles, 747 unaccounted nodes). Both exceed the 10 GB chapter cap on A1_IAC (MemoryError in their ray /
   triangle grids). Fix them with oversized-triangle exclusion / coarser cells (Streets byte-identical as the gate), then rerun both
   alone on every finished chapter. The default-material face list feeds the campaign texture / material pass.
4. **matc pass for campaign materials** (Rendering, when they have a gap): D5_OME 46 of 115; A1_IAC 269 of 524.
   - Lists: `work/campaign_pilot/<MAP>_materials_for_rendering.json`.
5. **Player-start ground check: campaign-mode relaxation** (approved 2026-10-16; in progress 2026-10-17). All 10 chapters are through the pipeline. Campaign starts are often airborne or on platforms
   (A1_IAC: 236 m drop; D2_COR: 15 of 30 grounded). Allow them in campaign mode; the MP rule stays unchanged.

