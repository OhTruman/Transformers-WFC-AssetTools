**Starts with no floor below (backlog 5 follow-up, 2026-10-17): verdict per actor.**
- Ruled out for this chapter: every A4 level is exported, so no streaming sublevel is missing.
- `Checkpoint_14441` ("02a -Watchdog Part 2"): **truly air, by design (PROVISIONAL).**
  - It has no paths of its own, and the only navigation within 30 m is three AirPathNodes.
  - No mover sits in its column, and no collision lies within 30 m below.
  - Its restart (`SeqEvent_GameplayStarted_12707` -> remote event `WatchdogPart2_GameplayStarted`) only spawns flyers at
    AirPathNodes ("only spawn two flyers if coming back from the checkpoint").
