# WFC frontend / game flow: authored data (2026-10-03)

Asset recovery only. The shipped frontend is the specification: nothing here is a redesign. Behaviour of every script or native
call is handed to RE (`manifests/frontend_re_handoff.json`).

* **Generator:** `scripts/wfc/fe_frontend.py`. Run it with no arguments; it reads authored.db, inventory.db and ExtractedAssets.
* **Validator:** `scripts/wfc/validate_frontend.py`, which writes `logs/validate_frontend.json`. Current result: 5,638 checks,
  0 failures.

## Manifests (`AssetTools/manifests/`)

| file | content |
|---|---|
| `frontend_flow.json` | boot config, movie files, full Kismet graphs of the 6 UI levels, ordered movie chain, GFx open/close, fscommands, music/ambience |
| `frontend_gfx.json` | all 38 cooked Scaleform movies (`content/UI_*/*.gfx`); fields listed below |
| `frontend_bindings.json` | the 14 ActionScript binding classes (`GFxEngine.ExternalInterfaceTypeNames`): InterfaceName and exported functions; input command → pad key table |
| `frontend_re_handoff.json` | every AS↔script boundary crossing, grouped by resolution status (see below) |
| `frontend_maps.json` | every `TnDataProvider_MapInfo` MP map: ids, file, modes, faction, thumbnail, INT/FRA names, cooked presence, menu order |
| `frontend_modes.json` | GameModeInfo (settings name, INT/FRA names), 9 playlists, playlist manager, `TnOnlineGameSettings*` classes, maps per mode |
| `frontend_audio.json` | UI-level music, ambience and one-shots; AS `PlaySound` names resolved to cues; all 104 UI cues; each with WAVs |
| `frontend_loading.json` | loading config, loading movies, LoadScreen GFx records, 26 tips, Kismet hooks |
| `frontend_localization.json` | every GFx `$File.Section.Key` key resolved INT/FRA; UIText / UIText_360 / GFxUI sections; frontend sections of TransGame.int |

Fields of each `frontend_gfx.json` record:
* exports;
* exported or labelled sprites with frame counts, frame labels and instance names;
* root labels;
* DefineEditText fields (variable, font, initial text);
* imports (`gfxfontlib.swf`, `SharedComponents.swf`) and embedded fonts;
* `.swf` names loaded at runtime;
* localization keys and font aliases;
* `_global` callbacks the movie defines;
* `ExternalInterface.call` bridge calls with their binding class;
* UI sound cue names and input handler names;
* extracted PNGs;
* the cooked `GFxMovieInfo` / `GFxMovie` objects (ExternalTextures, CaptureKeys, References).

## Startup → main menu (CONFIRMED, authored)

1. **Boot.** `Xe-TransEngine.ini [URL] Map=UI_FrontEnd_m`.
2. **Open MovieLoader.** In UI_FrontEnd_m: `TnSeqAct_OpenFrontEnd` → `SeqAct_InstallGame` → `GFxAction_OpenMovie`
   `UI_GFxFrontEnd_p.MovieLoader_GFX_1`.
3. **MovieLoader sends one of two fscommands:**
   * **`enterMovieSequence`** plays four movies, each starting on the previous one's Stopped output:
     `Logo_Activision` → `Logo_Hasbro` → `Logo_HighMoon` → `FMV_intro`. Then the front-end setup below runs.
   * **`enterFrontEnd`** runs the same setup without the movies.
   * Which one is sent is decided in MovieLoader's ActionScript through the Game bridge (`HasWatchedIntroMovie`). That decision
     is RE scope.
4. **Front-end setup:**
   * orbit camera matinees;
   * a RemoteEvent and reverb;
   * music `BL_LVL_HUD_INTERFACE.FRONTEND_MX_ORBIT_01` (fade-in 0.25 s);
   * sound `FRONTEND_WHSH_REVEAL` (authored silent: the cue has no wave);
   * `SetLoadingMovieFilename`, then ToggleHUD.
5. **Main menu.** `FrontEnd_GFX`:
   * menus `mc_menuPressStart`, `mc_menuMain360`, `mc_menuSolo`, `mc_menuOnline`, `mc_menuCampaign`;
   * the localized logo comes from the external textures `UI_TransformersWFCLogo_p.TransformersWFCLogo_<lang>`;
   * fscommand `startMainMenuCamera` starts a matinee;
   * submenus load as `.swf` files at runtime (Accounts, Brightness, CharacterSelect, CustomTransformers, DifficultySelect,
     Extras, OnlineFriends, Settings, MessagePrompt, TextPrompt).
6. **Logo audio.** `[Engine.MovieSettings] MoviesToAlwaysPlaySound` lists the three logo movies; their audio is inside the
   movie files.

## Multiplayer

* **Lobbies.**
  * Party lobby: `UI_PartyLobby_m` with `PartyLobby_GFX`; music `MP_PARTY_LOBBY_MX`, bed `MP_PARTY_LOBBY_AMB_BED_CUST_MENU`.
  * Game lobby: `UI_Lobby_m` with `GameLobby_GFX`; music `MP_LOBBY_MX`, bed `MP_LOBBY_AMB_BED`.
  * Character customization: `UI_CharacterCustomization_m`, driven by fscommands from the lobby movies (`hide/unhide/fadein/glow`
    Autobot / Decepticon, `initStreamingLvl`, …).
