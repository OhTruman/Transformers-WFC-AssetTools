"""Inventory the (read-only) Game Dump.

Produces, under AssetTools/manifests:
  files.json            every file: path, size, magic, md5, TOC check, format guess
  packages.json         every UE3 package: header, flags, deps, class histogram, role
  packages/<pkg>.json   full import/export tables for each package
  inventory.db          SQLite: files, packages, exports, imports, package_deps
  summary.json          totals, extensions, category rollups

Game Dump is only ever opened for reading.
"""
import hashlib, json, os, re, sqlite3, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DUMP = os.path.join(ROOT, 'Game Dump')
MANI = os.path.join(ROOT, 'AssetTools', 'manifests')

# ---------------------------------------------------------------- classification

MAGIC = [
    (b'\x9e\x2a\x83\xc1', 'ue3_package_be', 'Unreal Engine 3 package (big-endian, Xbox 360 cooked)'),
    (b'\xc1\x83\x2a\x9e', 'ue3_package_le', 'Unreal Engine 3 package (little-endian)'),
    (b'BIK',              'bink_video',     'RAD Bink 1 video'),
    (b'KB2',              'bink2_video',    'RAD Bink 2 video'),
    (b'XEX2',             'xex2',           'Xbox 360 executable (XEX2)'),
    (b'PIRS',             'stfs_pirs',      'Xbox 360 STFS package (PIRS, MS-signed)'),
    (b'LIVE',             'stfs_live',      'Xbox 360 STFS package (LIVE)'),
    (b'CON ',             'stfs_con',       'Xbox 360 STFS package (CON)'),
    (b'XMNP',             'xbox_manifest',  'Xbox 360 system update manifest'),
    (b'RIFF',             'riff',           'RIFF (WAV/XMA)'),
    (b'DDS ',             'dds',            'DirectDraw Surface'),
]

def guess_format(rel, head):
    for sig, fmt, desc in MAGIC:
        if head.startswith(sig):
            return fmt, desc
    name = os.path.basename(rel).lower()
    if name.startswith('coalesced.'):
        return 'ue3_coalesced_obfuscated', 'UE3 Coalesced ini/localization bundle (strings obfuscated)'
    if name == 'xbox360toc.txt':
        return 'ue3_toc', 'UE3 Xbox360 table of contents (size, path, md5)'
    if rel.lower().startswith('transgame\\movies\\') and name.endswith('.txt'):
        return 'subtitle_timing', 'Movie subtitle cue list (start,end,key)'
    try:
        head.decode('ascii')
        return 'text', 'plain text'
    except UnicodeDecodeError:
        return 'unknown', 'unknown binary'

PURPOSE = {
    'ue3_package_be': 'game content', 'bink_video': 'video/FMV', 'xex2': 'game executable',
    'stfs_pirs': 'Xbox LIVE/system container', 'xbox_manifest': 'system update',
    'ue3_coalesced_obfuscated': 'configuration/localization', 'ue3_toc': 'file table',
    'subtitle_timing': 'video subtitles',
}

# Package naming conventions observed in CookedXenon.
SUFFIXES = [('_LOC_', 'localized companion'), ('_LM', 'lightmap companion')]
PREFIX_ROLE = {
    'TR':   'transformer character (ROBO/VEH=textures, ROBODEF/VEHDEF=definitions)',
    'WEP':  'weapon', 'WL': 'sound wave library (WL_DX=dialog, WL_GUN/WPN=weapons, WL_MX=music)',
    'BL':   'sound event/cue bank', 'ENV': 'environment art', 'DES': 'design/gameplay content',
    'MP':   'multiplayer map', 'UI': 'user interface', 'FX': 'effects', 'CINE': 'cinematic',
    'TPRO': 'transform prop/level set', 'PROP': 'props', 'CAM': 'camera', 'VEH': 'vehicle',
    'HM':   'High Moon engine layer', 'CHR': 'character',
}
CAMPAIGN = re.compile(r'^(A[1-5]|D[1-5]|D3A|D3B)_')

