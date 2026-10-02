# MP_IAC_Streets navigation setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/navigation.json`** and **`navigation.glb`** (glTF metres:
POINTS = nav points, LINES = ReachSpecs). Regenerate: `AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_navigation.py`.
Handoff: **Gameplay** (AI and bots, if any).

## Bottom line
**Streets has no usable authored AI navigation.** Its packages contain no PathNodes, cover nodes, NavigationCells or nav mesh, and no
`TnTactical*` data. Other MP maps do (e.g. `MP_ESC_BrokenHope` has 1,118 tactical objects, probably for its AI Escalation mode).
What exists is UE3's editor-built path network between the gameplay NavigationPoints, and it is fragmented into small islands.
Any bot or AI navigation for Streets in the rebuild has to be **generated**, not recovered.

## What is authored (CONFIRMED)
* **123 NavigationPoints**: 60 team starts, 24 FFA starts, 14 ammo, 9 health, 1 overshield, 2 flag factories, 1 bomb factory,
  2 flag capture points, 2 bomb plant points, 3 domination points, 5 KOTH zones.
  * All carry `bMayCausePain`; 12 also carry `bNotBased`.
  * Per-node `MaxPathSize` (Radius/Height UU): 440/400 ×61, 750/800 ×17, 250/300 ×15, 1210/850 ×3; 27 nodes have none.
* **426 `TnReachSpec` edges**, owned by their start node (`NavigationPoint.PathList[]`). Each has Start, End{Nav,Guid}, Distance,
  CollisionRadius/Height, MaxCollisionRadius and reachFlags (class default `ForcedPathSizeName "Vehicle"`).
  * reachFlags: 425 × R_WALK and 1 × R_WALK|R_JUMP (`TnTeamPlayerStart_7032` → `TnFreeForAllPlayerStart_4010`, 2947 UU).
  * Collision sizes: r440/h400 ×293, r250/h300 ×76, r750/h800 ×48, r1210/h850 ×9.
  * Distances: 19–3385 UU (median 1138). They match Euclidean node distance to 0.001 UU, and every End resolves.
* **Direction:** 416 of 426 pairs are bidirectional. The 10 one-way edges all lead **into** objective points (capture, plant, KOTH),
  which own no edges: they are destinations only.

## Why it is fragmented
* Every edge is ≤ 3385 UU, just under the nav points' authored **`MaxConnectionDistance` 3400** (~34 m).
* The nearest-neighbour spacing of nav points is median 768 UU but up to 5437 UU. With no intermediate PathNodes the editor linked only
  nearby gameplay points.
* Result: **40 connected components**, the largest 8 nodes. 18 points are isolated, including all 3 domination points, 2 KOTH zones,
  the base-0 flag factory and 9 pickups. No player start reaches every pickup or objective.

## Unknown
The WFC path-size class table (names for 250/300, 440/400, 750/800 and 1210/850) is editor-only. The cooked `Engine.Default__Scout` is the
stock table (Human 48/80 … Vehicle 260/120) and doesn't match. reachFlags bit names are the stock UE3 enum (HIGH CONFIDENCE).
