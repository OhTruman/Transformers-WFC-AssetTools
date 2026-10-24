"""Inventory of the extracted WFC DLC packs (Integration RELEASE 2026-10-23; plan Rebuild/docs/DLC_PLAN.md). Read only on
work/dlc/<pack>/files (extracted by stfs_extract.py); separate outputs, the base manifests stay byte-identical:
  manifests/dlc/dlc_inventory.db      SQLite, the base inventory.db schema (files, packages, package_deps, exports, imports) + pack column
  manifests/dlc/packages/<pkg>.json   import / export tables per DLC package
  manifests/dlc/dlc_inventory.json    per pack: maps (TransLevels.ini MapInfo + TransGame.<lang> FriendlyName per language, versus / ESC by
                                      prefix, level packages by role), chassis entries (TransCustomization.ini), languages, ini sections,
                                      and per category the packages / exports: characters (ROBODEF / AICD / chassis classes), weapons
                                      (TnWeapon / WEPDATA / WEPMESH), anim sets, audio (SoundCue / SoundNodeWave / banks), textures, materials
    python dlc_inventory.py
"""
import json, os, re, sqlite3, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import ue3pkg  # noqa: E402
OUT = os.path.join(AT, 'manifests', 'dlc'); PK = os.path.join(OUT, 'packages')
PACKS = ['MapPack1', 'MapPack2']
CAT = OD([('characters', re.compile(r'(RobotDef|RoboDef|ROBODEF|AiCharacterDefinition|TnVehicleDef|VEHDEF|Chassis|TnDataProvider_Character)', re.I)),
          ('weapons', re.compile(r'(TnWeapon|WEPDATA|WEPMESH|WeaponData|Projectile)', re.I)),
          ('anim_sets', re.compile(r'^(AnimSet|AnimSequence|AnimTree)$')),
          ('audio', re.compile(r'(SoundCue|SoundNodeWave|AkBank|SoundClass|ReverbVolume|AmbientSound)', re.I)),
          ('textures', re.compile(r'^Texture2D$|^TextureCube$|LightMapTexture2D')),
          ('materials', re.compile(r'^Material$|MaterialInstance')),
          ('static_meshes', re.compile(r'^StaticMesh$')), ('skeletal_meshes', re.compile(r'^SkeletalMesh$')),
          ('particles', re.compile(r'^ParticleSystem$')), ('kismet', re.compile(r'^(Sequence|SeqAct_|SeqEvent_|TnSeqAct_)'))])

def ini(path):
    secs = OD(); cur = None
    b = open(path, 'rb').read()
    # the localized TransGame.<lang> files are UTF-16 LE with a BOM (Frontend 2026-10-23: "D�vastation"); ini files plain ASCII / UTF-8
    if b[:2] in (b'\xff\xfe', b'\xfe\xff'): text = b.decode('utf-16')
    else:
        try: text = b.decode('utf-8')
        except UnicodeDecodeError: text = b.decode('cp1252')
    for raw in text.lstrip('﻿').replace('\x00', '').splitlines():
        l = raw.strip()
        if l.startswith('[') and l.endswith(']'): cur = l[1:-1]; secs.setdefault(cur, [])
        elif cur and '=' in l: k, v = l.split('=', 1); secs[cur].append((k.strip().lstrip('+.'), v.strip()))
    return secs

