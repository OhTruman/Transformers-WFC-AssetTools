"""Fine Aim reticle / HUD presentation for Optimus + Ion Blaster (M03 P3).

Evidence chain (all from cooked data):
  TnHUD CDO -> HudMovie UI_GFxHud_p.Hud_GFX_1 (extracted content/UI_GFxHud_p/Hud_GFX.gfx)
  TnHUD data observers -> ActionScript callback names (CallbackBindingName)
  Hud_GFX ActionScript 2 (gfxscan.py + as2dis.py): crosshair selection by weapon class, fine-aim handler,
      spread handler, target colour handler, scope handler; symbol placement from PlaceObject matrices
  weapon CDOs / WEPDATA: ReticuleType, HasFineAimScope, FineAimSpreadModifier
Output: AssetTools/manifests/fineaim_hud.json
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, gfxscan, as2dis  # noqa: E402
from m03_common import field, lit, write, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402

GFX_REL = 'content/UI_GFxHud_p/Hud_GFX.gfx'
GFX = os.path.join(ROOT, GFX_REL)

def enum(pkg, path):
    p = objtree.package(pkg); x = p.exports[p._idx[path.lower()] - 1]
    raw = p.data[x['serial_offset']:x['serial_offset'] + x['serial_size']]
    n = struct.unpack_from('>i', raw, 20)[0]
    return [p.names[struct.unpack_from('>i', raw, 24 + 8 * j)[0]] for j in range(n)]

def func_body(sprite, name):
    """Disassembly lines of the AS2 function assigned to _global.<name> inside the sprite's DoAction."""
    for blk in as2dis.actions_for(GFX, sprite):
        lines = as2dis.dis(blk)
        for i, l in enumerate(lines):
            if ("Push '%s'" % name) in l and i + 1 < len(lines) and 'DefineFunction' in lines[i + 1]:
                ind = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                out = [lines[i + 1].strip()]
                for l2 in lines[i + 2:]:
                    if len(l2) - len(l2.lstrip()) <= ind: break
                    out.append(l2.strip())
                return out
    return None

def stage():
    b = open(GFX, 'rb').read()
    nb = b[8] >> 3
    bits = ''.join(format(x, '08b') for x in b[8:8 + 20])
    v = [int(bits[5 + i * nb:5 + (i + 1) * nb], 2) for i in range(4)]
    i = 8 + (5 + 4 * nb + 7) // 8
    return {'width_px': v[1] / 20, 'height_px': v[3] / 20, 'fps': b[i + 1] + b[i] / 256}

