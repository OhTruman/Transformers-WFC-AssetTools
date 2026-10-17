# Campaign Kismet custom classes (2026-10-16, PROVISIONAL; revised 2026-10-18 with RE)

**Revision 2026-10-18:** RE traced the handlers from script (`RE-Workspace/work/handoff/CAMPAIGN_KISMET_HANDLERS_RE.md`, 93790c1),
which extends this doc.
- **Three of the 15 have script after all:** TnSeqAct_MissionComplete, SeqAct_TnAiUseTurret and TnSeqAct_AiDisableShootingBehavior.
  They live in TransContent, which is cooked per map, so the shared decomp misses them. Decompile per map with
  `tools/ue3dis.py <map> TransContent.<Class>.<Func>` (e.g. A2_KON_BASE_m, A1_IAC_Elevator_Design_m).
- The changes are marked **(RE 93790c1)** below.

These are the 15 High Moon Kismet classes the campaign uses that have no RE decomp file of their own (CAMPAIGN_PIPELINE_SUMMARY §2).

**Sources** (read only):
- The class schema and class default objects in `manifests/authored.db`: properties, InputLinks / OutputLinks / VariableLinks.
- The authored instances in all 10 chapters.
- The RE decomp `RE-Workspace/work/script/decomp`, for the code that handles or fires them.

No exe was opened. ReVa was not connected, and native analysis would need a writable Ghidra project, which this lane's rules don't
allow, so it's left to RE. Raw extraction: `work/campaign_pilot/kismet_classes_raw.json`.

**Finding:** these classes have no decomp file because they are data-only nodes, not because their behaviour is unknown.
- Each has no script functions of its own.
- Their behaviour lives in the handler that the UE3 Kismet dispatch calls on the target (`On<ActionName>` in the target's controller /
  actor), or in the actor that fires the event via `ActivateEventClass`. Those handlers ARE decompiled.
- **Truly native, still UNKNOWN:**
  - the movie playback behind `SeqAct_MoviePlayer.PlayMovie` / `StopMovie`;
  - the stock UE3 latent move (`AIController.OnAIMoveToActor` is script, the movement itself native).

## 1. The four used in 9–10 chapters

### TnSeqAct_MissionComplete: all 10 chapters, 12 instances
- **Class:** `TransContent.TnSeqAct_MissionComplete` ← `HM_Engine.SeqAct_MoviePlayer` ← `Engine.SeqAct_Latent`. No properties of its own.
- **Links:** input `Play`; variable `Player` (Targets); no outputs.
- **Authored values:** `MovieName` = the chapter outro FMV (`FMV_a1outro.bik`, `FMV_a2outro.bik`, …, or `Blank.bik`), `bIsSkippable`.
- **Behaviour** (decomp `HM_Engine.SeqAct_MoviePlayer`):
  - `Activated`: on the Play impulse while not playing, sets `bIsRequestingPlaying`.
  - `OnPlayMovie`: hands `HmMovieInterface(Game).MovieParameters = {MovieFileName, bRenderLastFrameAtEnd, bBlendWithGameRendering, Start 0}`.
  - `OnStopMovie` clears the file name.
  - Playback is native.
  - "Mission complete" bookkeeping is separate: `TnProfileSettings.GetCheckpointMissionComplete` (read by
    `TnGameActionScriptBinding`) tracks the profile progress.
- **Post-movie flow (RE 93790c1, CONFIRMED script):** profile `CompleteMission` + save + `EndGame("Complete")`. The movie becomes
  skippable only after the end-game handling completes; stopping it calls `ReturnToGameLobby`.
- **Movie names (RE 5e6e8de):** authored `MovieName` values sometimes end in a space (`"FMV_a1text.bik "`), and one file is named
  `FMV_a5otext_ESN .bik`. Trim before matching. The original resolves `Movies\<name>_<LANG>.bik` before the plain name.
- **Rebuild:** play `ExtractedAssets/movies/<MovieName>.mkv` full screen (all 54 FMVs are converted, with subtitle JSON). Complete
  the mission in the profile and save, then end the game as "Complete". Allow the skip once that is done; skip / stop returns to the
  game lobby (campaign menu).

### TnSeqEvent_Interact: all 10 chapters, 245 instances
- **Class:** `TransGame.TnSeqEvent_Interact` ← `Engine.SequenceEvent`.
- **Links:** outputs `Touch`, `Untouch`, `Adjusting`, `Begin Use`, `End Use`. `Originator` = the interact actor
  (TnInteractButton, TnInteractHackingTerminal, TnInteractDetpack, TnInteractCorruptOmegaBattery, …).
- **Fired by** `TnInteractBase.TriggerKismetInteractEvent(EventType)` (decomp): `ActivateEventClass(TnSeqEvent_Interact, CurrentUser,
  GeneratedEvents, [EventType.default.SequenceEventMapType])`. `EndUse` also clears the pending AI interact.
- **Output mapping (RE 93790c1):** output index = `EInteractEventType` {0 Touch, 1 Untouch, 2 BeginAdjust (output "Adjusting"),
  3 BeginUse, 4 EndUse, 5 Null}. Null-type events fire nothing.
- **Rebuild:** needs the TnInteract* actors (their TnInteractAction* sequences are decompiled and present in the chapters), then fire the
  matching output per event type.

### SeqAct_TnAiMoveToActor: 9 chapters, 390 instances
- **Class:** `TransGame.SeqAct_TnAiMoveToActor` ← stock `Engine.SeqAct_AIMoveToActor` ← `SeqAct_Latent`. Own properties: `Range`
  (RANGE_Close / Medium / Striking), `DestinationActor`, `FocusActor`.
