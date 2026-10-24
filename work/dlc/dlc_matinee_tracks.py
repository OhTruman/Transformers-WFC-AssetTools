"""Every matinee (SeqAct_Interp) of one DLC map, keyed by FULL object path, with each InterpGroup bound to its actor(s) and every
track's keys as authored -> out/dlc_render/<MAP>/matinee_tracks.json (Rendering 2026-10-23: District's Power_Outage Interp_6320
material tracks, Tranquillity's Flood_Gate Interp_5361 drain / fog and the door matinees).

Why a separate file: Rendering's build_scene_floatprops.py exports InterpTrackFloatProp only, and movers.json keys matinees by the
short action name (SeqAct_Interp_10535 exists in 8 Tranquillity sequences) and pairs every group with every linked actor.
Binding (UE3 SeqAct_Interp): the action's VariableLink whose LinkDesc equals the group's GroupName -> SeqVar_Object(s) -> ObjValue.
Track application per class is the engine's (a FloatMaterialParam track here authors only ParamName + FloatTrack, no Materials
list, so it acts on the group's bound actor, e.g. a MaterialInstanceActor's MatInst): PROVISIONAL, not proven by RE.
Units as cooked: positions cm (UE axes), EulerTrack degrees, times s. Reads manifests/dlc/authored.db (read only).
    python dlc_matinee_tracks.py <MAP>
"""
import json, os, sqlite3, sys
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
LINK_KEYS = ('VariableLinks', 'InputLinks', 'OutputLinks', 'EventLinks', 'ParentSequence', 'ObjPosX', 'ObjPosY', 'DrawWidth', 'DrawHeight')


def main(m):
    db = sqlite3.connect('file:%s?mode=ro' % os.path.join(AT, 'manifests', 'dlc', 'authored.db').replace('\\', '/'), uri=True)
    pk = (m, m + '\\_%')

    def obj(path):
        r = db.execute('select class, props from objects where opath=?', (path,)).fetchone()
        return (r[0], json.loads(r[1]) if r and r[1] else {}) if r else (None, None)

    def seq_of(path):
        s = path.split('.Main_Sequence', 1)
        return s[1].lstrip('.').rsplit('.', 1)[0] if len(s) > 1 and '.' in s[1].lstrip('.') else ''
    out, stats = [], Counter()
    for path, pr in db.execute("select opath, props from objects where class='SeqAct_Interp' and (package=? or package like ? escape '\\') "
                               'order by opath', pk):
        p = json.loads(pr or '{}')
        links = {v.get('LinkDesc'): v.get('LinkedVariables') or [] for v in p.get('VariableLinks') or [] if isinstance(v, dict)}
        data = (links.get('Data') or [None])[0]
        dcls, dp = obj(data) if data else (None, None)
        groups = []
        for gp in (dp or {}).get('InterpGroups') or []:
            gcls, g = obj(gp)
            g = g or {}; name = g.get('GroupName')
            bound = []
            for var in links.get(name) or []:
                vcls, v = obj(var)
                a = (v or {}).get('ObjValue')
                if not a: bound.append(OD([('variable', var), ('variable_class', vcls), ('actor', None)])); continue
                acls, ap = obj(a)
                b = OD([('variable', var), ('actor', a), ('actor_class', acls)])
                if ap and ap.get('MatInst'): b['material_instance'] = ap['MatInst']
                bound.append(b)
            stats['groups'] += 1; stats['groups_bound' if any(b.get('actor') for b in bound) else 'groups_unbound'] += 1
            tracks = []
            for tp in g.get('InterpTracks') or []:
                tcls, t = obj(tp)
                tracks.append(OD([('track', tp), ('class', tcls), ('props', t)])); stats[tcls] += 1
            groups.append(OD([('group', gp), ('class', gcls), ('name', name), ('bound', bound), ('tracks', tracks)]))
        out.append(OD([('action', path), ('seq', seq_of(path)), ('interp_data', data), ('length_s', (dp or {}).get('InterpLength')),
                       ('action_props', {k: v for k, v in p.items() if k not in LINK_KEYS}), ('groups', groups)]))
        stats['matinees'] += 1
    res = OD([('map', m), ('generated_by', 'AssetTools/work/dlc/dlc_matinee_tracks.py'), ('source', 'AssetTools/manifests/dlc/authored.db'),
              ('binding', "SeqAct_Interp VariableLink LinkDesc == InterpGroup.GroupName -> SeqVar_Object.ObjValue (UE3)"),
              ('units', 'as cooked: cm, UE axes, EulerTrack degrees, seconds'),
              ('provisional', 'how each track class applies to its bound actor (material-param tracks without a Materials list) is not RE-proven'),
              ('stats', dict(stats)), ('matinees', out)])
    od = os.path.join(AT, 'out', 'dlc_render', m); os.makedirs(od, exist_ok=True)
    json.dump(res, open(os.path.join(od, 'matinee_tracks.json'), 'w', encoding='utf-8'), indent=1)
    print(m, dict(stats))


if __name__ == '__main__':
    main(sys.argv[1])
