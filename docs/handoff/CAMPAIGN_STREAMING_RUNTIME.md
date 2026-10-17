# Campaign streaming-state runtime: design note (2026-10-16, PROVISIONAL)

What the engine must do with each chapter's `streaming.json` (written by `scripts/wfc/vs_streaming.py` into
`work/campaign_pilot/VerticalSlice/Maps/<chapter>/`) to make a campaign chapter traversable. This is a design note only; no code.

**Sources:**
- Authored data in `manifests/authored.db`: LevelStreamingKismet, LevelStreamingState, TnWorldInfo, Checkpoint and
  SeqAct_SetStreamingState / SeqAct_FlushLevelStreaming props.
- The read-only RE decomp (`RE-Workspace/work/script/decomp`): Engine.LevelStreamingState, Engine.Checkpoint,
  HM_Engine.CheckpointManager, HM_Engine.SeqAct_SetActiveCheckpoint / RestartFromActiveCheckpoint.

**Revision 2026-10-18:** the six RE corrections are folded in, and §2 now follows the native code.
- **Source:** `RE-Workspace/work/handoff/CAMPAIGN_STREAMING_RE.md` (RE lane, b68e7aa; on integration as
  `docs/handoff/CAMPAIGN_STREAMING_RE.md`).
- §2 rules are CONFIRMED native unless marked otherwise. The earlier "(inferred)" rules on activation order, Finished, loaded-hidden
  levels, restart and save data were wrong in the places listed in RE §6.
- streaming.json gained two sibling keys; no key was renamed:
  - `sublevels[*].fully_static`: `bIsFullyStatic` (126 of 430 sublevels);
  - `checkpoints`: per checkpoint, its `streaming_state`, tag, display order and auxiliary spawn points (211 checkpoints, all with
    a state).

## 1. Data model (CONFIRMED from authored data)

| object | authored fields | in streaming.json |
|---|---|---|
| persistent level `<chapter>_Base_m` | TnWorldInfo: `StreamingLevels` (the LevelStreamingKismet list), `StreamingStates`, `InitialStreamingState`, `StreamingLevelLayout` (editor grouping only) | `persistent_level`, `initial_state` |
| LevelStreamingKismet | `PackageName`, `bIsFullyStatic` (126 of 430 sublevels), DrawColor | `sublevels[*].streaming_object`, `sublevels[*].fully_static` |
| LevelStreamingState (High Moon) | `Levels: [{LevelName, LevelVisible}]` | `states[*].levels` |
| Checkpoint (NavigationPoint) | `StreamingState`, `AuxilliarySpawnPoints`, `DisplayOrder`, `Tag` (display name, e.g. "14 - Decagon Plaza") | `states[*].checkpoints`, `checkpoints[*]` |
| SeqAct_SetStreamingState | `StreamingState`; latent (`bLatentExecution`), outputs `Started` / `Finished` / `Aborted`; usually fired by a SeqEvent_RemoteEvent | `states[*].set_by` (action + triggering events with EventName) |
| SeqAct_FlushLevelStreaming | input `Flush`, output `Finished` | `flush_actions` |

Over the 10 chapters:
- 196 states, between 5 and 54 levels each (median 10).
- 2,021 level entries visible and 32 loaded but hidden (`LevelVisible: false`).
- 200 SetStreamingState actions, 211 checkpoints, 42 flush actions.
- Every sublevel belongs to at least one state.

## 2. Runtime rules (CONFIRMED native per RE b68e7aa, unless marked)

1. **Load the persistent level.** It is always loaded and never in a state. It holds the chapter's Kismet, checkpoints, objectives and
   the TnCampaignPlayerStart(s).
2. **Level start** (CONFIRMED):
   - Starting from a checkpoint of this map activates that checkpoint's `StreamingState` (`checkpoints[*].streaming_state`).
   - Otherwise `TnWorldInfo.InitialStreamingState` is activated (`initial_state`; e.g. A1 `LevelStart`, D3B `IntroCine`, A2
     `Start_State`), unless the URL carries `?DontLoadInitialStreamingState` (set by restarts and save loads).
   - Then a **blocking flush** runs before play, behind the loading screen: the start state's levels are fully loaded and added.
