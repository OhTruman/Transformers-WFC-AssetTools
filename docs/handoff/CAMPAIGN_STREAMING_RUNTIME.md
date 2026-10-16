# Campaign streaming-state runtime: design note (2026-10-16, PROVISIONAL)

What the engine must do with each chapter's `streaming.json` (written by `scripts/wfc/vs_streaming.py` into
`work/campaign_pilot/VerticalSlice/Maps/<chapter>/`) to make a campaign chapter traversable. This is a design note only; no code.

**Sources:**
- Authored data in `manifests/authored.db`: LevelStreamingKismet, LevelStreamingState, TnWorldInfo, Checkpoint and
  SeqAct_SetStreamingState / SeqAct_FlushLevelStreaming props.
- The read-only RE decomp (`RE-Workspace/work/script/decomp`): Engine.LevelStreamingState, Engine.Checkpoint,
  HM_Engine.CheckpointManager, HM_Engine.SeqAct_SetActiveCheckpoint / RestartFromActiveCheckpoint.

**Native gap:** the UnrealScript side of LevelStreamingState is native stubs only (AddLevel, RemoveLevel, GetLevelTargetState,
PreActivate, Activate, IsTargetState, IsCurrentState), and so are CheckpointManager.RestartFromActiveCheckpoint / GenerateCheckpointData.
Their exact native behaviour is **UNKNOWN** until the exe is read; the rules below marked (inferred) come from the authored data and
UE3 conventions.

## 1. Data model (CONFIRMED from authored data)

| object | authored fields | in streaming.json |
|---|---|---|
| persistent level `<chapter>_Base_m` | TnWorldInfo: `StreamingLevels` (the LevelStreamingKismet list), `StreamingStates`, `InitialStreamingState`, `StreamingLevelLayout` (editor grouping only) | `persistent_level`, `initial_state` |
| LevelStreamingKismet | `PackageName`, `bIsFullyStatic` (34 of 97 in A1 / D3A), DrawColor | `sublevels[*].streaming_object` |
| LevelStreamingState (High Moon) | `Levels: [{LevelName, LevelVisible}]` | `states[*].levels` |
| Checkpoint (NavigationPoint) | `StreamingState`, `AuxilliarySpawnPoints`, `DisplayOrder`, `Tag` (display name, e.g. "14 - Decagon Plaza") | `states[*].checkpoints` |
| SeqAct_SetStreamingState | `StreamingState`; latent (`bLatentExecution`), outputs `Started` / `Finished`; usually fired by a SeqEvent_RemoteEvent | `states[*].set_by` (action + triggering events with EventName) |
| SeqAct_FlushLevelStreaming | input `Flush`, output `Finished` | `flush_actions` |

Over the 10 chapters:
- 196 states, between 5 and 54 levels each (median 10).
- 2,021 level entries visible and 32 loaded but hidden (`LevelVisible: false`).
- 200 SetStreamingState actions, 211 checkpoints, 42 flush actions.
- Every sublevel belongs to at least one state.

## 2. Runtime rules

1. **Load the persistent level.** It is always loaded and never in a state. It holds the chapter's Kismet, checkpoints, objectives and
   the TnCampaignPlayerStart(s).
2. **Initial state** (inferred): on level start, activate `TnWorldInfo.InitialStreamingState`. Every listed level is loaded, and made
   visible when `LevelVisible` is true; every sublevel not listed stays unloaded. For example, A1 starts in `LevelStart`, D3B in
   `IntroCine`, A2 in `Start_State`.
   - When the game starts from a checkpoint (`CheckpointManager.OnStartingFromCheckpoint` → `StartCheckpoint.ProcessActions()`),
     the checkpoint's own `StreamingState` replaces the initial one (inferred from the authored link `Checkpoint.StreamingState`,
     which `Checkpoint.CheckForErrors` requires: "Checkpoint missing streaming state.").
3. **Activating a state** (inferred, UE3 LevelStreaming semantics):
   - Target set = the state's levels. Load the targets not loaded yet. Then set visibility per `LevelVisible`.
   - Then make levels that are loaded but not in the target set invisible, and unload them.
   - Gameplay keeps running while loads proceed. The latent SeqAct_SetStreamingState fires `Started` at once and `Finished` when every
     target level is loaded and its visibility applied (the `IsTargetState` / `IsCurrentState` pair suggests a polled target).
4. **Flush:** SeqAct_FlushLevelStreaming blocks until every pending load / visibility change is done, then fires `Finished`. In a
   rebuild, all pending work is completed synchronously.
5. **Checkpoints:**
   - SeqAct_SetActiveCheckpoint stores the checkpoint as active (CheckpointManager.SetActiveCheckpoint) and saves it.
   - SeqAct_RestartFromActiveCheckpoint reloads it: activate the checkpoint's StreamingState, then spawn at
     `Checkpoint.GetStartSpotForPlayer`, which is the checkpoint itself for the local player and rotates through
     `AuxilliarySpawnPoints` for co-op clients. Then `TeleportPlayerToCheckpoint`.
6. **Visibility vs collision** (inferred): a loaded-hidden level is neither drawn nor collidable; only visible levels add geometry,
   collision, nav and actors. Its Kismet should still run once loaded (UE3 behaviour; UNKNOWN for High Moon).
7. **CINE sublevels:** they appear in states like any other level (A1 `Thumper_Cine`, A3 6, A4 5, D3B 3…). streaming.json tags them
   `hidden_outside_matinee` as an export default.
   - Until a matinee player exists, keep them unloaded, or loaded-hidden, even when a state lists them visible.
   - With a matinee player, follow the state (the authored data makes them visible when the cutscene's state is active).

## 3. Using the export

- `node_sublevel` maps every world.glb node to its sublevel (ambiguous names list every candidate: 28–140 per chapter). A renderer
  can keep the merged world.glb and toggle node visibility per level, instead of loading per-level files.
- **Load timing:** the export is one file per chapter (world.glb 8–163 MB), so "loading" a level is a visibility / collision toggle with
  no I/O. Real streaming (memory budget) is only needed if the whole chapter does not fit. The largest chapter (D1_ORB, 26,960
  placed meshes) is about the size of 3 MP maps.
- Lightmaps, collision (`collision*.glb`), nav (`navigation.json`), audio and FX already carry the level per item or per node, so
  the same per-level toggle applies to them.

## 4. Open points (need the exe or a test)

1. The native `LevelStreamingState.Activate` order (unload before load? all at once?) and whether `LevelVisible: false` levels tick.
2. Whether `Finished` waits for visibility or only for loading.
3. Checkpoint save data (`GenerateCheckpointData` is native): what besides the streaming state is restored (Kismet state, pickups,
   destructibles).
4. Co-op: `AuxilliarySpawnPoints` rotation is in script (CONFIRMED); remote-player streaming is not covered.

Order of implementation: (1) initial state + per-level visibility toggles on the merged chapter; (2) SetStreamingState with Started /
Finished from RemoteEvents (needs the core Kismet set); (3) checkpoints (start-from and restart); (4) flush; (5) CINE handling with the
matinee player.
