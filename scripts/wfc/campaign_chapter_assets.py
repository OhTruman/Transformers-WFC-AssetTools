"""Campaign chapter asset manifest (Integration 2026-10-18; campaign background prep). Reusable: python campaign_chapter_assets.py <CH>
(A1_IAC, A2_KON, ... D5_OME).

Everything the chapter loads: the persistent level + every streaming sublevel (VerticalSlice campaign streaming.json) and their package
dependencies. Console cooks are seek-free, so each level package carries its content inline under the source package names; the set
of loaded objects is the union of the level packages' exports (deduplicated by object path). Per class: count, cooked bytes, extraction
status (ExtractedAssets/content files), material translator status, FX pstream status, sound / dialog files (+ _LOC twins), Kismet /
matinee (incl. live_without_actor), AI factories, movies, checkpoints, HUD / objective strings, and imports the dump cannot resolve.
Read-only. Writes manifests/campaign/<ch_lower>_assets.json.
"""
import glob, json, os, sqlite3, sys
from collections import Counter, OrderedDict as OD, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
EA = os.path.join(TR, 'ExtractedAssets'); CONTENT = os.path.join(EA, 'content')
VS = os.environ.get('WFC_VS_ROOT') or os.path.join(ROOT, 'work', 'campaign_pilot', 'VerticalSlice')
NM = os.path.join(ROOT, 'manifests', 'next_map')
INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))

