# MP_IAC_Streets lighting setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/lighting.json`**. Regenerate with
`AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_lighting.py`. It reads `authored.db` through `authored.py`, plus the light
collection's native placement matrices. It supersedes the old `lights.json`, which recorded a single empty `StaticLightCollectionActor`.
Handoff: **Rendering**. Units: UE units (cm); Brightness is unitless; colours are 8-bit sRGB.

## Two decoding corrections (CONFIRMED) — affect existing rebuild values
1. **FColor byte order is B,G,R,A** in this cook. Proof: `Engine.Default__HUD.RedColor` decodes to R255 G0 B0 A255 and
   `ConsoleColor` to (153,216,253,255), both UE3's stock values. `props.py` returns colours as the raw byte list, and reading that list as
   R,G,B swaps red and blue. **This affects Rendering:**
   * HeightFog `LightColor` bytes [234,91,116,0] = **RGB (116, 91, 234) `#745bea`, a blue-violet**. Rendering applied (234,91,116), "warm red-pink".
   * The dominant directional light = **RGB (117, 117, 255) `#7575ff`, blue-violet**. Rendering's notes describe it as "red".
   * Re-check every colour taken from `props.py` (lights, fog, particle and decal colours).
2. **Tagged FMatrix rows are stored (W, X, Y, Z).** Proof: all 265 lights' tagged `CachedParentToWorld` equals the collection actor's
   native LocalToWorld (max error 0.0) after reordering each row; decal `CachedParentToWorld` becomes the identity.
   `typed_props.fix_raw` now applies this; `authored.py` corrects matrices from the existing DB on read (`DB_MATRIX_FIXED=False`).

## Inventory (all in `MP_IAC_Streets_ART_m`, one `StaticLightCollectionActor_2528`)
* 268 light components with their native placement matrices: 182 point, 83 spot, 2 directional, 1 sky. 266 have been built into
  the lightmaps; 73 distinct colours. No standalone light actors, no dynamic shadows, no disabled lights.
* Point lights: Brightness 0.1–12 (median 2), Radius 506–9865 UU (median 1483), FalloffExponent 2 (one light uses 4).
* Spot lights: Brightness 0.4–12 (median 6), Radius 2068–7491 UU (median 4171), FalloffExponent 2. Common Inner/Outer cones:
  15/35°, 10/25°, 20/25°, 25/50°, 25/40°. 53 point down, 21 horizontal, 9 up.
* All local lights have CastShadows and CastStaticShadows on and CastDynamicShadows off.
* Palette (most frequent): `#f9bd88` warm white ×18, `#f45000` orange ×17, `#da2303` red ×15, `#ff2828` ×14, `#b7430b` ×12,
  violet `#8864f4` ×11, `#774bfa` ×10, `#a79df9` ×9, white ×8.
* Placement check: all 265 local lights lie inside the prop bounds, at a median 5.8 m from the nearest prop.

## Global lights
| role | light | Brightness | colour (RGB) | direction (UE, light travel) | channels on |
|---|---|---|---|---|---|
| dominant, baked | DirectionalLight_11360 | 6.0 | (117,117,255) | (−0.518, −0.542, −0.662) | BSP, Static, CompositeDynamic |
| character fill | DirectionalLight_727 | 0.2 | (149,149,198) | (0.012, 0, −1.0) straight down | CompositeDynamic only |
| sky | SkyLight_3181 | 0.1 (LowerBrightness 0) | upper (118,114,197); lower (157,203,236) | — | Dynamic, CompositeDynamic |
| height fog | HeightFog_8248 | LightBrightness 0.1 | **(116,91,234)** | Height −57273.8, Density 2e-5, Start 2048, Extinction 1e8 | — |

## How lighting reaches what (channel analysis)
Channels are deep-merged through each light's archetype chain. The stock actor templates `Default__PointLight.PointLightComponent0`
and `Default__DirectionalLight…` turn `Dynamic` off.
* **World geometry:** the 265 local lights plus the dominant directional are `LAC_STATIC_AFFECTING` with BSP+Static, so they are
  baked into the lightmaps (Beast). This matches Rendering's lightmap work.
* **Characters / dynamic objects:** **every** light has `CompositeDynamic` on, so all 268 reach characters through the light-environment
  composite path (HIGH CONFIDENCE; native). The fill directional reaches *only* characters this way. Only the SkyLight also has `Dynamic`.
  `LightsVisibilitiesVolume_2224` (744,772 native bytes, DrawScale3D 26729) holds the precomputed per-cell visibility for that composite.
* **Character light environments (CONFIRMED values):**

| owner | component | TotalLightCount | UpdateDistanceThreshold | EnvironmentTransitionTime | NormalizedSampleOffsets |
|---|---|---|---|---|---|
| TnRobotForm | LightEnvironment0 | **2** | 30 | 0.5 s | (0,0,.9) (0,0,−.7) (±.7,±.7,.7)… 6 samples |
| TnVehicleForm/TnTruckForm | MyLightEnv | 2 | 30 | 0.5 s | (0,0,.7) (±.8,±.8,0) 5 samples |
| TnWeaponMesh | MyLightEnvironment | 1 | 50 | 0.5 s | (0,0,0) |

  The robot mesh authors `LightingChannels.PlayerOnly`, bAcceptsLights/DynamicLights, CastShadow and bCastDynamicShadow. INFERRED (UE3
  DLE semantics, consistent with Rendering's decoded 2-light + ambient-cube shader): keep the 2 strongest contributions as lights and
  fold the rest into ambient.

## World settings (TnWorldInfo, struct deep-merged)
* BASE (persistent): DefaultPostProcessSettings = bloom on, **Bloom_Scale 0.1**, Bloom_Threshold 1, **DOF on**, DOF_MaxFarBlurAmount 0.6,
  DOF_FocusFarFalloff 40000, motion blur off, Scene_Desaturation 0, ColorCorrectionTexture `ENV_MPCLUT_p.MP_Streets_CLUT` (50 fields in json).
  `PackedLightAndShadowMapTextureSize 1024`, `EffectAmbientColor` white,
  `SemiTransparentPostProcess = ENV_AllShader_p.PostProcess.Hologram_PostProcess`, `bMapNeedsLightingFullyRebuilt` true.
* `LevelLightingGroups`: Tag "Layer", LevelsToLight `MP_IAC_Street_ART_m`, `MP_IAC_Street_DESIGN_m`. These are authored names
  *without* the "s" and match no cooked package; probably a stale editor entry.
* ART and AUDIO WorldInfos carry stock post-process defaults; BASE is the persistent level and governs.
* `BeastSettingsReferer_12059` has no authored bake settings (actor defaults only); the Beast bake parameters are not in the cook.

## Unknown / native
How light environments composite lights (selection and SH) and use `NormalizedSampleOffsets`; the `LightsVisibilitiesVolume` cell format;
the PrimitiveComponent native default channel mask; whether sRGB→linear is applied to FColor light colours in this build (assumed, as UE3).
