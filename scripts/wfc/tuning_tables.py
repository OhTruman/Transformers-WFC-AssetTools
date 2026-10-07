"""Authored weapon / vehicle tuning values for Gameplay's tuning passes -> manifests/mp_content/tuning_tables.json

  python tuning_tables.py

Consolidates the per-weapon / per-vehicle authored values already exported (Weapons/*/weapon.json, Characters/*/character.json;
CONFIRMED authored data) into flat tables, and classifies every numeric field whose effect can depend on the tick rate
(the original ran a smoothed 15-30 Hz tick, bSmoothFrameRate / MaxSmoothedFrameRate=30, manifests/config/timing_config.json):
  rate        per-second quantity (speed, acceleration, rate)      -> frame-rate independent if integrated with DeltaTime
  duration    seconds (time, delay, duration, interval)            -> frame-rate independent
  per_tick?   unitless smoothing / damping / interpolation / lerp factors (Interp, Smooth, Damp, Lerp, Alpha, Decay, Friction,
              Stiffness, Factor, Blend) -> MAY be applied once per tick in native code; if so, behaviour at > 30 Hz differs and needs
              a correction such as 1 - (1 - f)^(30 * dt). PROVISIONAL: which of these are per-tick is RE's to confirm (native).
"""
import glob, json, os, re, sys, time
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402
import authored as A  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
PER_TICK = re.compile(r'Interp|Smooth|Damp|Lerp|Alpha|Decay|Friction|Stiffness|Factor|Blend|Recover|Settle|Follow', re.I)
DURATION = re.compile(r'Time$|Time[A-Z_]|Duration|Delay|Interval|Period|Lifetime|Cooldown', re.I)
RATE = re.compile(r'Speed|Accel|Rate|PerSec|Velocity|Gravity|Force|Torque|Impulse', re.I)

def flat(prefix, v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            if k in ('object', 'class', 'source'): continue
            flat(prefix + '.' + k if prefix else k, x, out)
    elif isinstance(v, list):
        if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v): out[prefix] = v
        else:
            for i, x in enumerate(v[:16]): flat('%s[%d]' % (prefix, i), x, out)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out[prefix] = v

# RE ce24514, TARGETED_PASS4 A4 addendum 3 (CONFIRMED from script): verdict per property name
RE_VERDICT = {
    'Stiffness': ('dt_correct', 'TnSpring semi-implicit solve v_new=(v+dt(K(L0-L)+g))/(1+B dt+K dt^2), K=Stiffness/m, m=mass/4 per probe'),
    'Damping': ('dt_correct', 'TnSpring semi-implicit solve, B=Damping/m'),
    'AngularDamping': ('dt_correct', 'PhysX rigid-body damping (set_AngularDamping), continuous; car x5(1-|steer|)^2'),
    'TireFrictionCoefficient': ('dt_correct', 'force law F=clamp(-v_lat mu LateralForceScale Load, +-MaxForce)'),
    'DriftFrictionScale': ('dt_correct', 'LateralForceScale (x0.8 front / x0.5 rear while drifting), force scale only'),
    'ExtraRotationLerpValue': ('per_tick_30hz', 'TnPlaneSimulation.CalculateFinalRotationToMatch RLerp(prev, delta, f) once per player '
                                                'update: f_dt = 1-(1-f)^(30 dt)'),
    'AiLinearDamping': ('unused', 'no script reader (AI planes use HoverPhysics.MoveToTargetLocation / RotateToTargetOrientation)'),
    'AiLinearStiffness': ('unused', 'no script reader'),
}

def classify(name):
    leaf = name.split('.')[-1]
    if leaf in RE_VERDICT: return RE_VERDICT[leaf][0]
    if DURATION.search(leaf): return 'duration'      # time constants (SmoothTime, BlendInTime) are seconds: frame-rate independent
    if PER_TICK.search(leaf): return 'per_tick?'
    if RATE.search(leaf): return 'rate'
    return None

def resolve_sub(v, depth=0):
    """inline object references one level deep (suspension / blueprint sub-objects)"""
    if depth > 2: return v
    if isinstance(v, str) and '.' in v and A.get(v) and A.get(v)['class'] not in ('Material', 'MaterialInstanceConstant', 'Texture2D',
                                                                                     'StaticMesh', 'SkeletalMesh', 'SoundCue', 'ParticleSystem'):
        return {'object': v, 'class': A.get(v)['class'], **{k: resolve_sub(x, depth + 1) for k, x in (A.values(v) or {}).items()}}
    if isinstance(v, dict): return {k: resolve_sub(x, depth) for k, x in v.items()}
    if isinstance(v, list): return [resolve_sub(x, depth) for x in v]
    return v

