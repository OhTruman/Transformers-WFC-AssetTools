# MP_IAC_Streets multiplayer gameplay setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/gameplay.json`**. It supersedes the raw `spawnpoints.json` for meaning:
effective values merged with class defaults, cross-references, modes, Kismet and validation.
Regenerate: `AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_gameplay.py`. Handoff: **Gameplay** (and Systems for pickups/objectives).
All gameplay actors live in the persistent `MP_IAC_Streets_BASE_m`. Units: UE units.

## Modes (Coalesced config, CONFIRMED)
`TransLevels.ini [MP_IAC_Streets_Base_m TnDataProvider_MapInfo]`: MapId 508, PresenceId 17, thumbnail `UI_LevelThumbnails_p.MP_Streets`.
| tag | playlist (id) | game class | min players | time limits (s) | objective rule |
|---|---|---|---|---|---|
| DM | Deathmatch (2) | TnFreeForAllGame | 4 | 600/900/1200 | — |
| TDM | Civil War (1) | TnVersusGame | 4 | 600/900/1200 | — |
| CTF | Code of Power (3) | TnVersusGame | 4 | **240/300/360** | `TnGameRules_SingleFlagCTF` (TimeBetweenRounds 5, IndividualScore via ScoreFlags 10) |
| KOTH | Power Struggle (4) | TnVersusGame | 4 | 600/900/1200 | `TnGameRules_ScoreKingOfTheHill` (IndividualScore 1) |
| EXT | Countdown to Extinction (5) | TnVersusGame | 4 | 600/900/1200 | `TnGameRules_ScoreBombingRun` (IndividualScore 10) |
| DOM | Conquest (7) | TnVersusGame | 4 | 600/900/1200 | domination |
Game class defaults: MaxPlayers 10, MaxSpectators 2, MaxIdleTime 180, DefaultPawnClass `TnPlayerPawnMultiplayer`.

## Player starts and spawn clusters
* **60 team starts: 30 Autobot, 30 Decepticon.** The Autobot team is the unset enum value 0 of `ETnTeamGameTeam`. There are also **24 free-for-all starts**.
* **12 `TnSpawnCluster`s: 6 Autobot, 6 Decepticon, all single-team.** Eleven hold 5 starts and one holds 4. Free-for-all starts are not clustered.
  `FactionNeutralGameTypes = [TDM, KOTH, DOM]`: in those modes clusters are used regardless of faction (cluster scoring is native).
* Validation: 59/60 team starts are in exactly one cluster and none is in two. **`TnTeamPlayerStart_2650`** (Decepticon) is in no cluster.
  It sits 11.9 m from the 4-member Decepticon cluster `TnSpawnCluster_3906`, almost certainly that cluster's intended fifth member
  (INFERRED authoring omission in the original data, preserved as-is).

## Pickups
| factory | count | respawn | inventory (CDO payload) | effect |
|---|---|---|---|---|
| TnAmmoCratePickupFactory | 14 | **30 s** | TnAmmoCratePickup: refills ValidWeaponTypes Primary/Secondary/Vehicle (amount native) | `FX_Pickups_p.FX.Pickup_FX` highlight beam + crate mesh `PROP_NEU_AmmoPickup_STAT` |
| TnHealthPickupFactory | 9 | **60 s** | TnHealthPickup: **AddedHealth 50** | `HealthPickup_FX` (its `Pickup_FX` component is cooked but never attached) |
| TnOverShieldPickupFactory | 1 | **120 s** | TnOverShieldPickup: no authored amount or duration (native) | `OvershieldPickup_FX` (its `Pickup_FX` component is never attached) |

**Visibility rule (CONFIRMED; RE script decompilation, `RE-Workspace/notes/MILESTONE04_STREETS_PICKUP_OBJECTIVE_PRESENTATION.md` §1):**
* `SetPickupVisible` activates the effect and `SetPickupHidden` deactivates it.
* A factory is visible (mesh + effect) while available and hidden from pickup until `RespawnTime`.

**TDM pickup state** (vertical-slice mode; DM identical; CONFIRMED):

| factories | TDM state | drawn / touchable |
|---|---|---|
| ammo crates (14) | active | crate mesh + beam while available; touchable |
| health (9) | active | `HealthPickup_FX` while available; touchable |
| overshield (1) | active | `OvershieldPickup_FX` while available; touchable |
| flag factories (2) | **Disabled** (no SingleFlagCTF rule) | hidden, `SetCollision(false,false)`, no touch |
| bomb factory (1) | **Disabled** (no ScoreBombingRun rule) | hidden, no collision, no touch |

