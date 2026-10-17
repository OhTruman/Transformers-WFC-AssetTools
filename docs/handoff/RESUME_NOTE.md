# AssetTools resume note (2026-10-17 04:35)

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
- **Blocked (reported to Integration, waiting for a go):** D1_ORB map_structure_audit hits MemoryError at the 10 GB cap.
  - Cause: the walk graph, seeded from 22 starts, holds its reachable set as Python tuples.
  - Proposed fix: a packed numpy reachable set, gated MP byte-identical on 10 maps plus the 9 finished chapters, then rerun D1 audit +
    map_complete.
  - D1's map_complete ran on the stale audit.
- **Open:** reconcile the vs_validate ground-check count with the audit's start count in the chapter docs; regenerate the chapter docs
  and summary after D1. The FaceFX bone-blend visual check stays parked until Gameplay's hook.
- **Rules:** check `*/work/PERF_HOLD` before any interpreter. While a hold is on: no python, node or py_compile at all; edit with the
  editor or the shell only.
- **Nothing is running.**
