"""Per DLC map, two lists for packaging (Integration 2026-10-23), written into out/dlc_render/<MAP>/:
  audio_loc.json      the map's audio / localisation packages (the <MAP>_AUDIO_m level, BL_LVL_* / WL_LVL_* bank packages naming the map,
                      <MAP>_*_LOC_<LANG>) with their sound waves exported to out/dlc_content (assets.json owner_package) + languages
  outside_assets.tsv  files outside out/dlc_render the map's data references: the image URIs of its world.glb (and every glb in the map's
                      VerticalSlice dir), 'content/...' strings in its JSONs -> resolved under out/dlc_content (DLC) or ExtractedAssets
                      (base); path relative to F:/Transformers Rebuild, bytes, exists, source
    python dlc_map_lists.py <MAP>      (reads only; dlc_env.sh not needed)
"""
import glob, json, os, re, struct, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
DLC_CONTENT = os.path.join(AT, 'out', 'dlc_content'); BASE_EA = os.path.join(TR, 'ExtractedAssets')
LANGS = ('INT', 'FRA', 'DEU', 'ITA', 'ESN')

def glb_json(p):
    with open(p, 'rb') as f:
        h = f.read(20); return json.loads(f.read(struct.unpack_from('<I', h, 12)[0]))

def resolve_content(rel):
    for root in (DLC_CONTENT, BASE_EA):
        p = os.path.join(root, *rel.split('/'))
        if os.path.exists(p): return p
    return os.path.join(DLC_CONTENT, *rel.split('/'))

def main(M):
    short = M.split('_', 2)[-1].lower()                                   # e.g. fortress
    out = os.path.join(AT, 'out', 'dlc_render', M); os.makedirs(out, exist_ok=True)
    VS = os.path.join(AT, 'work', 'dlc_maps', 'VerticalSlice', 'Maps', M)
    pk = [os.path.splitext(f)[0] for f in os.listdir(os.path.join(HERE, 'cooked'))]
    audio = [p for p in pk if p.lower() == (M + '_audio_m').lower() or (p.upper().startswith(('BL_LVL_', 'WL_LVL_')) and short in p.lower())]
    loc = sorted(p for p in pk if p.lower().startswith(M.lower() + '_') and '_loc_' in p.lower())
    A = json.load(open(os.path.join(AT, 'manifests', 'dlc', 'assets.json'), encoding='utf-8'))['assets']
    waves = OD()
    for a in A:
        if a.get('asset_type') == 'sound_wave' and a.get('owner_package') in set(audio + loc):
            waves.setdefault(a['owner_package'], []).extend(o for o in a.get('extracted') or [] if o.lower().endswith('.wav'))
    al = OD([('map', M), ('generated_by', 'AssetTools/work/dlc/dlc_map_lists.py'),
             ('audio_packages', audio), ('loc_packages', loc), ('languages', [l for l in LANGS if any(x.upper().endswith('_LOC_' + l) for x in loc)]),
             ('waves_by_package', OD((k, sorted(set(v))) for k, v in waves.items())),
             ('waves_root', 'AssetTools/out/dlc_content (paths relative to it)'), ('packages_root', 'AssetTools/work/dlc/cooked')])
    json.dump(al, open(os.path.join(out, 'audio_loc.json'), 'w', encoding='utf-8'), indent=1)
    files = OD()
    for g in glob.glob(os.path.join(VS, '*.glb')) + glob.glob(os.path.join(out, '*.glb')):
        for im in glb_json(g).get('images') or []:
            u = im.get('uri') or ''
            for key, root in (('ExtractedAssets/', TR), ('dlc_content/', os.path.join(AT, 'out'))):
                if key in u: files.setdefault(os.path.normpath(os.path.join(root, *(key + u.split(key, 1)[1]).split('/'))), os.path.basename(g))
    rx = re.compile(r'"(content/[^"]+\.(?:gltf|png|wav|psa|glb|bin))"')
    for j in glob.glob(os.path.join(VS, '*.json')) + glob.glob(os.path.join(out, '*.json')):
        for m in set(rx.findall(open(j, encoding='utf-8', errors='replace').read())):
            files.setdefault(os.path.normpath(resolve_content(m)), os.path.basename(j))
    for k, v in waves.items():
        for w in v: files.setdefault(os.path.normpath(resolve_content(w)), 'audio_loc.json')
    with open(os.path.join(out, 'outside_assets.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('path\tbytes\texists\tsource\n')
        for p, src in sorted(files.items()):
            ex = os.path.exists(p); f.write('%s\t%d\t%s\t%s\n' % (os.path.relpath(p, TR).replace(os.sep, '/'), os.path.getsize(p) if ex else 0, ex, src))
    n_ex = sum(1 for p in files if os.path.exists(p))
    print(M, '| audio', audio, '| loc', len(loc), al['languages'], '| waves', sum(len(v) for v in waves.values()),
          '| outside files', len(files), 'existing', n_ex, '%.1f MB' % (sum(os.path.getsize(p) for p in files if os.path.exists(p)) / 1e6))

if __name__ == '__main__':
    main(sys.argv[1])
