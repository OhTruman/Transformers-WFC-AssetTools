# Product-ready multiplayer characters and weapons (2026-10-05)

Runtime-ready files live in **local `ExtractedAssets/VerticalSlice/`** (not pushed). The indexes below are in git.

## Characters: `Characters/<ChassisId>/` for all 33 chassis
**Generator:** `scripts/wfc/vs_roster_export.py --all`, run under `run_bounded`. It takes about 90 s and peaks at 2.3 GB.
**Index:** `manifests/mp_content/character_export_index.json`.

**Contract.** The same contract as the Optimus slice character, so Gameplay can load any chassis instead of falling back to
Optimus:
* `robot.glb` / `vehicle.glb`: the authored MP meshes (ROBODEF.SkelMesh / VEHDEF.SkeletalMesh), skinned;
* `textures/`;
* `character.json`.

**Stable ID** = the RE chassis UniqueId, so the folder names follow it: `Car2` = Sideswipe, `Truck4` = Soundwave, `Truck` =
Optimus Prime (MP chassis). The original `Characters/Optimus` slice folder is unchanged.

**What each `character.json` carries:**
* identity: iconic id, display names, faction, chassis class, iconic preset (CharacterName, Specialty, WeaponTypes,
  VehicleWeapons, Abilities, Skills), availability, locks;
* per form:
  * mesh object, definition, skeleton signature and joint count, physics asset, anim tree;
  * compatible / partial / rejected AnimSets;
  * sockets (WeaponSocket_*), read from the cooked mesh;
  * per-slot materials: MIC, every texture file (Lum / CustClrAlphas / Grunge / Normal / Reflection / …), roles, and the
    **customization parameters** (vector / scalar values incl. Cust_Color_A / Cust_COLOR_B);
  * baked base colour / emissive / specular;
  * clip list with category and source set;
* robot only: overshield / energy-death / buff materials, arm blueprint, FaceFX;
* transformation: the authored `Transform_*` clips and which of them are present in each glb;
* stats, weapons (on-foot allowed and vehicle-form), abilities, UI (portraits, class icon), menu (customization camera id),
  audio (voice and vehicle sound event sets);
* **team colour behaviour** (TnCharacterApplier parameter bindings, the three team EnergonColors);
* `validation`: every path is checked.

**Clip selection:**
* every clip of the chassis-specific sets (ability forms such as Transform_Hover / Whirlwind / ShieldPush are categorised
  `ability_form_*`);
* plus the categorised locomotion / aim / fire / reload / melee / hit / death / jump / land clips from the shared compatible
  sets.

**Bone-verified compatibility** comes from `mp_animation_compat.json`. **Partial sets** missing at most 2 bones (≤ 5 %) are
used because UE3 skips tracks for bones a mesh lacks. Soundwave's sets miss only `R_ElbowRobo02_XT`, the weapon-arm elbow,
and are listed under `anim_sets_partial_used`.

**Coverage.** All 33 chassis export with 0 missing paths:
* robot clips: 72–84 for player chassis, 10–19 for soldier and minion chassis (their own 24-bone sets);
* vehicle clips: 11–30;
* every chassis has its transform clips.

Laserbeak uses a single bird mesh for both forms and has no separate VEH set.

## Weapons: `Weapons/<ProviderId>/` for all 53 weapon classes
**Generator:** `scripts/wfc/vs_weapon_export.py --all` (about 16 s).
**Index:** `manifests/mp_content/weapon_export_index.json`.

**Stable ID** = the TnDataProvider_Weapon id, the same one Frontend reads from `TransWeapons.ini`.

**Files:**
* `weapon.glb`: the weapon skeletal mesh, resolved materials, and every clip of its AnimSet (Fire / Reload / Equip / Drop /
  Idle; taken from the weapon SkeletalMeshComponent `AnimSets`);
* `weapon.json`, which carries:
  * definition and ammo / damage (WEPDATA), AI data, damage types;
  * restrictions and `usable_by_chassis`;
  * mesh sockets, muzzle sockets, reference bone (`WEP_Reference_XR`), pickup mesh and offset;
  * attachment rule (robot WeaponSocket_Primary);
  * procedural recoil, heat;
  * effects (muzzle flash, tracer, squib, decal, muzzle light);
  * projectiles (class defaults and projectile mesh templates);
  * sounds resolved to WAV;
  * UI: ratings, kill-feed icon, HUD weapon icon, and loadout icons (GFx export name == provider id).

**IonBlaster.** The slice weapon (`weapon.glb` / `weapon.json`, built by `vs_weapon.py` and loaded by Gameplay) is kept; the
generic export sits next to it as `weapon_mp.*`.

**Weapons without a held mesh:** 8 vehicle-form weapons and the frag grenade. Their weapon mesh component authors no
SkeletalMesh, a CONFIRMED absence.

**Weapons without a provider entry:** 17 melee variants and turrets are not loadout-selectable. Melee weapons have no HUD or
loadout icon.

**Validation:** `validate_mp_content.py` opens every character and weapon glb and checks skins, clip counts, transform clips,
identity and every recorded path. Result: 3,122 checks, 0 failures.
