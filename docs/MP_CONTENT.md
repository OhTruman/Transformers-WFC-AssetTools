# Multiplayer characters, classes, weapons, selection UI, AI evidence (2026-10-04)

**What's here:**
* **Manifests:** in `AssetTools/manifests/mp_content/`.
* **Generators:** `scripts/wfc/mp_roster.py` (characters, classes, weapons, animation compatibility) and
  `scripts/wfc/mp_handoffs.py` (selection UI, AI evidence, versus-mode visuals, bundles).
* **Validator:** `scripts/wfc/validate_mp_content.py`, writing `logs/validate_mp_content.json`. Result: **2,574 checks,
  0 failures**. It checks every path and cooked object reference, the roster meshes, materials, portraits and classes, the
  weapons, animation compatibility, and the bundles.

Nothing is inferred from filenames alone. MP membership comes from what every MP map cooks: the
`TnAssetReferencesMultiplayer` actor present in all 10 MP maps. Selection data comes from the config providers and presets;
unlock rules come from script (RE decompilation, read-only).

## How WFC multiplayer characters work (CONFIRMED from data and script)

**Classes.**

| class | vehicle form | default secondary weapon | speed multiplier |
|---|---|---|---|
| Scout | car | EMPShotgun | 1.0 |
| Scientist | jet | RepairRay | 0.9 |
| Soldier | tank | HomingRocket | 0.9 |
| Leader | truck | HeavyPistol | 0.95 |

**Two selection modes.**
* **Custom mode:** the player builds a character on a **chassis** (body) of their class. Each chassis is one `ROBODEF` with a
  body name: Runner, Seeker, Destroyer, Heavy Rig and so on. The player picks colours, weapons, abilities and skills.
* **Iconic mode:** set by `OnlyAllowIconicCharacters`, or `GameTeamStatus` 2 or 4. The player picks a preset iconic character
  from `TnProfileSettings.PresetIconicCharacters` (30 `*_PCD_SP` presets); each iconic character can be claimed once per team.
  * An iconic preset lists a chassis per faction (for example AirRaid → Jet4 on both teams).
* **Class presets.** `TR_MPPlayerCharacterData_p.{Scout,Scientist,Soldier,Leader}_PCD_MP` give each class's default loadout and
  default chassis per faction.

## Roster (`mp_characters.json`)
Every chassis and archetype carries an `availability` label, decided by where its ROBODEF is cooked:

| label | count |
|---|---|
| **MULTIPLAYER CONFIRMED** | 9: in every MP map, not cooked into campaign |
| **SHARED (MULTIPLAYER CONFIRMED + campaign)** | 18: e.g. Optimus, Bumblebee, Megatron, Starscream (also cooked into campaign maps) |
| **CAMPAIGN ONLY** | 6 chassis entries (car soldiers, minions) + all 33 non-chassis TnTransformer archetypes |
| **UNKNOWN** | none |

**Class icons.**
* `mc_specialtyIcon<Class>` in SharedIcons_GFX and CharacterSelect_GFX.
* `mc_classInfo<Class>` / `mc_classInfoHealth<Class>` in CustomTransformers_GFX.
* The Hud's `mc_specialtyIconReference`.
* All are listed in `mp_classes.json` under `ui_icons`.

| status | chassis (iconic character) |
|---|---|
| **MP, available by default (15)** | Car (Bumblebee), Car2 (Sideswipe), Car3 (Breakdown), Car4 (Barricade), Jet (Starscream), Jet4 (Air Raid), Jet5 (Jetfire), Jet6 (Silverbolt), Tank (Megatron), Tank2 (Brawl), Tank3 (Warpath), Truck (Optimus Prime), Truck2 (Ratchet), Truck3 (Ironhide), Truck4 (Soundwave) |
| **MP, locked (12)** | Car5 Arcee (Autobot campaign completion), Jet8 Slipstream (Decepticon campaign completion); Car6 Jazz, Car7 Deadend, Jet2 Thundercracker, Jet3 Skywarp, Jet7 Shockwave, Tank4 Scattershot, Tank5 Demolishor, Truck5 Zeta Prime, Truck6 Onslaught, Truck7 Optimus (no unlock in script: native or online entitlement, UNKNOWN) |
| **Not MP (6)** | Car8/9/10 (Decepticon/Autobot/Neutral car soldiers) and Minion1–3 (Frenzy, Rumble, Laserbeak): never referenced by any MP map |
| **Campaign / Escalation archetypes (33 other `TnTransformer` defs)** | brutes, titans, CQC, soldier car/jet/tank variants, bosses (Omega Supreme, Trypticon, Soundwave/Starscream boss), drones, spider, HoloBrute (Escalation) |

