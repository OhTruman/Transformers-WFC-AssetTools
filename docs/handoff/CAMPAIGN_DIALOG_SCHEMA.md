# Campaign dialog manifest: schema, rules and coverage (2026-10-18)

**What it is:** `manifests/next_map/<chapter>_dialog.json`, written by `scripts/wfc/vs_dialog.py`. It is the data side of the campaign
dialog runtime (design: Systems' `CAMPAIGN_AUDIO_DIALOG.md`).

**Sources, all read-only:**
- `manifests/authored.db` (effective values: authored + class defaults);
- `work/dialog/subtitles.json` (`dialog_subtitles.py`: per-language Duration + Subtitles read from the cooked packages);
- the 22 FaceFX `.fxa` files;
- the RE script decomp for the rules.

**Scope:** campaign chapters only. The writer refuses MP_ / UI_ maps, and the MP outputs are proven unchanged (§6).

## 1. File layout

```
{ map, generated_by, source, counts{...},
  conversations: [ { action, sublevel, comment, ducking_mixer_preset, ducking{preset values}, outputs[{output, to[]}],
                     fired_by_direct[], fired_by_events[],
                     lines: [ { index, cue, post_delay, speaker{link, actors, via}, face{link, actors, via},
                                cue_category, cue_secondary_category, cue_play_mixer_preset, cue_volume,
                                waves: [ { wave (<bank>.<wave>), dialog_character, speaker_code, speaker_facefx_actor,
                                           duration, subtitles[{t, text, use}],            <- INT (primary; the runtime reads INT)
                                           duration_fra, subtitles_fra[...],               <- FRA twin
                                           wav, wav_int, wav_fra, facefx[{fxa, group, anim}], subtitle_source } ] } ] } ],
  anim_notifies: [ { notify, anim_set, anim_sequence, time, sound_event, min_weight, cooked_in[] } ],
  anim_notifies_unmatched: [ { package, notify } ],
  sound_event_rules: { <HmSoundEvent>: { dialog_priority, dialog_group, notifies, other{} } },
  dialog_groups: { <HmSoundEventDialogGroup>: { instance_limit, retrigger_delay_min, retrigger_delay_max, initial_chance_to_play,
                                                parent, other{} } },
  dialog_event_managers: [ { object, values } ] }
```

### Conversations (`SeqAct_Conversation`, HM_Engine)

- **Lines** are `Lines[{SoundCue, PostDelayTime}]`.
- **Speaker:** line *i* is spoken by the actor on `VariableLinks[2i]` (`Speaker_i …`), with the face target on `[2i+1]` (`Face_i`).
  This pairing is CONFIRMED from `SeqAct_Conversation.CheckForErrors`.
  - Bindings resolve with the matinee resolver (`vs_matinee.var_targets`).
  - Kinds: placed actor, `CHARACTER:<ROBODEF>` for a TnSeqVar_Character, named, external, and runtime-spawned / written.
- **Wave per speaker:** a dialog cue's root holds one `SoundNodeWaveEvent` per `DialogCharacter` (e.g. `DialogCharacters.MGTRON`). The
  speaker's dialog characters select the wave (`CheckSoundCueForErrors`). So `waves[*].dialog_character` is the selector, and
  a line can carry several waves.
- **Playback:** `PlayDialog` hands the cue to the speaker's `HmDialogInterface.PlayDialog(SoundCue, true, Type, false, callback)`.
  - Play / Stop / Finished are driven by the dialog callback (`OnDialogEnded` → `IsFinished`).
  - Ducking: `DuckingMixerPreset` per conversation, plus the cue root's `PlayMixerPreset` (e.g. `GLB_DUCK_FOR_DX_9DB`).
  - PARTIAL: the native side of Play / Stop and the PostDelayTime wait are stubs in the decomp.
- **`fired_by_events`:** the same Kismet back-walk as the pawn factories and matinees.

### Subtitles and duration

- INT is primary; FRA is a twin column. Both are read straight from the cooked `WL_*_INT` / `WL_*_FRA` bank packages and the map
  `_LOC_int` / `_LOC_FRA` packages.
- authored.db holds only one language per wave path (the twins share the path), so its row can be the French one. Do not use it for
  subtitles.
- `subtitles[*].use` is `UseSubtitles` as authored. Many lines are false, which suggests the HUD shows only flagged lines (PROVISIONAL).
- `wav_int` / `wav_fra` are the language twins in `ExtractedAssets/content/_LOC/{int,FRA}`. The merged `content/<bank>/` wave is one of
  the two, not always INT; for Trypticon it is FRA (CAMPAIGN_FACEFX_RE.md).

### Speaker naming

- `speaker_code`: from the wave name (`DX_<CODE>_LK…`).
- `speaker_facefx_actor`: the `.fxa` that holds an animation of the same name.
- `dialog_character`: the cue's selector.
- `speaker.actors`: the bound actor or character slot. This one is authoritative.

### Anim notifies (`HmAnimNotify_Dialog`)

- The cook copies each animation (with its notifies) into every map package that uses it: 3,702 copies in the campaign.
- The copies keep the original object path, so each is matched to the parsed original (`TR_*_ANM_p`) by path. `cooked_in` lists the
  chapter packages carrying it.
- Unmatched copies would be listed in `anim_notifies_unmatched`; the count is 0 in all 10 chapters (§5).
- `time` is the notify's time in its AnimSequence `Notifies` array. `sound_event` is an `HmSoundEvent` (e.g.
  `SoundEvents_Dialog.DeathRX_NonVerbalDialog`); the character's dialog component resolves it to a cue at runtime.