def main():
    s = gfxscan.scan(GFX)
    ex = {int(k): v for k, v in s['exports'].items()}
    sym = {v: k for k, v in ex.items()}
    hud = 'TransGame.Default__TnHUD'
    obs = {o.rsplit('.', 1)[-1]: {'object': o, 'class': A.get(o)['class'], 'CallbackBindingName': A.values(o).get('CallbackBindingName'),
                                  **({'ConversionFactor': A.values(o).get('ConversionFactor')} if 'Spread' in o else {})}
           for o in A.values(hud)['DataObservers'] if any(t in o for t in ('Spread', 'Reticule', 'TargetType', 'CurrentWeaponAndAim'))}
    weapons = {}
    for w in ('TnWeaponIonBlaster', 'TnWeaponHeavyPistol', 'TnWeaponSniperRifle', 'TnWeaponBurstRifle'):
        cdo = 'TransContent.Default__' + w
        if not A.get(cdo): continue
        weapons[w] = {'cdo': cdo, 'ItemName': A.values(cdo).get('ItemName'),
                      'ReticuleType': field(cdo, 'ReticuleType', default='WRT_Default',
                                            note='enum TransGame.TnWeapon.EWeaponReticuleType = %s; unset -> 0 = WRT_Default'
                                                 % enum('TransGame', 'TransGame.TnWeapon.EWeaponReticuleType')),
                      'HasFineAimScope': field(cdo, 'HasFineAimScope', default=False)}
    wd = 'WEP_IonBlaster_p.IonBlaster_WEPDATA'
    crosshair_symbols = {n: sym.get(n) for n in ('mc_crosshairGeneric', 'mc_crosshairShotgun', 'mc_crosshairIonBlaster',
                                                 'mc_crosshairBazooka', 'mc_crosshairIncreaseDamage', 'mc_turretReticule',
                                                 'mc_rangeFinderCrosshair', 'mc_zoomScope', 'mc_shortScope', 'mc_mediumScope',
                                                 'mc_longScope')}
    out = {
        'generated_by': 'AssetTools/scripts/wfc/vs_fineaim_hud.py',
        'answer': {
            'special_fine_aim_reticle_for_ion_blaster': {
                'value': False, 'confidence': CONF,
                'proof': ['Hud_GFX NotifyFineAimChanged(newFineAimState): state 1 shows a scope ONLY for CurrentWeapon == '
                          'TnWeaponHeavyPistol (short) / TnWeaponBurstRifle (medium) / TnWeaponSniperRifle (long); every other '
                          'weapon -> hideScope(). It never touches the crosshair clip.',
                          'TnWeaponIonBlaster leaves HasFineAimScope unset (false) while HeavyPistol and SniperRifle set it true',
                          'TnWeaponIonBlaster leaves ReticuleType unset -> WRT_Default']},
            'normal_and_fine_aim_reticle_asset': {'value': 'mc_crosshairIonBlaster (same clip in both states)', 'confidence': CONF},
            'normal_reticle_hidden_or_replaced_during_fine_aim': {'value': False, 'confidence': CONF,
                                                                  'note': 'no ShowCrosshair/SetWeaponCrosshair call in the fine-aim handler'},
            'fine_aim_visible_change': {
                'value': 'the 3 prongs move inward because the weapon spread shrinks (prong offset = spread * 300 px, '
                         'eased 0.2 s); Ion Blaster WEPDATA FineAimSpreadModifier = 0.5',
                'confidence': HIGH,
                'note': 'HUD reaction to spread is CONFIRMED (ActionScript); the spread value fed through '
                        'NotifyWeaponSpreadChanged and how FineAimSpreadModifier enters it are native'}},
        'hud_movie': {'TnHUD.HudMovie': field(hud, 'HudMovie'), 'TnHUD.DefaultHudMovie': field(hud, 'DefaultHudMovie'),
                      'extracted_file': GFX_REL, 'stage': stage(),
                      'signature': s['signature'], 'swf_version': s['version']},
        'data_observers (TnHUD CDO, CONFIRMED)': obs,
        'observer_enums': {'EHudAimType (TnHudDataObserverCurrentWeaponAndAim)':
                               enum('TransGame', 'TransGame.TnHudDataObserverCurrentWeaponAndAim.EHudAimType'),
                           'ETargetTypeForHud (TnHudDataObserverTargetType)':
                               enum('TransGame', 'TransGame.TnHudDataObserverTargetType.ETargetTypeForHud')},
        'observer_to_callback': {
            'CurrentWeaponAndAim0': {'callbacks': ['_global.NotifyCurrentWeaponChanged(WeaponName)', '_global.NotifyFineAimChanged(state)'],
                                     'confidence': HIGH,
                                     'evidence': 'observer stores SavedWeaponClass + SavedAimType (kHudStandardAim=0, kHudFineAim=1) '
                                                 'and has no CallbackBindingName; the movie defines exactly these two handlers taking '
                                                 'a weapon class name and a 0/1 state. The native call site is not in authored data.'},
            'WeaponSpreadObserver0': {'callbacks': ['_global.NotifyWeaponSpreadChanged(newWeaponSpread)'], 'confidence': CONF},
            'TargetType0': {'callbacks': ['_global.NotifyTargetTypeChanged(TargetType)'], 'confidence': CONF},
            'ReticuleTypeObserver0': {'callbacks': ['_global.NotifyWeaponReticuleTypeChanged'], 'confidence': CONF,
                                      'note': 'Hud_GFX defines NO handler with this name: the reticule-type callback has no '
                                              'effect in this movie (turret reticule uses DisplayTurretReticule instead)'}},
        'weapons': weapons,
        'ion_blaster_weapon_data': {k: field(wd, k) for k in ('FineAimSpreadModifier', 'PerShotSpreadModifier', 'GroundSpeedMultiplier',
                                                              'TargetSnapRange', 'bShouldApplyFineAimTargetFocus', 'FineAimTargetFocusParams')},
        'fine_aim_manager': {k: field('TransGame.Default__TnFineAimManager', k) for k in ('_TargetSnapTimeout', '_GroundSpeedMultiplier')},
        'crosshair_selection (sprite 599, NotifyCurrentWeaponChanged)': {
            'rule': {'TnWeaponShotgun / TnWeaponEmpShotgun': 'SetWeaponCrosshair(1) -> mc_crosshairShotgun',
                     'TnWeaponIonBlaster': 'SetWeaponCrosshair(2) -> mc_crosshairIonBlaster',
                     'TnWeaponBazooka': 'SetWeaponCrosshair(3) -> mc_crosshairBazooka',
                     'any other weapon': 'SetWeaponCrosshair(0) -> mc_crosshairGeneric',
                     'TnWeaponMountedRocketTurret / TnWeaponMountedHeavyIonBlaster': 'DisplayTurretReticule(true)',
                     'TnWeaponGrenadeLauncher': 'DisplayRangeFinder(true)'},
            'confidence': CONF, 'disassembly': func_body(599, 'NotifyCurrentWeaponChanged')},
        'SetWeaponCrosshair (sprite 621)': {
            'behaviour': 'if type changed: remove old clip; attachMovie(symbol, "crosshair<N>_mc") under crosshairAnchor_mc with '
                         '{_rotation: 60}, then interp to {_rotation: 0} over 0.3 s "easeout"',
            'confidence': CONF, 'disassembly': func_body(621, 'SetWeaponCrosshair')},
        'NotifyFineAimChanged (sprite 621)': {
            'behaviour': {'0 (kHudStandardAim)': 'hideScope(); turretReticuleClip.fineAim(false) if a turret reticule exists',
                          '1 (kHudFineAim)': 'HeavyPistol -> showScope("short"); BurstRifle -> showScope("medium"); SniperRifle -> '
                                             'showScope("long"); otherwise hideScope(); turretReticuleClip.fineAim(true) if present'},
            'confidence': CONF, 'disassembly': func_body(621, 'NotifyFineAimChanged')},
        'NotifyWeaponSpreadChanged (sprite 621) + mc_crosshairIonBlaster spread watch (sprite %s)' % sym.get('mc_crosshairIonBlaster'): {
            'behaviour': 'WeaponSpread stored on the controller; the crosshair clip watches it: each prongN_mc.prong_mc._y = '
                         'spread * -SpreadMultiplier, eased 0.2 s "easeout" (first value applied instantly)',
            'SpreadMultiplier': 300, 'units': 'HUD stage pixels (1120x720 stage) per unit of spread value',
            'confidence': CONF,
            'disassembly_controller': func_body(621, 'NotifyWeaponSpreadChanged')},
        'NotifyTargetTypeChanged (sprite 621)': {
            'behaviour': 'tint crosshairAnchor_mc over 0.2 s easeout: TTFH_Friend(0) -> 0x50B5D5, TTFH_Enemy(1) -> 0xFF3333, '
                         'other -> 0xFFFFFF',
            'colors_rgb': {'TTFH_Friend': [0x50, 0xB5, 0xD5], 'TTFH_Enemy': [0xFF, 0x33, 0x33], 'TTFH_None': [255, 255, 255]},
            'confidence': CONF, 'disassembly': func_body(621, 'NotifyTargetTypeChanged')},
        'ShowCrosshair (sprite 621 handler, called from the ammo panel sprite 600)': {
            'behaviour': 'crosshairAnchor_mc._visible = arg; the ammo panel calls ShowCrosshair(false) when ReserveAmmo == -2 or '
                         'ReserveCapacity < 0 (and fades the ammo panel to alpha 0 over 0.5 s), ShowCrosshair(true) otherwise',
            'confidence': CONF},
        'symbols': crosshair_symbols,
        'ion_blaster_reticle_geometry': {
            'symbol': 'mc_crosshairIonBlaster (character %s)' % sym.get('mc_crosshairIonBlaster'),
            'prongs': [{'instance': 'prong1_mc', 'rotation_deg': 0}, {'instance': 'prong2_mc', 'rotation_deg': 120},
                       {'instance': 'prong3_mc', 'rotation_deg': 240}],
            'prong_art': {'shape': 401, 'bitmap_character': 400, 'extracted_png': 'content/UI_GFxHud_p/Hud_GFX_I190.png',
                          'bitmap_size_px': [32, 16], 'drawn_size_px': [30, 12], 'drawn_offset_px': [-15, -6],
                          'note': 'bitmap fill matrix scale 18.75/15 twips per texel; placed at prong_mc origin; the prong moves '
                                  'along its local -Y (outward) with spread'},
            'other_crosshairs_prong_art': {'mc_crosshairBazooka': 'Hud_GFX_I195.png (char 405)',
                                           'mc_crosshairShotgun': 'Hud_GFX_I19A.png (char 410)',
                                           'mc_crosshairGeneric': 'Hud_GFX_I19F.png (char 415)'},
            'screen_placement': 'root hud_mc (0,0) -> midCenter_mc at (560, 360) px -> crosshair controller sprite 621 at '
                                '(0.2, 0.2) px -> crosshairAnchor_mc (0,0): reticle centre = stage centre',
            'scale': 1.0, 'base_opacity': '100 % (bitmap alpha); tint by target type',
            'confidence': CONF},
        'scope_system (not used by the Ion Blaster)': {
            'showScope(type)': 'attach mc_zoomScope at zoomScopeAttachPoint_mc (stage centre) + mc_<type>Scope; fade scope in '
                               '(alpha 100, 0.2 s linear) and fade HUD corner panels to alpha 0',
            'symbols': {k: v for k, v in crosshair_symbols.items() if 'Scope' in k}},
        'related_overlays': {'mc_crosshairIncreaseDamage': 'NotifyDamageIncrease(true) attaches it at increaseDamageAnchor_mc',
                             'mc_causeDamage': 'CausedDamage() hit marker + HmExternalInterface.Sound.PlaySound("HUD_POSITIVE_HIT_INDICATOR")'},
        'still_native': ['the call sites that invoke NotifyCurrentWeaponChanged / NotifyFineAimChanged / NotifyWeaponSpreadChanged',
                         'the spread value passed to the HUD (how FineAimSpreadModifier 0.5 and PerShotSpreadModifier combine)',
                         'TnPCS_FineAim camera state (no authored properties)']}
    write('fineaim_hud.json', out)
    print(out['answer']['special_fine_aim_reticle_for_ion_blaster']['value'], crosshair_symbols)

if __name__ == '__main__':
    main()
