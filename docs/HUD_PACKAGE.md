# Multiplayer HUD package (2026-10-04)

* **`manifests/hud/hud_package.json`** (`scripts/wfc/hud_package.py`): the canonical in-match UI handoff.
* **`manifests/hud/minimap_radar_search.json`** (`scripts/wfc/hud_radar_search.py`): systematic minimap/radar search.

Behaviour stays with RE/Gameplay; this package records only authored content and relationships.

## Ownership
* **Scaleform:** `UI_GFxHud_p.Hud_GFX_1` (`TnHUD.HudMovie`), with a 1120×720 stage. It holds every widget except world
  markers.
* **Canvas:**
  * objective/player markers (`TnObjectiveMarkerTypeTransformerVersus` / `…Domination`, materials in `UI_HudMarkers_p`, font
    `UI_TransEngineFonts_p.MarkerFont`);
  * TnHUD console messages.
* **Other movies:**
  * scoreboard: `InGameStats_GFX` (+ `PlayerList_GFX`);
  * respawn/spectate: `MultiplayerRespawn_GFX`;
  * pre-match countdown: `PreGameCountdown_GFX`;
  * results: `EndGameStats_GFX`;
  * pause: `PauseMenu_GFX`;
  * prompts: `MessagePrompt` / `TextPrompt`.

## Layout (CONFIRMED structure; widget-to-region mapping from bytecode, HIGH)
* **Anchors.** `hud_mc` holds 9 placement anchors plus `zoomScopeAttachPoint_mc` at the centre (560, 360):
  * top row at y 54, left / centre / right at x 84 / 560 / 1036;
  * middle row at y 360;
  * bottom row at y 666.
* **Widgets are attached at runtime** with `attachMovie` from unnamed controller sprites inside each anchor:

| region | widgets |
|---|---|
| topLeft | health: `mc_vitalBarHealthSegment` / `…ActiveBarDrained` into `healthBarAnchor_mc`; team chat `mc_teamchatPlayer` |
| topRight | weapon: `mc_currentWeaponIcon` (`iconAnchor_mc`), `mc_currentWeaponText` (`textAnchor_mc`); ammo: `mc_ammoBar` (`ammoBarAnchor_mc`), `mc_vitalBarAmmoSegment`; `mc_grenadeIcon`; `mc_ammoPickupNotification` |
| topCenter | match clock: `countdown_mc` → `objectiveTime_mc/time_txt`, `roundTime_mc/time_txt`; score panel (dynamic: `mc_scoreTeam` / `mc_scoreFreeForAll` / …, logo via `logoAnchor_mc`); `mc_roundSegment`; `mc_pointTransaction`; `mc_nextWaveTimer` |
| midCenter | crosshairs (`crosshairAnchor_mc`), `mc_turretReticule`, `mc_crosshairIncreaseDamage`, `mc_rangeFinderCrosshair`, `mc_causeDamage`, `mc_damageArrow`, missile warnings, charging indicator, reload / grenade prompts, `mc_cantTransform`, `mc_transformDisrupt`, `mc_tutorialMessage` |
| bottomRight | `mc_killstreakIcon`, `mc_killstreakBuffIcon`, `mc_objectiveNew`, `mc_waveIndicator` |
| bottomCenter | `mc_notify` (notify manager / kill feed); CTF `returnFlagNotifyTime_mc` |
| bottomLeft | `mc_gameMessage_default` |
| midRight | `mc_levelUpNotify`, `mc_networkConnectivityAlert` |
| zoomScopeAttachPoint | `mc_zoomScope` and the scope type (`mc_shortScope` / `mc_mediumScope` / `mc_longScope`) |

## Elements
Each requested element lists its layout instances, exported symbols with PNGs, the `TnHUD` data observers and callbacks, and its
`UIText [Hud]` strings. The elements are:
* match clock, team score, local score;
* health, overshield, ammo, crosshair;
* kill feed, kills/deaths, objective markers;
* weapon, class abilities, damage, notifications;
* the Escalation wave widgets.

