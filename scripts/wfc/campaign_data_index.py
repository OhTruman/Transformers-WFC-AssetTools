"""CAMPAIGN_DATA_INDEX.md: the data-side entry point for the campaign code phase (Integration 2026-10-18), mirroring the RE lane's
CAMPAIGN_RE_INDEX.md: one row per manifest kind (file pattern, writer, schema doc, known gaps) and per-chapter counts read from the
current outputs, so the index stays true when an export is rerun.

  python campaign_data_index.py   -> docs/handoff/CAMPAIGN_DATA_INDEX.md
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from campaign_summary import CHAPTERS, AT, VSR  # noqa: E402

NM = os.path.join(AT, 'manifests', 'next_map')
J = lambda p: json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None

KINDS = [
    # (kind, file pattern, writer, schema / rules doc, known gaps)
    ('Streaming', '`work/campaign_pilot/VerticalSlice/Maps/<ch>/streaming.json`', 'vs_streaming.py',
     'CAMPAIGN_STREAMING_RUNTIME.md (+ RE CAMPAIGN_STREAMING_RE.md)',
     'co-op remote streaming and loading-screen phases (RE PARTIAL); CINE sublevels tagged hidden_outside_matinee as an export default'),
    ('Pickups', '`manifests/next_map/<ch>_pickup_factories.json` (+ gameplay.json `pickups`)', 'vs_pickups.py / vs_gameplay.py',
     'CAMPAIGN_BACKLOG.md item 1; CAMPAIGN_PILOT_<ch>.md',
     'MP Escalation weapon pickups are a package-7 regen item; loot drop tables are RE data (campaign_loot_tables.json)'),
    ('Starts / walk graph', '`manifests/next_map/campaign_starts_report.json`, `manifests/maps/<ch>/structure_audit.json`',
     'map_structure_audit.py, campaign_starts_report.py', 'CAMPAIGN_PIPELINE_SUMMARY.md §1c; chapter_notes/<ch>.md',
     'airborne exemption reads reachFlags 2 as R_FLY (PROVISIONAL); D2 Guardian Chamber starts are elevated spawns over a real floor (elevated_above_floor); unclassified off-graph pickups need a per-actor look'),
    ('Collision', '`.../Maps/<ch>/collision_pawn.glb` (+ skeletal boxes in the audit walk graph)', 'vs_collision.py / vs_physics.py; skel_collision.py',
     'MP_TRANSFORMING_ACTORS.md; structure_audit `skeletal_world_actor_collision`',
     'TnTransformingWorldActor PhysicsAsset boxes are in the campaign walk graph only, not in collision_pawn.glb (runtime: Gameplay fidelity check); poses are the skeletal reference pose'),
    ('Pawn factories', '`manifests/next_map/<ch>_pawn_factories.json`', 'campaign_pawn_factories.py', 'CAMPAIGN_PILOT_<ch>.md; RE CAMPAIGN_AI_LAYER_RE.md',
     'none known; TnSeqVar_Character variables feed AI actions, not factories'),
    ('Matinee', '`manifests/next_map/<ch>_matinee.json`', 'vs_matinee.py', 'CAMPAIGN_MATINEE_SCHEMA.md (+ RE CAMPAIGN_MATINEE_RUNTIME_RE.md)',
     '165 groups unresolved (variables empty in the cook, listed); 1 bare InterpTrack'),
    ('Dialog', '`manifests/next_map/<ch>_dialog.json`, `work/dialog/subtitles.json`', 'vs_dialog.py, dialog_subtitles.py', 'CAMPAIGN_DIALOG_SCHEMA.md',
     '6 speakers via named variables absent from the exported levels; 52 waves have only the _LOC language twins (no merged copy; runtime reads twins); native Play / PostDelay timing'),
    ('Objectives', '`manifests/next_map/<ch>_objectives.json`', 'vs_objectives.py', 'CAMPAIGN_OBJECTIVES_SCHEMA.md (+ RE CAMPAIGN_HUD_OBJECTIVES_RE.md)',
     'blank Description read as "clear" (PROVISIONAL); D1 sets one key not in its bank'),
    ('FaceFX', '`ExtractedAssets/content/**/*.fxa` (+ `work/fxa/*.csv`)', 'work/fxa/fxa_parse.py, fxa_proof.py',
     'CAMPAIGN_FACEFX_RE.md (+ RE FACEFX_BONE_BLEND_RE.md)', 'visual check waits for Gameplay\'s hook; Trypticon correlation is a metric limit (PROVISIONAL)'),
    ('Collision physmats', '`manifests/maps/<ch>/collision_{weapon,pawn}_physmat.json`', 'collision_physmat.py', 'MP_COLLISION_PHYSMAT.md',
     'triangles without an authored PhysMaterial fall to the engine default (Metal), listed; simple-hull rule PROVISIONAL'),
    ('Materials for rendering', '`work/campaign_pilot/<ch>_materials_for_rendering.json`', 'campaign_chapter_doc.py',
     'CAMPAIGN_PIPELINE_SUMMARY.md §2', 'materials not compiled in any Rendering materials_glsl.json need a matc pass'),
]

def counts(M):
    md = os.path.join(VSR, 'Maps', M); r = {}
    st = J(os.path.join(md, 'streaming.json')) or {}
    r['streaming'] = '%d states, %d sublevels (%d static), %d checkpoints' % (len(st.get('states') or []), len(st.get('sublevels') or {}),
                     sum(1 for v in (st.get('sublevels') or {}).values() if v.get('fully_static')), len(st.get('checkpoints') or []))
    pf = J(os.path.join(NM, M + '_pickup_factories.json')) or {}
    r['pickups'] = '%d' % sum(((pf.get('counts') or {}).get('instances_by_class') or {}).values())
    sr = next((x for x in (J(os.path.join(NM, 'campaign_starts_report.json')) or {}).get('chapters', []) if x['map'] == M), {})
    cv = sr.get('campaign_verdict') or {}
    r['starts'] = '%s / %s starts, %s m2, %s%s' % (sr.get('starts_on_reachable_floor'), sr.get('starts'), '{:,.0f}'.format(sr.get('walk_graph_area_m2') or 0),
                                                  cv.get('status'), ' (PROV.)' if cv.get('exemption_applied') else '')
    sa = (J(os.path.join(AT, 'manifests', 'maps', M, 'structure_audit.json')) or {}).get('skeletal_world_actor_collision') or {}
    r['collision'] = '%s skeletal actors, %s boxes' % (sa.get('with_collision'), sa.get('boxes'))
    r['pawn'] = '%d' % len((J(os.path.join(NM, M + '_pawn_factories.json')) or {}).get('pawn_factories') or [])
    mc = (J(os.path.join(NM, M + '_matinee.json')) or {}).get('counts') or {}
    r['matinee'] = '%s / %s groups (%s unres.)' % (mc.get('interp_data'), mc.get('groups'), (mc.get('group_binding') or {}).get('unresolved', 0))
    dc = (J(os.path.join(NM, M + '_dialog.json')) or {}).get('counts') or {}
    r['dialog'] = '%s conv / %s lines (%s bound)' % (dc.get('conversations'), dc.get('lines'), dc.get('lines_speaker_bound'))
    oc = (J(os.path.join(NM, M + '_objectives.json')) or {}).get('counts') or {}
    r['objectives'] = '%s keys / %s setters' % (oc.get('bank_keys'), oc.get('setters'))
    ml = (J(os.path.join(AT, 'work', 'campaign_pilot', M + '_materials_for_rendering.json')) or {}).get('materials') or []
    r['materials'] = '%d / %d need matc' % (sum(1 for x in ml if not x.get('compiled_somewhere')), len(ml))
    return r

def main():
    L = []; a = L.append
    a('# Campaign data index (entry point for the campaign code phase; AssetTools, generated %s)\n' % time.strftime('%Y-%m-%d'))
    a('Generated by `scripts/wfc/campaign_data_index.py` from the current outputs. This is the data-side twin of the RE lane\'s '
      '`CAMPAIGN_RE_INDEX.md`, which covers semantics. Every manifest is read-only data written by AssetTools; campaign chapters only, '
      'with MP outputs proven unchanged for each export. All paths are relative to `AssetTools/` unless they say ExtractedAssets.\n')
    a('**Labels** as in the RE index: CONFIRMED (read in data or code), PROVISIONAL (our reading, not yet confirmed), UNKNOWN.\n')
    a('## Manifest kinds\n')
    a('| kind | file | writer (`scripts/wfc/`) | schema / rules | known gaps |'); a('|---|---|---|---|---|')
    for k, f, w, d, g in KINDS: a('| %s | %s | %s | %s | %s |' % (k, f, w, d, g))
    a('\nPer-chapter summaries: `CAMPAIGN_PILOT_<chapter>.md` and `CAMPAIGN_PIPELINE_SUMMARY.md`. Backlog: `CAMPAIGN_BACKLOG.md`.\n')
    a('## Counts per chapter\n')
    cols = [('streaming', 'streaming'), ('pickups', 'pickups'), ('starts', 'starts / walk graph / verdict'), ('collision', 'skeletal collision'),
            ('pawn', 'pawn factories'), ('matinee', 'matinee'), ('dialog', 'dialog'), ('objectives', 'objectives'), ('materials', 'materials')]
    a('| chapter | ' + ' | '.join(c[1] for c in cols) + ' |'); a('|---' * (len(cols) + 1) + '|')
    for M in CHAPTERS:
        r = counts(M); a('| %s | %s |' % (M, ' | '.join(r[c[0]] for c in cols)))
    a('\n## Related data from other lanes (read in place)\n')
    a('- RE `notes/data/campaign_player_characters.json` (30 SP iconic presets) and `campaign_loot_tables.json` (11 TnLootTable) '
      '(RE CAMPAIGN_CONTENT_DELTAS_RE.md, 38fb9c7).')
    a('- Localization: `ExtractedAssets/config/Coalesced_{int,FRA}.json` (decoded Coalesced; objectives, tutorial messages, subtitles keys).')
    a('- Movies: `ExtractedAssets/movies/*.mkv` (54 FMVs with subtitle JSON); semantics in RE FMV_PLAYBACK_RE.md.\n')
    out = os.path.join(AT, 'docs', 'handoff', 'CAMPAIGN_DATA_INDEX.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print(out)

if __name__ == '__main__':
    main()
