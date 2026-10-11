"""Slim playtest package manifest (lossless): which files of the verified 19.8 GB playtest tree a runtime package needs

  python package_manifest.py [--xpr] [--wav-gate PATH] [--png-droppable PATH] [--filelog LOG ...] [--measure-xpress]

Source trees (relative to F:/Transformers Rebuild, mirrored under 'Transformers Rebuild/' in the package, Play.bat maps it to F:)
are those of Integration's verified package (Rebuild/work/playtest_pkg):
  Rebuild/build/release/bin   (minus run artefacts: *.log, wfc_crash_*, *.dmp, wfc_profile.ini)
  Rebuild/work/render
  AssetTools/manifests        (minus *.db, packages/, authored_shards/)
  AssetTools/out/dds
  ExtractedAssets
Rules (each file gets action keep | drop | xpr and a reason; every rule is reported with its file count and bytes):
  psa            drop *.psa: the game never opens them (Integration; animations load from .anim.gltf + .bin)
  png_dds_twin   drop a PNG whose DDS twin Rendering verified: lightmap PNGs keyed in Rebuild/work/render/texture_formats.json,
                 plus every path in --png-droppable (default Rebuild/work/png_droppable.txt, Rendering's list; skipped if absent)
  wav_fsb        drop X.wav beside X.fsb ONLY with --wav-gate <json> (Systems' FSB playback 100 % md5 gate, 'passed': true)
  compress       .bin / .glb / .gltf -> listed as compressible (.xpr, XPRESS_HUFF); with --xpr the package names become <file>.xpr
                 (only once the loaders read .xpr); --measure-xpress fills in the compressed sizes (cabinet.dll, round trip)
  filelog        --filelog: Systems' WFC_FILELOG lines '<r|w> <ok|missing> <path>' -> any opened content path that the
                 manifest drops or lacks is reported as a FAILURE (verification run per map)
Outputs: AssetTools/out/package/slim_files.tsv (dest, source, bytes, action, reason; local, large) and
         AssetTools/manifests/package/slim_package.json (rules, totals, verification).
"""
import json, os, sys, time
from collections import OrderedDict as OD, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
AT = os.path.normpath(os.path.join(HERE, '..', '..'))
REB = os.path.dirname(AT)
G = 1024 ** 3
# Rebuild/data: frontend defaults read at runtime through WFC_SOURCE_DIR (Catalog.cpp loadSettingsDefaults fallback; Systems'
# WFC_FILELOG Seed run: game_settings / character_presets / chassis_xp_unlocks / profile_defaults / scenes .json)
# exe tree: --bin-tree (default the playtest Release); --bin-dest = its path inside the package (default the same; Play.bat runs
# Rebuild/build/release/bin). The slim package uses Integration's Release of the 09c head, Rebuild/build/release-slim/bin, which
# carries the four *-vgmstream-*.dll and licenses/vgmstream (FSB playback, Systems)
BIN_TREE = None
TREES = ['Rebuild/build/release/bin', 'Rebuild/work/render', 'Rebuild/data', 'AssetTools/manifests', 'AssetTools/out/dds', 'ExtractedAssets']
COMPRESS = ('.bin', '.glb', '.gltf')
HD_TREE = 'AssetTools/out/hd/pack'

def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

def excluded(tree, rel):
    low = rel.lower(); base = os.path.basename(low)
    if tree == BIN_TREE:
        return base.endswith(('.log', '.dmp')) or base.startswith('wfc_crash_') or base == 'wfc_profile.ini'
    if tree == 'AssetTools/manifests':
        return low.endswith('.db') or low.startswith(('packages/', 'authored_shards/'))
    return False

