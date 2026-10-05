"""Extras / credits / movie catalogue for the Frontend lane -> manifests/frontend_package/extras.json

Sources (all read-only, authored):
  UI_GFxExtras_p.ExtrasMenu_GFX (the Extras screen; frontend_gfx.json scan), UIText.int / UIText.FRA [Extras] keys,
  UI_GFxExtras_p.Concept<Category> category thumbnails, UI_ExtrasContent_p <Category><NN> gallery images
  (SeekFreePackage in Xe-TransEngine.ini), Game Dump Movies/*.bik (converted: ExtractedAssets/movies/*.mkv +
  *.subtitles.json by movies.py).
Matching rules: gallery category = localization key Concept<Category> = thumbnail texture Concept<Category> = image name
prefix <Category> (exact token match, HIGH); movie entry Movie<Id> = FMV_<id>.bik (case-insensitive exact token, HIGH).
Unlock rules: only the authored UnlockWith* strings are known; the unlock bookkeeping is native / ActionScript (UNKNOWN).
"""
import glob, json, os, re, subprocess, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
DUMP = os.path.normpath(os.path.join(AT, '..', 'Game Dump', 'TransGame', 'Movies'))
CFG = os.path.join(ROOT, 'config')
FFPROBE = os.path.join(AT, 'bin', 'ffmpeg', 'ffprobe.exe')
GEN = 'AssetTools/scripts/wfc/fe_extras.py'

def ini_section(path, name):
    out, cur = OrderedDict(), None
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\r\n')
        if line.startswith('['): cur = line.strip('[]'); continue
        if cur == name and '=' in line:
            k, v = line.split('=', 1); out[k] = v
    return out

def probe(p):
    if not os.path.exists(FFPROBE) or not os.path.exists(p): return None
    try:
        r = subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height', '-of', 'json', p],
                           capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout)
        v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), {})
        return {'duration_s': round(float(j['format']['duration']), 2), 'width': v.get('width'), 'height': v.get('height'),
                'audio_tracks': sum(1 for s in j.get('streams', []) if s.get('codec_type') == 'audio')}
    except Exception as e:
        return {'error': repr(e)[:120]}

def main():
    intx = ini_section(os.path.join(CFG, 'Coalesced_int', 'TransGame', 'Localization', 'INT', 'UIText.int'), 'Extras')
    fra_p = glob.glob(os.path.join(CFG, 'Coalesced_FRA', 'TransGame', 'Localization', 'FRA', 'UIText.*'))
    fra = ini_section(fra_p[0], 'Extras') if fra_p else {}
    loc = lambda k: {'INT': intx.get(k), 'FRA': fra.get(k)}
    content = os.path.join(ROOT, 'content', 'UI_ExtrasContent_p')
    imgs = sorted(f for f in os.listdir(content) if f.endswith('.png')) if os.path.isdir(content) else []
    galleries = []
    for k in intx:
        m = re.match(r'^Concept(\w+)Title$', k)
        if not m: continue
        cat = m.group(1)
        pics = [f for f in imgs if re.match(r'^%s\d+\.png$' % re.escape(cat), f)]
        thumb = 'content/UI_GFxExtras_p/Concept%s.png' % cat
        galleries.append(OrderedDict([('id', cat), ('title', loc('Concept%sTitle' % cat)), ('description', loc('Concept%sDescription' % cat)),
                                      ('thumbnail', thumb if os.path.exists(os.path.join(ROOT, thumb)) else None),
                                      ('images', ['content/UI_ExtrasContent_p/' + f for f in pics]), ('count', len(pics)),
                                      ('match', 'exact token: loc key Concept%s / texture Concept%s / images %sNN (HIGH)' % (cat, cat, cat))]))
    assigned = {i for g in galleries for i in g['images']}
    unassigned = ['content/UI_ExtrasContent_p/' + f for f in imgs if 'content/UI_ExtrasContent_p/' + f not in assigned]
    movies = []
    for k in intx:
        m = re.match(r'^Movie(\w+)Title$', k)
        if not m: continue
        mid = m.group(1)
        stem = 'FMV_intro' if mid == 'Intro' else 'FMV_' + mid.lower()
        bik = [f for f in os.listdir(DUMP) if f.lower() == (stem + '.bik').lower()] if os.path.isdir(DUMP) else []
        mkv = os.path.join(ROOT, 'movies', stem + '.mkv')
        subs = os.path.join(ROOT, 'movies', stem + '.subtitles.json')
        movies.append(OrderedDict([('id', mid), ('title', loc('Movie%sTitle' % mid)), ('description', loc('Movie%sDescription' % mid)),
                                   ('bik', ('Game Dump/TransGame/Movies/' + bik[0]) if bik else None),
                                   ('mkv', 'movies/%s.mkv' % stem if os.path.exists(mkv) else None),
                                   ('subtitles', 'movies/%s.subtitles.json' % stem if os.path.exists(subs) else None),
                                   ('text_overlays', sorted('movies/' + os.path.basename(x) for x in glob.glob(os.path.join(ROOT, 'movies', stem.replace('intro', 'text').replace('outro', 'text') + '_*.mkv')))),
                                   ('probe', probe(mkv)),
                                   ('match', 'loc key Movie%s <-> %s.bik (case-insensitive exact token, HIGH)' % (mid, stem))]))
    credits_mkv = os.path.join(ROOT, 'movies', 'FMV_credits.mkv')
    out = OrderedDict([
        ('generated_by', GEN), ('screen', {'movie': 'UI_GFxExtras_p/ExtrasMenu_GFX', 'file': 'content/UI_GFxExtras_p/ExtrasMenu_GFX.gfx',
                                           'scan': 'manifests/frontend_gfx.json (ExtrasMenu_GFX)', 'title': loc('ExtrasTitle'),
                                           'description': {'INT': None}, 'buttons': {b: {'label': loc(b + 'Button'), 'rollover': loc(b + 'Rollover')}
                                                                                       for b in ('ConceptArt', 'Movies', 'Credits')},
                                           'content_package': 'UI_ExtrasContent_p (Xe-TransEngine.ini [Engine.PackagesToAlwaysCook] SeekFreePackage)'}),
        ('concept_art_galleries', galleries), ('unassigned_images', unassigned),
        ('movies', movies),
        ('credits', OrderedDict([('label', loc('CreditsButton')), ('rollover', loc('CreditsRollover')),
                                 ('bik', 'Game Dump/TransGame/Movies/FMV_credits.bik' if os.path.exists(os.path.join(DUMP, 'FMV_credits.bik')) else None),
                                 ('mkv', 'movies/FMV_credits.mkv' if os.path.exists(credits_mkv) else None), ('probe', probe(credits_mkv)),
                                 ('note', 'credits are a pre-rendered movie (no scrolling text data authored)')])),
        ('unlock_strings', {k: loc(k) for k in intx if k.startswith('UnlockWith')}),
        ('unlock_logic', 'UNKNOWN: which chapter unlocks which gallery / movie is bookkept natively or in the Extras ActionScript; '
                         'only the UnlockWith* strings are authored'),
        ('paths', 'content/* and movies/* are relative to ExtractedAssets (local)')])
    path = os.path.join(AT, 'manifests', 'frontend_package', 'extras.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('galleries', len(galleries), [(g['id'], g['count']) for g in galleries], 'unassigned', len(unassigned), 'movies', len(movies),
          [(m['id'], bool(m['mkv']), (m['probe'] or {}).get('duration_s')) for m in movies], 'credits', out['credits']['probe'])

if __name__ == '__main__':
    main()