CLASS_CATEGORY = {
    'SkeletalMesh': 'skeletal_meshes', 'StaticMesh': 'static_meshes', 'FracturedStaticMesh': 'static_meshes',
    'AnimSet': 'animations', 'AnimSequence': 'animations', 'AnimTree': 'animations',
    'MorphTargetSet': 'animations', 'MorphTarget': 'animations', 'FaceFXAsset': 'animations',
    'FaceFXAnimSet': 'animations', 'PhysicsAsset': 'skeletons_physics',
    'Texture2D': 'textures', 'TextureCube': 'textures', 'LightMapTexture2D': 'lightmaps',
    'ShadowMapTexture2D': 'lightmaps', 'TextureMovie': 'textures', 'TextureRenderTarget2D': 'textures',
    'TextureFlipBook': 'textures',
    'Material': 'materials', 'MaterialInstanceConstant': 'materials', 'MaterialInstanceTimeVarying': 'materials',
    'ParticleSystem': 'particles_effects', 'ParticleEmitter': 'particles_effects',
    'SoundNodeWave': 'audio', 'SoundNodeWaveEx': 'audio', 'SoundCue': 'audio_events', 'HmSoundEvent': 'audio_events',
    'World': 'maps', 'Level': 'maps', 'SwfMovie': 'ui', 'GFxMovieInfo': 'ui', 'Font': 'ui',
    'Class': 'script_classes', 'Function': 'script_code', 'Enum': 'script_code', 'ScriptStruct': 'script_code',
    'Prefab': 'gameplay_data', 'Sequence': 'gameplay_data',
}

def package_family(stem):
    """Strip companion suffixes -> base package name."""
    base = re.sub(r'_LOC_[A-Za-z]+$', '', stem)
    base = re.sub(r'_LM$', '', base)
    return base

def package_role(stem, classes):
    roles = []
    if '_LOC_' in stem: roles.append('localized companion (%s)' % stem.rsplit('_LOC_', 1)[1])
    elif stem.endswith('_LM'): roles.append('lightmap companion')
    if classes.get('World') or stem.endswith('_m') or stem.endswith('_m_LM'):
        roles.append('map/level')
    m = CAMPAIGN.match(stem)
    if m: roles.append('campaign chapter %s' % m.group(1))
    pre = stem.split('_', 1)[0]
    if pre in PREFIX_ROLE: roles.append(PREFIX_ROLE[pre])
    if not roles: roles.append('script/engine package' if classes.get('Class') else 'unclassified')
    return roles

# ---------------------------------------------------------------- workers

def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()

def scan_file(args):
    full, rel = args
    size = os.path.getsize(full)
    with open(full, 'rb') as f:
        head = f.read(64)
    fmt, desc = guess_format(rel, head)
    return {'path': rel, 'name': os.path.basename(rel), 'ext': os.path.splitext(rel)[1].lower(),
            'size': size, 'magic': head[:16].hex(), 'format': fmt, 'format_desc': desc,
            'purpose': PURPOSE.get(fmt, 'unknown'), 'md5': md5_file(full)}

def scan_package(args):
    full, rel = args
    stem = os.path.splitext(os.path.basename(rel))[0]
    try:
        p = ue3pkg.Package(full)
    except Exception as ex:  # keep going; record the failure
        return {'package': stem, 'path': rel, 'error': repr(ex)}
    s = dict(p.summary); chunks = s.pop('chunks')
    exports = []
    for i, e in enumerate(p.exports):
        exports.append({'index': i + 1, 'class': p.class_name(e), 'name': e['name'],
                        'path': p.full_path(i + 1), 'opath': p.object_path(i + 1), 'outer': e['outer'],
                        'archetype': e['archetype'], 'object_flags': e['object_flags'],
                        'serial_size': e['serial_size'], 'serial_offset': e['serial_offset'],
                        'export_flags': e['export_flags']})
    imports = [{'index': -(i + 1), 'class_package': im['class_package'], 'class': im['class'],
                'name': im['name'], 'path': p.full_path(-(i + 1))} for i, im in enumerate(p.imports)]
    classes = Counter(e['class'] for e in exports)
    detail = {'package': stem, 'path': rel, 'summary': s, 'compressed_chunks': len(chunks),
              'names': p.names, 'imports': imports, 'exports': exports}
    os.makedirs(os.path.join(MANI, 'packages'), exist_ok=True)
    with open(os.path.join(MANI, 'packages', stem + '.json'), 'w', encoding='utf-8') as f:
        json.dump(detail, f, separators=(',', ':'))
    flags = s['package_flags']
    return {'package': stem, 'path': rel, 'family': package_family(stem),
            'file_version': s['file_version'], 'licensee_version': s['licensee_version'],
            'engine_version': s['engine_version'], 'cooker_version': s['cooker_version'],
            'package_flags': '%08X' % flags, 'store_compressed': bool(flags & ue3pkg.PKG_STORE_COMPRESSED),
            'contains_map': bool(flags & ue3pkg.PKG_CONTAINS_MAP), 'cooked': bool(flags & ue3pkg.PKG_COOKED),
            'compression_flags': s['compression_flags'], 'compressed_chunks': len(chunks),
            'uncompressed_size': len(p.data),
            'name_count': s['name_count'], 'import_count': s['import_count'], 'export_count': s['export_count'],
            'depends_on': p.import_packages(), 'classes': dict(classes.most_common()),
            'role': package_role(stem, classes)}

