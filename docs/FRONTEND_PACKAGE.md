# Frontend delivery package (2026-10-03)

**Start here.** `AssetTools/manifests/frontend_package/` is the consolidated handoff for the Frontend lane. It joins every
recovered frontend manifest with the shipped script logic (RE decompilation, read-only), so implementation code does not need
to open packages or scan the asset tree. The shipped game is the specification; nothing here is a redesign.

* **Generator:** `scripts/wfc/fe_package.py`.
* **Validator:** `scripts/wfc/validate_frontend_package.py` (dangling references), which writes
  `logs/validate_frontend_package.json`. Current result: 2,371 checks, 0 failures.
* **Regeneration order:** `fe_frontend.py` → `fe_presentation.py` → `fe_map_catalog.py` → `fe_package.py` →
  `validate_frontend.py` + `validate_frontend_package.py`.

## Files

| file | use it for |
|---|---|
| `frontend_package.json` | the screen graph (`screen_order`, `screens`), one dependency record per movie (`movies`), the font library chain, boot/loading config |
| `mp_registry.json` | the runtime map and mode registry: all 13 MapInfo maps (10 cooked) and 9 modes, selection rules, settings options and defaults, presentation references |
| `loading_handoff.json` | the exact selected map/mode → loading screen rules, layout, spinner, tips and audio |
| `hud_handoff.json` | HUD, scoreboard and match-flow inputs grouped by element |

## Screens (`frontend_package.json` → `screens`)

| screen | level / class | movie | key relationships |
|---|---|---|---|
| boot_legal | engine | `TF_InitialStartup_<NA\|EU>_<INT\|FRA>.mkv` | config `InitialStartupFileName`; then `Map=UI_FrontEnd_m` |
| logo_sequence | `UI_FrontEnd_m`, TnFrontEndGame | `MovieLoader_GFX` | fscommand `enterMovieSequence`: Activision → Hasbro → High Moon → `FMV_intro`; skip via `enterFrontEnd` |
| title | `UI_FrontEnd_m` | `FrontEnd_GFX` `mc_menuPressStart` | localized logo external textures; music `FRONTEND_MX_ORBIT_01` |
| main_menu | `UI_FrontEnd_m` | `FrontEnd_GFX` `mc_menu*` | submovies (settings, accounts, friends, extras…); multiplayer via `Online.OpenPartyLobby` → `UI_PartyLobby_m` |
| settings | — | `SettingsMenu_GFX` | loaded from FrontEnd_GFX (and the pause menu where listed) |
| party_lobby | `UI_PartyLobby_m`, TnPartyLobbyGame, TnUIControllerPartyLobby | `PartyLobby_GFX` | playlist/mode menus (`mc_menuMultiplayerGameModes`, `…GameModeSettings`, `mc_gameModeInfo`); lobby URL builder |
| game_lobby | `UI_Lobby_m`, TnGameLobbyGame*, TnUIControllerGameLobby | `GameLobby_GFX` | map display via `<TnMenuItems:Maps>` / `<CurrentGame:SelectedMapID>`; ImagePath → `SetExternalTextureWithPath`; veto / host choice; status strings; 45 s intermission |
| loading | `TnMoviePlayer` | `LoadScreen_GFX` (+ video defaults) | see `loading_handoff.json` |
| match | TnVersusGame, TnUIControllerMultiplayer | Hud, InGameStats, PreGameCountdown, PauseMenu, MultiplayerRespawn, EndGameStats | countdowns 10 s / 15 s |
| post_match | — | `EndGameStats_GFX` | `TnGame.ReturnToGameLobby` → lobby URL `?MapId=` → loading (lobby branch) |
| quit_to_front_end | — | — | `Game.QuitToMainMenu` / `TnGame.OpenFrontEndMap` → `UI_FrontEnd_m` |

