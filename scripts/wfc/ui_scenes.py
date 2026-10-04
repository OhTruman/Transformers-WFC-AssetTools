"""Frontend 3D scene package: what is drawn BEHIND each frontend / lobby screen (answers 'UI over black').

Run the map pipeline first for each UI level family (vs_map, vs_mapfx, vs_lighting, vs_postprocess with MAP = UI_FrontEnd,
UI_PartyLobby, UI_Lobby, UI_CampaignLobby, UI_CharacterCustomization) - outputs ExtractedAssets/VerticalSlice/Maps/<MAP>/.
This script adds what those stages do not export: level streaming, cameras, Matinee camera / actor tracks with keys,
skeletal actors (mesh + anim sets), ambient sounds, and the GFx overlay per screen.
Output: manifests/frontend_package/ui_scenes.json        python ui_scenes.py
"""
import json, os, sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT, VS  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
GEN = 'AssetTools/scripts/wfc/ui_scenes.py'
FAMILIES = OrderedDict([('UI_FrontEnd', ['UI_FrontEnd_m', 'UI_FrontEnd_capture_VIG_m']), ('UI_PartyLobby', ['UI_PartyLobby_m']),
                        ('UI_Lobby', ['UI_Lobby_m']), ('UI_CampaignLobby', ['UI_CampaignLobby_m']),
                        ('UI_CharacterCustomization', ['UI_CharacterCustomization_m'])])

def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')
def V(o): return A.values(o) if o and A.get(o) else {}

def actors(lv, cls):
    d = A.con()
    return [o for (o,) in d.execute('SELECT opath FROM objects WHERE opath >= ? AND opath < ? AND class=?',
                                    (lv + '.TheWorld.PersistentLevel.', lv + '.TheWorld.PersistentLevel/', cls)).fetchall() if o.count('.') == 3]

def track(t):
    v = V(t); c = (A.get(t) or {}).get('class')
    out = {'track': t.rsplit('.', 1)[-1], 'class': c}
    for k in ('PosTrack', 'EulerTrack', 'FloatTrack', 'VectorTrack'):
        pts = ((v.get(k) or {}).get('Points') or [])
        if pts: out[k] = [{'t': p.get('InVal'), 'v': p.get('OutVal'), 'mode': p.get('InterpMode')} for p in pts]
    for k in ('CutTrack', 'AnimSeqs', 'FOVTrack', 'Sounds', 'FadeTrack', 'EventTrack'):
        if v.get(k): out[k] = v[k]
    for k in ('MoveFrame', 'RotMode', 'bUseQuatInterpolation', 'TrackTitle'):
        if k in v: out[k] = v[k]
    return out

def matinees(lv, nodes):
    out = []
    for n in nodes:
        if n['class'] != 'SeqAct_Interp': continue
        dname = (n['variables'].get('Data') or [None])[0]
        dobj = next((o['opath'] for o in A.find(lv + '.TheWorld.PersistentLevel.Main_Sequence.%' + str(dname)) if o['class'] == 'InterpData'), None) if dname else None
        dv = V(dobj)
        groups = []
        for g in dv.get('InterpGroups') or []:
            gv = V(g)
            groups.append({'group': gv.get('GroupName'), 'class': (A.get(g) or {}).get('class'),
                           'anim_sets': gv.get('GroupAnimSets'), 'tracks': [track(t) for t in gv.get('InterpTracks') or []]})
        bound = {k: v for k, v in n['variables'].items() if k != 'Data'}
        out.append({'action': n['object'], 'looping': n['authored'].get('bLooping', False), 'play_rate': n['authored'].get('PlayRate'),
                    'interp_data': dobj, 'length_s': dv.get('InterpLength'), 'groups': groups, 'bound_variables': bound,
                    'outputs': n['outputs'], 'comment': n['authored'].get('ObjComment')})
    return out