- **Links:** variables `Target`, `Destination`, `Look At`.
- **Behaviour:** `TnAiController.OnTnAiMoveToActor` clears any running move and stores `ScriptedMoveToAction`. The AI planner then
  moves there (`IsScriptedMoveExecuting`), stopping at `Range`. The stock `AIController.OnAIMoveToActor` is also decompiled.
- **Outputs (RE 93790c1):** Finished / Aborted / Out (inherited from SeqAct_AIMoveToActor). A new move aborts the running one;
  navigation success → Finished, failure → Aborted.
- **Rebuild:** a scripted-move goal in the AI runtime, firing those outputs. Without AI, teleport or ignore.

### TnSeqAct_ActivateTogethernessVolume: 9 chapters, 135 instances
- **Class:** `TransGame.TnSeqAct_ActivateTogethernessVolume` ← `SequenceAction`. Own: `HideTeleports` (always true), `InstigatingPawn`.
- **Links:** variables `Volume` (Targets), `Instigator`.
- **Behaviour:** `TnTogethernessVolume.OnActivateTogethernessVolume` (decomp):
  - Off on clients.
  - Spawns pending AI squad members (`AiSquad.SpawnPendingMembers`).
  - Notifies the game that the player is inside.
  - Teleports friendlies (up to 3) that are outside the volume to its `TeleportPoints`, preferring points out of the player's view,
    validated by `SpawnValidator.IsSafeSpawnLocation`.
- **Rebuild:** this keeps the AI squad (the two buddies) with the player across streaming. It needs the squad; single-player without
  buddies can treat it as a no-op.

## 2. The remaining 11 (by chapter count)

| class | chapters | instances | links | behaviour (decomp) |
|---|---|---|---|---|
| SeqAct_TnAssignTacticalVolume | 8 | 434 | in Assign / UnAssign / Toggle; var Target, Tactical Volume | `TnAiController.OnTnAssignTacticalVolume`: confine the AI to a TnTacticalVolume (Assign), release (UnAssign), or toggle |
| SeqAct_TnAiUseTurret | 7 | 54 | in Stay In Turret / Can Leave Turret; var Target, Turret Object | swaps the AI goal / action sets to `TR_AiGoalSet_UseTurret` / `TR_AiActionSet_UseTurret` (authored); handler in the AI planner (turret world state). **RE 93790c1:** has script (TransContent); "Can Leave Turret" also cancels the current plan |
| TnSeqAct_DownRevive | 5 | 12 | in Down / Revive | `TnAiController` / `TnPlayerController.OnDownRevive`: Down sets DownedEnabled, DrainHealthWhenDown and CanHealWhenDown, then `DownTransformer()`; Revive calls `GetRevive(FullRevive)` |
| TnSeqEvent_Downed | 5 | 16 | out Downed / Revived | fired by TnPawn on down / revive |
| TnSeqEvent_DetPack | 2 | 12 | out BaBoom | fired by `TnInteractActionFireDetpackEvent` (Originator = TnInteractDetpack) |
| TnSeqEvent_TankStatus | 2 | 4 | out FuelCellDamaged / FuelCellDestroyed | fired by `TnTankAiPawn` |
| SeqAct_TnAiJump | 1 (A3) | 6 | in Jump | `TnAiController.OnTnAiJump`: robot form and not downed → world state Reaction = 2, replan |
| TnSeqAct_AiDisableShootingBehavior | 1 (A2) | 6 | in Disable Shooting Behavior / Enable Default Behavior | swaps to `NoWeapon_Buddy` goal / action sets (authored). **RE 93790c1:** has script (TransContent); **both** inputs destroy the AI's inventory |
| TnSeqEvent_HealthStatus | 1 (A3) | 2 | out Healthy / Wounded | fired by `TnAiHealthMonitor` |
| TnSeqEvent_OmegaStatus | 1 (D5) | 2 | out Healthy, Wounded, Critical, Dying, GrabbedBattery, ShootingRockets, Corrupted, SentryDestroyed, LockingGrabOnEnemy, HeartArmorDestroyed | fired by `TnOmegaSupremePawn` (+ TnAiActionGrab / LockOnTarget) |
| TnSeqEvent_TrypticonEvents | 1 (A5) | 2 | out 18 boss beats (tail smash / strike L/C/R, shoulder / chest / back destroyed, back exposed, 5 test attacks) | fired by `TnTrypticonPawn` |

## 3. What this means for the campaign phase

- **Core set first:** these classes plus stock Kismet (RemoteEvent, Toggle, Gate, Delay, Touch, Interp, SetStreamingState, checkpoints).
  `MissionComplete` (movie + profile) and `Interact` (interact actors) can be implemented without AI. The other 13 depend on the AI
  squad / planner (6), the downed system (2), or a specific pawn (5: tank, Omega, Trypticon, detpack, health monitor).
- **Events** come from actors, so the actor classes (TnInteract*, TnTogethernessVolume, TnTacticalVolume, boss pawns) are the real
  work. Their decomp is available.
- **For RE (exe):**
  - the native movie path behind `SeqAct_MoviePlayer.PlayMovie`;
  - ~~`ActivateEventClass` index mapping~~: answered by RE 93790c1 (EInteractEventType order, above);
  - the AI planner's handling of `ScriptedMoveToAction` and the turret goal sets.
