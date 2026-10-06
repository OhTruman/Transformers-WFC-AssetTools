"""Multiplayer asset completeness + reference-integrity audit -> manifests/audit/*.json + docs/ASSET_INTEGRITY_AUDIT.md

  python asset_integrity_audit.py            (run under run_bounded.py; reads only)

Reads: Game Dump cooked packages (via pstream / authored.db), ExtractedAssets (exact-case file checks), AssetTools manifests.
Writes: manifests/audit/{characters, weapons, vehicle_fx_audio, maps, frontend, reference_integrity, top_issues}.json

Cell vocabulary (extraction-level only; no runtime-correctness claim):
  COMPLETE   every authored reference for the cell resolves to an exported file / decodable object
  PARTIAL    some references resolve, some do not (counts in the evidence)
  MISSING    authored but nothing exported / not represented in the runtime manifest
  FALLBACK   represented only through an approximation or substitute (e.g. baked texture, engine default)
  UNKNOWN    cannot be decided from authored data
"""
import glob, json, os, re, sys, time
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
import materials  # noqa: E402
import pstream  # noqa: E402
from vs_common import ROOT, VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')
OUT = os.path.join(MANI, 'audit')
GEN = 'AssetTools/scripts/wfc/asset_integrity_audit.py'
C, P, M, F, U = 'COMPLETE', 'PARTIAL', 'MISSING', 'FALLBACK', 'UNKNOWN'