In total: 24 pickup effects + 14 crate meshes drawn. Machine-readable: `render_index.json` `tdm_render_state` /
`pickup_fx_components`, and the `state_behaviour` section of `manifests/streets_pickup_factories.json`.

## Objectives
Two team bases plus central and spread objectives. Objective volumes are TriggerVolumes with world polygons (12/12 resolved).
| objective | actors | key authored values |
|---|---|---|
| Flag spawn (CTF) | 2: base 0 (12515,−56191) and base 1 (31938,−39809, DefenderTeamIndex 1) | RequiredGameRuleClass SingleFlagCTF, marker "Code Of Power", inventory `TnWeaponFlag` |
| Flag capture point | 2, at each base | volumes `TriggerVolume_13959` (base 0) and `_4887` (base 1) |
| Bomb spawn (EXT) | 1, centre (20480,−40385) | RequiredGameRuleClass ScoreBombingRun, WaitAfterScoreTime 5, inventory `TnWeaponBomb` |
| Bomb plant point | 2, at each base; **same volumes as the capture points** | FuseTime 15, DefuseTime 5, DetonateRadius 5000, DetonateDamage 9999, sound `MP_BOMB_EXPL_IMPT_WORLD` |
| Domination point (DOM) | 3, PointNumber 0/1/2 | CaptureTime 20, ScoreInterval 3, ScoreAmount 1, PersonalScore 2, capture colours (red/blue linear), anims `EnergonTotem*` |
| King-of-the-Hill zone (KOTH) | 5 | marker "Active Node", ZoneActiveTime 60, ScoreInterval 1, announcer events for neutral/contested/captured/moved |
* Spawn modifier on the flag, bomb and KOTH objectives: `TnSpawnModifierRuleInverseDistance`, CutoffDistance 5000, Factor −50. Spawning
  is penalized near the objective (scoring formula native).
* Base 0 actors leave `DefenderTeamIndex` unset (byte default 0 = Autobots); base 1 sets 1 (Decepticons). Recorded as `defender_team`.
* **Single-flag CTF rounds (CONFIRMED, RE script):** `TnGameRules_SingleFlagCTF.SetupRoundStart` calls `ActivateIfMatchingTeam`
  on each flag factory.
  * The factory whose `DefenderTeamIndex` matches the defending team goes to `Pickup`; the other one Sleeps (hidden, beam off).
  * Taken → Sleeping (RespawnTime 9999999); returned → `Pickup` immediately.
  * Bomb: returns after `WaitAfterScoreTime` 5 s after a score, immediately otherwise.
* **Mode gating of objective actors (CONFIRMED, RE script + Kismet), in modes other than their own:**
  * flag/bomb factories are Disabled;
  * capture/plant points are inert;
  * domination totems are hidden outside DOM;
  * KOTH zones are hidden except the one active zone in KOTH;
  * the 4 objective bases are visible only in CTF/EXT and still collide while hidden.
  * Full table: `render_index.json` `mode_visual_state`.

## Kismet (BASE Main_Sequence, CONFIRMED graph)
* `SeqEvent_GameplayStarted` →
  * `ActivateRemoteEvent "StartBeam"` → sub-sequence **SkyBeam**: a looping 9.0 s matinee on 3 StaticInterpActors (`InterpTrackMove`,
    relative-to-initial, quaternion interpolation). The rotation sways about 19.4° at 4.5 s and returns at 9 s; full curves in json.
  * `SeqCond_GameRuleActive(ScoreBombingRun)` "EXT" **or** `(SingleFlagCTF)` "CTF" → `SeqAct_ToggleHidden` input **UnHide** on 4
    InterpActors: objective bases `Base_A`, `Base_D` and two `RepairNodeB` props. All start `bHidden`, so **they appear only in EXT and CTF**.

## Other
* `CameraActor_13199`: FOV 90, aspect 16:9 (no Kismet reference on Streets; likely a spectator/intro view, INFERRED).
* 8 StaticInterpActors (3 ART, 5 BASE; 3 of the BASE ones are the sky beam).
* `TnAssetReferencesMultiplayer` lists every MP transformer definition (Optimus, Bumblebee, Megatron …) for cooking.

## Native / unknown
Cluster and spawn scoring; ammo-crate refill amount and overshield strength/duration; DOM capture contest rules beyond the authored
timings.

Resolved since 2026-10-01 by RE script work:
* the single-flag round flow (above);
* KOTH zone selection: a random initial zone at MatchStarting, then `ActivateNewZone` every `ZoneActiveTime` 60 s. The exact choice
  of the next zone is in that script (see the RE note).
