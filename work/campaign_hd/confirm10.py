"""Campaign HD confirmation (Integration 2026-10-23, decision b): rerun pack D's pipeline on the 10 pack-D-eligible campaign textures
(work/campaign_hd/campaign_hd_build_set.json) in a separate root, AssetTools/out/hd/campaign_push_20261023, to confirm the automatic
gate outcome. Pack D's roots and defaults are untouched (hd_push.py WFC_HD_PUSH_ROOT; unset = push_full as before).

    python confirm10.py select      the full-pass rows (hd_push.select_full, same i keys / kinds / verdicts) filtered to the 10
then, with WFC_HD_PUSH_SET=full and WFC_HD_PUSH_ROOT set (see run_confirm10.cmd):
    hd_push.py gen [--cpu-only]     model outputs (normal / mask models on DML, the rgt-s colour model on CPU)
    hd_full_push.py build           ladder D -> C -> B -> A -> original with pack D's gates
    hd_full_push.py sheets 0        eye sheets of anything that reached a level
"""
import json, os, sys
os.environ['WFC_HD_PUSH_SET'] = 'full'
os.environ.setdefault('WFC_HD_PUSH_ROOT', r'F:\Transformers Rebuild\AssetTools\out\hd\campaign_push_20261023')
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import hd_push as P  # noqa: E402

def select():
    want = {t['object'].lower() for t in json.load(open(os.path.join(HERE, 'campaign_hd_build_set.json'), encoding='utf-8'))['textures']}
    P.select_full()                                    # the full-pass rows, written into this root's select.json
    R = [r for r in P.rows() if r['object_path'].lower() in want]
    json.dump(R, open(os.path.join(P.OUT, 'select.json'), 'w', encoding='utf-8'), indent=1)
    print(P.OUT, len(R), [(r['i'], r['object_path'].split('.')[-1], r['kind'], r['verdict']) for r in R])

if __name__ == '__main__':
    {'select': select}[sys.argv[1]]()
