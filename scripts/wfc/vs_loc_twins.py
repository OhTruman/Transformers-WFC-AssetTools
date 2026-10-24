"""Both localized twins of every localized SoundNodeWave -> ExtractedAssets/content/_LOC/<twin>/<group>/<name>.wav
                                                         + manifests/audio/loc_twins.json

  python vs_loc_twins.py [--limit N]

Why: every map (and Startup) cooks _LOC_int and _LOC_FRA twins whose SoundNodeWaves share object paths. The merged
content/<group>/<name>.wav keeps one twin per path (authored.db keys objects by class|path), so 666 of 2538 merged localized
waves are French (manifests/audit/reference_integrity.json). Shipped WFC loads only _LOC_<GLanguage>. Layout requested by
Systems (agents/systems 2a7bdda, SoundCues::localizedWave): <twin> = the cooked package suffix ('int' / 'FRA').
Extraction: ue3pkg + sounds.locate_fsb -> FSB -> vgmstream WAV (same tools as the merged extraction). Each path is written once
per twin (first package in sorted order); copies of the same path in other packages are hashed and any differing copy is reported.
"""
import hashlib, json, os, re, subprocess, sys, time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, sounds, extract  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
VGM = os.path.join(AT, 'bin', 'vgmstream', 'vgmstream-cli.exe')
OUT = os.path.join(ROOT, 'content', '_LOC')
GEN = 'AssetTools/scripts/wfc/vs_loc_twins.py'

def md5(b): return hashlib.md5(b).hexdigest()[:12]

def main():
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    pk = sorted(n[:-4] for n in os.listdir(extract.COOKED) if n.endswith('.xxx') and
                (n.lower().endswith('_int.xxx') or n.lower().endswith('_fra.xxx')))
    # *_LOC_int / *_LOC_FRA level twins, Startup_int / _FRA, and the per-language seek-free wave banks WL_DX_<char>_INT / _FRA
    # (the level twins often hold 278-byte bulk stubs whose audio lives in the WL_*_INT / _FRA bank)
    rec = OrderedDict(); diff = []; stats = Counter(); t0 = time.time()
    for name in pk:
        twin = 'FRA' if name.lower().endswith('fra') else 'int'
        p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
        for i, e in enumerate(p.exports):
            if p.class_name(e) not in ('SoundNodeWave', 'SoundNodeWaveEx'): continue
            op = p.object_path(i + 1)
            # seek-free wave banks export as <Group>_INT.<Name> / <Group>_FRA.<Name>: canonical path drops the language suffix
            g0, n0 = op.split('.', 1)
            op = re.sub(r'_(INT|FRA)$', '', g0, flags=re.I) + '.' + n0
            try:
                blob, how = sounds.locate_fsb(p, e)
            except Exception as ex:
                stats['locate_error'] += 1; continue
            if not blob: stats['no_audio_data'] += 1; continue
            h = md5(blob)
            r = rec.setdefault(op, OrderedDict())
            if twin in r:
                stats['duplicate_copies'] += 1
                if r[twin]['fsb_md5'] != h: diff.append({'path': op, 'twin': twin, 'kept': r[twin]['package'], 'other': name})
                continue
            g, nm = op.split('.', 1)
            d = os.path.join(OUT, twin, g); os.makedirs(d, exist_ok=True)
            wav = os.path.join(d, nm + '.wav')
            if not os.path.exists(wav):
                fsb = wav[:-4] + '.fsb'
                open(fsb, 'wb').write(blob)
                subprocess.run([VGM, '-o', wav, fsb], capture_output=True)
                os.remove(fsb)
                stats['extracted'] += 1
            else:
                stats['already_present'] += 1
            ok = os.path.exists(wav)
            r[twin] = OrderedDict([('package', name), ('fsb_md5', h), ('wav', os.path.relpath(wav, ROOT).replace(os.sep, '/') if ok else None),
                                   ('wav_md5', md5(open(wav, 'rb').read()) if ok else None)])
            if not ok: stats['vgmstream_failed'] += 1
            if limit and len(rec) >= limit: break
        print(name, len(rec), dict(stats), '%.0fs' % (time.time() - t0), flush=True)
        if limit and len(rec) >= limit: break
    # compare with the merged extraction
    same = Counter()
    for op, r in rec.items():
        g, nm = op.split('.', 1)
        mp = os.path.join(ROOT, 'content', g, nm + '.wav')
        if os.path.exists(mp):
            mh = md5(open(mp, 'rb').read())
            for tw, x in list(r.items()):
                if x['wav_md5'] == mh: r['merged_copy_is'] = tw
        same[r.get('merged_copy_is', 'none/unknown')] += 1
    out = OrderedDict([('generated_by', GEN), ('layout', 'content/_LOC/<twin>/<group>/<name>.wav; twin = int | FRA (cooked package suffix)'),
                       ('packages', len(pk)), ('stats', dict(stats)), ('paths', len(rec)),
                       ('paths_with_both_twins', sum(1 for r in rec.values() if 'int' in r and 'FRA' in r)),
                       ('merged_copy_language (content/<group>/<name>.wav matches which twin)', dict(same)),
                       ('differing_copies_within_a_twin', diff[:200]), ('waves', rec)])
    # opt-in DLC run (WFC_COOKED_DIR = the DLC packs, 2026-10-23): the manifest goes to manifests/dlc/audio/, the base one is untouched
    mdir = os.path.join(AT, 'manifests', 'dlc', 'audio') if os.environ.get('WFC_COOKED_DIR') else os.path.join(AT, 'manifests', 'audio')
    os.makedirs(mdir, exist_ok=True)
    json.dump(out, open(os.path.join(mdir, 'loc_twins.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: out[k] for k in ('packages', 'stats', 'paths', 'paths_with_both_twins')}), out['merged_copy_language (content/<group>/<name>.wav matches which twin)'])

if __name__ == '__main__':
    main()
