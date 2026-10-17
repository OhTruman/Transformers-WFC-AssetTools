# Decoy Trap (Scout MP ability): asset manifest (AssetTools, 2026-10-18)

**For:** Gameplay (implementation) and Systems (audio / FX cues).
**Mechanics:** RE `RE-Workspace/work/handoff/MP_DECOY_TRAP_RE.md` (3f0271f). This doc lists only the assets.

**Files:**
- Manifest: `AssetTools/manifests/abilities/decoy_trap_assets.json`, written by `scripts/wfc/decoy_trap_assets.py`. It reads only
  authored.db, inventory.db and ExtractedAssets.
- Exports: `AssetTools/out/abilities/decoy_trap/` (gitignored; local):
  - `icons/` (3 PNGs);
  - `fx/` (DecoyTrap_FX, Pickup_FX and Electrocution_Transformer_FX as full pstream system JSON).
- Labels: everything is cooked / authored data (CONFIRMED) unless marked HIGH or UNKNOWN.

## 1. The trap object: no mesh of its own

- `TnDecoyTrap` has `DroppedPickupMesh` None. Its `PickupFactoryMesh` (MeshComponentA) has no StaticMesh anywhere in the archetype
  chain; TnBuffPickup sets only render flags (CollideActors false).
- At deploy, `SetDecoyWeapon(thrower's current weapon class)` makes the dropped trap show **that weapon's pickup mesh** (RE §2).
  - Its mesh and materials are the per-weapon exports already in `ExtractedAssets/VerticalSlice/Weapons/<W>/weapon.{glb,json}`.
  - The manifest lists all 53 exported weapons with their glb, materials, `PickupScale` and `PickupRotationRate`.
  - Spin: Yaw negated (RE).
  - Scale: `PickupScale`, HIGH.
- **Fade-in and glitch:** the weapon materials' defrag path (they sample `WEP_Shared_p` `WEP_Defrag_Alphas`). The `Defragger0`
  (TnDefragger) has no authored values through the chain.
- **Inherited from TnDroppedPickupDefrag:**
  - `HighlightFx0`: StaticMesh `FX_Mesh_p.Mesh.Plane_STAT` + `HighlightFxMat = WEP_Shared_p.WEP_PickupTarget_MAT`
    (AbsoluteRotation, no collision);
  - `PickupEffect0`: `FX_Pickups_p.FX.Pickup_FX`, bAutoActivate false;
  - `InstantKillDamageTypes = [FlashBang, Melee]`.

## 2. Collision

Cylinders only; the weapon mesh doesn't collide.

| component | radius | height | offset Z | set by |
|---|---|---|---|---|
| CollisionCylinder (world) | 20 | 20 | +20 | TnDroppedPickupWeapon (IgnoreForOverlapChecks) |
| TouchCylinder (pickup volume) | 200 | 100 | +100 | TnDroppedPickupWeapon (CollideActors) |

- Both components set BlockCameras false.
- Lifespan: `MultiplayerLifeSpan` 30 s (TnDroppedPickupWeapon; RE HIGH that it applies).

## 3. Animations (robot.glb tracks; AnimSet None in the CDOs, so the pawn's own sets are used)

| clip | role | duration | AnimSet |
|---|---|---|---|
| `Skill_Barrier` | deploy, one-shot at trigger (blend out 0.3, root motion ignored) | 0.967 s | `TR_LightMedium_ANM_p` / `TR_HeavyMedium_ANM_p` `.Shared_ROBO_ANIM` |
| `HitReactions_React_DecoyTrap_In` | victim stun loop (full body, high priority, blend in 0.3 / out 0.1) | 2.133 s | same |
| `HitReactions_React_DecoyTrap_Out` | victim stun end (blend in 0.1 / out 0.35) | 0.900 s | same |

- **No dedicated deploy or hold anim.** The ability reuses the Barrier clip and has no hold state.
- **Who has the clips:**
  - all 27 shipped MP chassis have all three as robot.glb tracks;
  - the stun clips play in **robot form only**, and a vehicle-form victim gets no anim (RE §4).
- **`React_DecoyTrap_In` carries an anim notify:** `HmAnimNotify_PlayEffect` `FX_Transformers_p.FX.Electrocution_Transformer_FX`
  at socket `Chest_FX`, t = 0.019 s. So the victim gets that effect on top of DecoyTrap_FX.
- **Missing** (none ship in MP):
  - Car8, Car9, Car10 have no stun clips;
  - Minion3 and Optimus have none of the three.
- `HitReactions_React_DecoyTrap` (without _In / _Out) is also in the sets, but no class references it.
- **Decoy in the class pool:** 13 chassis, all Scouts. That's Car to Car10 plus Minion1–3; only Car2–Car7 and Car are shipped MP.
  The per-chassis table is in the manifest.

