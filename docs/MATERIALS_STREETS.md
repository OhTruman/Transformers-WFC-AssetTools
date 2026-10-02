# MP_IAC_Streets materials setup (recovered from authored.db, 2026-10-01)

Machine-readable: **`ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/materials_authored.json`**. The existing role-based
`materials.json` (PBR summary used to build `world.glb`) is unchanged.
Regenerate: `AssetTools\bin\py\python.exe AssetTools\scripts\wfc\vs_materials.py` (after vs_map / vs_mapfx). Handoff: **Rendering**.

## Scope
* **176 materials** used by Streets: 148 MaterialInstanceConstants and 28 base Materials, resolving to **48 masters**. Sources:
  * prop sections, from the cooked `FStaticMeshElement` bindings plus per-component overrides;
  * BSP surfaces, decals and emitter materials.
  * None is missing and every MIC chain resolves to a master.
* **Masters:** `ENV_AllShader_p.Release.ENV_PhongMain_NS_Mat` drives **113** instances. Next: ForceField_ALL (6), LightRays_V2 (5),
  FogSheet (3), MonitorScreen (3); the rest are single-use.
* **Blend modes:** Opaque 130, Additive 34, Translucent 5, Masked 5, Modulate 2.
* **Lighting:** Phong 129, Unlit 46, MediumLambert 1. 14 materials are two-sided.
* **Physical materials:** Metal 120, ForceField 6, Water 1, Rubber 1; 48 set none.

## What each record holds
* **Usage:** prop sections, component overrides, BSP/other, decals, particles.
* **Instance levels**, nearest first: the scalar/vector/texture/TextureSet/font overrides, `BoolPropertyValues` and PhysMaterial at each level.
* **Master meta:** blend, lighting, two-sided, masked/clip, PhysMaterial, usage flags (instance bool overrides applied).
* **Effective parameters:** the nearest instance override, else the master default, with the object that set it.
  * Parameters are collected **through MaterialFunctions**, recursively. WFC masters declare most parameters inside functions:
    PhongMain calls 12 (`ENV_Diffuse_MF`, `ENV_TextureMaps_MF`, `ENV_NormalMap_MF`, `ENV_Reflection_MF`, `ENV_Specular_MF`,
    `ENV_SpecPower_MF`, `ENV_Emissive_MF`, `ENV_AnisotropicHighlight_MF` and four decal functions), for 50 parameters and 17 static switches.
* **Static switch defaults** (master), plus **`compiled_resource_parameters`**: the parameter names the cooked compiled resource
  references (uniform-expression table in each MIC's native tail), i.e. what survives the instance's static permutation.
* **Textures:** extracted PNG paths, size, format, sRGB, unpack ranges.
* **TextureSets:** set, blueprint, intermediates and files.

## Findings
* **Static switches are per-instance and native.** PhongMain defaults `UseTextureSet = false`, yet **114 of 115** TextureSet-bound
  instances compile the TextureSet branch (their compiled resource samples `TextureSetIntermediate` parameters). The cooked static
  permutation enables it per instance; that permutation is not decoded here.
  * Use `texture_set_live` per material: true for 114.
  * The exception is `PROP_IAC_Statues_p.Texture.ChestOutStatue_MATINST`, which binds a TextureSet its compiled shader never reads.
* **The compiled resource agrees with the graphs:** for 137 of 140 instances every compiled parameter name is declared in the master or
  its functions. The remainder are a blank `None` entry and one non-parameter expression.
* **Dead overrides:** 75 MIC overrides name parameters the master no longer declares and the compiled resource never reads, e.g.
  `Reflection_FresnelIntensity`, `BumpOffset_MasksMap`, `SpecPowerScale`. They are leftovers from older master versions, ignored at runtime.
  3 more are blank entries named `None`.
* **TextureSets (WFC licensee):** a single blueprint, `ENV_AllShader_p.Release.ENV_MainTexSet_BluePrint`. It takes sources Color (Clr),
  Masks (Mask) and Normal (Norm; blur 4, Mitchell resize) and packs two intermediates:
  * `Color_NormX` (256–1024): Color RGB + normal X.
  * `Masks_NormY` (128–512): Masks RGB + normal Y.
  * The blueprint authors `OutputTextureChannel` R/G for the normal inputs (byte-level CONFIRMED), but the cooked intermediates are DXT5
    with `UnpackMin[A] = −1` and carry the normal in **alpha**. The cooker evidently routes normal channels to alpha (INFERRED);
    trust the intermediates' unpack ranges.
* **Not extracted by AssetTools:** 5 TextureCubes (`Iacon_Streets_CubeMap`, `IaconCity_Cubemap`, `ENV_Desaturated_Glass_CUBEMAP`,
  `Glass_Blue_CUBE`, `CHR_Metals_CUBEMAP_Metals_A_Center`), which Rendering decodes itself. Also 4 engine utility textures with no PNG
  (`Pixel_4_*`, `Crackle_1_NORM`).

## Not decoded (native)
The per-instance static permutation (the switch values themselves) and the full compiled uniform-expression stream with its constant
values. Rendering decoded the latter for its shader translation; here only parameter names are extracted.
