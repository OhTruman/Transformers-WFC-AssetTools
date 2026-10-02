"""UE3 material expression-graph tracer (authored data, read-only).

graph(material_opath, pkg) -> {
   'material': props of the Material (BlendMode, LightingModel, ... and the
               property inputs DiffuseColor/Normal/EmissiveColor/... -> node ids),
   'nodes': {node_name: {'class', 'props', 'inputs': [{'pin','node','output_index','mask'}]}},
   'functions': MaterialFunction call nodes are followed into their own graphs }
Edges are FExpressionInput structs: {Expression, ExpressionOutputIndex, Mask, MaskR..A}.
TextureSample output indices (UE3): 0 RGB, 1 R, 2 G, 3 B, 4 A   (CONFIRMED UE3 convention).

Queries (CLI):
  python matgraph.py <Material> --pkg P                 summary: root pins -> upstream params/textures
  python matgraph.py <Material> --pkg P --consumers NAME   who reads node/param NAME (pin, output index)
  python matgraph.py <Material> --pkg P --upstream PIN     full upstream tree of a root pin
  python matgraph.py <MIC> --pkg P --chain               MIC -> parent chain with overrides
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, typed_props as tp  # noqa: E402

ROOT_PINS = ('DiffuseColor', 'DiffusePower', 'SpecularColor', 'SpecularPower', 'Normal', 'EmissiveColor', 'Opacity',
             'OpacityMask', 'Distortion', 'TwoSidedLightingMask', 'TwoSidedLightingColor', 'CustomLighting',
             'CustomSkylightDiffuse', 'AnisotropicDirection', 'WorldPositionOffset', 'WorldDisplacement',
             'TessellationMultiplier', 'SubsurfaceInscatteringColor', 'SubsurfaceAbsorptionColor',
             'SubsurfaceScatteringRadius', 'ScreenAlpha')  # ScreenAlpha: WFC licensee pin (post-process materials)
OUT_NAMES = {0: 'RGB', 1: 'R', 2: 'G', 3: 'B', 4: 'A'}

def _short(path): return path.rsplit('.', 1)[-1] if path else path

def _edges(props):
    out = []
    for k, v in props.items():
        vals = v if isinstance(v, list) else [v]
        for n, x in enumerate(vals):
            if isinstance(x, dict) and 'Expression' in x and x['Expression']:
                e = {'pin': k if len(vals) == 1 else '%s[%d]' % (k, n), 'node': _short(x['Expression']),
                     'output_index': x.get('ExpressionOutputIndex', 0)}
                if x.get('Mask'): e['mask'] = ''.join(c for c in 'RGBA' if x.get('Mask' + c))
                out.append(e)
            elif isinstance(x, dict):
                for e in _edges(x): e['pin'] = k + '.' + e['pin']; out.append(e)
    return out

def graph(mat, pkg=None):
    pkg = pkg or objtree.owner(mat)
    p = objtree.package(pkg)
    i = p._idx.get(mat.lower())
    if not i: return {'material': mat, 'missing_in': pkg}
    md = tp.simplify(p._tr.read_dict(i))
    nodes = {}
    pre = mat.lower() + '.'
    for k, j in p._idx.items():
        if not k.startswith(pre): continue
        c = p.class_name(p.exports[j - 1])
        if not c.startswith('MaterialExpression') or c == 'MaterialExpressionTree': continue
        try: d = tp.simplify(p._tr.read_dict(j))
        except Exception as ex: d = {'__error__': str(ex)}
        d.pop('EditorX', None); d.pop('EditorY', None); d.pop('bRealtimePreview', None)
        nodes[_short(p.object_path(j))] = {'class': c, 'props': d, 'inputs': _edges(d)}
    roots = {k: {'node': _short(v['Expression']), 'output_index': v.get('ExpressionOutputIndex', 0)}
             for k, v in md.items() if k in ROOT_PINS and isinstance(v, dict) and v.get('Expression')}
    meta = {k: v for k, v in md.items() if k not in ROOT_PINS and k not in ('ExpressionTree', 'Expressions')}
    return {'material': mat, 'package': pkg, 'class': p.class_name(p.exports[i - 1]), 'meta': meta,
            'roots': roots, 'nodes': nodes}

def label(n):
    pr = n['props']
    for k in ('ParameterName', 'Texture', 'Desc', 'FunctionName', 'R'):
        if pr.get(k) is not None: return '%s=%s' % (k, pr[k])
    return ''

def consumers(g, name):
    """nodes (and root pins) that read node `name` or a parameter named `name`."""
    targets = {k for k, n in g['nodes'].items() if k == name or n['props'].get('ParameterName') == name}
    out = []
    for k, n in g['nodes'].items():
        for e in n['inputs']:
            if e['node'] in targets:
                out.append({'consumer': k, 'class': n['class'], 'pin': e['pin'], 'from': e['node'],
                            'output': OUT_NAMES.get(e['output_index'], e['output_index']) if
                            g['nodes'][e['node']]['class'].startswith('MaterialExpressionTextureSample') else e['output_index']})
    for pin, r in g['roots'].items():
        if r['node'] in targets: out.append({'consumer': 'ROOT', 'pin': pin, 'from': r['node'], 'output': r['output_index']})
    return out

def upstream(g, node, depth=0, seen=None, maxd=40):
    seen = set() if seen is None else seen
    n = g['nodes'].get(node)
    if n is None: return {'node': node, 'missing': True}
    t = {'node': node, 'class': n['class'].replace('MaterialExpression', ''), 'label': label(n)}
    if node in seen or depth > maxd: t['ref'] = True; return t
    seen.add(node)
    kids = []
    for e in n['inputs']:
        k = upstream(g, e['node'], depth + 1, seen, maxd); k['pin'] = e['pin']
        if e['output_index']: k['out'] = OUT_NAMES.get(e['output_index'], e['output_index'])
        if e.get('mask'): k['mask'] = e['mask']
        kids.append(k)
    if kids: t['in'] = kids
    return t

def leaves(tree, out=None):
    out = [] if out is None else out
    if tree.get('label'): out.append((tree['class'], tree['label']))
    for k in tree.get('in', []): leaves(k, out)
    return out

def mic_chain(mi, pkg=None):
    pkg = pkg or objtree.owner(mi)
    chain = []
    cur = mi
    while cur and len(chain) < 12:
        pk = pkg if objtree.package(pkg)._idx.get(cur.lower()) else objtree.owner(cur)
        if not pk: chain.append({'object': cur, 'missing': True}); break
        p = objtree.package(pk); i = p._idx.get(cur.lower())
        if not i: chain.append({'object': cur, 'missing_in': pk}); break
        d = tp.simplify(p._tr.read_dict(i)); c = p.class_name(p.exports[i - 1])
        chain.append({'object': cur, 'class': c, 'package': pk, 'props': d})
        cur = d.get('Parent') if c.startswith('MaterialInstance') else None
    return chain

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mat'); ap.add_argument('--pkg')
    ap.add_argument('--consumers'); ap.add_argument('--upstream'); ap.add_argument('--chain', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.chain:
        r = mic_chain(a.mat, a.pkg)
    else:
        g = graph(a.mat, a.pkg)
        if a.consumers: r = consumers(g, a.consumers)
        elif a.upstream:
            rt = g['roots'].get(a.upstream)
            r = upstream(g, rt['node']) if rt else {'error': 'no root pin ' + a.upstream, 'roots': list(g['roots'])}
        else:
            r = {'material': g['material'], 'meta': g.get('meta'), 'node_count': len(g.get('nodes', {})),
                 'roots': {pin: sorted(set('%s %s' % x for x in leaves(upstream(g, v['node']))))
                           for pin, v in g.get('roots', {}).items()}}
    s = json.dumps(r, indent=1, default=str)
    if a.out: open(a.out, 'w').write(s)
    else: print(s)
