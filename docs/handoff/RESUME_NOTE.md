# AssetTools resume note (2026-10-17 04:50)

- **Done today:**
  - Campaign starts seed the walk graph; the ground check is reported only in campaign mode (544f3d9; MP identical on all 10).
  - Pawn-factory manifest: 1,263 / 1,263 factories (f350205).
  - FaceFX rest-pose CSV + Optimus binding (ae600dd).
  - Hold watchdog (1b70368, 3d1cc87).
  - Starts report for 9 chapters: `manifests/next_map/campaign_starts_report.json` (`campaign_starts_report.py`).
- **Hold watchdog test (PASS, 2026-10-17, A2_KON map_complete via run_stages.cmd).** Log lines from
  `work/campaign_pilot/A2_KON_stages.log`:
  ```
  run_bounded: rc=76  wall=3.0s  peak_job_memory=1.39 GB  cap=10.0 GB  cmd=scripts\wfc\map_complete.py A2_KON  INTERRUPTED by PERF_HOLD at 2026-10-17 04:14:29 (F:\Transformers Rebuild\AssetTools\work\PERF_HOLD): outputs may be partial, rerun the stage
  map_complete interrupted by PERF_HOLD  4:14:29.36, waiting for 60 s without a hold
  run_bounded: rc=0  wall=9.2s  peak_job_memory=1.39 GB  cap=10.0 GB  cmd=scripts\wfc\map_complete.py A2_KON
  map_complete rc 0  4:16:08.71
  ```
  - The hold was set at 04:14:28 and removed at 04:14:58; the rerun started about 04:15:59.
  - A stage killed by a hold leaves `<stage log>.HOLD_INTERRUPTED`; the next start deletes it.
- **Backlog 5 DONE (d84baf2):** all 10 chapters are in the starts report.
  - Generated outputs: summary section 1c and section 6 of each chapter doc.
  - Off-walk-graph triage: airborne_by_design / on_mover / no_floor_below / unclassified.
  - D1's cap at 04:24 was a launch error: run_stages.cmd had no WFC_AUDIT_CELL=2, so the audit ran at 1 m. Fixed in run_stages.cmd
    and run_campaign_rest.cmd; D1 reran at 2 m, peak 3.51 GB, PASS.
- **Open:**
  - Code items from the triage, for the campaign phase: mover collision at its initial pose in the walk graph; 6 no_floor_below starts
    (A4 / D2) still need a look.
  - The FaceFX bone-blend visual check stays parked until Gameplay's hook.
  - Integration copies the docs by file.
- **Rules:** check `*/work/PERF_HOLD` before any interpreter. While a hold is on: no python, node or py_compile at all; edit with the
  editor or the shell only.
- **Nothing is running.**
