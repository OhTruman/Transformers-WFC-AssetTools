"""Campaign render gap #1 (CAMPAIGN_RENDER_DRYRUN.md finding 1): per-package umodel -obj lists for the inline LightMapTexture2D of
every campaign chapter. umodel aborts at the first -obj missing from the package, so each level package gets only its own exports.

Level packages = the chapter's map.json sublevels (campaign VerticalSlice); the chapter's _LM packages are exported whole by step 1a and
are not listed. Source: manifests/inventory.db exports (class LightMapTexture2D). Writes inline_lightmaps.json beside this script:
{chapter: {package: [object names]}} plus per-chapter counts. Read-only.
"""
import json, os, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')

def main():
    inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
    out, summary = {}, {}
    for ch in sorted(os.listdir(CVS)):
        subs = json.load(open(os.path.join(CVS, ch, 'map.json'), encoding='utf-8')).get('sublevels') or []
        per = {}
        for pk in subs:
            names = sorted({r[0] for r in inv.execute("select name from exports where package=? and class='LightMapTexture2D'", (pk,))})
            if names: per[pk] = names
        out[ch] = per
        summary[ch] = {'level_packages': len(subs), 'packages_with_inline': len(per), 'inline_objects': sum(len(v) for v in per.values())}
    json.dump({'generated_by': 'AssetTools/work/campaign_render_dryrun/inline_lightmaps.py',
               'use': 'umodel -export -path=<cooked> -game=trans -png <package> -obj=<each name of that package only>',
               'summary': summary, 'per_package': out}, open(os.path.join(HERE, 'inline_lightmaps.json'), 'w', encoding='utf-8'), indent=1)
    for ch, s in summary.items(): print(ch, s)
    print('total inline objects', sum(s['inline_objects'] for s in summary.values()))

if __name__ == '__main__':
    main()