def main():
    flow = json.load(open(os.path.join(MANI, 'frontend_flow.json'), encoding='utf-8'))['levels']
    pkg = json.load(open(os.path.join(MANI, 'frontend_package', 'frontend_package.json'), encoding='utf-8'))
    out = OrderedDict()
    for fam, levels in FAMILIES.items():
        d = os.path.join(VS, 'Maps', fam)
        m = json.load(open(os.path.join(d, 'map.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'map.json')) else {}
        fx = json.load(open(os.path.join(d, 'map_fx.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'map_fx.json')) else {}
        pp = json.load(open(os.path.join(d, 'postprocess.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'postprocess.json')) else {}
        lt = json.load(open(os.path.join(d, 'lighting.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'lighting.json')) else {}
        rec = OrderedDict([('levels', levels), ('export_dir', rel(d))])
        rec['streaming'] = {lv: [{'object': o, 'class': c, **{k: x for k, x in V(o).items() if k in ('PackageName', 'Levels')}}
                                 for (o, c) in A.con().execute("SELECT opath, class FROM objects WHERE opath >= ? AND opath < ? AND "
                                                               "(class LIKE 'LevelStreaming%')", (lv + '.', lv + '/')).fetchall()] for lv in levels}
        rec['geometry'] = {'world_glb': rel(os.path.join(d, 'world.glb')) if os.path.exists(os.path.join(d, 'world.glb')) else None,
                           'world_glb_bytes': os.path.getsize(os.path.join(d, 'world.glb')) if os.path.exists(os.path.join(d, 'world.glb')) else 0,
                           'placed_props': m.get('placed_props'), 'unique_meshes': m.get('unique_meshes'),
                           'bsp_render_triangles': {k: v.get('render_triangles') for k, v in (m.get('bsp') or {}).items()},
                           'not_exported_by_vs_map': m.get('unhandled_actor_classes')}
        rec['fx'] = {'map_fx': rel(os.path.join(d, 'map_fx.json')) if fx else None, 'particle_components': len(fx.get('particle_components', [])),
                     'decals': len(fx.get('decals', [])), 'systems': sorted(fx.get('particle_systems', {}))}
        rec['lighting'] = {'lights': lt.get('summary') or (len(lt.get('lights', [])) if isinstance(lt.get('lights'), list) else None)}
        rec['postprocess'] = {k: pp.get(k) for k in ('scene_chain', 'governing') if k in pp}
        per = OrderedDict()
        for lv in levels:
            nodes = (flow.get(lv) or {}).get('nodes', [])
            cams = [{'actor': o.rsplit('.', 1)[-1], **{k: V(o).get(k) for k in ('Location', 'Rotation', 'FOVAngle', 'AspectRatio', 'bConstrainAspectRatio', 'Tag')}}
                    for o in actors(lv, 'CameraActor')]
            skel = []
            for cls in ('HmSkeletalMeshActor', 'SkeletalMeshActor', 'SkeletalMeshActorMAT'):
                for o in actors(lv, cls):
                    v = V(o); sc = V(v.get('SkeletalMeshComponent'))
                    skel.append({'actor': o.rsplit('.', 1)[-1], 'class': cls, 'mesh': sc.get('SkeletalMesh'), 'anim_sets': sc.get('AnimSets'),
                                 'materials': sc.get('Materials'), 'hidden': v.get('bHidden'), 'tag': v.get('Tag'),
                                 **{k: v.get(k) for k in ('Location', 'Rotation', 'DrawScale', 'DrawScale3D')}})
            snd = [{'actor': o.rsplit('.', 1)[-1], 'cue': V(V(o).get('AudioComponent')).get('SoundCue')} for o in actors(lv, 'AmbientSound')]
            per[lv] = {'cameras': cams, 'matinee': matinees(lv, nodes), 'skeletal_actors (not in world.glb)': skel,
                       'lens_flares': len(actors(lv, 'LensFlareSource')), 'fog': {c: len(actors(lv, c)) for c in ('HeightFog', 'FogVolumeConstantDensityInfo')},
                       'material_instance_actors': [o.rsplit('.', 1)[-1] for o in actors(lv, 'MaterialInstanceActor')],
                       'ambient_sounds': snd, 'music': (flow.get(lv) or {}).get('music'),
                       'kismet_class_counts': (flow.get(lv) or {}).get('kismet_class_counts')}
        rec['per_level'] = per
        out[fam] = rec
    screens = OrderedDict([
        ('boot_legal / logo_sequence / opening movie', {'scene': None, 'background': 'full-screen Bink movies (TF_InitialStartup, Logo_*, FMV_intro); '
                                                        'the 3D front-end scene is loaded behind but covered by the movie player', 'black_is': 'expected only between movies'}),
        ('title / main menu / settings / extras / friends / leaderboards / campaign select', {'scene': 'UI_FrontEnd (UI_FrontEnd_m + streamed UI_FrontEnd_capture_VIG_m)',
              'camera': 'UI_FrontEnd_m cameras + Matinee (fscommand startMainMenuCamera -> orbit camera Interp)',
              'background': '3D orbit battle scene: world.glb props, %d particle components, %d skeletal ships/actors (Matinee-animated, not in world.glb), lens flares, fog' % (
                  out['UI_FrontEnd']['fx']['particle_components'], sum(len(p['skeletal_actors (not in world.glb)']) for p in out['UI_FrontEnd']['per_level'].values())),
              'black_is': 'an omission: the front end is drawn over this level, not over black'}),
        ('party lobby / multiplayer / private match / create character (custom transformers)', {
              'scene': 'UI_PartyLobby_m (no scenery) + streamed UI_CharacterCustomization_m (LevelStreamingState Customize, visible)',
              'camera': 'UI_CharacterCustomization_m CameraActor + 15 Matinee camera moves chosen by CustomizationCameraId',
              'background': 'customization room (BSP + 5 props + fog volume + 4 MaterialInstanceActors) + preview pawn spawned by SeqAct_TnPawnFactory',
              'black_is': 'an omission if UI_CharacterCustomization_m is not streamed / the preview pawn not spawned'}),
        ('game lobby (map vote / host choice)', {'scene': 'UI_Lobby_m (no scenery) + streamed UI_CharacterCustomization_m (LevelStreamingState Customization, visible)',
              'background': 'same customization room; GameLobby_GFX map display uses MapInfo.ImagePath thumbnails', 'black_is': 'as party lobby'}),
        ('campaign lobby', {'scene': 'UI_CampaignLobby_m (12 BSP triangles + 1 prop; its LevelStreamingState lists no level)',
                            'background': 'essentially empty 3D scene: the screen is carried by the GFx movie (CampaignSelect / GameLobby art)',
                            'black_is': 'largely authored - verify against footage (UNKNOWN)'}),
        ('loading', {'scene': None, 'background': 'LoadScreen_GFX over black with the ring motif (loading_handoff.json); TF_LoadingScreen video is black + ring',
                     'black_is': 'authored'}),
        ('pause / match end / respawn', {'scene': 'the gameplay map', 'background': 'PauseMenu / EndGameStats / MultiplayerRespawn GFx over the live map',
                                         'black_is': 'an omission (map not rendered behind)'})])
    json.dump(OrderedDict([('generated_by', GEN), ('families', out), ('screens', screens),
                           ('confidence', CONF + ' (cooked levels, streaming objects, Kismet, map pipeline exports); verdicts HIGH')]),
              open(os.path.join(MANI, 'frontend_package', 'ui_scenes.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print({f: (r['geometry']['placed_props'], r['fx']['particle_components'], sum(len(p['matinee']) for p in r['per_level'].values()),
               sum(len(p['skeletal_actors (not in world.glb)']) for p in r['per_level'].values())) for f, r in out.items()})

if __name__ == '__main__':
    main()
