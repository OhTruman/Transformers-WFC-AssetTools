# MP_IAC_Streets post-process setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/postprocess.json`**; decoded grade **`postprocess_clut.png`**
(1024×32 strip: column = z·32 + x, row = y; input R = x, G = y, B = z).
Regenerate: `AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_postprocess.py`. Handoff: **Rendering** (camera/fine-aim items: **Gameplay**).

## Layers (all CONFIRMED unless noted)
1. **Scene chain:** `[Engine.Engine] DefaultPostProcessName = EngineMaterials.DefaultScenePostProcess` → `MotionBlurEffect` → `UberPostProcessEffect`.
   Both effects have `bUseWorldSettings = true`, so their parameters come from the governing world settings below.
   `DefaultPostProcess=PostProcess_XENON.PostProcessChain_0` in the same section points to a package that doesn't exist in the dump
   (INFERRED stale). `DisplayGamma 2.2`.
2. **Governing world settings:** the persistent level **`MP_IAC_Streets_BASE_m` TnWorldInfo**. It authors only these fields over the
   stock `Default__WorldInfo` struct (deep-merged; 50 fields in json):

| setting | value |
|---|---|
| Bloom | on, **Bloom_Scale 0.1**, Threshold 1.0 |
| Depth of field | **on**, FOCUS_Distance, FocusDistance 0, NearFalloff 2000, **FarFalloff 40000**, MaxNearBlur 1.0, **MaxFarBlur 0.6**, FalloffExponent 4, kernel 16, DOF/DOFAndBloom X/Y scale 1 |
| Motion blur | **off** (world `bEnableMotionBlur false`; the chain's MotionBlurEffect therefore does nothing). Stored params: Amount 0.5, MaxVelocity 1, 5 samples, camera+object |
| Scene tone | SceneEffect on, Desaturation 0, HighLights (1,1,1), MidTones (1,1,1), Shadows (0,0,0), i.e. neutral |
| Colour grading | **ColorCorrectionTexture `ENV_MPCLUT_p.MP_Streets_CLUT`** (32³ PF_A8R8G8B8 Texture3D) |
| Ambient occlusion | not allowed |

   The ART and AUDIO sublevel WorldInfos carry the stock defaults and do not govern.
   **Not used:** the UberPostProcessEffect's own class defaults (MidTones 1.3, HighLights 0.8, Desaturation 0.4, Shadows −0.003,
   focus falloffs 400). They apply only when world settings are bypassed.
3. **Colour grade (CLUT), decoded and validated:**
   * The native tail is exactly 20 + 32³·4 bytes; each channel is 100% monotone along its own axis; alpha is 255 everywhere.
   * Affine fit (out = M·in + b): M ≈ [[0.515, 0.239, 0.207], [0.243, 0.513, 0.216], [0.208, 0.213, 0.524]], b ≈ (0.076, 0.056, 0.073).
     RMS residual 10.4/255, so there is a non-linear curve on top.
   * **Saturation kept: about 29%** of the input. Grey ramp: black → 0, 0.5 → 0.577, white → 1. Mean luma +0.046. The lift has a slight
     magenta bias (green lifts least).
   * UE3 lookup in the uber shader: `tex3D(c·(N−1)/N + 0.5/N)`, applied after gamma (Rendering decoded it from microcode). The texture is
     not sRGB (`Default__Texture3D`).
4. **PostProcessVolumes:** none on Streets. The only matinee (SkyBeam) animates a move track; there are no post-process tracks.
5. **Semi-transparent chain:** `SemiTransparentPostProcess = ENV_AllShader_p.PostProcess.Hologram_PostProcess`, a single MaterialEffect
   with `Hologram_Post_MATINST` (HologramOpacity 0.85). The parent `Hologram_Post_MAT` is translucent and unlit, uses scene colour,
   and its EmissiveColor comes from HologramBaseColor/ColorTint, TimeScale, DiffClouds/Leather-height textures and a scan-line ShaderCode.
6. **HUD screen effects:** `UI_GFxHud_p.Hud_GFX_1.PostProcessChains`:
   * [0] `StaticDischargeScreenEffect`: unlit, uses scene colour, StaticPanner1 noise, 0.15 constant.
   * [1] `LowHealth.LowHealthScreenEffect`: scan lines and a tunnel-vision mask feeding the WFC-specific **ScreenAlpha** pin (0.04/0.3 constants).
   * `CurrentPostProcessChainIndex = −1`, so none is active by default. The activation logic is native or ActionScript (UNKNOWN).
7. **Camera / fine aim:**
   * `TnCamera.PPM0` (TnPostProcessModifier) defaults to an inactive modification: ActiveTime 0, ramps 0, stock settings.
   * `TnCamera.TargetFocuser0` defaults: kernel 8, FocusSize 1000, FalloffExponent 1, MaxNear 0.6, MaxFar 1.0.
   * Fine-aim target-focus DOF needs `bShouldApplyFineAimTargetFocus`. The **MP Ion Blaster does not set it** (default false). Only
     BurstRifle_AI, TurretIonGun_AI, MountedTurret_Rocket_AI, MountedRepairRay, Starscream_EMPShotgun_AI and MPBomb weapon data enable it.
8. **SystemSettings (Xe-TransEngine.ini):** MotionBlur, DepthOfField, Bloom, QualityBloom, Distortion, LensFlares, FogVolumes,
   FloatingPointRenderTargets all True; ResX/Y 1280×720; 3D-mode 1040×592; UpscaleScreenPercentage True; UpscaleSharpness 0.5.

## Notes
* The CLUT decoder (`texture3d.py`) is ported from the Rendering agent's `tools/render/xbox_texture.py` (xenia Tiled3D addressing) and was
  re-validated here by tail size, per-axis monotonicity and channel/axis correlation (R~x 0.83, G~y 0.83, B~z 0.84).
* The world DOF curve (blur as a function of distance from FocusDistance 0 with FarFalloff 40000 and exponent 4) follows the UE3 DOF
  formula and is INFERRED here; Rendering decoded the packing from the shader.
