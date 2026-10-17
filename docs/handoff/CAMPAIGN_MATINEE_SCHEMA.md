# Campaign matinee export: schema and coverage (2026-10-18)

**What it is:** `manifests/next_map/<chapter>_matinee.json`, written by `scripts/wfc/vs_matinee.py`. It is the data side of the campaign
matinee player: every InterpData of a chapter with its groups and tracks, the actors each group binds to, and the Kismet that plays
it.

**Source:** `manifests/authored.db` only, read-only. Values are *effective*: authored values with class defaults filled in, so a key
missing from the cook (e.g. `MoveFrame` at its default) still appears.

**Scope:** campaign chapters only. The writer refuses MP_ / UI_ maps, and the MP outputs are proven unchanged (§5).

**Status:** decoded fields are CONFIRMED from the cooked data. Runtime semantics marked PROVISIONAL are stock UE3 behaviour that RE has
not checked against WFC's native code.

## 1. File layout

```
{ map, generated_by, source,
  counts: { interp_data, played, not_played_by_any_seqact_interp, seqact_interp, seqact_interp_without_data_in_levels,
            groups, director_groups, groups_without_bound_actor, group_binding{director|bound|bound_runtime|empty_link|no_link|unresolved},
            tracks_by_class{}, undecoded_track_classes{}, unresolved_bindings{} },
  matinees: [ {
     interp_data, sublevel, length (s), path_building,
     played_by: [ { action (SeqAct_Interp), class, comment, looping, play_rate, rewind_on_play, no_reset_on_rewind,
                    rewind_if_already_playing, force_start_position, force_start_time, skippable,
                    group_bindings: { <group name>: { actors: [...], via: [...] } },
                    fired_by_direct: [ {op, class, output} ], fired_by_events: [ {event, class, EventName, Originator, ObjComment,
                    MaxTriggerCount, depth} ] } ],
     groups: [ { name, class (InterpGroup | InterpGroupDirector), binding, bound: { <action>: {actors, via} },
                 tracks: [ { track, class, title, disabled, ...decoded fields (§2) } ] } ] } ] }
```

- **`fired_by_events`:** the same Kismet back-walk as the pawn-factory manifest. It starts at the Play input (index 0) and walks up to
  12 ops back to the nearest SeqEvent_* / TnSeqEvent_* (e.g. remote event `StartIntroMovie` for the D5 intro).
- **SeqAct_Interp outputs** (RE 27d1ee0): only **Completed** and **Aborted**.
  - A skip (CancelMatinee) fires Aborted.
  - A reverse play that reaches the start fires Aborted.
  - A mid-way Stop fires nothing.
  - The runtime semantics (director cuts, MoveFrame, AnimControl, FaceFX) are in `RE-Workspace/work/handoff/CAMPAIGN_MATINEE_RUNTIME_RE.md`.
- **Times** are seconds on the matinee timeline. Keys before 0 occur: lead-in keys are authored that way.
- **Units are as authored:** UE units (cm) and degrees for move tracks, UE axes (X, Y, Z = UE, not glTF). Convert with
  `vs_common.ue_points_to_gltf` / the pipeline's C matrix like every other position.

## 2. Track classes (all 19 seen in the campaign)