**Contents of each movie record:**
* the cooked `GFxMovieInfo` and `GFxMovie` objects and their instance settings;
* shared-library imports (`SharedComponents`, `SharedIcons`, `ButtonIcons`, `gfxfontlib` → `UI_GFxFonts_p/Fonts_EFIGS`);
* runtime submovies (the movie's `.swf` path resolved to the cooked movie key);
* fonts: embedded faces and `$` aliases mapped through `GFxUI.int`;
* textures: runtime `ExternalTextures` slots, cooked `References` and per-symbol bitmaps, each with its PNG;
* exports, plus timelines (frames, labels, instance names) of exported or labelled sprites;
* text fields and data-store bindings (`<DataStore:Field>` markup);
* localization keys (INT/FRA) and UI sound cues with their WAVs;
* fscommands sent, bridge calls made, and callbacks defined.

## Map / mode registry (`mp_registry.json`)

* **Selection rules.** These come from script (`TnGameReplicationInfoGameLobby`, `TnDataProvider_MapInfo`).
  * A map is compatible when its `CompatibleGameTypes` contains the mode tag and `IsProviderDisabled()` is false.
    `IsProviderDisabled` is `!HasRequiredAssets()` (native) or a DlcId not in the playlist `ContentIds`. All shipped playlists
    list `(0)`, and no map authors a DlcId.
  * Rotation picks a different random compatible map after each match.
* **Maps.** Each record has:
  * internal name, MapId, PresenceId, menu order, display name (INT/FRA), Faction;
  * preview (`ImagePath` → PNG, fallback `LevelUnavailable`) and supported modes;
  * persistent, streamed and companion packages;
  * audio (AUDIO sublevel, `BL_LVL_MP_<MAP>` bank, announcer set);
  * localization source and the loading-screen association.
  * No map description strings and no per-map loading art exist in the shipped data.
* **Modes.** Each record has:
  * id, display name, description and rules text with tokens (`` `p `` points, `` `t `` time, `` `r `` rounds);
  * playlist and menu order;
  * game, lobby and lobby-map classes, team type, player counts;
  * settings with value lists and defaults. TDM, for example: Time Limit 10/15/20 min, default 15; Points to Win
    20/30/40/50, default 40; Team Balancing default Autobalanced; Map Selection default Rotate.
  * rules classes, icon (`SharedIcons_GFX` `mc_gameModeIcon<TAG>`, vector art), HUD score panel;
  * loading tips, announcer lines, music and objective-presentation dependencies.

## Loading screen (`loading_handoff.json`)

* `TnMoviePlayer.StartLoadingMovie(URL)` reads `Game`, `GameModeTag` and `MapId` from the travel URL.
* **Match loads.** The title is the mode's `FriendlyName`, upper-cased by the AS. The text is `UIText.LoadScreen.LoadingMap`
  (`"in `m"`) with the map's `FriendlyName`. The tips are 3 random picks from the mode's `EngageText`.
* **Lobby and other loads.** Empty title and text, and the base tips.
* **Which movie plays.**
  * The front-end Kismet sets the loading movie to `UI_GFxLoading_p.LoadScreen_GFX`.
  * The `TF_LoadingScreen` video is the configured default before that.
  * `LoadScreenAlpha_GFX` is the configured alpha overlay (`mc_connectingToHost`).
* **Layout.** `mc_levelInfo` (`title_txt` / `description_txt`), `mc_engageText` (`engage_txt`), the "LOADING" label, and the
  spinner motif (sprite timelines plus ring textures `LoadScreen_GFX_I20/I24/I27/I2D`).
* **Audio.** No loading music is authored. Movie audio presence is recorded per file.
* **Shipped data quirk.** All 26 TDM tips are the same sentence ("Don't get fooled. Decoy Traps can be destroyed by shooting
  them."), so every TDM load shows that one tip. CONFIRMED.

## HUD / scoreboard (`hud_handoff.json`)
* **Groups.** Elements are grouped as health, overshield, ammo/reload, weapon, crosshair, heat, score/team, clock,
  kills/deaths, objectives, abilities and messages.
* **What each group lists.**
  * Hud_GFX symbols, with bitmaps and PNGs;
  * TnHUD data observers and their AS callbacks;
  * TnHUD callbacks;
  * `UIText [Hud]` strings.
* **Objectives** also carry the canvas marker materials and textures.
* **Scoreboard and kill feed.** The scoreboard (`InGameStats_GFX`), match-flow movies, end-of-match movie and messages, and the
  kill-feed icons (`death_<DamageType>`).
* **Open items.** Unresolved callbacks are listed with their absence evidence. Behaviour is RE/Gameplay scope.

## Confidence
* **CONFIRMED:** cooked objects, movie tags and bytecode, config, and the script decompilation (relationships cited per field).
* **HIGH:**
  * name-based HUD grouping;
  * that uncooked maps are excluded by the native `HasRequiredAssets`;
  * the native loading-movie composition order.
* **UNKNOWN:** listed per item in `frontend_re_handoff.json` and `hud_handoff.json` → `unresolved_callbacks`.

## Frontend backgrounds: what is behind each screen (`ui_scenes.json`, `scripts/wfc/ui_scenes.py`)
* **How it was built.** The UI levels were run through the generalized map pipeline (`vs_map`, `vs_mapfx`, `vs_lighting`,
  `vs_postprocess`, all under the 6 GB cap). Outputs are in `ExtractedAssets/VerticalSlice/Maps/UI_*`.
* **What `ui_scenes.py` adds:**
  * level streaming;
  * cameras;
  * Matinee camera and actor tracks with keys;
  * skeletal actors not in `world.glb` (mesh plus anim sets);
  * ambient sounds and music;
  * a per-screen verdict on whether a black background is authored or an omission.

| screens | 3D scene | verdict |
|---|---|---|
| boot / logos / opening movie | full-screen Bink movies | black only between movies (authored) |
| title, main menu, settings, extras, friends, leaderboards, campaign select | **UI_FrontEnd_m + streamed UI_FrontEnd_capture_VIG_m**: orbit battle with 105 props, 326 particle components (explosions, anti-air and laser fire, dropship boosters), 17 Matinee-animated skeletal ships, lens flares, fog | **black is an omission**. The camera is a looping 393.6 s Matinee (`SeqAct_Interp_2880`, 34 move keys) plus the `startMainMenuCamera` move |
| party lobby, multiplayer, private match, create character | `UI_PartyLobby_m` has no scenery; it **streams UI_CharacterCustomization_m** (LevelStreamingState "Customize", visible) | omission unless the customization room is streamed and the preview pawn (`SeqAct_TnPawnFactory`) spawned; 15 camera Matinees chosen by CustomizationCameraId |
| game lobby | `UI_Lobby_m` (no scenery) + the same customization room | as party lobby |
| campaign lobby | `UI_CampaignLobby_m`: 12 BSP triangles + 1 prop; its streaming state lists no level | carried by GFx art. UNKNOWN; verify against footage |
| loading | LoadScreen_GFX ring motif over black | authored black |
| pause / match end / respawn | the live gameplay map | omission if the map is not rendered behind |

## Additional screens (2026-10-04)
`frontend_package.json` → `screens` adds:
* `campaign`: CampaignSelect / DifficultySelect, `UI_CampaignLobby_m`, checkpoint art;
* `escalation`: PartyLobby `mc_menuEscalation*`, the survival lobby classes, ESC maps, HUD wave widgets;
* `private_match`: host and game-mode-settings menus, the Online.* bridge calls, private settings classes;
* `friends`: OnlineFriendsMenu;
* `leaderboards`: LeaderboardMenu;
* `challenges_teletraan`: ChallengeMenu / ChallengeNotify plus `TransChallenges.ini`;
* `create_character`: CustomTransformers plus the customization scene.

Each lists the movies that load it. Backgrounds per screen are in `ui_scenes.json`.

## Runtime-ready UI scenes (map contract, 2026-10-04)
Each UI scene folder `ExtractedAssets/VerticalSlice/Maps/<scene>/` now has:
* `world.glb`, collision, `lightmaps.json` plus atlas PNGs, `materials*.json`, `map_fx.json`, `lighting.json`,
  `postprocess.json`, `props*.json`;
* **`render_index.json`**, which lists every actor a Matinee or Kismet sequence drives, by name:
  * InterpActors, whose `world_glb_node` is the node name in `world.glb`;
  * skeletal actors as glTF plus anim sets plus matrix (they are not in `world.glb`);
  * emitters with template and matrix;
  * lens flares;
  * fog, post-process, cameras and Matinee tracks.

| scene | levels | actors |
|---|---|---|
| `UI_FrontEnd` | `UI_FrontEnd_m` + streamed `UI_FrontEnd_capture_VIG_m` | front end: 48 InterpActors, 5 emitters, 3 lens flares; vignette: 6 InterpActors, 17 HmSkeletalMeshActors (SoldierJet fly-bys), 321 emitters; 8 lightmapped props |
| `UI_CharacterCustomization` | `UI_CharacterCustomization_m` | SpaceDome, CybertronCards, 2 preview SkeletalMeshActors (Sideswipe, Barricade) |
| `UI_PartyLobby`, `UI_Lobby` | lobby level + streamed `UI_CharacterCustomization_m` (via authored LevelStreaming) | as customization |
| `UI_CampaignLobby` | `UI_CampaignLobby_m` | SpaceDome + BSP (authored space-dome scene) |

**Verdict corrections**, agreeing with RE D:
* The campaign/escalation lobby is the authored space-dome scene. **Black there is an omission.**
* Pause is shown over the live match, and results over the frozen match world.

### Matinee → actor bindings (runtime-ready, 2026-10-04)
In `render_index.json`, every group under `matinee (groups carry bound_actors …)` lists `bound_actors`: the actor names its
SeqAct_Interp VariableLinks bind, matching `actors_by_level` and the `world.glb` node names.
* **Front-end level:** `SeqAct_Interp_2880` (393.6 s loop) drives the camera dummies and `CameraActor_6585`. `SeqAct_Interp_9395`
  drives the rings: `OuterRingMESH` → `InterpActor_14597`, `InnerRingMESH` → `InterpActor_11976`, plus three
  MaterialInstanceActor parameter tracks.
* **Vignette:**
  * ship fly-bys: `SeqAct_Interp_490`, for example `dec01` → `HmSkeletalMeshActor_7960` (Move tracks) and `thrust01` → three
    emitters;
  * explosions, AA fire, lasers and sparks: InterpTrackToggle on named Emitters.
* **Ships:** 17 SoldierJet Aut/Dec fly-bys, each spawned from its glTF (`gltf`, `gltf_matrix`) and moved by Matinee. They have no
  AnimSets: authored motion is Move tracks only.