* **Bridge calls** go out through `Online.*` (PlayPlaylist, EditGameMode, SetSelectedMapID, SubmitMapVeto, HostOnlineGame …).
  * **134 of 175** distinct bridge calls match a function exported on the binding class. CONFIRMED name match.
  * **14** have a same-name function only on another class (e.g. `HostOnlineGame` on `TnPartyLobbyGame`); the dispatch path is
    UNKNOWN.
  * **27** have no script function of that name at all. They are native-only or dead AS code; UNKNOWN, for RE.

## Maps (`frontend_maps.json`)

* 13 MapInfo sections in `TransLevels.ini`; **10 are cooked**.
* Menu order is the ini section order (HIGH). Online ids: MapId 501–513.
* All versus maps list DM / TDM / CTF / KOTH / EXT / DOM. BrokenHope and Remnant list SV (Escalation) only.
* Fortress, Havoc and Forsaken (Tranquillity) are configured but **not cooked**; they use the `LevelMultiGeneric` thumbnail.
* **Streets** (reference record):
  * internal name `MP_IAC_Streets_Base_m`, MapId 508, PresenceId 17;
  * INT "Streets", FRA "Rues";
  * thumbnail `UI_LevelThumbnails_p.MP_Streets` → `content/UI_LevelThumbnails_p/MP_Streets.png`;
  * all six versus modes;
  * cooked package `MP_IAC_Streets_BASE_m`.
* **Description:** no MapInfo description string is authored for any map (UNKNOWN / not shipped).
* **Per-map loading art:** none. Loading uses one shared movie (see Loading).

## Modes (`frontend_modes.json`)

| tag | INT name | FRA | playlist id | menu visible |
|---|---|---|---|---|
| TDM | Team Deathmatch | Match à élimination en équipe | 1 (CivilWar, default quickmatch) | yes |
| DM | Deathmatch | Match à élimination | 2 | yes |
| DOM | Conquest | Conquête | 7 | yes |
| CTF | Code of Power | Codex | 3 | yes |
| EXT | Countdown to Extinction | Extinction | 5 | yes |
| KOTH | Power Struggle | Lutte pour le pouvoir | 4 | yes |
| SV | Escalation | Escalade | 6 | no |
| CP / CCP | Co-op / Competitive Co-op | | 100 / 101 | no |

* **Menu order:** the `TnOnlinePlaylistManager.Playlists` order is TDM, DM, DOM, CTF, EXT, KOTH, SV, CP, CCP. HIGH that the
  menu follows it.
* **One Must Fall (OMF):** has a GameModeInfo but no playlist.
* **Mode icons:** no per-mode icon asset was found by name. UNKNOWN.

## Loading presentation (`frontend_loading.json`)

* **Config.** `[LoadingMovie]`:
  * `InitialStartupFileName=TF_InitialStartup`;
  * `DefaultFileName=TF_LoadingScreen`;
  * `AlphaFileName=UI_GFxLoading_p.LoadScreenAlpha_GFX`.
* **Movies.** `TF_LoadingScreen_INT/FRA`, `TF_InitialStartup` (+ EU/NA, INT/FRA variants) and `LoadingScreenAlpha` are
  extracted. The movie region is `RegionLoadingScreen=0.2,0.6,0.8,0.9`.
* **LoadScreen_GFX symbols:** `mc_levelInfo` (map name) and `mc_engageText` (tips).
  * Script calls the `_global` callbacks `SetLevelText` / `AddEngageText`. The caller is RE scope.
* **Tips:** 26 `TnOnlineGameSettingsBase.EngageText` strings (INT).
* **Music:** none authored for loading. Movie audio is in the movie file (HIGH).
* **Kismet:** `SeqAct_SetLoadingMovieFilename` (native `TnOnlineActionScriptBindingNative.SetLoadingMovieFilename`).

## Localization

* GFx keys resolved: **531 of 544** INT (FRA alongside).
* 3 keys are runtime-suffixed prefixes (`Extras.Concept*`, `Extras.Movie*`, `Extras.UnlockWith*`); HIGH.
* 10 are UNKNOWN: they exist in no shipped .int file. These are Tutorials Car/Jet/Tank 01–02, `HUD.Jammed`,
  `PlayerList.GamerCard`, `Customization.Upgrades` and `Errors.MustBeLoggedInLB`.

## Confidence

| level | items |
|---|---|
| CONFIRMED | config values; Kismet links and the movie order; GFx tags, labels, exports and bytecode strings; cue graphs; MapInfo and playlist records; binding classes and function exports |
| HIGH | menu order equals ini/playlist order; `PlaySound` name equals cue name; roles of LoadScreen symbols; runtime-suffixed key prefixes |
| PARTIAL | bridge calls without a binding-class function; `TnSurveyActionScriptBinding` is listed but not cooked |
| UNKNOWN | native vs script status of each function (the WFC FunctionFlags tail is not decoded); mode icons; map descriptions; the 10 missing keys |