def main():
    weapons = OD()
    for f in sorted(glob.glob(os.path.join(VS, 'Weapons', '*', 'weapon*.json'))):
        w = json.load(open(f, encoding='utf-8')); wid = '%s/%s' % (os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-5])
        vals = OD()
        for sec in ('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)', 'heat', 'recoil (procedural, WEPMESH)',
                    'class_defaults (weapon CDO, sub-objects resolved)', 'fine_aim_camera (OverTheShoulder strategy FOV)'):
            flat(sec.split(' ')[0], w.get(sec), vals)
        weapons[wid] = OD([('class', w.get('class')), ('values', vals),
                           ('tick_sensitive', OD((k, c) for k, c in ((k, classify(k)) for k in vals) if c))])
    vehicles = OD()
    for f in sorted(glob.glob(os.path.join(VS, 'Characters', '*', 'character.json'))):
        c = json.load(open(f, encoding='utf-8'))
        if not c.get('chassis_id'): continue
        st = c.get('stats') or {}
        vals = OD()
        vp = resolve_sub(st.get('vehicle_physics'))
        flat('vehicle_physics', vp, vals)
        for sec in ('vehicle_scalars (VEHDEF)', 'momentum', 'acrobatics', 'class_speed_multiplier', 'robot_scalars (ROBODEF)'):
            flat(sec.split(' ')[0], st.get(sec), vals)
        vehicles[c['chassis_id']] = OD([('iconic_id', c.get('iconic_id')), ('vehicle_definition', (c.get('vehicle') or {}).get('definition')),
                                        ('values', vals), ('tick_sensitive', OD((k, x) for k, x in ((k, classify(k)) for k in vals) if x))])
    pt = sorted({k.split('.')[-1] for t in (weapons, vehicles) for r in t.values() for k, c in r['tick_sensitive'].items() if c == 'per_tick?'})
    out = OD([('generated_by', 'AssetTools/scripts/wfc/tuning_tables.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('source', 'Weapons/*/weapon.json + Characters/*/character.json (authored CDO / WEPDATA / VEHDEF / physics blueprints, CONFIRMED)'),
              ('original_tick', 'smoothed 15-30 Hz (Xe-TransEngine.ini [Engine.GameEngine] bSmoothFrameRate=TRUE, MaxSmoothedFrameRate=30)'),
              ('classification', {'rate': 'per-second, DeltaTime-integrated -> frame-rate independent',
                                  'duration': 'seconds -> frame-rate independent',
                                  'per_tick?': 'unitless smoothing / damping factor without an RE verdict yet (PROVISIONAL)',
                                  'dt_correct': 'RE CONFIRMED: integrated with dt / continuous physics -> no conversion',
                                  'per_tick_30hz': 'RE CONFIRMED: applied once per 30 Hz tick -> f_dt = 1 - (1 - f)^(30 * dt)',
                                  'unused': 'RE CONFIRMED: no script reader'}),
              ('per_tick_candidate_property_names (for RE)', pt),
              ('re_verdicts (RE ce24514 TARGETED_PASS4 A4 addendum 3, CONFIRMED)', OD((k, {'verdict': v[0], 'native': v[1]}) for k, v in RE_VERDICT.items())),
              ('re_extra_per_tick', 'hover-car airborne / inverted upright pull: 5% of the angle error per tick (30 Hz) - not an authored '
                                    'property; convert as per_tick_30hz'),
              ('re_time_constants', '*SmoothTime / AimSmoothTime are seconds: HmC2Smoother w=4/SmoothTime, x=w dt, '
                                    'decay ~ 1/(1+x+0.48x^2+0.235x^3) - frame-independent'),
              ('weapons', weapons), ('vehicles', vehicles),
              ('summary', {'weapons': len(weapons), 'vehicles': len(vehicles), 'per_tick_candidate_names': len(pt)})])
    json.dump(out, open(os.path.join(AT, 'manifests', 'mp_content', 'tuning_tables.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['summary'])); print('per-tick candidates:', pt)

if __name__ == '__main__':
    main()