def main():
    os.makedirs(PK, exist_ok=True)
    dbp = os.path.join(OUT, 'dlc_inventory.db')
    if os.path.exists(dbp): os.remove(dbp)
    db = sqlite3.connect(dbp)
    db.executescript('''
      CREATE TABLE files(pack TEXT, path TEXT, name TEXT, ext TEXT, size INT, magic TEXT);
      CREATE TABLE packages(pack TEXT, package TEXT, path TEXT, flags TEXT, contains_map INT, name_count INT, import_count INT, export_count INT,
                            uncompressed_size INT, error TEXT);
      CREATE TABLE package_deps(pack TEXT, package TEXT, depends_on TEXT);
      CREATE TABLE exports(pack TEXT, package TEXT, idx INT, class TEXT, name TEXT, path TEXT, opath TEXT, outer_idx INT, serial_size INT,
                           serial_offset INT, object_flags INT, export_flags INT);
      CREATE TABLE imports(pack TEXT, package TEXT, idx INT, class_package TEXT, class TEXT, name TEXT, path TEXT);''')
    out = OD([('generated_by', 'AssetTools/work/dlc/dlc_inventory.py'), ('source', 'work/dlc/<pack>/files (extracted read-only from 4156084C/00000002)'),
              ('packs', OD())])
    base_pkgs = {r[0].lower() for r in sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db')).execute('select package from packages')}
    for pack in PACKS:
        man = json.load(open(os.path.join(HERE, pack, 'manifest.json'), encoding='utf-8'))
        F = os.path.join(HERE, pack, 'files')
        cat = OD((k, Counter()) for k in CAT); per_pkg = OD(); langs = set(); inis = OD(); maps = OD(); chassis = []
        for e in man['entries']:
            p = os.path.join(F, *e['path'].split('/')); ext = os.path.splitext(p)[1].lower(); stem = os.path.splitext(os.path.basename(p))[0]
            if ext == '.xxx' and not os.path.exists(p): p = os.path.join(HERE, 'cooked', os.path.basename(p))   # packages moved to work/dlc/cooked
            head = open(p, 'rb').read(4)
            db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)', (pack, e['path'], os.path.basename(p), ext, e['size'], head.hex()))
            if ext in ('.int', '.fra', '.deu', '.ita', '.esn', '.jpn', '.kor', '.cht', '.pol', '.rus', '.ptb', '.cze', '.hun'):
                langs.add(ext[1:].upper()); inis[e['path']] = ini(p); continue
            if ext == '.ini': inis[e['path']] = ini(p); continue
            if ext != '.xxx': continue
            m = re.search(r'_LOC_([A-Za-z]+)$', stem)
            if m: langs.add(m.group(1).upper())
            try: pk = ue3pkg.Package(p)
            except Exception as x:
                db.execute('INSERT INTO packages(pack,package,path,error) VALUES(?,?,?,?)', (pack, stem, e['path'], repr(x)[:300])); continue
            s = pk.summary; flags = s['package_flags']
            exps = [(i + 1, pk.class_name(x), x['name'], pk.full_path(i + 1), pk.object_path(i + 1), x['outer'], x['serial_size'], x['serial_offset'],
                     x['object_flags'] & 0x7FFFFFFFFFFFFFFF, x['export_flags']) for i, x in enumerate(pk.exports)]
            imps = [(-(i + 1), im['class_package'], im['class'], im['name'], pk.full_path(-(i + 1))) for i, im in enumerate(pk.imports)]
            db.execute('INSERT INTO packages VALUES(?,?,?,?,?,?,?,?,?,NULL)', (pack, stem, e['path'], '%08X' % flags, int(bool(flags & ue3pkg.PKG_CONTAINS_MAP)),
                                                                                s['name_count'], s['import_count'], s['export_count'], len(pk.data)))
            db.executemany('INSERT INTO package_deps VALUES(?,?,?)', [(pack, stem, d) for d in pk.import_packages()])
            db.executemany('INSERT INTO exports VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', [(pack, stem) + r for r in exps])
            db.executemany('INSERT INTO imports VALUES(?,?,?,?,?,?,?)', [(pack, stem) + r for r in imps])
            json.dump({'package': stem, 'pack': pack, 'names': pk.names,
                       'exports': [dict(zip(('index', 'class', 'name', 'path', 'opath', 'outer', 'serial_size', 'serial_offset', 'object_flags',
                                             'export_flags'), r)) for r in exps],
                       'imports': [dict(zip(('index', 'class_package', 'class', 'name', 'path'), r)) for r in imps]},
                      open(os.path.join(PK, stem + '.json'), 'w', encoding='utf-8'), separators=(',', ':'))
            cls = Counter(r[1] for r in exps)
            for k, rx in CAT.items():
                n = sum(v for c, v in cls.items() if rx.search(c or '')) + (sum(1 for r in exps if k == 'characters' and re.search(r'(ROBODEF|_AICD|VEHDEF)', r[2] or '')))
                if n: cat[k][stem] += n
            per_pkg[stem] = OD([('path', e['path']), ('size', e['size']), ('contains_map', bool(flags & ue3pkg.PKG_CONTAINS_MAP)),
                                ('exports', len(exps)), ('in_base_game', stem.lower() in base_pkgs), ('top_classes', OD(cls.most_common(6)))])
        # maps: TransLevels.ini MapInfo + friendly names per language
        for path, secs in inis.items():
            for sec, kv in secs.items():
                if sec.endswith('TnDataProvider_MapInfo'):
                    mp = sec.split()[0]; r = maps.setdefault(mp, OD([('map', mp), ('mode', 'Escalation' if '_ESC_' in mp else 'versus'), ('friendly', OD())]))
                    lang = os.path.splitext(path)[1][1:].upper()
                    for k, v in kv:
                        if k == 'FriendlyName': r['friendly'][lang] = v
                        elif k == 'CompatibleGameTypes': r.setdefault('game_types', []).append(v)
                        elif lang == 'INI': r[k] = v
                if sec.endswith('TnDataProvider_Chassis'): chassis.append(OD([('chassis', sec.split()[0])] + [(k, v) for k, v in kv]))
        for mp, r in maps.items():
            pre = mp.rsplit('_', 2)[0] if mp.lower().endswith('_base_m') else mp
            r['level_packages'] = sorted(k for k in per_pkg if k.lower().startswith(pre.lower() + '_'))
        out['packs'][pack] = OD([('display_name', man['display_name']), ('files', man['files']), ('bytes', man['bytes']),
                                 ('languages', sorted(langs)), ('maps', list(maps.values())), ('chassis_entries', chassis),
                                 ('ini_sections', OD((p, list(s.keys())) for p, s in inis.items())),
                                 ('categories', OD((k, OD(v.most_common())) for k, v in cat.items() if v)),
                                 ('packages', per_pkg)])
        print(pack, '| languages', sorted(langs), '| maps', [(r['map'], r['mode'], r['friendly'].get('INT')) for r in maps.values()])
        print('   chassis', [c['chassis'] for c in chassis], '| categories', {k: sum(v.values()) for k, v in cat.items() if v})
    db.executescript('CREATE INDEX ix_exp_class ON exports(class); CREATE INDEX ix_exp_opath ON exports(opath); CREATE INDEX ix_exp_pkg ON exports(package);')
    db.commit(); db.close()
    json.dump(out, open(os.path.join(OUT, 'dlc_inventory.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
