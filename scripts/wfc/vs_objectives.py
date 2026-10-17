"""Campaign objectives export (Integration 2026-10-18; RE CAMPAIGN_HUD_OBJECTIVES_RE.md b8f071e): the objective text source of the
campaign HUD. Per chapter:
  bank        TnWorldInfo._ObjectiveBank of the persistent level, in order (SeqAct_TnSetCurrentObjective.Description is a key from it)
  text        each key localized from [Objectives] in TransGame.int / TransGame.fra (ExtractedAssets/config/Coalesced_{int,FRA}.json,
              the decoded Coalesced files of the Game Dump)
  setters     every SeqAct_TnSetCurrentObjective: key, bank index, sublevel, comment, all effective properties, firing events
Read only; writes manifests/next_map/<MAP>_objectives.json. Campaign chapters only.

  python vs_objectives.py <MAP> [...]
"""
import json, os, sys
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import write, map_out, map_levels  # noqa: E402
from vs_common import is_campaign, ROOT  # noqa: E402
from campaign_pawn_factories import build, fired_by  # noqa: E402

SKIP = ('ObjPosX', 'ObjPosY', 'DrawWidth', 'DrawHeight', 'InputLinks', 'OutputLinks', 'VariableLinks', 'EventLinks', 'ParentSequence',
        'ObjName', 'ObjComment', 'Description', 'bSuppressAutoComment', 'ObjClassVersion', 'ObjInstanceVersion')
_LOC = {}

def objectives_text(lang):
    """[Objectives] of TransGame.<lang> -> {key: text}; a key repeated in the file keeps all values (listed)"""
    if lang not in _LOC:
        d = json.load(open(os.path.join(ROOT, 'config', 'Coalesced_%s.json' % lang), encoding='utf-8'))
        f = next(v for k, v in d.items() if k.lower().endswith('/transgame.' + lang.lower()))
        _LOC[lang] = f.get('Objectives') or {}
    return _LOC[lang]

def text(key):
    key = (key or '').strip()      # authored keys can carry a trailing space (A4 bank 'A4_OBJ_OBJ10 '); the .int keys do not
    it = objectives_text('int').get(key); fr = objectives_text('FRA').get(key)
    return OD([('int', it[0] if it else None), ('fra', fr[0] if fr else None),
               ('int_all', it if it and len(it) > 1 else None), ('fra_all', fr if fr and len(fr) > 1 else None)])

def chapter(M):
    if not is_campaign(M): sys.exit('vs_objectives: campaign chapters only (%s is MP / UI)' % M)
    lvs, ops, back = build(M)
    base = map_levels(M)['base']
    banks = OD()
    for lv in lvs:
        for o in A.find(lv + '.TheWorld.PersistentLevel.%', 'TnWorldInfo'):
            b = (A.values(o['opath']) or {}).get('_ObjectiveBank')
            if b: banks[o['opath']] = list(b)
    bank = next((v for k, v in banks.items() if k.split('.')[0].lower() == (base or '').lower()), None)
    if bank is None and banks: bank = next(iter(banks.values()))
    bank = bank or []
    bank_t = [(k or '').strip() for k in bank]          # match on trimmed keys, keep the raw ones
    setters = []; missing_text = set()
    for a in sorted(o for o, x in ops.items() if x['class'] == 'SeqAct_TnSetCurrentObjective'):
        v = A.values(a) or {}; raw = v.get('Description'); key = (raw or '').strip() or None
        # RE CAMPAIGN_PROVISIONALS_CLOSED_RE.md (2d2a231, CONFIRMED): only an EMPTY Description clears (script tests != ""); a
        # whitespace-only one (A1 " ") localizes to "<?INT?TransGame.Objectives. ?>", which is not in the bank -> runtime no-op
        clears = (raw or '') == ''; ws_noop = bool(raw) and not raw.strip()
        direct, events = fired_by(a, ops, back)
        t = text(key) if key else None
        if key and not (t or {}).get('int'): missing_text.add(key)
        setters.append(OD([('action', a), ('sublevel', a.split('.')[0]), ('key', key), ('key_raw', raw), ('clears_objective', clears), ('whitespace_noop', ws_noop),
                           ('bank_index', bank_t.index(key) if key in bank_t else None),
                           ('comment', v.get('ObjComment')), ('text', t), ('properties', {k: x for k, x in v.items() if k not in SKIP}),
                           ('fired_by_direct', direct), ('fired_by_events', events)]))
    bank_rows = []
    for i, k in enumerate(bank):
        t = text(k)
        if not t['int']: missing_text.add(k.strip())
        bank_rows.append(OD([('index', i), ('key', k.strip()), ('key_raw', k), ('text', t), ('set_by', [s['action'] for s in setters if s['key'] == k.strip()])]))
    rep = OD([('map', M), ('generated_by', 'AssetTools/scripts/wfc/vs_objectives.py'),
              ('source', 'authored.db TnWorldInfo._ObjectiveBank + SeqAct_TnSetCurrentObjective; text: ExtractedAssets/config/Coalesced_{int,FRA}.json '
                         '[Objectives] of TransGame.int / .fra; semantics RE CAMPAIGN_HUD_OBJECTIVES_RE.md (b8f071e)'),
              ('counts', OD([('bank_keys', len(bank)), ('setters', len(setters)),
                             ('setters_with_key_in_bank', sum(1 for s in setters if s['bank_index'] is not None)),
                             ('setters_key_not_in_bank', sum(1 for s in setters if s['key'] and s['bank_index'] is None)),
                             ('setters_clearing', sum(1 for s in setters if s['clears_objective'])),
                             ('setters_whitespace_noop', sum(1 for s in setters if s['whitespace_noop'])),
                             ('setters_with_firing_event', sum(1 for s in setters if s['fired_by_events'])),
                             ('bank_keys_never_set', sum(1 for r in bank_rows if not r['set_by'])),
                             ('keys_without_int_text', len(missing_text)), ('banks_found', len(banks))])),
              ('bank_owner', next((k for k, v in banks.items() if v == bank), None)), ('other_banks', {k: v for k, v in banks.items() if v != bank}),
              ('bank', bank_rows), ('setters', setters), ('keys_without_int_text', sorted(missing_text))])
    write(map_out(M, 'streets_objectives.json'), rep)
    print(M, json.dumps(rep['counts']), flush=True)
    return rep

if __name__ == '__main__':
    for M in sys.argv[1:]: chapter(M)