* **Truck and Truck7** share `Optimus_ROBODEF` (custom body "Heavy Rig").
* **The 26 distinct MP ROBODEFs** are exactly `TnAssetReferencesMultiplayer.Transformers`.
* **Each ROBODEF is cooked identically** into every campaign, MP and lobby package that uses it (`cooked_copies.consistent`).

**What each character record holds:**
* **Robot form:** skeletal mesh and glTF, physics asset, anim tree, anim sets, material slots (resolved within the mesh package
  family: HIGH), overshield / defrag / buff materials, arm blueprint, cameras, size class, collision, movement stats, melee set,
  hit reactions, deaths, FaceFX.
* **Vehicle form:** form class (car / jet / tank / truck), mesh, physics blueprints, jump / hover / boost FX, weapon sockets,
  gibs, death sound.
* **Voice:** the `SoundEventSet` (event → cue).
* **Selection data:** iconic preset (class, factions, chassis per faction, starting form, weapons, vehicle weapons, melee,
  abilities, skills), locks and unlock source, customization camera id.
* **Weapons:** `weapons_allowed_by_provider`, from the weapon provider `ChassisRestriction`.

## Classes, abilities, skills, killstreaks (`mp_classes.json`)
* **Providers:** 4 specialties, 18 abilities, 56 skills and 12 killstreaks, with restrictions, level requirements, INT/FRA names
  and descriptions, and class defaults.
* **Abilities by class:**
  * Scout: Cloaking, HardLock, DecoyTrap, Dodge
  * Scientist: Shockwave, Drain, SpawnSentry, Disguise
  * Soldier: Hover, SpawnAmmoCrate, Whirlwind, AbilityJammer
  * Leader: Warcry, TransformDisruptor, RollerSphere, Barrier
  * Single-player only: Poke, GuidedMissile

## Weapons (`mp_weapons.json`)
**53 weapon classes:** 34 from `TnDataProvider_Weapon` plus 19 more cooked by every MP map (turrets, killstreak rocket turret,
extra melee).

**Each weapon record holds:**
* the provider id, display name and description (INT/FRA), `ItemName`, and the `WeaponType` code;
* faction and chassis restrictions;
* UI rating bars;
* mesh (`*_WEPMESH` → skeletal mesh → glTF), pickup mesh, muzzle sockets and flashes, tracers, squibs, event animations, sounds;
* player `*_WEPDATA`: ammo, clip, damage, damage types, shots, fire interval, range, spread, reload, equip time, heat;
* `AiData` and damage types.

**Notes:**
* **WeaponType codes:** 2 melee, 3 vehicle-form, 4 grenade. Codes 0 (AssaultRifle, BurstRifle, IonBlaster) and 1 (the rest,
  including every class default secondary) are both on-foot guns; their role names are UNKNOWN.
* **No held mesh (CONFIRMED absence):** vehicle-form weapons and grenades author no held skeletal mesh.
* **Kill-feed icons** come from the Hud_GFX `death_<Weapon>` bitmaps.

## Animation compatibility (`mp_animation_compat.json`)
* **Method.** Bone-level: every `AnimSet.TrackBoneNames` entry must exist as a joint of the extracted mesh.
* **Results.** Over the 33 chassis entries: 170 anim-set uses compatible, 24 partial, 2 incompatible. All MP characters are
  compatible or partial.
  * The only partials on MP characters are 2 ankle helper bones (`L/R_AnkleRobo01_XT`) missing for heavy bodies in the shared
    `Death_LightMed_ROBO_ANIM`, and one elbow bone (`R_ElbowRobo02_XT`) on Soundwave.
  * Non-MP car soldiers lack the finger bones.
* **Shared skeletons** (identical ordered joint lists):
  * Starscream / Thundercracker / Skywarp / Air Raid / Ratchet;
  * Breakdown / Arcee / Jazz / Deadend / Slipstream;
  * Bumblebee / Sideswipe;
  * Megatron / Warpath;
  * Optimus / Scattershot.