3. **Activating a state** (`SeqAct_SetStreamingState` → `LevelStreamingState.Activate`):
   - It only **sets a target per level**: listed with `visible: true` → Visible; listed with `visible: false` → Loaded; not listed →
     Unloaded. No I/O happens at activation.
   - **Levels whose target does not change are not touched.**
   - The streaming tick then works through the levels **in StreamingLevels order**, one level at a time: async load, AddToWorld over
     several frames, or the unload stages. Loads and unloads interleave; there is no "load all, then unload all". Gameplay keeps
     running.
   - Outputs: `Started` at once. `Finished` once **every** level is exactly at its target, unloads included. `Aborted` if another
     SetStreamingState replaces the target first.
   - Rebuild: switch only the levels whose target changed, then fire `Finished` when all have switched. `Aborted` only matters if two
     state changes overlap.
4. **Flush:** SeqAct_FlushLevelStreaming is blocking. It ticks streaming until nothing is pending, ticking the loading screen
   between passes, with an optional GC; then it fires `Finished`. Rebuild: complete all pending switches synchronously.
5. **Checkpoints:**
   - **Set:** SeqAct_SetActiveCheckpoint stores the active checkpoint; SeqAct_SaveActiveCheckpoint writes the save.
   - **Save data is player-only:** character, health, ability resource, weapons with clip and reserve ammo, plus the checkpoint and map
     path. Kismet state, pickups and destructibles are **not** saved.
   - **Restart, checkpoint on this map** (in place, blocking):
     1. The checkpoint's actions run (e.g. `TnStartingFormOverrideCheckpointAction`).
     2. AI controllers and pawns, and the player pawns, are destroyed. Music stops.
     3. `ResetLevel`: `Reset()` on every resettable actor; the game Kismet sequence resets; every `SeqEvent_SequenceActivated` re-fires.
     4. **Every level that is not `fully_static` is unloaded and reloaded fresh** from its package, so its actors, pickups,
        destructibles and Kismet return to their authored state. Fully-static levels in the checkpoint's state are kept.
     5. The checkpoint's state is activated with a blocking flush.
     6. Players respawn at `GetStartSpotForPlayer`: the checkpoint itself for the local player, `AuxilliarySpawnPoints` in rotation
        for others, then `TeleportPlayerToCheckpoint`. Their saved data is restored.
   - **Restart, checkpoint not on this map** (or loading a save from the menu): URL travel with `?LoadCheckpoint` and
     `?DontLoadInitialStreamingState` (a full map load), then the same restore.
   - Rebuild: reset each non-static sublevel to its authored state, reset the persistent level's actors and Kismet, apply the
     checkpoint's state, then respawn the players.
6. **Visible vs loaded** (CONFIRMED):
   - Visible = added to the world: render, collision, nav, actors, the level's Kismet begun.
   - **Loaded but not visible = not in the world**: no actors, no collision, no ticking and **no Kismet**. The rebuild treats it as
     absent.
7. **CINE sublevels:** they appear in states like any other level (A1 `Thumper_Cine`, A3 6, A4 5, D3B 3…). streaming.json tags them
   `hidden_outside_matinee` as an export default (not a native rule).
   - Until a matinee player exists, keep them absent, even when a state lists them visible.
   - With a matinee player, follow the state.

## 3. Using the export

- `node_sublevel` maps every world.glb node to its sublevel (ambiguous names list every candidate: 28–140 per chapter). A renderer
  can keep the merged world.glb and toggle node visibility per level, instead of loading per-level files.
- **Load timing:** the export is one file per chapter (world.glb 8–163 MB), so "loading" a level is a visibility / collision toggle with
  no I/O. Real streaming (memory budget) is only needed if the whole chapter does not fit. The largest chapter (D1_ORB, 26,960
  placed meshes) is about the size of 3 MP maps.
- Lightmaps, collision (`collision*.glb`), nav (`navigation.json`), audio and FX already carry the level per item or per node, so
  the same per-level toggle applies to them.

## 4. Open points

The four earlier open points (activation order, `Finished`, save data, co-op spawn rotation) are answered by RE (b68e7aa), and
§2 follows that. Still open:

1. Co-op: remote-player streaming (RE: the state change is sent to clients through H `ClientUpdateLevelStreamingState`; not decoded).
2. The native `GenerateCheckpointData` body (RE: PARTIAL, but no non-player data appears anywhere in the save path).
3. The loading-screen phases (native notify ids 0x32–0x38: H).
