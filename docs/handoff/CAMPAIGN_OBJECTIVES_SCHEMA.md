# Campaign objectives export (2026-10-18)

**What it is:** `manifests/next_map/<chapter>_objectives.json`, written by `scripts/wfc/vs_objectives.py`. It is the objective text source
for the campaign HUD.

**Sources:**
- `authored.db`: TnWorldInfo `_ObjectiveBank` and `SeqAct_TnSetCurrentObjective`;
- `ExtractedAssets/config/Coalesced_{int,FRA}.json`: the decoded Game Dump `Coalesced.int` / `.FRA`, section `[Objectives]` of
  `TransGame.int` / `.fra`.

**Semantics:** RE `CAMPAIGN_HUD_OBJECTIVES_RE.md` (b8f071e).

## Layout

```
{ map, generated_by, source,
  counts: { bank_keys, setters, setters_with_key_in_bank, setters_key_not_in_bank, setters_clearing, setters_with_firing_event,
            bank_keys_never_set, keys_without_int_text, banks_found },
  bank_owner,                      # the persistent level's TnWorldInfo
  bank: [ { index, key, key_raw, text{int, fra, int_all, fra_all}, set_by[] } ],         # _ObjectiveBank in order
  setters: [ { action, sublevel, key, key_raw, clears_objective, bank_index, comment, text{...}, properties{},
               fired_by_direct[], fired_by_events[] } ],
  keys_without_int_text[] }
```

**Field notes:**
- **`key` vs `key_raw`:** `key` is the trimmed authored key, and all matching uses it. `key_raw` is the key exactly as authored. One bank
  entry carries a trailing space (A4 `"A4_OBJ_OBJ10 "`); the .int keys never do.
- **`clears_objective`:** the setter's Description is empty or blank (A1 uses `" "`). Read as "clear the current objective"
  (PROVISIONAL: inferred from the data, not checked in RE's doc).
- **`text.int`:** the first value of the key in `[Objectives]`. `int_all` / `fra_all` list every value when a key repeats.
- **`fired_by_events`:** the same Kismet back-walk as the other manifests (e.g. D5 remote event `Set_Objective_DestroyTurrets`).

## Results (10 chapters)

- 88 bank keys and 179 setters. Every setter has a firing event; 41 setters clear the objective.
- Every bank key is set at least once, and every key has INT and FRA text.
- **One key is set but missing from its bank:** D1 `D1_ORB_OBJ08` ("Confront Starscream"). It has text in `[Objectives]`.
  - Whether the original HUD shows a key that isn't banked is UNKNOWN; RE says Description is a key *from* the bank. Treat it as
    PROVISIONAL.
  - Frontend (2026-10-18): the original's SetCurrentObjective logs an unknown (unbanked) objective as an error and shows nothing; Frontend keeps that refusal.

## MP gate

The writer refuses MP_ / UI_ maps. Before and after hashes of the MP manifests and the ExtractedAssets MP map files are identical
(`work/dialog/mp_gate.json`, rerun for this export).