# ---------------------------------------------------------------- main

def load_toc():
    toc = {}
    path = os.path.join(DUMP, 'TransGame', 'Xbox360TOC.txt')
    for line in open(path, encoding='latin-1'):
        parts = line.strip().split(' ', 3)
        if len(parts) < 4: continue
        rest = parts[3].rsplit(' ', 1)
        rel = rest[0].replace('..\\', '', 1)
        toc[rel.lower()] = {'size': int(parts[0]), 'md5': rest[1] if len(rest) > 1 else None}
    return toc

def main():
    t0 = time.time()
    os.makedirs(MANI, exist_ok=True)
    work = []
    for dp, dn, fn in os.walk(DUMP):
        for n in fn:
            full = os.path.join(dp, n)
            work.append((full, os.path.relpath(full, DUMP)))
    work.sort(key=lambda w: w[1].lower())
    print('files found:', len(work))
    toc = load_toc()
    with ProcessPoolExecutor() as ex:
        files = list(ex.map(scan_file, work, chunksize=8))
        print('hashed in %.1fs' % (time.time() - t0))
        pkg_work = [w for w, f in zip(work, files) if f['format'].startswith('ue3_package')]
        packages = list(ex.map(scan_package, pkg_work, chunksize=4))
    print('packages parsed in %.1fs' % (time.time() - t0))

    for f in files:
        t = toc.get(f['path'].lower())
        f['in_toc'] = t is not None
        f['toc_md5_match'] = (t['md5'] == f['md5']) if t and t['md5'] else None
        f['compressed'] = None; f['encrypted_or_obfuscated'] = None
        if f['format'] == 'ue3_coalesced_obfuscated': f['encrypted_or_obfuscated'] = True
        if f['format'] == 'stfs_pirs': f['encrypted_or_obfuscated'] = 'signed container (not encrypted payload)'
        if f['format'] == 'xex2': f['encrypted_or_obfuscated'] = 'XEX2 (typically encrypted+compressed image)'
    pkg_by_path = {p['path']: p for p in packages}
    for f in files:
        p = pkg_by_path.get(f['path'])
        if p and 'error' not in p:
            f['compressed'] = p['store_compressed']; f['encrypted_or_obfuscated'] = False
            f['ue_package'] = True; f['package_role'] = p['role']
        elif f['format'] == 'bink_video':
            f['compressed'] = True
    # relationships between similarly named files
    fam = defaultdict(list)
    for p in packages:
        if 'error' not in p: fam[p['family']].append(p['package'])
    for p in packages:
        if 'error' not in p:
            p['related'] = sorted(x for x in fam[p['family']] if x != p['package'])
    movies = defaultdict(list)
    for f in files:
        if f['path'].lower().startswith('transgame\\movies\\'):
            movies[re.sub(r'(_?(text|itext|otext)?_?(FRA|INT|ESN)?)?\s*$', '', os.path.splitext(f['name'])[0])].append(f['name'])
    for f in files:
        if f['path'].lower().startswith('transgame\\movies\\'):
            key = re.sub(r'(_?(text|itext|otext)?_?(FRA|INT|ESN)?)?\s*$', '', os.path.splitext(f['name'])[0])
            f['related'] = sorted(x for x in movies[key] if x != f['name'])

    json.dump(files, open(os.path.join(MANI, 'files.json'), 'w'), indent=1)
    json.dump(packages, open(os.path.join(MANI, 'packages.json'), 'w'), indent=1)
    write_db(files, packages)
    write_summary(files, packages, toc, time.time() - t0)
    print('done in %.1fs' % (time.time() - t0))

