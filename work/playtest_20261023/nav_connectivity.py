"""Nav regression diagnosis (Integration 2026-10-23): bot_nav walk-graph connectivity, live vs adapted (out/pc_adapt/<MAP>).
Directed graph: cell edges' neighbors (both ways) + links (drop_down / jump_up / double_jump_up, one way). A* fails between cells in
different strongly connected components, so the measure is the largest SCC's share of the walkable area, plus 'trap' area (cells that
reach the largest SCC only... or not at all: outside it). Read-only.
    python nav_connectivity.py [MAP ...]
"""
import json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
VSM = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']

def graph(d):
    ids = [c['id'] for c in d['cells']]; area = {c['id']: c['area_m2'] for c in d['cells']}
    g = defaultdict(set)
    for c in d['cells']:
        for e in c.get('edges') or []:
            for nb in e.get('neighbors') or []:
                n = nb.get('cell') if isinstance(nb, dict) else nb
                if n is not None: g[c['id']].add(n)
    for l in d.get('links') or []: g[l['from_cell']].add(l['to_cell'])
    return ids, area, g

def scc(ids, g):
    """iterative Tarjan -> list of components"""
    index, low, on, st, out, cnt = {}, {}, set(), [], [], [0]
    for s in ids:
        if s in index: continue
        stack = [(s, iter(g.get(s, ())))]; index[s] = low[s] = cnt[0]; cnt[0] += 1; st.append(s); on.add(s)
        while stack:
            v, it = stack[-1]; adv = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = cnt[0]; cnt[0] += 1; st.append(w); on.add(w); stack.append((w, iter(g.get(w, ())))); adv = True; break
                elif w in on: low[v] = min(low[v], index[w])
            if adv: continue
            stack.pop()
            if stack: low[stack[-1][0]] = min(low[stack[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = st.pop(); on.discard(w); comp.append(w)
                    if w == v: break
                out.append(comp)
    return out

def stats(path):
    d = json.load(open(path, encoding='utf-8')); ids, area, g = graph(d)
    comps = sorted(scc(ids, g), key=lambda c: -sum(area[x] for x in c))
    tot = sum(area.values()); big = sum(area[x] for x in comps[0])
    anchors = [a.get('cell') for a in d.get('anchors') or [] if a.get('cell') is not None]
    bigset = set(comps[0])
    return {'cells': len(ids), 'area_m2': round(tot), 'sccs': len(comps), 'largest_scc_area_share': round(big / tot, 4),
            'outside_largest_scc_m2': round(tot - big), 'anchors_outside_largest_scc': sum(1 for a in anchors if a not in bigset),
            'links': len(d.get('links') or [])}

def main(maps):
    rows = {}
    for m in maps:
        live = stats(os.path.join(VSM, m, 'bot_nav.json')); ad = stats(os.path.join(AT, 'out', 'pc_adapt', m, 'bot_nav.json'))
        rows[m] = {'live': live, 'adapted': ad}
        print('%-18s largest-SCC share %.3f -> %.3f | outside %6d -> %6d m2 | anchors outside %2d -> %2d | sccs %5d -> %5d | links %d -> %d' % (
            m, live['largest_scc_area_share'], ad['largest_scc_area_share'], live['outside_largest_scc_m2'], ad['outside_largest_scc_m2'],
            live['anchors_outside_largest_scc'], ad['anchors_outside_largest_scc'], live['sccs'], ad['sccs'], live['links'], ad['links']))
    json.dump(rows, open(os.path.join(HERE, 'nav_connectivity.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main(sys.argv[1:] or MAPS)
