"""split-dir inputs for a level the sublevel splitter skipped (add_units.sh): an empty world.glb that keeps 'nodes' / 'scenes', and
map_fx.json / render_index.json filtered for the level from the chapter files (campaign_render.filt, the prep rule)."""
import json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); sys.path.insert(0, HERE)
import campaign_render as CR  # noqa: E402

def empty_glb(path, note):
    j = {'asset': {'version': '2.0', 'generator': 'AssetTools add_units (%s)' % note}, 'scene': 0, 'scenes': [{'nodes': []}], 'nodes': []}
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
    with open(path, 'wb') as f:
        # + a zero-length BIN chunk: vs_common.read_glb (AssetTools passes) always reads one
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8)); f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack('<II', 0, 0x004E4942))

def main(ch, lv):
    D = os.path.join(CR.CVS, 'Maps', ch); S = os.path.join(D, 'sublevels', lv); os.makedirs(S, exist_ok=True); levels = CR.chapter_levels(ch)
    empty_glb(os.path.join(S, 'world.glb'), 'empty: no static geometry in %s' % lv)
    for f in ('map_fx.json', 'render_index.json'):
        src = os.path.join(D, f)
        if not os.path.exists(src): continue
        d = json.load(open(src, encoding='utf-8'))
        x = dict(CR.filt(d, lv, levels), sublevel=lv, split_from=f) if isinstance(d, dict) else d
        json.dump(x, open(os.path.join(S, f), 'w', encoding='utf-8'), indent=1)
    print(lv, 'split inputs written')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