Grouping is name-based (HIGH); the existence of each item is CONFIRMED.

## Icon sets (bound to authored ids)
* **Characters:** export = iconic character name. 26 MP characters plus the vehicle-form icons Car / Jet / Tank / Truck.
* **By class name:** abilities (`TnAbility<Name>`) and weapons (`TnWeapon<Name>`).
* **Killstreaks:** export = killstreak UniqueId.
* **Other:** grenades, kill-feed `death_<DamageType>`, and misc (`IconUnknown`, `Infinity`, `PowerIcon`).

## Crosshair (bytecode)
* **`SetWeaponCrosshair(type)`:** 0 Generic, 1 Shotgun, 2 IonBlaster, 3 Bazooka. The symbol is attached into
  `crosshairAnchor_mc` and rotates in from 60° (0.3 s).
* **`NotifyTargetTypeChanged` tint:** type 0 `#50B5D5`, type 1 `#FF3333`, otherwise white (0.2 s).
* **Which weapon uses which type: UNKNOWN (native).** No script calls `SetWeaponCrosshair`, and no weapon authors it. The
  name-based expectation is PROVISIONAL.
* **Turret reticule:** `TnWeapon.GetReticuleType` gives `WRT_Turret` only for `WT_Mounted` weapons (enum `EWeaponReticuleType`
  {Default, Turret}); `ReticuleType` is never authored.
* **Scopes:** `HasFineAimScope` on SniperRifle and HeavyPistol.

## Other content
* **Match result:** `EndGameStats_GFX` plus `TnVersusGameOverMessage` (win/lose/forfeit/tie text and announcer) and the per-mode
  win/tie music.
* **Notifications:**
  * point events (`_global.PointEvent`);
  * game messages (`TnGameMessage` and killstreak message strings);
  * announcements (game-type message text, progress announcements, killstreak announcer);
  * level up, ammo pickup, and the message colours.
* **Class-specific HUD:** abilities, ability icons and killstreaks per class.
* **Weapon-specific HUD:** weapon icons, scopes, charging indicator, heat observers. The heat callbacks are defined in no movie.
* **Unresolved for RE:** 11 TnHUD callbacks that no shipped movie defines; 10 of them occur in no movie at all.

## Minimap / radar: none shipped (CONFIRMED negative)
* **What was searched:** cooked object and class names; every GFx export, label, instance, text field and AS string; all INT/FRA
  localization and ini files; extracted filenames; and RE script function names.
* **Every hit is unrelated:** ambient cues, campaign props (hospital scanner, holomap mesh), a laser-scanner FX, engine
  `Volume.Encompasses*`, and the lobby `mc_mapDisplay` map preview.
* **Enemy awareness in MP** is the canvas marker system: Orbital Recon killstreaks apply the team buff
  `TnBuffSeeEnemyObjectiveMarkers`.
* **`[TnRadarTargetTracker] _MaxDistance=20000`** configures a class with no cooked export; it is UNKNOWN and not a radar widget.

## RE OVERNIGHT_2026-10-04 incorporated
* **Element map.** `element_map (RE A1 …)` holds 23 elements with controller clip, anchor, offset and absolute position. Every
  RE anchor agrees with this movie's layout, and the computed absolutes reproduce RE's: health (104, 64), ammo (1016, 64),
  kill feed (84, 626), score (560, 59), clock (560, 104), announcements (560, 166), popups (560, 229). The wave indicator, left
  blank by RE, sits in bottomRight here.
* **Spatial cues.** Damage-direction arrows, missile-lock warnings, canvas off-screen objective arrows, ally name tags (an ally
  health bar for Scientist viewers only), and enemy tags only through buffs.
* **Minimap / radar:** closed as **NONE** (CONFIRMED by AssetTools' search and by RE A9, including `default.xex` strings). Do not
  add one as "original".