* **Sequence categories** (locomotion, jump, fire, reload, fine aim, transform, vehicle, death, hit reaction, ability, idle,
  melee) are name-based: HIGH.

## Character selection UI (`character_select_ui.json`)
* **Portraits.** `CharacterSelect_GFX` AS builds the portrait linkage as `CharacterName + "_Robot" / "_Vehicle"` (bytecode).
  26 MP characters match exactly and Silverbolt matches case-insensitively. Arcee and Slipstream also have `…Locked_…`
  variants.
* **Icons.** Weapon icons (export = weapon UniqueId) and ability icons; CustomTransformers weapon icons and palettes.
* **Data and script hooks.** Data-store bindings (`<TnMenuItems:Chassis|Weapons|Abilities|Skills|Specialties>`,
  `<CurrentGame:ClaimedIconicCharacters>`, …) and the Customize.* bridge calls with their script status.
* **Selection logic.** `TnCharacterScriptBinding` (lock filtering, iconic versus custom).
* **Preview scene.** `UI_CharacterCustomization_m`:
  * one camera actor and 15 Matinee camera moves chosen by `SeqVar_TnCustomizationCameraId` (chassis
    `CustomizationCameraId`);
  * 2 `SeqAct_TnPawnFactory` that spawn the preview pawn;
  * 38 lobby fscommands.

## AI / bots (`ai_bot_evidence.json`)
* **MP versus bots were NOT shipped (CONFIRMED).**
  * No versus map cooks any AI spawner, and the versus game classes have no bot path.
  * `NumBots` appears only in stock engine counters.
  * The automated-testing policies drive real player controllers.
  * Offline versus AI in the rebuild would be a **new feature**.
* **Debris exception.** `MP_ORB_Debris_BASE_m` cooks one `TnAiSquad` with no spawner; its role is UNKNOWN.
* **Where shipped MP AI does exist.** Escalation (SV): 36 `TnSurvivalGenerator` per ESC map, plus spawn lists. Campaign AI uses
  `TnActorFactoryAI` / `TnTacticalVolume` / `TnAiSquad` in 110 packages.
* **Reusable for future bots:** weapon `AiData` (`DesiredFiringRange`), AI ability variants, AI and difficulty config sections,
  AI character names, AI transformer archetypes, and the authored nav networks in every versus map.

## Versus-mode visuals (`versus_mode_visuals.json`, map-independent)
* **CTF:** flag (`WEP_CodeOfPower2H_SKEL`, +150 UU), dropped-flag class, objective bases.
* **EXT:** bomb (`NEU_MPBomb_SKEL`), and on `TnBombPlantPoint` the planted bomb `NEU_MPBombExplode_SKEL` plus detonate FX
  `Exp_GenericLvl_LRG_FX`.
* **KOTH:** ring `pTorus1_STAT`, plus zone colours.
* **DOM:** totem `NEU_EnergonTotem_SKEL`, plus the canvas marker material.
* **Every mode:** icon, announcer, music cues, score panel.
* **Placement:** per-map placement stays in each map's manifest.

## Character bundles (`mp_content/bundles/<chassis>.json`)
* **Bundles made:** Car (Bumblebee), Jet (Starscream), Tank (Megatron), Truck (Optimus Prime), Car2 (Sideswipe),
  Truck2 (Ratchet).
* **What each holds** (references into `ExtractedAssets/content`, nothing copied):
  * robot and vehicle glTFs, material files, textures;
  * anim-set glTFs with their compatibility status;
  * the iconic loadout with weapon glTFs;
  * sockets, voice set, cameras, stats.
* **Validation:** all bundle files exist. Tank and Truck carry the known ankle-bone partial in the shared death set.

## Canonical roster package (`roster_package.json`, `scripts/wfc/mp_roster_package.py`, 2026-10-04)
* **Keyed by RE chassis ids** from `RE-Workspace/notes/data/mp_chassis_roster.json` (read-only), with RE
  `OVERNIGHT_2026-10-04` §E as the identity evidence.