def write_db(files, packages):
    path = os.path.join(MANI, 'inventory.db')
    if os.path.exists(path): os.remove(path)
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE files(path TEXT PRIMARY KEY, name TEXT, ext TEXT, size INT, magic TEXT, format TEXT,
                         purpose TEXT, md5 TEXT, in_toc INT, toc_md5_match INT, compressed INT);
      CREATE TABLE packages(package TEXT PRIMARY KEY, path TEXT, family TEXT, flags TEXT, store_compressed INT,
                            contains_map INT, name_count INT, import_count INT, export_count INT,
                            uncompressed_size INT, role TEXT, error TEXT);
      CREATE TABLE package_deps(package TEXT, depends_on TEXT);
      CREATE TABLE exports(package TEXT, idx INT, class TEXT, name TEXT, path TEXT, opath TEXT, outer_idx INT,
                           serial_size INT, serial_offset INT, object_flags INT, export_flags INT);
      CREATE TABLE imports(package TEXT, idx INT, class_package TEXT, class TEXT, name TEXT, path TEXT);
    ''')
    db.executemany('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   [(f['path'], f['name'], f['ext'], f['size'], f['magic'], f['format'], f['purpose'], f['md5'],
                     f['in_toc'], f['toc_md5_match'], f['compressed']) for f in files])
    for p in packages:
        if 'error' in p:
            db.execute('INSERT INTO packages(package,path,error) VALUES(?,?,?)', (p['package'], p['path'], p['error']))
            continue
        db.execute('INSERT INTO packages VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)',
                   (p['package'], p['path'], p['family'], p['package_flags'], p['store_compressed'],
                    p['contains_map'], p['name_count'], p['import_count'], p['export_count'],
                    p['uncompressed_size'], '; '.join(p['role'])))
        db.executemany('INSERT INTO package_deps VALUES(?,?)', [(p['package'], d) for d in p['depends_on']])
        detail = json.load(open(os.path.join(MANI, 'packages', p['package'] + '.json')))
        db.executemany('INSERT INTO exports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       [(p['package'], e['index'], e['class'], e['name'], e['path'], e['opath'], e['outer'], e['serial_size'],
                         e['serial_offset'], e['object_flags'] & 0x7FFFFFFFFFFFFFFF, e['export_flags'])
                        for e in detail['exports']])
        db.executemany('INSERT INTO imports VALUES(?,?,?,?,?,?)',
                       [(p['package'], i['index'], i['class_package'], i['class'], i['name'], i['path'])
                        for i in detail['imports']])
    db.executescript('''
      CREATE INDEX ix_exp_class ON exports(class); CREATE INDEX ix_exp_path ON exports(path); CREATE INDEX ix_exp_opath ON exports(opath);
      CREATE INDEX ix_exp_pkg ON exports(package); CREATE INDEX ix_imp_pkg ON imports(package);
    ''')
    db.commit(); db.close()

def write_summary(files, packages, toc, secs):
    ok = [p for p in packages if 'error' not in p]
    cls = Counter()
    for p in ok: cls.update(p['classes'])
    cats = defaultdict(lambda: {'objects': 0, 'packages': 0})
    for p in ok:
        seen = set()
        for c, n in p['classes'].items():
            k = CLASS_CATEGORY.get(c)
            if k:
                cats[k]['objects'] += n; seen.add(k)
        for k in seen: cats[k]['packages'] += 1
    ext = Counter(f['ext'] or '(none)' for f in files)
    fmt = Counter(f['format'] for f in files)
    summary = {
        'generated': time.strftime('%Y-%m-%d %H:%M:%S'), 'scan_seconds': round(secs, 1),
        'total_files': len(files), 'total_bytes': sum(f['size'] for f in files),
        'extensions': dict(ext.most_common()), 'formats': dict(fmt.most_common()),
        'toc_entries': len(toc),
        'toc_md5_mismatches': [f['path'] for f in files if f['toc_md5_match'] is False],
        'files_not_in_toc': [f['path'] for f in files if not f['in_toc']],
        'packages_total': len(packages), 'packages_parse_errors': [p for p in packages if 'error' in p],
        'package_versions': dict(Counter('%d/%d engine %d cooker %d' % (p['file_version'], p['licensee_version'],
                                 p['engine_version'], p['cooker_version']) for p in ok)),
        'compression_flags': dict(Counter(str(p['compression_flags']) for p in ok)),
        'packages_store_compressed': sum(p['store_compressed'] for p in ok),
        'map_packages': sorted(p['package'] for p in ok if p['classes'].get('World')),
        'total_exports': sum(p['export_count'] for p in ok),
        'categories': dict(sorted(cats.items())),
        'top_classes': dict(cls.most_common(150)),
        'package_prefixes': dict(Counter(p['package'].split('_', 1)[0] for p in ok).most_common()),
    }
    json.dump(summary, open(os.path.join(MANI, 'summary.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
