# bot_nav: false drop links (parked follow-up)

Status: PARKED by Integration (2026-10-11) until after M2/M3. The stranded recovery covers the effect meanwhile (Gorge: 1 stranding
in 848 logs). Nothing below is implemented.

## Problem
`bot_nav.py` adds a `drop_down` link from a source cell to every nav floor below it in the scanned column (`for q in by_k[kk]`),
not only to the first floor the pawn would land on. Two cases produce links a pawn cannot follow:

1. **Through a nav floor.** The landing column holds another nav polygon between source and landing. Gorge example:
   (-100.5, 11.52, 50.5) -> (-99.5, -9.57, 50.5) passes the meshed -2.04 deck (polygon) in the same column.
2. **Through an eroded rim of the source floor.** The source floor continues into the scanned column as an open sample that was
   eroded out of the polygons by `min_radius` (a "rim"). The existing exception (cae2607: drops across eroded ledges are real,
   Gorge spawn ledges over sloped cliffs) lets the drop through. That's right at a cliff edge, but wrong where the "rim" is just the
   edge strip of a floor that goes on. Gorge example: deck (-69.5, -2.04, -130.5) -> (-70.5, -9.7, -130.5) under the deck's rim.

Effect on Gorge: four one-way areas of about 2,300-2,400 m2 each (y -9.7, x -113..-40, z 49..121 and z -131..-59). They are
the interior of the deck structure (StaticMeshCollectionActor_1543 plus BlockingVolume_14059, -16.2..-9.57), closed above by the
-2.04 deck and by walls on every probed edge. They are reached only through these links. The playable prune already drops them
(one-way), but the false drops stay in the kept cells, so a bot can choose a route that cannot be walked.

## Proposed rule
- (A) A drop lands on the highest floor below the source in the landing column. Drop to `q` only if no nav polygon floor `q2` in
  that column has `q + step < q2 < h - step`.
- (B) A level open rim in the scanned column means the pawn walks onto it rather than falling. Skip drop targets in that column and
  keep scanning; the drop happens in the first column past the rim with no level floor. This keeps the cliff-edge drops from
  cae2607, which happen beyond the rim.

## Expected per-map diff (estimate, upper bound)
These counts are taken from dry7 outputs: drop links whose landing (x, z) lies under a kept nav cell between landing + 0.37 and
source - 0.37. That approximates (A) only. (B) and links into pruned cells are not counted.

| map | drop links | through a kept nav floor |
|---|---:|---:|
| MP_IAC_Streets | 1,329 | 59 |
| MP_ESC_BrokenHope | 570 | 11 |
| MP_ESC_Remnant | 1 | 0 |
| MP_IAC_Berth | 1,918 | 15 |
| MP_IAC_Rust | 879 | 4 |
| MP_IAC_Seed | 1,353 | 8 |
| MP_KON_Molten | 339 | 2 |
| MP_ORB_Debris | 2,671 | 105 |
| MP_UND_Complex | 1,092 | 72 |
| MP_UND_Gorge | 2,837 | 637 |

Every map would change, Streets included, so this is a re-baseline for all maps. It needs:
- a 10-map dry run;
- `bot_nav_audit.py` (ReachSpec ground truth: no new missing paths, detours not worse);
- the Gameplay 5-config gate with the current nav as control.

## Diagnostics available
`bot_nav.py --debug` writes, per pruned group in `bot_nav_pruned.json`:
- `exit_rejects` and `exit_reject_examples`;
- `entry_examples`.

`--probe "x,z;..."` traces the link scan of source columns. `--probe-box "x0,x1,z0,z1,y0,y1;..."` dumps column floors and
occupancy. Both write to `<out>/link_probe*.txt` and leave the outputs unchanged.