* **Cross-check against RE.** Every RE field is compared with the AssetTools extraction: 33 chassis, **0 mismatches**. The 21
  fields RE leaves `null` (size, vehicle damage multiplier) are values inherited from the class default (`Default__TnTransformer`);
  they are labelled as such.
* **Default four classes** (`TR_MPPlayerCharacterData_p`), identical to RE:

| class | Autobot | Decepticon |
|---|---|---|
| Leader | Truck3 Ironhide | Truck4 Soundwave |
| Scientist | Jet4 Air Raid | Jet Starscream |
| Scout | Car2 Sideswipe | Car4 Barricade |
| Soldier | Tank3 Warpath | Tank2 Brawl |

* **What each chassis carries:**
  * robot and vehicle meshes, glTFs, skeleton signatures, physics, anim tree, anim sets, material slots, extra materials;
  * **transform clips**: `Transform_ToVehicle/ToRobot_ROBO` on the robot mesh, `_VEH` on the vehicle mesh, plus ability-form
    clips (Hover, Whirlwind, ShieldPush …);
  * clip counts by category and bone-level animation compatibility;
  * **resolved stats**: ROBODEF / VEHDEF scalars, `SharedHealth` (segments 175/125/125/125, overshield 550), momentum,
    acrobatics, hover/car physics, class speed multiplier;
  * portraits, class icon, iconic loadout, provider-allowed weapons, abilities and audio.
* **Locks / unlocks:** native unlock rules are not guessed. Only the two script-proven unlocks (Arcee, Slipstream) are recorded.
* **Correction:** the customization preview actors are Sideswipe and Barricade (`RB_*WeaponArm_SKEL`). Their `RB_Ratchet_SKEL`
  tag is a stale editor label.
* **Correction:** MP maps carry only a ReachSpec graph (Streets 426, Gorge 738), with no PathNode or tactical data. Original-AI
  bots would need new navigation data. Agrees with RE §F.

### Weapon links per chassis (fix, 2026-10-04)
`roster_package.json` `weapons` now resolves two fields per chassis:
* **`allowed_on_foot_by_provider`:** the TnDataProvider_Weapon providers whose FactionRestriction (`Any` or the chassis
  faction) and ChassisRestriction (empty = any) admit the chassis, excluding vehicle-form weapons. Each of the 33 chassis has 6;
  for example, Car (Bumblebee, Scout) gets HeavyPistol, KamikazeMines, PlasmaCannon, ShortSword, Shotgun and SniperRifle.
* **`vehicle_form_weapons`:** WeaponType 3 providers carry no chassis restriction, so the vehicle weapon comes from the preset
  `VehicleWeapons` (Jet / Starscream: HomingRocketVehicle + PlaneAssaultRifle).

The previous `allowed_by_provider` field was null for every chassis because `mp_roster.py` did not link them. Locked portraits
exist only for Arcee and Slipstream (`*Locked_Robot/_Vehicle`); every other chassis has none authored.

### Versus data corrections (RE TARGETED_PASS3 2026-10-05, applied in the generators)
* **Weapons:** versus reads each weapon's **MultiplayerData** WEPDATA (`TnMultiplayerGame.DesiredWeaponDataType = 3`).
  `PlayerData` (`*_SP_WEPDATA`) is used by campaign only.
  * `mp_weapons.json` now carries `gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)` (e.g. IonBlaster: 15 damage, 150
    reserve) and `wepdata_objects`.
  * The old `gameplay (player WEPDATA)` block is kept and marked superseded; it holds the SP values.
* **Health:** versus health is the specialty blueprint applied by `TnSpecialty.Apply`, not ROBODEF SharedHealth:

  | specialty | segments | health | speed multiplier |
  |---|---|---|---|
  | Leader | 5×60 | 300 | 0.95 |
  | Scientist | 3×60 | 180 | 0.90 |
  | Scout | 4×50 | 200 | 1.00 |
  | Soldier | 6×55 | 330 | 0.90 |

  * Overshield is 200 for every specialty. Values are verified in authored data.
  * `roster_package.json` `stats.versus_health …`: select by the **character data Specialty**, never the chassis.
    Custom MP characters use `by_specialty[<slot class>]`; iconic presets use `by_iconic_preset_specialty`. The chassis
    DefaultSpecialty is a UI default only (RE). Example: Sideswipe is Scout by chassis UI default and Soldier by preset.
