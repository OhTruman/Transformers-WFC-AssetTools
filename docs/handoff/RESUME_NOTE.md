# AssetTools resume note (2026-10-16 21:50)

- **Diagnostic chain** (m05 tiled `WFC_M05_TILE=256` + structure audit `WFC_AUDIT_CELL=2`, then map_complete / render_index): done
  for 8 of 10 chapters (A2, A4, A5, D1, D2, D3A, D3B, D5 both OK; A1 and A3 structure audit OK). **Open:** the m05 retry for A1_IAC
  and A3_COR (tiled). The 14:59 retry loop in `work/campaign_pilot/run_diag.cmd` logged "done" without running; rerun it with
  `work/campaign_pilot/run_m05_retry.cmd`. Then regenerate the chapter docs (`campaign_chapter_doc.py`) and the summary.
- **Deletions:** you approved directly (21:4x) deleting `out/hd/push_full` and `out/hd/full/{in,in_normal,in_dat}`; keep
  full/*.json. b0-2 / b0-6 / b0-12 are already deleted. hd_dev_full junctions point only at b0-31 and push_m6 (checked).
- **Feasibility doc** `docs/handoff/CROSSPLAY_PLATFORM_FEASIBILITY.md`: not started (fill-in work after the items above; drop it
  for any package 6 task).
- **Particle LOD check:** dropped by Integration (Systems: the original's LOD 1 really is heavier).
