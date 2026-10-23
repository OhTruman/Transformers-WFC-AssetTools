# Playtest 2026-10-23 #14: authored water / liquid materials (AssetTools, read-only)

**For:** Rendering.

**Data:** `work/playtest_20261023/water_materials.json` (script `water_materials.py`), with one record per material:
- maps using it;
- the translator's record (master, chain, blend mode, lighting model, connected inputs, graph features);
- the master's expression classes (authored.db);
- the authored instance-chain scalar / vector / texture parameters;
- the textures, with files and sizes.

**Scope:** every material matching water / liquid / coolant / puddle / waterfall / river in `Rebuild/work/render/MP_*/materials_glsl.json`
(14). The translator reports no error on any of them. Every texture object exists in authored.db and every referenced file exists on disk.
Texture names that look concatenated (`WaterFall_NORMWaterFall_CLR`, `Water_NORMENV_EnergonRiver_MAT`) are the real cooked object names.

## What WFC authored (CONFIRMED from cooked data)

WFC has **no lit, refractive "real water" shader** in MP. Every water-like surface is one of the families below.

### 1. Waterfall_Parent_MAT family (unlit, additive)

- **Used by:**
  - `Waterfall1 / Waterfall2_MATINST` (Remnant, Complex);
  - `ComplexWaterfall_MATINST` (Complex);
  - `Waterfall_Slow_MATINST` (Gorge, own parent `ENV_CORE_Wall_p…Waterfall_Parent_MAT`, same graph).
- **Material:** MLM_Unlit, BLEND_Additive.
- **Connected inputs:** EmissiveColor, Opacity, Normal, **Distortion**.
- **Graph:**
  - 4 Panners on Time (movement);
  - a ReflectionVector into a cubemap (`IaconCity_Cubemap`) tinted by `ReflectionColor`;
  - DepthBiasedAlpha (soft depth fade at intersections);
  - vertex colour.
- **Parameters:**

  | instance | Speed | Scale | Brightness | ReflectionColor (R, G, B) |
  |---|---|---|---|---|
  | Waterfall1 | 1.2 | 1.8 | 0.2 | 0.18 / 0.73 / 0.72 |
  | Waterfall2 | default | 1.0 | default | 0.085 / 1.0 / 0.69 |
  | ComplexWaterfall | 1.2 | 2.5 | 0.4 | 0.085 / 1.0 / 1.0 |
  | Waterfall_Slow (Gorge) | 1.2 | 1.8 | — | 0.043 / 0.34 / 0.63 |

- **Textures:** WaterFall_NORM 512², WaterFall_CLR 512², plus the cubemap.

### 2. Coolant_Parent_MAT family (unlit, additive)

- **Used by:**
  - `CoolantPuddles_MATINST` (Remnant);
  - `OmegaLiquidSurface_MATINST` (**every MP map**: the Omega battery liquid surface).
- **Graph:** 4 Panners, a 2-input Time path, ReflectionVector into the cubemap, DepthBiasedAlpha.
- **Parameters:**

  | instance | Speed | Scale | Brightness | DepthBiasBlend | ReflectionColor (R, G, B) |
  |---|---|---|---|---|---|
  | CoolantPuddles | 0.5 | 1.0 | 0.2 | 300 | 0.17 / 0.75 / 0.73 |
  | OmegaLiquidSurface | 1.0 | 2.0 | 0.5 | default | 0.085 / 0.65 / 1.0 |

- **Textures:** Fluid1_Norm 512² + `IaconCity_Cubemap`.

### 3. TryptiGelGlass_Mat (unlit, translucent): `OmegaLiquid_MATINST` (every MP map)

- **Graph:** 5 Panners, Sine wobble, 3 CameraVector (fresnel-style edge), two cubemaps (`ENV_Metals_CUBEMAP`, `FluidRed_Cubemap`),
  Distortion.
- **Parameters:**
  - Distortion_Scale −1.0, OpacityIntensity 0.3, ReflectionIntensity 3.0, ReflectionExponent 1.5, Scale 0.5, Speed 1.0;
  - Edge_Fresnel_Color = Refractive_Caustic_Color = Light_A_Color = (0.085, 0.60, 1.0).

### 4. Others

- `RainPuddles_Mat` → `MoltenRainPuddle_MatInst` (Molten):
  - unlit translucent; panned half-tone ripple textures (r1 / r2 / alphas);
  - a reflection cubemap tinted ReflectionColorTint (0.19, 0.17, 0.10), with BackgroundColorTint;
  - 5 Time nodes.
- `Energon_Lava_Mat` (Streets, BrokenHope): unlit translucent; 7 Panners, CameraVector, DepthBiasedAlpha.
- `Energon_CubeB_Mat` → ChemicalTankLiquid (Rust, Seed): Phong opaque, 5 Panners, emissive.
- Phong opaque coolant surfaces with no animation: CoolantFloor (Debris), CoolantPipe2, AngledSupportBlue.

## Notes for the user's checklist

- **Movement:** panned normal / colour maps, with authored Speed / Scale per instance.
- **Reflection:** cubemap only (reflection vector), tinted per instance. No planar or screen-space reflection is authored.
- **Refraction:** UE3 `Distortion` on families 1 to 3. This needs a scene-colour (refraction) pass; if the rebuild skips Distortion, that
  is a missing authored feature.
- **Transparency / depth:** additive or translucent opacity, with DepthBiasedAlpha soft intersections (CoolantPuddles DepthBiasBlend 300).
  This needs scene depth in the translucent pass.
- **Lighting interaction:** none. Families 1 to 3 are MLM_Unlit, so the look depends entirely on the emissive / cubemap terms.
- **Status:** whether the rebuild currently drops Distortion or DepthBiasedAlpha is UNKNOWN to AssetTools. The translator lists both under
  `connected` / `uses`, so Rendering can check its runtime paths.
- **Which water the user meant:** UNKNOWN (no map named). Candidates: the Gorge waterfall, the Remnant / Complex coolant and waterfalls,
  and the Omega battery liquid on every map.
