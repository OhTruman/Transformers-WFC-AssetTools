# Campaign render gap #3: height fog not picked up (AssetTools, read-only trace, 2026-10-23)

**For:** Rendering. Source: finding 3 of `CAMPAIGN_RENDER_DRYRUN.md` (A1 `lighting.json` `fogs` = [] although Intr1_Art_m has 3 fog actors).

## Cause (CONFIRMED)

- `Rebuild/tools/render/build_lighting.py` `fog()` (line 253) and `fogs()` (line 269) keep only exports whose class is exactly
  `HeightFogComponent`.
- The campaign mostly authors its fog as **`PostProcessVolumeHeightFogComponent`**, the component of a `PostProcessVolumeHeightFog`
  actor. authored.db `types`: `Engine.PostProcessVolumeHeightFogComponent` super = `Engine.HeightFogComponent`; the actor super =
  `Engine.Info`.
- It is a subclass with the same properties: Height, Density, LightBrightness, LightColor, StartDistance, ExtinctionDistance. The A1
  Intr1 values, for example:

  | component | Height | Density | LightBrightness | LightColor (R, G, B) | other |
  |---|---|---|---|---|---|
  | `_13919` | 31014 | 1e-6 | 4.0 | 226 / 168 / 139 | ExtinctionDistance 1e10 |
  | `_3450` | 52541 | 3e-6 | 1.0 | 213 / 172 / 153 | — |
  | `_15131` | 15214 | — | 0.35 | 201 / 182 / 156 | StartDistance 10000 |

- The exact-class filter skips them.

## Counts (inventory.db)

| scope | PostProcessVolumeHeightFogComponent | plain HeightFogComponent |
|---|---|---|
| campaign packages | 169 | 27 |
| A1 | 31 in 20 sublevels | 5 (DecoInt, DecoPlaza, Elevator, Global, IntroVista) |
| MP | 1: **MP_ESC_Remnant_ART_m** `PostProcessVolumeHeightFog_8512` (Height 127986, Density 2e-6, LightColor 181 / 125 / 74) | — |

The 3 dry-run packages contain none of A1's 5 plain HeightFogComponents, so they produced `fogs` = [].

## Semantics: PROVISIONAL / UNKNOWN

- The actor's script has only `AddVolumeLink` / `RemoveVolumeLink` stubs (RE decomp `Engine.PostProcessVolumeHeightFog.txt`). This
  suggests the fog is tied to volumes and turns on as the view enters a linked volume, rather than being global like HeightFog.
- The native code isn't decompiled, so how the fog is gated is UNKNOWN. A question for RE.

## Proposed fix (Rendering's code; not applied)

- Accept the subclass in `fog()` / `fogs()`, e.g. `class_name(e) in ('HeightFogComponent', 'PostProcessVolumeHeightFogComponent')`.
- Keep the actor and its volume links in the record, so the runtime can gate the fog once RE confirms the rule.
- **MP impact:** this changes `MP_ESC_Remnant` `lighting.json` (+1 fog layer). Keep MP byte-identical by gating the subclass to campaign
  maps, or take it as a deliberate, recorded MP change.