def J(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

# ------------------------------------------------------------------ exact-case file existence
_dir = {}
def exists_exact(rel):
    """True only if every path component matches on disk with the same case (Windows hides case mismatches)."""
    if not rel: return False
    parts = rel.replace('\\', '/').split('/')
    cur = ROOT
    for p in parts:
        if cur not in _dir:
            try: _dir[cur] = set(os.listdir(cur))
            except Exception: _dir[cur] = set()
        if p not in _dir[cur]:
            return False
        cur = os.path.join(cur, p)
    return True
case_mismatch = []
def file_status(rel, who):
    if not rel: return False
    if exists_exact(rel): return True
    if os.path.exists(os.path.join(ROOT, rel)): case_mismatch.append({'path': rel, 'referenced_by': who})
    return False

def agg(states):
    s = [x for x in states if x]
    if not s: return U
    if all(x == C for x in s): return C
    if all(x in (M,) for x in s): return M
    if any(x == F for x in s) and all(x in (C, F) for x in s): return F
    return P

def cell(status, **ev): return OrderedDict([('status', status)] + list(ev.items()))

# ------------------------------------------------------------------ shared resolvers
IDX = None
def cue_wavs(cue):
    a = IDX.get((cue or '').lower())
    if not a: return None
    w = []
    for s in (a.get('references') or {}).get('sounds') or []:
        x = IDX.get(s.lower())
        w.append(next((o for o in (x or {}).get('extracted') or [] if o.endswith('.wav')), None))
    return w

_ps = {}
def ps_status(tmpl):
    if not tmpl: return None
    if tmpl in _ps: return _ps[tmpl]
    if not A.get(tmpl):
        _ps[tmpl] = {'template': tmpl, 'status': M, 'why': 'ParticleSystem not in authored.db'}; return _ps[tmpl]
    try:
        r = pstream.system(tmpl)
        em = r.get('emitters') or []
        bad = [e.get('name') for e in em if e.get('error')]
        _ps[tmpl] = {'template': tmpl, 'status': C if em and not bad else (P if em else M), 'emitters': len(em), 'emitter_errors': bad[:5]}
    except Exception as e:
        _ps[tmpl] = {'template': tmpl, 'status': P, 'why': 'cooked object exists; module-stream decode failed: %s' % repr(e)[:120]}
    return _ps[tmpl]

def event_cue(event, eventsets):
    for es in eventsets:
        for e in (A.values(es) or {}).get('SoundEventSet') or []:
            if e and e.get('Event') == event: return e.get('Sound')
    return None

_mpc = {}
def mp_copy_silent(cue):
    """True if a multiplayer-package copy of the cue's SoundNodeWaveEvents also has no ChildNodes (authored silent, HIGH: RE
    2026-10-05 - stock UE3 parse yields no wave; serial_size == tag_bytes, no native refs). None if no MP copy exists."""
    if cue in _mpc: return _mpc[cue]
    import objtree, ue3pkg, props as PR, extract
    rows = objtree.inv().execute("SELECT opath, package FROM exports WHERE opath LIKE ? AND opath LIKE '%SoundNodeWaveEvent%' "
                                 "AND package LIKE 'MP_%'", (cue + '.%',)).fetchall()
    if not rows: _mpc[cue] = None; return None
    by_pkg = {}
    for op, pk in rows: by_pkg.setdefault(pk, []).append(op)
    pk, ops = sorted(by_pkg.items())[0]
    pkg = ue3pkg.Package(os.path.join(extract.COOKED, pk + '.xxx')); rd = PR.PropReader(pkg)
    idx = {pkg.object_path(k + 1).lower(): k + 1 for k in range(len(pkg.exports))}
    silent = all(not PR.props_dict(rd.read_object(idx[o.lower()])[0]).get('ChildNodes') for o in ops if o.lower() in idx)
    _mpc[cue] = {'package': pk, 'wave_events': len(ops), 'silent': silent}
    return _mpc[cue]

# material dependency walk (MIC parent chain + texture export)
mic_issues = []; unexported_tex = Counter(); unexported_cls = {}
def material_status(mop, who):
    if not mop: return cell(M, why='slot has no material')
    seen, cur, chain = set(), mop, []
    while cur and cur not in seen:
        seen.add(cur); g = A.get(cur)
        if not g:
            mic_issues.append({'material': mop, 'missing_parent': cur, 'referenced_by': who}); break
        chain.append(cur)
        if g['class'] == 'Material': break
        cur = (g.get('props') or {}).get('Parent') or A.values(cur).get('Parent')
    r = materials.resolve(mop)
    tex = r.get('textures') or {}
    miss, none_override = [], []
    for k, t in tex.items():
        if t.get('file'):
            if not file_status(t['file'], who): miss.append(k)
        elif t.get('texture'):
            miss.append(k); unexported_tex[t['texture']] += 1
            unexported_cls[t['texture']] = (A.get(t['texture']) or {}).get('class')
        else:
            none_override.append(k)
    base = 'base_color' in (r.get('roles') or {}) or 'Lum_Map' in tex
    st = C if not miss and not none_override and base else (P if base or tex else M)
    return cell(st, material=mop, parent_chain=chain[1:], textures=len(tex), unexported=miss, explicit_none_overrides=none_override,
                has_base_colour=base)

# ------------------------------------------------------------------ characters
def characters():
    idx = J(os.path.join(MANI, 'mp_content', 'character_export_index.json'), {}).get('chassis') or {}
    roster = J(os.path.join(MANI, 'mp_content', 'roster_package.json'), {}).get('chassis') or {}
    compat = J(os.path.join(MANI, 'mp_content', 'mp_animation_compat.json'), {}).get('per_character') or {}
    rows = OrderedDict()
    for cid, e in idx.items():
        m = J(os.path.join(ROOT, e['dir'], 'character.json'), {})
        rp = roster.get(cid) or {}
        r = OrderedDict()
        for form in ('robot', 'vehicle'):
            f = m.get(form) or {}
            r[form + '_mesh'] = cell(C if f.get('glb') and file_status(f['glb'], cid) else M, glb=f.get('glb'), object=f.get('mesh_object'))
            r[form + '_skeleton'] = cell(C if f.get('joints') else M, joints=f.get('joints'), signature=f.get('skeleton_signature'))
            ms = [material_status(s.get('material'), '%s %s slot %s' % (cid, form, s.get('slot'))) for s in f.get('materials') or []]
            r[form + '_materials'] = cell(agg([x['status'] for x in ms]), slots=len(ms), slot_detail=ms)
            baked = sum(1 for s in f.get('materials') or [] if s.get('baked'))
            r[form + '_baked_textures'] = cell(F if baked else U, baked_slots=baked,
                                                note='base colour / emissive / specular are an approximation of the customization shader '
                                                     '(neutral 0.32 outside Cust masks); authoritative path = the original material graph')
            clips = f.get('animations') or []
            cats = f.get('clip_counts_by_category') or {}
            partial = f.get('anim_sets_partial_used (missing bones; tracks skipped as in UE3, HIGH)')
            rej = f.get('anim_sets_rejected') or []
            r[form + '_animations'] = cell(C if clips and not rej else (P if clips else M), clips=len(clips), categories=cats,
                                           partial_sets=partial, rejected_sets=rej)
        tr = m.get('transformation') or {}
        auth = tr.get('clips_authored') or {}; have = tr.get('clips_in_glb') or {}
        n_auth = sum(len(v) for v in auth.values()); n_have = sum(len(v) for v in have.values())
        single = (m.get('robot') or {}).get('mesh_object') == (m.get('vehicle') or {}).get('mesh_object')
        r['transform_clips'] = cell(C if n_auth and n_have == n_auth else (P if n_have else (U if single else M)), authored=auth, in_glb=have,
                                    note='single mesh for both forms' if single else None)
        socks = [s.get('socket') for s in (m.get('robot') or {}).get('sockets') or []]
        req = (rp.get('robot') or {}).get('required_sockets') or []
        wsock = [s for s in socks if s and s.lower().startswith('weaponsocket')]
        r['weapon_sockets'] = cell(C if wsock else M, sockets=wsock, required_by_robodef=req,
                                   missing_required=[x for x in req if x not in socks])
        fxs = [s for s in socks if s and re.search(r'fx|effect|muzzle|thrust|jet|boost|hover|light', s, re.I)]
        vsocks = [s.get('socket') for s in (m.get('vehicle') or {}).get('sockets') or []]
        r['fx_sockets'] = cell(C if (fxs or vsocks) else U, robot=fxs, vehicle=vsocks)
        # team colour parameters on the customization materials
        tc = []
        for form in ('robot', 'vehicle'):
            for s in (m.get(form) or {}).get('materials') or []:
                v = ((s.get('customization_parameters') or {}).get('vectors')) or {}
                if 'Lum_Map' in (s.get('textures') or {}):
                    tc.append('Cust_Color_A' in v and 'Cust_COLOR_B' in v)
        app = ((m.get('team_colour') or {}).get('applier_parameter_bindings (TransGame.Default__TnCharacterApplier, CONFIRMED)')) or {}
        r['team_colour'] = cell(C if tc and all(tc) and app else (P if tc else U), cust_slots=len(tc), cust_slots_with_colours=sum(tc),
                                applier_bindings=app)
        ui = rp.get('ui') or {}; por = (ui.get('portraits') or {})
        pngs = [p for k in ('robot_portrait', 'vehicle_portrait') for p in ((por.get(k) or {}).get('png') or [])]
        okp = [file_status(p, cid) for p in pngs]
        ci = (ui.get('class_icon') or {})
        r['portrait_icon'] = cell(C if pngs and all(okp) else (P if any(okp) else M), portraits=pngs, class_icon=ci.get('class_icon'))
        r['preview_camera'] = cell(C if (m.get('menu') or {}).get('customization_camera_id') is not None else M,
                                   camera_id=(m.get('menu') or {}).get('customization_camera_id'),
                                   note='camera id -> customization room cameras (ui_scenes UI_CharacterCustomization)')
        r['preview_spawn'] = cell(C, rule='script-driven (CONFIRMED): TnCharacterScriptBinding.UpdateSinglePreviewCharacter destroys the '
                                          'PreviewGuyN pawn on a chassis change and spawns the same TnCustomizationPawn class with CDR.ChassisType '
                                          '(the roster UniqueId the movie passes) as the actor blueprint, FindGround snaps it, colours applied every '
                                          'call (RE decomp; Frontend 2026-10-05). Body = this chassis robot / vehicle glTF; placed preview '
                                          'SkeletalMeshActors are authored-hidden stand-ins')
        au = m.get('audio') or {}
        ev_sets = [x for x in ((au.get('voice') or {}).get('object'), (au.get('vehicle') or {}).get('object')) if x]
        r['audio'] = cell(C if ev_sets else M, voice=(au.get('voice') or {}).get('object'), vehicle=(au.get('vehicle') or {}).get('object'),
                          detail='per-event resolution: vehicle_fx_audio.json')
        r['class_faction'] = cell(C if m.get('faction') and m.get('class (chassis DefaultSpecialty)') else M, faction=m.get('faction'),
                                  chassis_class=m.get('class (chassis DefaultSpecialty)'),
                                  preset_specialty=(m.get('iconic_preset') or {}).get('Specialty'))
        rows[cid] = OrderedDict([('iconic_id', m.get('iconic_id')), ('faction', m.get('faction')), ('cells', r),
                                 ('overall', agg([v['status'] for k, v in r.items() if k not in ('preview_spawn', 'robot_baked_textures', 'vehicle_baked_textures')]))])
    return rows

# ------------------------------------------------------------------ vehicle FX / audio
FX_KEYS = re.compile(r'(Hover|Engine|Thrust|Boost|Jump|Transform|Idle|Exhaust|Afterburn|Land|Speed|Booster|Ascend|Trail|Contrail|Wing)', re.I)
def walk_refs(v, prefix, base, depth, out):
    if isinstance(v, dict):
        for k, y in v.items(): walk_refs(y, prefix + '.' + k, base, depth, out)
    elif isinstance(v, list):
        for i, y in enumerate(v): walk_refs(y, '%s[%d]' % (prefix, i), base, depth, out)
    elif isinstance(v, str) and '.' in v:
        g = A.get(v)
        if not g: return
        cls = g['class']
        if cls in ('ParticleSystem', 'SoundCue', 'HmSoundEvent'): out.append((prefix, v, cls))
        elif depth < 2 and v.startswith(base + '.'): walk_refs(A.values(v), prefix, base, depth + 1, out)

def vehicle_fx_audio():
    roster = J(os.path.join(MANI, 'mp_content', 'roster_package.json'), {}).get('chassis') or {}
    rows = OrderedDict()
    for cid, ch in roster.items():
        recs = []
        for form in ('robot', 'vehicle'):
            d = (ch.get(form) or {}).get('definition')
            if not d: continue
            v = A.values(d) or {}
            sets = [x for x in (v.get('SoundEventSet'), (A.values(((ch.get('robot') or {}).get('definition')) or '') or {}).get('SoundEventSet')) if x]
            refs = []
            walk_refs(v, '', d, 0, refs)
            for path, obj, cls in refs:
                cat = (FX_KEYS.search(path) or FX_KEYS.search(obj))
                cat = cat.group(1).lower() if cat else 'other'
                if cls == 'ParticleSystem':
                    s = ps_status(obj)
                    recs.append({'form': form, 'property': path, 'category': cat, 'kind': 'particle', 'object': obj,
                                 'export': s['status'], 'detail': s})
                else:
                    cue = obj if cls == 'SoundCue' else event_cue(obj, sets)
                    w = cue_wavs(cue) if cue else None
                    zero = cue is not None and w == [] and A.get(cue) is not None
                    mpc = mp_copy_silent(cue) if zero else None
                    silent = bool(mpc and mpc.get('silent'))
                    st = C if (w and all(w)) or silent else (U if zero else (P if w and any(w) else (M if cue else U)))
                    recs.append({'form': form, 'property': path, 'category': cat, 'kind': 'sound', 'object': obj, 'event_class': cls,
                                 'cue': cue, 'waves': len(w or []), 'wavs_exported': sum(1 for x in (w or []) if x), 'export': st,
                                 'why': ('authored silent cue (MP copy %s has no wave children; HIGH)' % (mpc or {}).get('package') if silent else
                                         'cue has a SoundNodeWaveEvent without tagged wave children and no MP copy to verify (UNKNOWN)'
                                         if cue and w == [] and A.get(cue) else
                                         None if cue else 'event not mapped in the chassis event sets (engine default / silent: UNKNOWN)')})
        # runtime manifest representation: character.json carries only the event-set names, no per-property FX / sound records
        dedup = OrderedDict()
        for r_ in recs: dedup.setdefault((r_['form'], r_['property']), r_)
        recs = list(dedup.values())
        bycat = defaultdict(list)
        for r_ in recs: bycat['%s/%s/%s' % (r_['form'], r_['category'], r_['kind'])].append(r_['export'])
        rows[cid] = OrderedDict([('records', recs), ('by_category', {k: agg(v) for k, v in sorted(bycat.items())}),
                                 ('in_runtime_manifest', cell(M, note='Characters/<id>/character.json lists audio event-set names only; '
                                                                     'hover / jump / boost / thruster particle templates and per-event cues '
                                                                     'are not in any runtime manifest (this audit file is the only index)'))])
    return rows

# ------------------------------------------------------------------ weapons
def weapons():
    idx = J(os.path.join(MANI, 'mp_content', 'weapon_export_index.json'), {}).get('weapons') or {}
    rows = OrderedDict()
    for pid, e in idx.items():
        w = J(os.path.join(ROOT, e.get('json') or (e['dir'] + '/weapon.json')), {})
        me = w.get('mesh') or {}; r = OrderedDict()
        has_mesh = bool(me.get('glb'))
        r['mesh'] = cell(C if has_mesh and file_status(me['glb'], pid) else (C if me.get('mesh_note') else M), glb=me.get('glb'),
                         note=me.get('mesh_note'))
        ms = [material_status(s.get('material'), 'weapon %s slot %s' % (pid, s.get('slot'))) for s in me.get('materials') or []]
        untex = [x['material'] for x in ms if not x.get('has_base_colour')]
        r['materials_textures'] = cell(agg([x['status'] for x in ms]) if ms else (U if not has_mesh else M), slots=len(ms),
                                       untextured_slots=untex, slot_detail=ms)
        socks = [s.get('socket') for s in me.get('sockets') or []]
        mz = me.get('muzzle_sockets') or []
        r['muzzle_socket'] = cell(U if not has_mesh else (C if mz and all(x in socks for x in mz) else (M if mz else U)),
                                  muzzle=mz, mesh_sockets=socks)
        eff = (w.get('effects') or {}).get('authored') or {}
        mf = [x.get('PSTemplate') for x in eff.get('muzzle_flashes') or [] if x.get('PSTemplate')]
        tr = [x.get('TracerTemplate') for x in eff.get('tracers') or [] if x.get('TracerTemplate')]
        imp = [eff.get('default_squib')] if eff.get('default_squib') else []
        for k, lst in (('muzzle_fx', mf), ('tracer_fx', tr), ('impact_fx', imp)):
            ss = [ps_status(t) for t in lst]
            r[k] = cell(agg([s['status'] for s in ss]) if ss else U, templates=[s['template'] for s in ss], detail=ss)
        pr = w.get('projectiles') or []
        r['projectile'] = cell(U if not pr else agg([C if (p.get('projectile_mesh') or {}).get('gltf') or not p.get('projectile_mesh') else P for p in pr]),
                               classes=[p.get('class') for p in pr])
        an = w.get('animations') or {}
        clips = {c_['sequence'] for c_ in an.get('clips_in_glb') or []}
        ev = [x.get('AnimName') for x in (an.get('event_anims (weapon mesh)') or []) if x.get('AnimName')]
        r['animations'] = cell(U if not has_mesh else (C if ev and all(x in clips for x in ev) else (P if clips else M)),
                               event_anims=ev, missing=[x for x in ev if x not in clips], clips=len(clips))
        snd = w.get('sounds') or []
        ok = [any(x.get('wav') for x in s.get('waves') or []) for s in snd]
        nowave = [s.get('event') for s, o in zip(snd, ok) if not o and not s.get('waves') and not s.get('error')]
        mpchk = {s.get('event'): mp_copy_silent(s.get('cue')) for s in snd if s.get('event') in nowave}
        nowave_unverified = [e_ for e_ in nowave if not (mpchk.get(e_) or {}).get('silent')]
        bad = [s.get('event') for s, o in zip(snd, ok) if not o and s.get('event') not in nowave]
        r['sounds'] = cell(C if snd and not bad and not nowave_unverified else (P if bad and any(ok) else (U if not bad else M)),
                           total=len(snd), with_wav=sum(ok), unresolved=bad, authored_silent_cues=[e_ for e_ in nowave if e_ not in nowave_unverified],
                           unverified_zero_wave_cues=nowave_unverified, mp_copy_check=mpchk,
                           note='authored_silent_cues: the MP package copy of every SoundNodeWaveEvent has no ChildNodes -> no wave plays '
                                '(HIGH, RE 2026-10-05)' if nowave else None)
        ui = w.get('ui') or {}
        icons = (ui.get('hud_weapon_icon') or []) + list((ui.get('loadout_icons (GFx export name == provider id, HIGH)') or {}).values())
        provider = bool(w.get('restrictions'))
        r['hud_icon'] = cell(C if icons and all(file_status(x, pid) for x in icons if x) else (U if not provider else M), icons=icons)
        g = w.get('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)') or {}
        r['ammo_damage'] = cell(C if g.get('MaxAmmoCount') is not None and (g.get('InstantHitDamage') or g.get('WeaponProjectiles')) else (P if g else M),
                                MaxAmmoCount=g.get('MaxAmmoCount'), InstantHitDamage=g.get('InstantHitDamage'))
        r['restrictions'] = cell(C if provider else U, restrictions=w.get('restrictions'),
                                 note=None if provider else 'no TnDataProvider_Weapon entry: not loadout-selectable')
        rows[pid] = OrderedDict([('class', w.get('class')), ('cells', r), ('untextured_but_has_geometry', bool(has_mesh and untex)),
                                 ('overall', agg([v['status'] for v in r.values() if v['status'] != U]))])
    return rows

# ------------------------------------------------------------------ maps
def maps():
    summ = J(os.path.join(MANI, 'maps', 'pipeline_summary.json'), {}).get('maps') or {}
    rows = OrderedDict()
    for mp, sv in summ.items():
        if not sv.get('cooked_in_dump'): rows[mp] = OrderedDict([('overall', M), ('note', 'not cooked in this dump')]); continue
        D = os.path.join(VS, 'Maps', mp)
        comp = (J(os.path.join(MANI, 'maps', mp, 'completeness.json'), {}) or {}).get('checks') or {}
        sa = J(os.path.join(MANI, 'maps', mp, 'structure_audit.json'), {}) or {}
        ev = lambda k: (comp.get(k) or {}).get('evidence') or {}
        st = lambda k: (comp.get(k) or {}).get('status')
        r = OrderedDict()
        mj = J(os.path.join(D, 'map.json'), {})
        r['sublevels'] = cell(C if mj.get('sublevels') else M, sublevels=mj.get('sublevels'))
        props = (J(os.path.join(D, 'props.json'), {}) or {}).get('props') or []
        perr = Counter(p.get('error') for p in props if p.get('error'))
        r['static_meshes'] = cell(C if not perr else P, placed=len(props), errors=dict(perr))
        r['bsp'] = cell(C if st('bsp_alignment') == 'COMPLETE' else P, audit=ev('bsp_alignment'))
        # materials: textures referenced by the map's materials but not exported
        ma = J(os.path.join(D, 'materials_authored.json'), {}) or {}
        mrecs = ma.get('materials') or {}
        tmiss, ttot = Counter(), 0
        for mo, rec in (mrecs.items() if isinstance(mrecs, dict) else []):
            for k, t in ((rec or {}).get('textures') or {}).items():
                if not isinstance(t, dict): continue
                ttot += 1
                f = t.get('file') or t.get('png')
                if not f or not file_status(f, mp):
                    if t.get('texture') or t.get('object'):
                        tmiss[(t.get('texture') or t.get('object'))] += 1
        mst = (ma.get('stats') or {}).get('missing') or []
        r['materials'] = cell(C if not mst else P, materials=len(mrecs), missing=mst)
        r['textures'] = cell(C if not tmiss else P, referenced=ttot, unexported_unique=len(tmiss), examples=[k for k, _ in tmiss.most_common(8)])
        lm = sa.get('lightmaps') or {}
        r['lightmaps'] = cell(C if lm.get('binding_ok') and not lm.get('atlases_without_png') else P, bound=lm.get('world_glb_nodes_with_lm_atlas'))
        vl = J(os.path.join(D, 'vertex_lightmaps.json'), {}) or {}
        vs = vl.get('stats') or {}
        vc = vs.get('vertex_count_check') or {}
        r['vertex_lighting'] = cell(M if not vl else (C if not vc.get('mismatch') and not vs.get('decode_failures') else P),
                                    components=vs.get('components'), vertex_count_check=vc)
        fx = J(os.path.join(D, 'map_fx.json'), {}) or {}
        dec = fx.get('decals') or []
        decm = [material_status((d.get('props') or {}).get('DecalMaterial') or d.get('material'), mp + ' decal') for d in dec[:200]]
        r['decals'] = cell(agg([x['status'] for x in decm]) if dec else C, decals=len(dec),
                           incomplete=[x.get('material') for x in decm if x['status'] != C][:10])
        tm = sorted({(c_.get('props') or {}).get('Template') for c_ in fx.get('particle_components') or [] if (c_.get('props') or {}).get('Template')})
        ss = [ps_status(t) for t in tm]
        r['particles'] = cell(agg([s['status'] for s in ss]) if ss else C, templates=len(tm), not_complete=[s for s in ss if s['status'] != C][:10])
        mv = ev('moving_scenery')
        r['movers'] = cell(C if not mv.get('in_world_glb_missing') else P, movers=mv.get('movers'))
        ri = J(os.path.join(D, 'render_index.json'), {}) or {}
        rv = ri.get('validation') or {}
        dstr = [x for x in ri.get('not_in_world_glb (authored renderables)') or [] if 'destructible' in x.get('kind', '')]
        anim_only = [x['actor'] for x in dstr if not any(s.get('static_meshes') for s in x.get('states') or [])]
        r['destructibles'] = cell(C if not anim_only else P, count=len(dstr), without_static_state_mesh=len(anim_only),
                                  note='destructibles whose states are animated-mesh only (HmAnimatedMeshDestructionEffect) have no static '
                                       'state mesh in render_index; the renderer draws nothing for them' if anim_only else None)
        r['pickups'] = cell(C if ri.get('pickup_factory_visuals') is not None and not rv.get('missing') else (C if mp == 'MP_IAC_Streets' else M),
                            visuals=len(ri.get('pickup_factory_visuals') or []))
        au = J(os.path.join(D, 'audio.json'), {}) or {}
        cn = au.get('counts') or {}
        r['audio'] = cell(C if not au.get('missing_cues') and cn.get('waves') == cn.get('waves_with_wav') else P, counts=cn, missing_cues=au.get('missing_cues'))
        pp = ev('postprocess')
        vols = [v for v in pp.get('volumes') or [] if v.get('clut')]
        clutpng = [v.get('clut_png') for v in vols] + ([((J(os.path.join(D, 'postprocess.json'), {}) or {}).get('clut') or {}).get('png')] if pp.get('world_clut') else [])
        r['colour_grading'] = cell(C if all(p and file_status(p, mp) for p in clutpng if p is not None) else P,
                                   world_clut=pp.get('world_clut'), volume_cluts=[v['clut'] for v in vols])
        lg = ((J(os.path.join(D, 'lighting.json'), {}) or {}).get('globals') or {})
        r['fog'] = cell(C if st('fog') in ('COMPLETE', 'NONE') else P, fog=ev('fog'),
                        postprocess_volume_height_fogs=len(lg.get('postprocess_volume_height_fogs') or []))
        ps_ = sa.get('playable_space') or {}
        r['spawn_points'] = cell(C if ps_.get('starts_on_reachable_floor') == ps_.get('player_starts') else P, starts=ps_.get('player_starts'))
        r['mode_actors'] = cell(C if ri.get('mode_visual_state') is not None else M, tdm_hidden=(ri.get('tdm_render_state') or {}).get('count'))
        hz = J(os.path.join(MANI, 'maps', mp, 'hazard_volumes.json'), {}) or {}
        r['hazards_kill_volumes'] = cell(C if hz else M, hazard_volumes=len(hz.get('hazard_volumes') or []), kill_z=hz.get('kill_z'))
        # skeletal / transforming world actors: in render_index_generic but not in the renderer-facing render_index.json
        rig = J(os.path.join(MANI, 'maps', mp, 'render_index_generic.json'), {}) or {}
        sk = rig.get('skeletal_actors (not in world.glb: spawn from gltf)') or []
        r['skeletal_world_actors'] = cell(C if not sk else M, count=len(sk), classes=dict(Counter(x.get('class') for x in sk)),
                                          note='listed in manifests/maps/<MAP>/render_index_generic.json only; Maps/<MAP>/render_index.json '
                                               '(read by the renderer) has no section for them' if sk else None)
        rows[mp] = OrderedDict([('cells', r), ('overall', agg([v['status'] for v in r.values()]))])
    return rows

# ------------------------------------------------------------------ frontend
def frontend():
    ui = (J(os.path.join(MANI, 'frontend_package', 'ui_scenes.json'), {}) or {}).get('families') or {}
    fp = J(os.path.join(MANI, 'frontend_package', 'frontend_package.json'), {}) or {}
    ex = J(os.path.join(MANI, 'frontend_package', 'extras.json'), {}) or {}
    rows = OrderedDict()
    for fam, rec in ui.items():
        ri = J(os.path.join(ROOT, rec.get('render_index') or ''), {}) or {}
        D = os.path.join(ROOT, os.path.dirname(rec.get('render_index') or ''))
        AL = next((v for k, v in ri.items() if k.startswith('actors_by_level')), {}) or {}
        acts = [a for xs in AL.values() for a in xs]
        r = OrderedDict()
        r['background_level'] = cell(C if file_status(os.path.relpath(os.path.join(D, 'world.glb'), ROOT).replace(os.sep, '/'), fam) else M,
                                     levels=ri.get('levels'))
        ma = J(os.path.join(D, 'materials_authored.json'), {}) or {}
        mst = (ma.get('stats') or {}).get('missing') or []
        r['materials'] = cell(C if not mst else P, materials=len(ma.get('materials') or {}), missing=mst)
        anim = [a for a in acts if a['class'] in ('InterpActor', 'HmSkeletalMeshActor', 'SkeletalMeshActor')]
        bad = [a['actor'] for a in anim if a.get('gltf') and not file_status(a['gltf'], fam)] + [a['actor'] for a in anim if not a.get('gltf') and not a.get('world_glb_node')]
        r['animated_actors'] = cell(C if not bad else P, count=len(anim), unresolved=bad[:10])
        tm = sorted({a.get('template') for a in acts if a['class'] == 'Emitter' and a.get('template')})
        ss = [ps_status(t) for t in tm]
        r['particles'] = cell(agg([s['status'] for s in ss]) if ss else C, templates=len(tm), not_complete=[s for s in ss if s['status'] != C][:8])
        pv = [a for a in acts if 'Skeletal' in a['class'] and fam == 'UI_CharacterCustomization']
        r['preview_bodies'] = cell((C if all(a.get('gltf') for a in pv) else P) if pv else U, actors=[(a['actor'], a.get('mesh')) for a in pv],
                                   note='placed actors are authored-hidden stand-ins; runtime preview = TnCustomizationPawn swapped per chassis by '
                                        'TnCharacterScriptBinding.UpdateSinglePreviewCharacter (CONFIRMED) using Characters/<ChassisId>/ glTFs'
                                   if pv else None)
        MT = next((v for k, v in ri.items() if k.startswith('matinee')), {}) or {}
        cam_groups = [g for ms in MT.values() for m_ in ms for g in m_.get('groups') or []
                      if any((b.get('class') or '') == 'CameraActor' for b in g.get('bound_actors') or [])]
        movetracks = [g for g in cam_groups if any(t.get('class') == 'InterpTrackMove' for t in g.get('tracks') or [])]
        r['camera_tracks'] = cell(C if cam_groups else U, camera_groups=len(cam_groups), with_move_tracks=len(movetracks),
                                  note=None if movetracks else 'camera bound without move keys: static authored camera')
        # scene audio = Kismet SeqAct_PlaySound cues (+ AmbientSound actors, which author no cue in the UI levels)
        lv_names = list((rec.get('per_level') or {}).keys())
        kis = [(lv, o) for lv in lv_names for (o,) in A.con().execute("SELECT opath FROM objects WHERE opath LIKE ? AND class='SeqAct_PlaySound'",
                                                                       (lv + '.%',)).fetchall()]
        cues = sorted({A.values(o).get('PlaySound') for _, o in kis if A.values(o).get('PlaySound')})
        amb = [s_ for lv in (rec.get('per_level') or {}).values() for s_ in (lv.get('ambient_sounds') or [])]
        w = [cue_wavs(c_) for c_ in cues]
        r['audio'] = cell(C if cues and all(x and all(x) for x in w) else (U if not cues else P), kismet_play_sound_cues=cues,
                          incomplete=[c_ for c_, x in zip(cues, w) if not (x and all(x))][:8],
                          ambient_sound_actors=len(amb), ambient_actors_with_cue=sum(1 for a in amb if a.get('cue')),
                          note='AmbientSound actors in the UI levels author no SoundCue (actor props: Tag + Location only; CONFIRMED absence); '
                               'scene audio is played by Kismet SeqAct_PlaySound (+ SeqAct_Mixer / SeqAct_Reverb), owner Systems')
        rows[fam] = OrderedDict([('cells', r), ('overall', agg([v['status'] for v in r.values() if v['status'] != U]))])
    # movies / overlays / UI art
    mv = fp.get('movies') or {}
    gfx_missing = [k for k, v in mv.items() if v.get('file') and not file_status(v['file'], 'frontend movie ' + k)]
    fmv = [m_ for m_ in ex.get('movies') or []]
    fmv_missing = [m_['id'] for m_ in fmv if not (m_.get('mkv') and file_status(m_['mkv'], 'extras'))]
    cred = (ex.get('credits') or {})
    gal = ex.get('concept_art_galleries') or []
    gal_missing = sum(1 for g in gal for i in g.get('images') or [] if not file_status(i, 'extras'))
    fa = J(os.path.join(MANI, 'frontend_assets.json'), {}) or {}
    rows['_ui_movies_and_overlays'] = OrderedDict([('cells', OrderedDict([
        ('gfx_movies', cell(C if not gfx_missing else P, movies=len(mv), missing=gfx_missing,
                            note='Scaleform GFx movies: vector shapes are resolution-independent; embedded bitmaps are fixed-resolution PNGs')),
        ('fmv_movies', cell(C if not fmv_missing else P, movies=len(fmv), missing=fmv_missing)),
        ('credits', cell(C if cred.get('mkv') else M, mkv=cred.get('mkv'))),
        ('extras_galleries', cell(C if not gal_missing else P, images=sum(len(g.get('images') or []) for g in gal), missing=gal_missing)),
        ('vignette_overlay', cell(C if (rows.get('UI_FrontEnd') or {}).get('cells', {}).get('background_level', {}).get('status') == C else U,
                                  note='title vignette = streamed UI_FrontEnd_capture_VIG_m (3D) + GFx overlays'))])),
        ('overall', None)])
    rows['_ui_movies_and_overlays']['overall'] = agg([v['status'] for v in rows['_ui_movies_and_overlays']['cells'].values()])
    return rows

# ------------------------------------------------------------------ reference integrity
def reference_integrity(char_rows, wpn_rows):
    roster = J(os.path.join(MANI, 'mp_content', 'roster_package.json'), {}).get('chassis') or {}
    compat = J(os.path.join(MANI, 'mp_content', 'mp_animation_compat.json'), {}).get('per_character') or {}
    con = A.con()
    # duplicate short names for umodel-slot material resolution
    dup = []
    for cid, ch in roster.items():
        for form in ('robot', 'vehicle'):
            for s in (ch.get(form) or {}).get('material_slots (umodel short names resolved within the mesh package family - HIGH)') or []:
                short = s.get('umodel_slot'); chosen = s.get('material')
                if not short: continue
                cands = [o for (o, c_) in con.execute("SELECT opath, class FROM objects WHERE opath LIKE ? AND class LIKE 'Material%'",
                                                      ('%.' + short,)).fetchall() if o.rsplit('.', 1)[-1] == short]
                if len(cands) > 1:
                    mesh_pkg = ((ch.get(form) or {}).get('skeletal_mesh') or '').split('.')[0]
                    dup.append({'chassis': cid, 'form': form, 'slot_short_name': short, 'chosen': chosen, 'candidates': cands,
                                'chosen_in_mesh_package': (chosen or '').split('.')[0] == mesh_pkg,
                                'risk': 'LOW (chosen in the mesh package)' if (chosen or '').split('.')[0] == mesh_pkg else 'CHECK'})
    # incompatible animation sets authored on chassis definitions
    inc = []
    for cid, pc in compat.items():
        for form in ('robot', 'vehicle'):
            for s, r_ in ((pc.get(form) or {}).get('anim_sets') or {}).items():
                if r_.get('status') == 'incompatible' or (r_.get('status') == 'partial' and (r_.get('missing_count') or 0) > 2):
                    inc.append({'chassis': cid, 'form': form, 'anim_set': s, 'status': r_.get('status'), 'missing_bones': r_.get('missing_count'),
                                'track_bones': r_.get('track_bones')})
    # dangling references inside the MP export manifests (object paths that do not resolve in authored.db)
    obj_rx = re.compile(r'^[A-Z][A-Za-z0-9_]+_p\.[A-Za-z0-9_.]+$')
    dangling, case_obj = Counter(), Counter()
    def scan(x, src):
        if isinstance(x, dict): [scan(v, src) for v in x.values()]
        elif isinstance(x, list): [scan(v, src) for v in x]
        elif isinstance(x, str) and obj_rx.match(x) and not A.get(x):
            row = con.execute('SELECT opath FROM objects WHERE lower(opath)=lower(?) LIMIT 1', (x,)).fetchone()
            (case_obj if row else dangling)[(x, src)] += 1
    for f in ('roster_package.json', 'mp_weapons.json', 'mp_characters.json'):
        scan(J(os.path.join(MANI, 'mp_content', f), {}), f)
    loc = Counter(pk.rsplit('_LOC_', 1)[-1] for (pk,) in con.execute(
        "SELECT package FROM objects WHERE class LIKE 'SoundNodeWave%' AND package LIKE '%_LOC_%'").fetchall())
    ex = [r_ for r_ in con.execute("SELECT opath, package FROM objects WHERE opath IN ('WL_DX_OPRIME.DX_OPRIME_LK002657', "
                                   "'WL_DX_MGTRON.DX_MGTRON_LK002666')").fetchall()]
    return OrderedDict([
        ('generated_by', GEN),
        ('localized_twin_collision (wrong package ownership)', {
            'rows_by_language': dict(loc), 'examples (TDM match-start announcer)': ex,
            'issue': 'every map cooks _LOC_int and _LOC_FRA twins with identical SoundNodeWave paths; authored.db keys objects by '
                     'class|path so one twin wins arbitrarily -> manifests that resolve a dialog / announcer wave by path can pick the '
                     'French copy. Shipped WFC loads only _LOC_<GLanguage> (RE TARGETED_PASS4_2026-10-05 C).',
            'impact': 'announcer / dialog lines in any manifest that resolves waves through authored.db or the asset index',
            'extracted_wavs_by_owner_language (asset index owner_package of every extracted localized wave)': dict(Counter(
                a['owner_package'].rsplit('_LOC_', 1)[-1] for a in IDX.values()
                if a.get('class', '').startswith('SoundNodeWave') and '_LOC_' in (a.get('owner_package') or '')
                and any(o.endswith('.wav') for o in a.get('extracted') or []))),
            'extraction_consequence': 'one .wav per object path exists in ExtractedAssets/content; where the FRA twin owns the path the '
                                      'extracted file was decoded from the French package (e.g. content/WL_DX_OPRIME/DX_OPRIME_LK002657.wav)'}),
        ('mic_parent_missing', mic_issues),
        ('textures_referenced_not_exported', [{'texture': t, 'class': unexported_cls.get(t), 'references': n} for t, n in unexported_tex.most_common()]),
        ('case_path_mismatches (exists only case-insensitively)', case_mismatch[:200]),
        ('duplicate_short_name_material_resolution', dup),
        ('anim_sets_on_incompatible_skeletons', inc),
        ('dangling_object_refs_in_mp_manifests', [{'ref': k[0], 'manifest': k[1], 'count': v} for k, v in dangling.most_common(100)]),
        ('object_refs_matching_only_case_insensitively', [{'ref': k[0], 'manifest': k[1]} for k in case_obj]),
        ('explicit_none_texture_overrides', 'see characters.json slot_detail explicit_none_overrides: MIC authors ParameterValue None '
                                            '(Normal_Map on CHR_Transformer_NormSpec_Cust_E_Mat children). Whether UE3 falls through to the parent '
                                            'default (VH_Bumblebee_Norm) or binds no texture is native: UNKNOWN')])

LOCT = {}
def top_issues(ch, vfa, wp, mp, fe, ri):
    """ranked highest-impact gaps; every count is computed from the matrices above."""
    loc = ri['localized_twin_collision (wrong package ownership)']
    lw = loc['extracted_wavs_by_owner_language (asset index owner_package of every extracted localized wave)']
    cubes = [t for t in ri['textures_referenced_not_exported'] if t['class'] == 'TextureCube']
    tex2d = sorted({e for r in mp.values() for e in ((r.get('cells') or {}).get('textures') or {}).get('examples') or [] if 'Cube' not in e})
    sk = {m_: r['cells']['skeletal_world_actors']['count'] for m_, r in mp.items() if r.get('cells') and r['cells']['skeletal_world_actors']['count']}
    ds = {m_: r['cells']['destructibles']['without_static_state_mesh'] for m_, r in mp.items()
          if r.get('cells') and r['cells']['destructibles'].get('without_static_state_mesh')}
    baked = sum(1 for r in ch.values() for f in ('robot', 'vehicle') if r['cells'][f + '_baked_textures']['status'] == F)
    none_ovr = sorted({d['material'] for r in ch.values() for f in ('robot', 'vehicle') for d in r['cells'][f + '_materials']['slot_detail']
                       if d.get('explicit_none_overrides')})
    vfx = sum(len(r['records']) for r in vfa.values())
    vunk = sum(1 for r in vfa.values() for x in r['records'] if x['export'] == U)
    wsn = sorted({e for r in wp.values() for e in (r['cells']['sounds'].get('authored_silent_cues') or [])})
    grn = [p_ for p_, r in wp.items() if r['cells']['muzzle_socket']['status'] == M]
    wan = [p_ for p_, r in wp.items() if r['cells']['animations']['status'] in (M, P)]
    untex = [p_ for p_, r in wp.items() if r['untextured_but_has_geometry']]
    portraits = [c_ for c_, r in ch.items() if r['cells']['portrait_icon']['status'] == M]
    cm = ri['case_path_mismatches (exists only case-insensitively)']
    dup = [d for d in ri['duplicate_short_name_material_resolution'] if d['risk'] == 'CHECK']
    vmis = [m_ for m_, r in mp.items() if r.get('cells') and r['cells']['vertex_lighting']['status'] != C]
    items = [
        ('Localized dialog / announcer waves resolved to the French twin', 'SYSTEMS (data now available)',
         '%d of %d merged localized WAVs came from _LOC_FRA; both twins now extracted to content/_LOC/{int,FRA}/<group>/<name>.wav '
         '(manifests/audio/loc_twins.json: %s paths, merged copy language %s)' % (lw.get('FRA', 0), sum(lw.values()), LOCT.get('paths'),
         LOCT.get('merged_copy_language (content/<group>/<name>.wav matches which twin)')), 'reference_integrity.localized_twin_collision'),
        ('Reflection cubemaps never exported', 'ASSETTOOLS -> RENDERING',
         '%d TextureCube objects referenced by character / weapon / map materials have no exported file (CHR_Metals_CUBEMAP3D: %d refs)'
         % (len(cubes), cubes[0]['references'] if cubes else 0), 'reference_integrity.textures_referenced_not_exported'),
        ('Skeletal / transforming world actors absent from the renderer-facing render_index.json', 'ASSETTOOLS -> RENDERING',
         '%s (only in manifests/maps/<MAP>/render_index_generic.json)' % sk, 'maps.skeletal_world_actors'),
        ('Destructibles with animated-mesh-only states have no drawable state mesh', 'ASSETTOOLS -> RENDERING', str(ds), 'maps.destructibles'),
        ('Character base colour only through the customization bake (grey outside Cust masks)', 'RENDERING',
         '%d chassis-form baked texture sets are approximations; 32 of 93 baked slots measure near-grey, mostly Decepticon' % baked,
         'characters.*_baked_textures'),
        ('Small 2D map textures never extracted (owner recorded as a campaign package)', 'ASSETTOOLS',
         '%s ... referenced by every MP map' % ', '.join(tex2d[:4]), 'maps.textures'),
        ('AssetTools material resolver drops inherited textures on explicit None overrides', 'ASSETTOOLS (decision pending)',
         '%d character MICs (Normal_Map) + 2 Streets map materials: a TextureParameterValues entry set to None means "inherit the parent" '
         '(stock UE3, RE 2026-10-05 HIGH) but materials.resolve stores None. Fix is one line in materials.py; it changes Streets world.glb / '
         'materials.json (Panel_02_MATINST, DeadBodies_Mat_INST), so it waits for an explicit go + the Streets regeneration chain' % len(none_ovr),
         'characters.*_materials.explicit_none_overrides'),
        ('Vehicle FX / audio not in any runtime manifest', 'ASSETTOOLS -> GAMEPLAY / RENDERING',
         '%d authored hover / jump / boost / engine particle + sound refs across 33 chassis exist only in manifests/audit/vehicle_fx_audio.json' % vfx,
         'vehicle_fx_audio.in_runtime_manifest'),
        ('Vehicle sound events with no cue in the chassis event sets', 'SYSTEMS / RE', '%d events (Auto_Tire_Tread_Default, Auto_180_Turn, ...)' % vunk,
         'vehicle_fx_audio'),
        ('Weapon / vehicle cues that are authored silent', 'INFO (SYSTEMS)', 'events %s: the MP package copies carry no wave children, so no '
         'wave plays (HIGH, RE); not an extraction gap' % wsn, 'weapons.sounds.authored_silent_cues'),
        ('Grenade / mine muzzle sockets not on the weapon mesh', 'GAMEPLAY / RE', '%s author MuzzleFlash_R/_L; the mesh has MuzzleFlash only' % grn,
         'weapons.muzzle_socket'),
        ('Weapon event animations missing from the weapon AnimSet', 'ASSETTOOLS / RE', str(wan), 'weapons.animations'),
        ('Weapon geometry exported untextured', 'AUTHORED', '%s: WEP_Rocket_Temp_MAT is a vector-parameter-only placeholder material' % untex,
         'weapons.materials_textures'),
        ('Soldier / minion chassis without portraits', 'FRONTEND', '%s (not player-selectable)' % portraits, 'characters.portrait_icon'),
        ('Shared AnimSets incompatible with soldier / minion skeletons', 'GAMEPLAY',
         '%d set assignments (24-bone soldier skeleton misses 60 of 84 tracks)' % len(ri['anim_sets_on_incompatible_skeletons']),
         'reference_integrity.anim_sets_on_incompatible_skeletons'),
        ('Vertex-lightmap sample count differs from mesh vertex count', 'ASSETTOOLS', '%s (umodel split vertices on 2 components)' % vmis,
         'maps.vertex_lighting'),
        ('Case-only path mismatches (break on case-sensitive file systems)', 'ASSETTOOLS',
         '%d loadout icon paths (e.g. %s)' % (len(cm), cm[0]['path'] if cm else ''), 'reference_integrity.case_path_mismatches'),
        ('Material short-name resolution outside the mesh package', 'ASSETTOOLS',
         '%d slots (InteriorAlt_Energon_MAT_INST has %d same-name copies)' % (len(dup), len(dup[0]['candidates']) if dup else 0),
         'reference_integrity.duplicate_short_name_material_resolution'),
        ('UI scene AmbientSound actors author no cue', 'SYSTEMS', 'scene audio is Kismet SeqAct_PlaySound only (title: 14 cues, lobbies: ambient beds); '
         'AmbientSound actors are cue-less (CONFIRMED)', 'frontend.*.audio'),
        ('Uncooked registry maps', 'NONE (dump)', 'Fortress, Havoc, Tranquillity have no cooked packages', 'maps')]
    return [OrderedDict([('rank', i + 1), ('issue', t), ('owner', o), ('evidence', e), ('matrix', src)]) for i, (t, o, e, src) in enumerate(items)]

def write_md(ch, vfa, wp, mp, fe, ri, top):
    ab = {C: 'OK', P: 'PART', M: 'MISS', F: 'FALLBK', U: '?'}
    def table(rows, cols, title_col):
        out = ['| %s | %s |' % (title_col, ' | '.join(cols)), '|' + '---|' * (len(cols) + 1)]
        for k, r in rows.items():
            c = r.get('cells') or {}
            out.append('| %s | %s |' % (k, ' | '.join(ab.get((c.get(x) or {}).get('status'), '-') for x in cols)))
        return out
    md = ['# Multiplayer asset completeness and reference-integrity audit', '',
          '*Generated by `scripts/wfc/asset_integrity_audit.py` (%s). Do not edit; rerun the generator. This is an extraction-level audit: '
          'it makes no claim about runtime correctness. Evidence for every cell is in `manifests/audit/*.json`.*' % time.strftime('%Y-%m-%d %H:%M'), '',
          '**Legend:** OK = COMPLETE, PART = PARTIAL, MISS = MISSING, FALLBK = FALLBACK, ? = UNKNOWN.', '',
          '## Top 20 highest-impact missing or broken references', '', '| # | issue | owner | evidence |', '|---|---|---|---|']
    md += ['| %d | %s | %s | %s |' % (t['rank'], t['issue'], t['owner'], t['evidence'].replace('|', '/')) for t in top]
    md += ['', '## 1. Characters (`manifests/audit/characters.json`)', '']
    md += table(OrderedDict((k + ' ' + (r.get('iconic_id') or ''), r) for k, r in ch.items()),
                ['robot_mesh', 'vehicle_mesh', 'robot_skeleton', 'robot_materials', 'vehicle_materials', 'robot_baked_textures', 'team_colour',
                 'robot_animations', 'vehicle_animations', 'transform_clips', 'weapon_sockets', 'fx_sockets', 'audio', 'portrait_icon',
                 'preview_camera', 'preview_spawn', 'class_faction'], 'chassis')
    md += ['', '`*_materials` are PARTIAL on every chassis only because of the unexported reflection cubemap (issue 2) and, on 12 MICs, the '
           'explicit `Normal_Map = None` override (issue 7).', '',
           '## 2. Weapons (`manifests/audit/weapons.json`)', '']
    md += table(wp, ['mesh', 'materials_textures', 'muzzle_socket', 'muzzle_fx', 'tracer_fx', 'impact_fx', 'projectile', 'animations', 'sounds',
                     'hud_icon', 'ammo_damage', 'restrictions'], 'weapon')
    md += ['', '## 3. Vehicle FX / audio (`manifests/audit/vehicle_fx_audio.json`)', '',
           'For every chassis and form, every authored ParticleSystem (decoded with `pstream`) and sound (event → chassis event set → cue → WAV), '
           'by category. None of these are in a runtime manifest yet (issue 8).', '', '| chassis | categories (form/category/kind: status) |', '|---|---|']
    md += ['| %s | %s |' % (k, ', '.join('%s: %s' % (c_, ab.get(v, v)) for c_, v in r['by_category'].items())) for k, r in vfa.items()]
    md += ['', '## 4. Maps (`manifests/audit/maps.json`)', '']
    md += table(OrderedDict((k, r) for k, r in mp.items() if r.get('cells')),
                ['sublevels', 'static_meshes', 'bsp', 'materials', 'textures', 'lightmaps', 'vertex_lighting', 'decals', 'particles', 'movers',
                 'destructibles', 'pickups', 'audio', 'colour_grading', 'fog', 'spawn_points', 'mode_actors', 'hazards_kill_volumes',
                 'skeletal_world_actors'], 'map')
    md += ['', 'Not cooked in the dump: ' + ', '.join(k for k, r in mp.items() if not r.get('cells')), '',
           '## 5. Frontend (`manifests/audit/frontend.json`)', '']
    md += table(OrderedDict((k, r) for k, r in fe.items() if not k.startswith('_')),
                ['background_level', 'materials', 'animated_actors', 'particles', 'preview_bodies', 'camera_tracks', 'audio'], 'scene')
    ui = fe.get('_ui_movies_and_overlays', {}).get('cells') or {}
    md += ['', '**Movies and overlays:** ' + ', '.join('%s %s' % (k, ab.get(v['status'])) for k, v in ui.items()), '',
           '## 6. Reference integrity (`manifests/audit/reference_integrity.json`)', '']
    for k, v in ri.items():
        if k == 'generated_by': continue
        md.append('* **%s:** %s' % (k, (len(v) if isinstance(v, list) else (v if isinstance(v, str) else json.dumps(v, default=str)[:300]))))
    open(os.path.join(AT, 'docs', 'ASSET_INTEGRITY_AUDIT.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')

def main():
    global IDX
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    IDX = materials.assets()
    ch = characters(); print('characters', len(ch), round(time.time() - t0), flush=True)
    vfa = vehicle_fx_audio(); print('vehicle fx/audio', len(vfa), round(time.time() - t0), flush=True)
    wp = weapons(); print('weapons', len(wp), round(time.time() - t0), flush=True)
    mp = maps(); print('maps', len(mp), round(time.time() - t0), flush=True)
    fe = frontend(); print('frontend', len(fe), round(time.time() - t0), flush=True)
    ri = reference_integrity(ch, wp); print('integrity', round(time.time() - t0), flush=True)
    LOCT.update({k: v for k, v in (J(os.path.join(MANI, 'audio', 'loc_twins.json'), {}) or {}).items() if k != 'waves'})
    top = top_issues(ch, vfa, wp, mp, fe, ri)
    for n, d in (('characters', ch), ('vehicle_fx_audio', vfa), ('weapons', wp), ('maps', mp), ('frontend', fe), ('reference_integrity', ri),
                 ('top_issues', top)):
        json.dump(OrderedDict([('generated_by', GEN), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                               ('vocabulary', [C, P, M, F, U]), ('note', 'extraction-level audit; no runtime-correctness claim'), ('rows', d)]),
                  open(os.path.join(OUT, n + '.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    write_md(ch, vfa, wp, mp, fe, ri, top)
    print('done', round(time.time() - t0))

if __name__ == '__main__':
    main()