## 2. Dialog event rules (CONFIRMED from script: `HM_Engine.HmDialogEventManager`, `Engine.HmSoundEventDialogGroup`)

**Per WorldInfo:** each world (each streamed sublevel's TnWorldInfo) has an `HmDialogEventManager` (`dialog_event_managers`). Its
`DefaultDialogGroup` is used when an event has none.

**`Play(Target, SoundEvent)`:**
1. Ignored on clients (NetMode 3) and while the manager is disabled (`DisabledTimer > 0`).
2. The group is `SoundEvent.DialogGroup`, or the default group.
3. **`CanPlayDialog`** walks from that group up the `ParentDialogGroup` chain. For each group:
   - disabled → no;
   - `RetriggerTimer > 0` → no;
   - if `InstanceLimit != 0` and the group already has `InstanceLimit` playing:
     - the new event's `DialogPriority` must be **higher** than the lowest-priority playing instance;
     - otherwise no;
     - if higher, that instance is **stopped** (`StopDialog`) and removed (preemption).
4. **`PlayInternal`** walks the same chain:
   - inserts the instance into each group's list, sorted by priority, ascending;
   - when a group reaches its limit (or has limit 0), it arms `RetriggerTimer = RandRange(ReTriggerDelayMin, ReTriggerDelayMax)`;
   - then `Target.PlayDialogEvent(SoundEvent, …)` plays it.

**Timers and chance:**
- `Tick` counts every group's `RetriggerTimer` down to 0.
- A new playback group starts with `RetriggerTimer = GetInitialDelay()`: 0 when `RandomInt(100) < InitialChanceToPlay`, else a
  retrigger delay. So `InitialChanceToPlay` is the chance that a group may fire immediately.

**Control:** `EnableGroup` / `DisableGroup` (the latter stops all of the group's dialog); `DisablePlayback` (stops everything, with a
1 s disable timer, ref-counted).

**Data fields:**
- `sound_event_rules[*].dialog_priority` / `dialog_group`;
- `dialog_groups[*]`: `instance_limit`, `retrigger_delay_min / max`, `initial_chance_to_play`, `parent`.
- An event without `DialogPriority` keeps the class default (null here means not authored).

## 3. Not decoded / not in data

- Native halves of `HmDialogInterface.PlayDialog` / `StopDialog` and the conversation's PostDelayTime timing.
- How `SoundEvent` → cue resolution works per character (`HmDialogComponent` / `DialogCharacters`) is script on the component, not in
  this manifest. It needs the character's dialog component data (a follow-up if Systems wants it).

## 4. Hand check (D5_OME)

- All 42 lines: wave, INT and FRA subtitles, FaceFX animation and bound speaker present.
- **Durations:** for all 84 wave files (42 INT + 42 FRA), the cooked `Duration` matches the file's length within 5 ms (median 2 ms).
- **Samples:**
  - Megatron `DX_MGTRON_LK001521`, 2.71 s: "Stop whining and start shooting, Breakdown!", fired by `CKP_02_StartStage2Dialog`.
  - Omega Supreme `DX_OMEGAS_LK000591`, 5.70 s: "Detected: system corruption. Action: release counter-virus."
- **Notifies:** all 165 have anim, time and SoundEvent.

## 5. Results over the 10 chapters (2026-10-18)

**Conversations and lines:**
- 892 conversations: 6 of the 898 in the cook sit in packages outside the exported levels.
- 1,561 lines. 858 conversations have a firing event within 12 Kismet steps.
- **Speakers:** 1,555 lines have a bound speaker. The 6 unbound ones go through SeqVar_Named (`Conversationer01` / `02`, `Brute1`) whose
  VarName exists in no exported level; they are listed, not guessed.
- **Waves:** 1,603 waves, all with INT and FRA subtitles. 1,403 have a FaceFX animation of the same name.
  - One line has an empty SoundCue in the data.
  - 56 waves are in their cues but were never extracted to ExtractedAssets (e.g. Ironhide `DX_IRNHDE_*`); `wav_extracted: false`.
    Their subtitles and duration come from the cook.

**Anim notifies:**
- 3,702 copies cooked into the chapters, all matched to their parsed originals (0 unmatched); 2,101 distinct per chapter.
- They use 126 sound events in 85 dialog groups.

**Dialog event managers:** 430, one per world (streamed sublevel).

Per chapter: `CAMPAIGN_PIPELINE_SUMMARY.md` §1e and each chapter doc's section 8.

## 6. MP gate

`work/dialog/mp_snapshot_before.json` vs `_after.json` → `work/dialog/mp_gate.json`:
- SHA-256 of every `manifests/maps/MP_*/*`, `manifests/next_map/MP_*` and `manifests/*.json` file;
- size and mtime of every file under `ExtractedAssets/VerticalSlice/Maps/MP_*`.