def main():
    global BIN_TREE
    BIN_TREE = arg('--bin-tree', 'Rebuild/build/release/bin').replace(os.sep, '/').rstrip('/')
    bin_dest = arg('--bin-dest', BIN_TREE).replace(os.sep, '/').rstrip('/')
    TREES[0] = BIN_TREE
    xpr = '--xpr' in sys.argv
    # render-data lightmap PNGs with a verified DDS twin (Rendering's list, relative to Rebuild/work/render)
    rd_path = arg('--png-droppable-render')
    rd_drop = {l.strip().replace(chr(92), '/').lower() for l in open(rd_path, encoding='utf-8') if l.strip()} if rd_path else set()
    tf = json.load(open(os.path.join(REB, 'Rebuild', 'work', 'render', 'texture_formats.json'), encoding='utf-8'))['textures']
    lm_keys = {k for k in tf if '/lightmaps/' in k}
    pd_path = arg('--png-droppable', os.path.join(REB, 'Rebuild', 'work', 'png_droppable.txt'))
    png_drop = set()
    if os.path.exists(pd_path):
        png_drop = {l.strip().replace('\\', '/').lower() for l in open(pd_path, encoding='utf-8') if l.strip()}
    # --hd-pack: the optional faithful HD pack (AssetTools/out/hd/pack; Rendering's loader reads <dds root>/../hd/pack/hd_index.json,
    # WfcPipeline.cpp hdRoot). Only the index, CREDITS.txt and the DDS files its rows name ship: the pack dir also holds DDS of
    # non-PASS textures (REMAKE / dropped keys), which no row references (hd_not_indexed)
    hd_rows = None
    if '--hd-pack' in sys.argv:
        TREES.append(HD_TREE)
        hd_rows = {r['dds'].replace('\\', '/').lower() for r in json.load(open(os.path.join(REB, HD_TREE, 'hd_index.json'), encoding='utf-8'))['rows']}
        miss = [d for d in hd_rows if not os.path.exists(os.path.join(REB, HD_TREE, d))]
        if miss: raise SystemExit('hd_index rows without a DDS file: %s' % miss[:5])
    gate = arg('--wav-gate'); wav_ok = False
    if gate:
        g = json.load(open(gate, encoding='utf-8')); wav_ok = g.get('passed') is True
    rows = []; rule = defaultdict(lambda: [0, 0])
    for tree in TREES:
        base = os.path.join(REB, tree)
        for dp, _, fn in os.walk(base):
            for nm in fn:
                src = os.path.join(dp, nm); rel = os.path.relpath(src, base).replace(os.sep, '/')
                if excluded(tree, rel): continue
                size = os.path.getsize(src); low = rel.lower(); ext = os.path.splitext(low)[1]
                dest = 'Transformers Rebuild/%s/%s' % (bin_dest if tree == BIN_TREE else tree, rel); action, why = 'keep', ''
                if tree == HD_TREE and low not in hd_rows and low not in ('hd_index.json', 'credits.txt'):
                    action, why = 'drop', 'hd_not_indexed'
                elif ext == '.psa':
                    action, why = 'drop', 'psa'
                elif ext == '.png' and tree == 'ExtractedAssets' and (low in lm_keys or low in png_drop):
                    action, why = 'drop', 'png_dds_twin'
                elif ext == '.png' and tree == 'Rebuild/work/render' and low in rd_drop:
                    action, why = 'drop', 'png_dds_twin_renderdata'
                elif ext == '.wav' and tree == 'ExtractedAssets' and wav_ok and os.path.exists(src[:-4] + '.fsb'):
                    action, why = 'drop', 'wav_fsb'
                elif ext in COMPRESS:
                    action, why = ('xpr', 'compress') if xpr else ('keep', 'compressible')
                    if xpr: dest += '.xpr'
                rows.append((dest, '%s/%s' % (tree, rel), size, action, why))
                rule[why or 'keep'][0] += 1; rule[why or 'keep'][1] += size
    xsize = {}
    if '--measure-xpress' in sys.argv:
        import xpress_sizing as X
        c, d = X.handles()
        for r in rows:
            if os.path.splitext(r[1])[1].lower() in COMPRESS:
                data = open(os.path.join(REB, r[1]), 'rb').read()
                xsize[r[1]] = X.roundtrip(c, d, data)[0] if data else 0
    # verification against Systems' WFC_FILELOG runs
    ver = None
    logs = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--filelog']
    if logs:
        ship = {r[1].lower() for r in rows if r[3] != 'drop'}
        dropped = {r[1].lower(): r[4] for r in rows if r[3] == 'drop'}
        fails, opened, written, missing_tried = [], set(), set(), []
        # --map-prefix OLD=NEW: logs from builds run elsewhere (e.g. a scratch source tree as WFC_SOURCE_DIR)
        prefix_map = [(a.replace('\\', '/').lower().rstrip('/') + '/', b.replace('\\', '/').rstrip('/') + '/')
                      for a, b in (sys.argv[i + 1].split('=', 1) for i, x in enumerate(sys.argv) if x == '--map-prefix')]
        for lg in logs:
            for l in open(lg, encoding='utf-8', errors='replace'):
                parts = l.rstrip('\n').split(' ', 2)
                if len(parts) < 3 or parts[1] != 'ok' or parts[0] not in ('r', 'w'): continue
                p = parts[2].replace('\\', '/')
                for a, b in prefix_map:
                    if p.lower().startswith(a): p = b + p[len(a):]
                if not p.lower().startswith('f:/transformers rebuild/'): continue
                rel = p[len('f:/transformers rebuild/'):].lower()
                (written if parts[0] == 'w' else opened).add(rel)   # any path under the root, inside the trees or not
            missing_tried += [l.rstrip().split(' ', 2)[2] for l in open(lg, encoding='utf-8', errors='replace')
                             if l.startswith('r missing ')]
        opened -= written            # files the game writes (wfc.log, wfc_characters.ini, profiles) are runtime state, not content
        for rel in sorted(opened):
            if rel in dropped: fails.append({'path': rel, 'problem': 'opened but dropped (%s)' % dropped[rel]})
            elif rel not in ship: fails.append({'path': rel, 'problem': 'opened but not shipped (outside the manifest trees or excluded)'})
        from collections import Counter
        by_kind = Counter('%s | %s' % (f['problem'], os.path.splitext(f['path'])[1] or '(none)') for f in fails)
        ver = OD([('filelogs', logs), ('content_paths_opened', len(opened)), ('failures', len(fails)),
                  ('failures_by_reason_and_extension', OD(by_kind.most_common())),
                  # WAVs opened by a pre-FSB build are expected to fail: listed in full only for the other kinds
                  ('failures_other_than_wav', [f for f in fails if not f['path'].endswith('.wav')]),
                  ('failure_list', fails[:500]),
                  ('tried_but_missing_at_capture (informational: fallbacks / optional files)', missing_tried[:500])])
    # outputs
    od = os.path.join(AT, 'out', 'package'); os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, 'slim_files.tsv'), 'w', encoding='utf-8') as f:
        f.write('dest\tsource\tbytes\taction\treason\n')
        for r in rows: f.write('%s\t%s\t%d\t%s\t%s\n' % r)
    # Systems' builder: the files shipped compressed (source, package name, raw bytes)
    with open(os.path.join(od, 'xpr_twins.tsv'), 'w', encoding='utf-8') as f:
        f.write('source\tdest_xpr\tbytes\n')
        for r in rows:
            if r[3] == 'xpr': f.write('%s\t%s\t%d\n' % (r[1], r[0], r[2]))
    total = sum(r[2] for r in rows); ship = [r for r in rows if r[3] != 'drop']
    ship_b = sum(xsize.get(r[1], r[2]) if r[3] == 'xpr' or (xsize and r[1] in xsize) else r[2] for r in ship)
    per_tree = OD()
    for t in TREES:
        rr = [r for r in ship if r[1].startswith(t + '/')]
        per_tree[t] = OD([('files', len(rr)), ('GB', round(sum(r[2] for r in rr) / G, 3))])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/package_manifest.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('source_trees', TREES), ('file_list', 'AssetTools/out/package/slim_files.tsv (dest, source, bytes, action, reason)'),
              ('inputs', OD([('texture_formats_lightmap_keys', len(lm_keys)), ('png_droppable', pd_path if os.path.exists(pd_path) else 'absent (rule part skipped)'),
                             ('png_droppable_entries', len(png_drop)), ('wav_gate', gate or 'not given (WAVs kept)'), ('wav_gate_passed', wav_ok),
                             ('xpr_names', xpr), ('xpress_measured', bool(xsize)),
                             ('hd_pack', OD([('index', HD_TREE + '/hd_index.json'), ('rows', len(hd_rows))]) if hd_rows is not None else 'not included')])),
              ('rules', OD((k, OD([('files', v[0]), ('GB', round(v[1] / G, 3))])) for k, v in sorted(rule.items()))),
              ('totals', OD([('source_files', len(rows)), ('source_GB', round(total / G, 3)), ('package_files', len(ship)),
                             ('package_GB_uncompressed', round(sum(r[2] for r in ship) / G, 3)),
                             ('package_GB_with_xpress' if xsize else 'package_GB', round(ship_b / G, 3))])),
              ('package_by_tree', per_tree), ('verification', ver or 'none yet (run with --filelog <WFC_FILELOG output> per map)')])
    os.makedirs(os.path.join(AT, 'manifests', 'package'), exist_ok=True)
    json.dump(out, open(os.path.join(AT, 'manifests', 'package', 'slim_package.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(OD([('rules', out['rules']), ('totals', out['totals'])]), indent=1))

if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()
