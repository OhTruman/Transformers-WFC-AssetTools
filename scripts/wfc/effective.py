"""Effective (inherited) property resolution for authored UE3 objects.

UE3 cooked objects serialize only the properties that differ from their ARCHETYPE.
For an archetype/instance the archetype is another object (often a class default
object, CDO); for a CDO the archetype is the super-class CDO.  So the effective
value of a property is the first object along  object -> archetype -> archetype ...
that serializes it.  (CONFIRMED rule of UE3 delta serialization; e.g.
VEH_SHARED_p.HoverTruck_Physics -> TransGame.Default__TnHoverCarSimulationBlueprint.)

API
  chain(opath)            -> [(opath, package, class, props), ...] object first
  effective(opath)        -> {prop: {"value": v, "from": opath_that_authored_it}}
  effective_values(opath) -> {prop: v}

CLI: python effective.py <opath> [--pkg PACKAGE] [--json]
Package choice: the given package (if the object is in it) else the largest cooked copy
(objtree.owner).  Archetypes are looked up in the same package first, then globally.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree  # noqa: E402

def _find(opath, prefer=None):
    if prefer:
        p = objtree.package(prefer)
        if opath.lower() in p._idx: return prefer
    return objtree.owner(opath)

def chain(opath, pkg=None, max_len=24):
    out, seen = [], set()
    cur = opath
    while cur and cur.lower() not in seen and len(out) < max_len:
        seen.add(cur.lower())
        pk = _find(cur, pkg)
        if not pk:
            out.append((cur, None, None, None)); break
        node = objtree.read(pk, cur)
        if node is None:
            out.append((cur, pk, None, None)); break
        import typed_props as tp
        out.append((cur, pk, node['class'], tp.simplify(node['raw'])))
        nxt = node.get('archetype')
        if not nxt:
            # cooked exports store archetype 0: the implicit archetype is the class default
            # object; a CDO's own parent is its super-class's CDO (super from schema.json).
            cls = node.get('class_path') or ''
            name = cur.rsplit('.', 1)[-1]
            if name.startswith('Default__'):
                t = tp.schema()['types'].get(tp.resolve_type(cls) or '', {})
                sup = t.get('super')
                nxt = (sup.rsplit('.', 1)[0] + '.Default__' + sup.rsplit('.', 1)[1]) if sup and '.' in sup else None
            elif '.' in cls:
                nxt = cls.rsplit('.', 1)[0] + '.Default__' + cls.rsplit('.', 1)[1]
        cur = nxt
    return out

def effective(opath, pkg=None):
    eff = {}
    for op, _pk, _cls, props in chain(opath, pkg):
        if not isinstance(props, dict): continue
        for k, v in props.items():
            if k not in eff: eff[k] = {'value': v, 'from': op}
    return eff

def effective_values(opath, pkg=None):
    return {k: v['value'] for k, v in effective(opath, pkg).items()}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('opath'); ap.add_argument('--pkg'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    c = chain(a.opath, a.pkg)
    if a.json:
        print(json.dumps({'chain': [x[0] for x in c], 'effective': effective(a.opath, a.pkg)}, indent=1, default=str))
    else:
        print('chain:', ' -> '.join('%s[%s]' % (x[0], x[2]) for x in c))
        for k, v in effective(a.opath, a.pkg).items():
            s = json.dumps(v['value'], default=str)
            print('  %-34s %-60s <- %s' % (k, s[:60] + ('...' if len(s) > 60 else ''), v['from']))