| class | decoded fields |
|---|---|
| InterpTrackMove | `move_frame` (IMF_World / IMF_RelativeToInitial), `rot_mode`, `use_quat_interpolation`, `pos` / `euler` curves, `lookup` [{t, group}] |
| InterpTrackDirector | `cuts` [{t, camera_group, transition}]: camera_group is a group name in the same InterpData |
| InterpTrackSound, InterpTrackDialog | `keys` [{t, cue, volume, pitch}], `volume_pitch` curve, `continue_on_end`, `continue_on_skip` |
| InterpTrackEvent | `keys` [{t, event}]: fires the SeqAct_Interp output of that name; `fire_forwards` / `fire_backwards` / `fire_when_jumping_forwards` |
| InterpTrackToggle | `keys` [{t, action}]: WFC's ETrackToggleAction is {ETTA_Off, ETTA_On, ETTA_Toggle} (RE 27d1ee0); the campaign uses only On (3,058) / Off (3,010) |
| InterpTrackAnimControl | `slot`, `keys` [{t, anim (AnimSeqName), start_offset, end_offset, rate, looping, reverse}], `weight` curve |
| InterpTrackFaceFX | `keys` [{t, group, anim}]: FaceFX group + sequence, played from the bound actor's .fxa (CAMPAIGN_FACEFX_RE.md) |
| InterpTrackFloatProp / VectorProp / ColorProp | `property` (e.g. FOVAngle on camera groups), `curve` |
| InterpTrackFloatMaterialParam / VectorMaterialParam | `param`, `materials`, `curve` |
| InterpTrackActorFloatMaterialParam / ActorVectorMaterialParam | `param`, `curve` (on the bound actor's materials) |
| InterpTrackFade | `curve` (0 = clear, 1 = black), `persist_fade` |
| InterpTrackSlomo | `curve` (time dilation) |
| InterpTrackColorScale | `curve` (scene colour scale) |

- **Curve key:** `{t, v, arrive, leave, mode}`, i.e. FInterpCurve InVal / OutVal / ArriveTangent / LeaveTangent / InterpMode.
- **Interp modes:** WFC's Core EInterpCurveMode is {CIM_Linear, CIM_CurveAuto, CIM_Constant, CIM_CurveUser, CIM_CurveBreak}, bytes 0–4.
  There is no CIM_CurveAutoClamped in this engine (RE 27d1ee0).
  - Campaign counts: CurveAuto 89,702, Linear 28,021, CurveUser 5,869, CurveBreak 2,129, Constant 934.
  - The names in the export are the cooked FNames, so no name table of ours is involved.
  - Evaluate as UE3 FInterpCurve: Hermite with the stored tangents, linear, or step for Constant.
- **Undecoded:** a class not in the table would be exported with its raw props and counted in `counts.undecoded_track_classes`. Over the
  10 chapters that count is empty, except for one bare `InterpTrack` with no properties (A-chapter data, nothing to decode).
- **Move tracks without position keys** (e.g. 2 in the D5 intro): rotation-only or lookup-only tracks. They are exported as authored.

## 3. Group bindings

A group binds to the objects linked to the SeqAct_Interp variable link whose name equals the group name. `via` says how each one was
resolved:

| via | meaning |
|---|---|
| `object` / `object_list` | a SeqVar_Object (ObjValue) / SeqVar_ObjectList: a placed actor (opath) |
| `player` | SeqVar_Player: `PLAYER` (all players) or `PLAYER:<index>` |
| `character` | TnSeqVar_Character: `CHARACTER:<ROBODEF>`. A character slot, not a placed actor; the runtime binds the pawn of that character definition (e.g. Megatron in D5) |
| `runtime_spawned` | an empty SeqVar_Object written by a pawn factory's "Spawned" output: `SPAWNED_BY:<factory> (<archetype>)` |
| `runtime_written` | an empty SeqVar_Object written by another Kismet op (a writeable link, or an event's Instigator / Originator): `WRITTEN_BY:<op> [<class>.<link>]` |
| `named:<VarName>` | a SeqVar_Named, followed to the variable(s) with that VarName and resolved recursively |
| `external:<ExtVarName>` | a SeqVar_External, followed through the parent sequence's variable link of that name |
| `object_empty` | an empty SeqVar_Object nothing in the exported levels writes: filled by script at runtime, or unused |
| `unresolved:<class>` | any other variable class, listed and never guessed |

**Group binding states** (`binding`):
- **director:** the InterpGroupDirector. No actor; it drives the player's view (cuts, fade, slomo, colour scale).
- **bound:** at least one placed actor resolved.
- **bound_runtime:** resolved only to what fills the slot at runtime (`SPAWNED_BY` / `WRITTEN_BY` / `CHARACTER` / `PLAYER`).
- **empty_link:** the action has a link for the group, but nothing is attached to it in the authored data. No InterpGroupInst / GroupActor
  is cooked either, so nothing else binds it.
- **no_link:** the action has no link for the group at all.
- **unresolved:** links exist, but none of them resolved.

**Runtime note (stock UE3 `USeqAct_Interp::InitInterp`; RE 27d1ee0 rates it HIGH for WFC):**
- A group without an actor still gets a group instance. Its Move / Toggle / AnimControl / material / property tracks have nothing to
  act on and do nothing.
- Director, Event and Fade / Slomo / ColorScale tracks need no actor.
- A Sound track without an actor plays at the listener.

## 3b. Results over the 10 chapters (2026-10-18)

**Totals:** 3,575 InterpData, of which 3,551 are played by a SeqAct_Interp (24 have no player in the exported levels); 3,614
SeqAct_Interp; 11,250 groups.

**Groups by binding state:**

| state | groups | notes |
|---|---|---|
| director | 444 | |
| bound | 9,358 | to placed actors |
| bound_runtime | 118 | character slots, pawn-factory spawns, Kismet-written variables |
| empty_link | 489 | |
| no_link | 676 | |
| unresolved | 165 | see below |

**The 165 unresolved, listed rather than guessed:**
- **149** link a SeqVar_Object that is **empty in the cook**, and nothing in the exported levels writes it. 15 more are referenced only by
  other consumers (ToggleHidden, Destroy, PlaySound, ChangeCollision, ActivateRemoteEvent).
  - So these 164 are empty in the authored data, and the group is a no-op at runtime (PROVISIONAL).
  - Example: `A1_IAC_DecoInt_Design_m … RobotArmActions.SeqVar_Object_15191`.
- **16** are SeqVar_External links (`Masher`, `Glyph_MatInst`, `Lightbeam_MatInst`, `Masher_MatInst`) whose enclosing-sequence variable
  is itself one of those empties.
- **1** is a SeqVar_ObjectList with an empty list.

**Track coverage:** every track class is decoded. The only undecoded item is one bare `InterpTrack` that has no properties.

**Hand check, D5 intro cutscene** (CINE_LevelIntro: 9 matinees, 28.4 s, fired by remote event `StartIntroMovie`):
- every director cut targets an existing camera group;
- all 22 sound cues exist;
- both FaceFX sequences are in the .fxa files;
- the 10 FOV groups bind to CameraActors;
- the Megatron / Soundwave / Breakdown groups bind to their character slots, and Omega Supreme to its two pawn factories.

## 4. Per-chapter counts

Each chapter doc (`CAMPAIGN_PILOT_<chapter>.md`, section 7) carries the counts: InterpData, played, groups by binding state, tracks by
class, and undecoded / unresolved totals. The summary carries the 10-chapter table.

## 5. MP gate

- The writer runs only on campaign chapters, and writes only `manifests/next_map/<chapter>_matinee.json`.
- Proof: `work/matinee/mp_snapshot_before.json` vs `_after.json`:
  - SHA-256 of every `manifests/maps/MP_*/*`, `manifests/next_map/MP_*` and `manifests/*.json` file;
  - size and mtime of every file under `ExtractedAssets/VerticalSlice/Maps/MP_*`;
  - identical before and after (`work/matinee/mp_gate.json`).
