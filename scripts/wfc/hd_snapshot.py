"""Freeze an HD pack as a snapshot, then gate it with the integrity pass (hd_pack_integrity.py). Copies hd_index.json and every row's
dds (only those: no strays) from <src>/pack into <dst>/pack, writes <dst>/integrity.json; on any failure the folder is renamed
<dst>_FAILED and the exit code is 1, so a broken snapshot is never handed out under a snapshot name.

  python hd_snapshot.py <src root> <dst root>     e.g. out/hd/push_full out/hd/push_full_snap_<date>_b0-NN
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hd_pack_integrity as I  # noqa: E402

def main(src, dst):
    if os.path.exists(dst): sys.exit('exists: ' + dst)
    idx = json.load(open(os.path.join(src, 'pack', 'hd_index.json'), encoding='utf-8'))
    for r in idx['rows']:
        q = os.path.join(dst, 'pack', r['dds']); os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(os.path.join(src, 'pack', r['dds']), q)
    shutil.copy2(os.path.join(src, 'pack', 'hd_index.json'), os.path.join(dst, 'pack', 'hd_index.json'))
    if I.check(dst): print('snapshot frozen:', dst); return 0
    os.rename(dst, dst + '_FAILED'); print('integrity FAILED: renamed to', dst + '_FAILED'); return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