GROUPS = OD([
    ('static_meshes', ['StaticMesh']),
    ('skeletal_meshes', ['SkeletalMesh']),
    ('materials', ['Material', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying', 'DecalMaterial']),
    ('textures', ['Texture2D', 'TextureCube', 'TextureMovie', 'TextureFlipBook', 'TextureRenderTarget2D']),
    ('lightmap_textures', ['LightMapTexture2D', 'ShadowMapTexture2D']),
    ('fx_templates', ['ParticleSystem']),
    ('sound_cues', ['SoundCue']),
    ('sound_waves', ['SoundNodeWave', 'SoundNodeWaveEx']),
    ('anim_sets', ['AnimSet']),
    ('anim_sequences', ['AnimSequence']),
    ('facefx', ['FaceFXAsset', 'FaceFXAnimSet']),
    ('physics_assets', ['PhysicsAsset']),
    ('kismet_sequences', ['Sequence', 'PrefabSequence']),
    ('matinee_data', ['InterpData']),
    ('gfx_movies', ['SwfMovie', 'GFxMovieInfo']),
    ('fonts', ['Font']),
    ('shader_caches', ['ShaderCache']),
])
EXT = {'static_meshes': ['.gltf'], 'skeletal_meshes': ['.gltf'], 'textures': ['.png', '.dds'], 'sound_waves': ['.wav', '.fsb'],
       'anim_sets': ['.anim.gltf'], 'facefx': ['.fxa'], 'gfx_movies': ['.gfx', '.swf']}

def extracted(opath, exts):
    base = os.path.join(CONTENT, *opath.split('.'))
    return any(os.path.exists(base + e) for e in exts)

def wave_files(opath):
    """where a wave's .wav / .fsb was extracted: plain (content/<pkg>), INT and FRA (content/_LOC/<lang>/<pkg> or content/<pkg>_<LANG>)"""
    pkg, rest = opath.split('.', 1); parts = rest.split('.')
    cand = {'plain': [os.path.join(CONTENT, pkg, *parts)],
            'int': [os.path.join(CONTENT, '_LOC', 'int', pkg, *parts), os.path.join(CONTENT, pkg + '_INT', *parts)],
            'fra': [os.path.join(CONTENT, '_LOC', 'FRA', pkg, *parts), os.path.join(CONTENT, pkg + '_FRA', *parts)]}
    return {k: any(os.path.exists(b + e) for b in v for e in ('.wav', '.fsb')) for k, v in cand.items()}

SCRIPT_PKGS = {'Core', 'Engine', 'WinDrv', 'GFxUI', 'HM_Engine', 'TransGame', 'TransContent', 'IpDrv', 'XAudio2', 'OnlineSubsystemLive',
               'GameFramework', 'UnrealEd', 'Editor'}

def translator_sets():
    """Rendering's material -> GLSL translator outputs (Rebuild/work/render/<map>/materials_glsl.json): material -> 'ok' / 'error'."""
    st = {}
    for f in glob.glob(os.path.join(TR, 'Rebuild', 'work', 'render', '*', 'materials_glsl.json')):
        try: d = json.load(open(f, encoding='utf-8'))
        except Exception: continue
        for k, v in d.items():
            if not isinstance(v, dict): continue
            ok = bool(v.get('glsl')) and not v.get('error')
            if st.get(k) != 'ok': st[k] = 'ok' if ok else 'error'
    return st

def master_of(opath, depth=0):
    if depth > 16: return opath
    r = DB.execute('select class, props from objects where opath=?', (opath,)).fetchone()
    if not r: return opath
    if r[0] in ('Material', 'DecalMaterial'): return opath
    p = json.loads(r[1]) if r[1] else {}
    par = p.get('Parent')
    return master_of(par, depth + 1) if par else opath

def load(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else None

def main(ch):
    mp_dir = os.path.join(VS, 'Maps', ch)
    st = load(os.path.join(mp_dir, 'streaming.json'))
    levels = sorted(st['sublevels'])
    known = {r[0] for r in INV.execute('select package from packages')}
    lacking_levels = [l for l in levels if l not in known]
    levels = [l for l in levels if l in known]
    low = {k.lower(): k for k in known}
    companions = OD((l, OD((suf, low.get((l + suf).lower())) for suf in ('_LM', '_LOC_int', '_LOC_FRA'))) for l in levels)
    loc_int = [c['_LOC_int'] for c in companions.values() if c['_LOC_int']]
    loc_fra = [c['_LOC_FRA'] for c in companions.values() if c['_LOC_FRA']]
    lm = [c['_LM'] for c in companions.values() if c['_LM']]
    union_pkgs = levels + lm + loc_int          # an INT build loads level + _LM + _LOC_int; FRA swaps _LOC_int for _LOC_FRA
    deps = sorted({d for l in union_pkgs for (d,) in INV.execute('select depends_on from package_deps where package=?', (l,))} - set(union_pkgs))
    loaded = union_pkgs + loc_fra + deps
    ph = ','.join('?' * len(union_pkgs))

    # every export of the level packages, deduplicated by object path
    objs = {}
    per_level = defaultdict(lambda: [0, 0])
    for pkg, cls, opath, size in INV.execute('select package, class, opath, serial_size from exports where package in (%s)' % ph, union_pkgs):
        per_level[pkg][0] += 1; per_level[pkg][1] += size or 0
        o = objs.get(opath)
        if o is None: objs[opath] = [cls, size or 0, {pkg}]
        else: o[1] = max(o[1], size or 0); o[2].add(pkg)
    by_cls = defaultdict(list)
    for o, (cls, size, pk) in objs.items(): by_cls[cls].append((o, size, pk))

    trans = translator_sets()
    groups = OD()
    for g, classes in GROUPS.items():
        items = sorted(x for c in classes for x in by_cls.get(c, []))
        rows = []
        for o, size, pk in items:
            r = OD([('object', o), ('class', objs[o][0]), ('bytes', size), ('levels', sorted(pk))])
            if g in EXT: r['extracted'] = extracted(o, EXT[g])
            if g == 'materials':
                if o.startswith('EngineMaterials.'): r['translator'] = 'engine_default'
                elif trans.get(o) == 'ok': r['translator'] = 'translated'
                elif trans.get(o) == 'error': r['translator'] = 'translator_error'
                else:
                    m = master_of(o); r['master'] = m
                    r['translator'] = 'candidate' if trans.get(m) == 'ok' else 'missing'   # refined below against translated masters
            if g == 'sound_waves':
                r['files'] = wave_files(o); r['extracted'] = any(r['files'].values())
            rows.append(r)
        s = OD([('classes', classes), ('count', len(rows)), ('bytes', sum(r['bytes'] for r in rows))])
        if g in EXT: s['extracted'] = sum(1 for r in rows if r.get('extracted')); s['not_extracted'] = [r['object'] for r in rows if not r.get('extracted')]
        if g == 'materials': s['translator'] = dict(Counter(r['translator'] for r in rows))
        if g == 'sound_waves':
            s['files'] = OD((k, sum(1 for r in rows if r['files'][k])) for k in ('plain', 'int', 'fra'))
            s['localized_without_fra_twin'] = [r['object'] for r in rows if r['files']['int'] and not r['files']['fra']]
        groups[g] = OD([('summary', s), ('items', rows)])

    # material translator: candidate = master material translated somewhere (instance only adds parameters)
    tr_masters = set()
    for k, v in trans.items():
        if v == 'ok': tr_masters.add(master_of(k))
    for r in groups['materials']['items']:
        if r['translator'] == 'missing' and r.get('master') in tr_masters: r['translator'] = 'candidate'
    groups['materials']['summary']['translator'] = dict(Counter(r['translator'] for r in groups['materials']['items']))

    # FX: pstream decode status per template
    import pstream
    fxs = Counter()
    for r in groups['fx_templates']['items']:
        try:
            s = pstream.system(r['object'])
            if s.get('missing_in'): r['pstream'] = 'not_found'; fxs['not_found'] += 1; continue
            L = [L for e in s['emitters'] for L in e['lods']]
            bad = [x for x in L if x.get('compiled_modules_error') or not x.get('assignment_complete', False)]
            prov = sum(1 for x in L for m in x.get('compiled_modules') or [] for d in m['distributions'] if d.get('confidence') != 'CONFIRMED')
            r['pstream'] = 'COMPLETE' if not bad and not prov else 'PARTIAL'
            r['lods'] = len(L); r['provisional_distributions'] = prov
        except Exception as ex:
            r['pstream'] = 'error'; r['error'] = str(ex)[:200]
        fxs[r['pstream']] += 1
    groups['fx_templates']['summary']['pstream'] = dict(fxs)

    # sound cues: wave files
    cue_missing = []
    for r in groups['sound_cues']['items']:
        c = A.cue(r['object'])
        ws = c.get('waves') or []
        r['waves'] = len(ws)
        r['waves_without_file'] = [w['wave'] for w in ws if not any(wave_files(w['wave']).values())]
        cue_missing += r['waves_without_file']
    groups['sound_cues']['summary']['waves_without_file'] = sorted(set(cue_missing))

    # imports the dump cannot resolve
    exp_all = None
    unresolved = Counter(); outside = defaultdict(set); script_refs = Counter()
    loaded_set = set(loaded)
    for pkg, path, cls in INV.execute('select package, path, class from imports where package in (%s)' % ph, union_pkgs):
        if cls == 'Package' or not path or '.' not in path: continue
        top = path.split('.', 1)[0]
        if top in SCRIPT_PKGS or cls == 'Class': script_refs[top] += 1; continue
        if path in objs: continue
        hits = [h for (h,) in INV.execute('select package from exports where opath=?', (path,))]
        if not hits: unresolved[path] += 1
        elif not set(hits) & loaded_set: outside[path].update(hits)

    def nm(name): return load(os.path.join(NM, '%s_%s.json' % (ch, name)))
    kis, mat, pf, dlg, obj = nm('kismet'), nm('matinee'), nm('pawn_factories'), nm('dialog'), nm('objectives')
    mv = load(os.path.join(ROOT, 'manifests', 'movies', 'movies_webm_manifest.json')) or {}
    tag = ch.split('_')[0].lower()
    movies = OD((k, OD([('source', v.get('source')), ('duration_s', v.get('source_duration_s'))]))
                for k, v in (mv.get('movies') or {}).items() if k.lower().startswith('fmv_' + tag))
    out = OD()
    out['chapter'] = ch
    out['generated_by'] = 'AssetTools/scripts/wfc/campaign_chapter_assets.py'
    out['method'] = ('loaded set = persistent level + every streaming sublevel in streaming.json (+ package_deps); objects = union of the '
                     'level packages\' exports by object path (seek-free cook: content is inline). bytes = cooked export serial size '
                     '(largest copy when an object is cooked into several levels).')
    out['levels'] = OD([('persistent', st.get('persistent_level')), ('count', len(levels)),
                        ('per_level', OD((l, OD([('kind', (st['sublevels'].get(l) or {}).get('kind')), ('exports', per_level[l][0]),
                                                 ('bytes', per_level[l][1])])) for l in levels)),
                        ('not_in_dump', lacking_levels)])
    out['companion_packages'] = OD([('per_level', companions), ('lightmaps', len(lm)), ('loc_int', len(loc_int)), ('loc_fra', len(loc_fra)),
                                    ('loc_fra_bytes', sum(sz or 0 for (sz,) in INV.execute(
                                        'select serial_size from exports where package in (%s)' % ','.join('?' * len(loc_fra)), loc_fra)) if loc_fra else 0),
                                    ('note', 'objects / bytes below count an INT build (level + _LM + _LOC_int); FRA swaps in _LOC_FRA')])
    out['package_dependencies'] = deps
    out['totals'] = OD([('distinct_objects', len(objs)), ('bytes_distinct_objects', sum(v[1] for v in objs.values())),
                        ('bytes_all_level_packages', sum(v[1] for v in per_level.values())),
                        ('by_group', OD((g, OD([('count', v['summary']['count']), ('bytes', v['summary']['bytes'])])) for g, v in groups.items()))])
    out['translator_status_definition'] = ('PROVISIONAL (AssetTools derivation; Rendering\'s translator has not run on campaign maps): '
        'translated = the material has GLSL without error in some Rebuild/work/render/<map>/materials_glsl.json; translator_error = present '
        'there with an error; candidate = not translated itself but its master Material is the master of a translated material (the '
        'instance only changes parameters); missing = master never seen by the translator; engine_default = EngineMaterials.*')
    out['groups'] = groups
    out['kismet'] = OD([('source', 'manifests/next_map/%s_kismet.json' % ch), ('counts_by_level', (kis or {}).get('counts')),
                        ('summary', (kis or {}).get('summary'))]) if kis else None
    out['matinee'] = OD([('source', 'manifests/next_map/%s_matinee.json' % ch), ('counts', (mat or {}).get('counts'))]) if mat else None
    out['ai'] = OD([('source', 'manifests/next_map/%s_pawn_factories.json' % ch), ('counts', (pf or {}).get('counts'))]) if pf else None
    out['dialog'] = OD([('source', 'manifests/next_map/%s_dialog.json' % ch), ('counts', (dlg or {}).get('counts'))]) if dlg else None
    out['objectives'] = OD([('source', 'manifests/next_map/%s_objectives.json' % ch), ('counts', (obj or {}).get('counts')),
                            ('bank', [OD([('key', b.get('key')), ('int', (b.get('text') or {}).get('int')), ('fra', (b.get('text') or {}).get('fra'))])
                                      for b in (obj or {}).get('bank') or []])]) if obj else None
    out['checkpoints'] = [OD([('checkpoint', c.get('checkpoint')), ('tag', c.get('tag')), ('display_order', c.get('display_order')),
                              ('streaming_state', c.get('streaming_state_name'))]) for c in st.get('checkpoints') or []]
    out['movies'] = movies
    out['dump_lacks'] = OD([
        ('levels_in_streaming_not_cooked', lacking_levels),
        ('imports_unresolved (content: no export with that path in any dumped package)', OD(sorted(unresolved.items()))),
        ('imports_resolved_only_in_other_packages (object -> packages that export it)', OD((k, sorted(v)) for k, v in sorted(outside.items()))),
        ('script_or_native_refs (not content; by package)', OD(sorted(script_refs.items()))),
        ('not_extracted_by_group', OD((g, len(v['summary'].get('not_extracted', []))) for g, v in groups.items() if g in EXT)),
        ('sound_waves_without_file', groups['sound_cues']['summary']['waves_without_file'])])
    path = os.path.join(ROOT, 'manifests', 'campaign', ch.split('_')[0].lower() + '_assets.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1)
    print('wrote', path)
    print(json.dumps(out['totals'], indent=1)[:2500])
    print('translator', groups['materials']['summary']['translator'], 'pstream', groups['fx_templates']['summary']['pstream'])
    print('lacks', json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in out['dump_lacks'].items()}))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'A1_IAC')