## 4. UI

| use | texture | size | copy |
|---|---|---|---|
| HUD ability icon | `UI_GFxHud_p.TnAbilityDecoyTrap` | 64 × 64 RGBA | `icons/TnAbilityDecoyTrap.png` |
| kill-feed icon | `UI_GFxHud_p.death_Decoy` | 32 × 32 RGBA | `icons/death_Decoy.png` |
| character-select ability icon | `UI_GFxCharacterSelect_p.DecoyTrap` | 64 × 64 RGBA | `icons/DecoyTrap.png` |

- **`death_Decoy` is the kill-feed icon texture, not a per-chassis death animation.** No death_Decoy anim exists.
- The two 64 × 64 icons are byte-identical.
- **Victim marker** (creator's client only):
  - material `UI_HudMarkers_p.MarkerDeceptDestructible_MAT` (EmissiveColor vector parameter);
  - text "Victim Trapped";
  - label colour (100, 210, 250, 220);
  - sizes 0.05 / offscreen 0.0625.

## 5. Audio (category SFX_TRANS_POWER; the .wav and .fsb for every wave are in ExtractedAssets/content)

**DECOY_TRAP_DEPLOY** (`BL_TRANS_POWER`; the ability's OnTriggerSound):
- Root: SmartPan_PreferPlayer, distance 1800–12000, priority 220, mixer preset TRANS_POWER_ACTIVATE (local player only).
- Waves:
  - `WL_TRANS_POWER.TRANS_POWER_TRAP_DEPLOY` (0.77 s) at 0;
  - `WL_HUD_INTERFACE.SYNTH_HEALTH_VACUUM` (1.12 s) at 0.50 s.

**DECOY_TRAP_EXPLODE** (TnDecoyTrap PickupSound; plays when an enemy picks the trap up):
- Root: −9 dB, SmartPan, distance 1000–12000, priority 220.
- Layers:
  - `TRANS_POWER_TRAP_ELEC_LP_EXPLO` (1.49 s) at 0;
  - `TRANS_POWER_TRAP_ELEC_LP` (4.59 s): envelope 0 → 1 by 0.15 s, held to 4.10 s, 0 at 4.57 s; pitch −36 → 0 over 0.28 s;
    PlayWhenSilent;
  - a random `WL_WPN_GRENADE.KAMIKAZE_EXPL_01..03` (pitch variation 2);
  - a random `WL_ELEC.DEATH_LIGHT_01..03` at 3.50 s (−3 dB).
- So it's a ~5 s one-shot spanning the stun.
- The root also carries LoopStart 0.320 / LoopEnd 1.052. **What the HM root does with them is UNKNOWN.**

**Trap loop:** no separate loop cue exists, and no decoy class has an ambient sound. The trap is silent on the ground; the "loop" is the
ELEC_LP layer inside EXPLODE.

## 6. FX (per-LOD compiled modules from pstream; all distributions CONFIRMED)

| template | used by | emitters | LODs |
|---|---|---|---|
| `FX_Multiplayer_p.FX.DecoyTrap_FX` | TnBuffDecoyTrap.ApplyFx: loops at the victim `TargetingSocket` for the stun | 6 (5 sprite + 1 mesh `FX_Mesh_p.Mesh.Sphere_01_MESH`) | 2 (LODDistances 0 / 10000) |
| `FX_Transformers_p.FX.Electrocution_Transformer_FX` | the notify on React_DecoyTrap_In (`Chest_FX`) | 5 | 3 |
| `FX_Pickups_p.FX.Pickup_FX` | the trap's inherited PickupEffect0 (not auto-activated) | 1 | 2 |

- **DecoyTrap_FX colour:**
  - every emitter has `ColorByParameter` with param name **`Color`**, default (134, 168, 196, 255);
  - whether the buff sets `Color` on the component is UNKNOWN (no instance parameter in the CDO), so the default applies unless RE
    finds a setter.
- **DecoyTrap_FX materials:** `FX_Materials_p` `Lightning_Anim_02_MAT` and `ElectroRing01_Mat` (additive, unlit). The full list is in the
  fx JSON.
- **Trap idle / explode FX:** none exist in the cook. On the ground the trap shows the weapon mesh plus the inherited highlight and
  pickup effect. "Explode" is only the pickup sound (RE §4).

## 7. Asked for but not in the dump

- A trap mesh of its own: by design it is the thrower's weapon mesh.
- A dedicated deploy or hold anim: `Skill_Barrier` is reused, with no hold.
- `death_Decoy` per chassis: it's the kill-feed icon texture.
- A trap loop sound: there's only the ELEC_LP layer inside EXPLODE.
- A trap idle or explode FX.
