# WFC (Xbox 360) content format notes

Established by direct inspection of the dump plus cross-checking with UE Viewer
(build 1590) and its source (`Unreal/UnrealPackage/UnPackage3.cpp`, `Exporters/ExportGLTF.cpp`,
`Exporters/ExportPsk.cpp`). All parsing code lives in `scripts/wfc/`.

## Files on disc
| Kind | Count | Notes |
|---|---|---|
| `TransGame/CookedXenon/*.xxx` | 2438 | UE3 cooked packages (all of them, no TFC/texture caches, no separate audio banks) |
| `TransGame/Movies/*.bik` | 54 | Bink 1 (`BIKi`), 1280x720 ~29.2 fps, many mono `binkaudio_dct` tracks |
| `TransGame/Movies/*.txt` | 12 | subtitle cue lists `start_ms,end_ms,KEY` (text in `Subtitles.int`) |
| `Config/Xenon/Cooked/Coalesced.ini`, `Localization/Cooked/Xenon/Coalesced.{int,FRA}` | 3 | XOR-obfuscated coalesced ini bundles |
| `Xbox360TOC.txt` | 1 | `size 0 0 path md5` per file; every listed file's MD5 matches |
| `default.xex` | 1 | XEX2 executable (not touched) |
| `nxeart`, `$SystemUpdate/su20076000_00000000` | 2 | `PIRS` STFS containers (dashboard art / system update) |
| `$SystemUpdate/system.manifest` | 1 | `XMNP` system update manifest |

## Package header (big-endian)
`9E2A83C1`, version dword `0x009001FF` -> FileVersion **511**, LicenseeVersion **144**,
then a WFC-only int32 (always `0x4BDCFCC0`), then standard UE3 summary:
HeaderSize, FolderName, PackageFlags, Name/Export/Import counts+offsets, DependsOffset,
Guid, Generations, EngineVersion **3428**, CookerVersion **113**, CompressionFlags, chunk table.

* `PKG_StoreCompressed (0x02000000)`: 918 packages. Compression flag **2 = LZO1X**
  (not LZX). Chunks are 1 MB of uncompressed data in standard UE3 compressed-chunk
  format (tag, block size 0x20000, sizes, per-block (c,u) pairs).
* Name entry: FString + uint64 flags. Import entry: standard 28 bytes.
* **Export entry (WFC licensee >= 116)**: Class, Super, Outer, ObjectName(FName),
  Archetype, ObjectFlags(u64), SerialSize, SerialOffset, *no ComponentMap*,
  ExportFlags(u32), then **1 byte flag**; only if non-zero do NetObjectCount[], Guid,
  PackageFlags follow. Usually 45 bytes.
* Cooked packages embed copies of every object they use. A copy sits under a
  `Package` export flagged `EF_ForcedExport` (export_flags & 1) whose name is the
  **original source package** -> `object_path` (`opath` in the DB) = original path.
  Objects native to a file get the file name prefixed. Dedup on (opath, class).

## Object serialization (tagged properties)
`int32 NetIndex`, then tags `Name(FName) Type(FName) Size(i32) ArrayIndex(i32)`
[`StructName` FName for StructProperty]; **BoolProperty value is 4 bytes**; ByteProperty
has no enum name (pre-633). Prefixes before NetIndex:
* components: TemplateOwnerClass (+ TemplateName) -> 8 or 16 bytes total
* `RF_HasStack` actors: FStateFrame (Node, StateNode, ProbeMask u64, LatentAction u16,
  StateStack[], Offset) = 26 bytes -> tags at +30.
Placed components only store overrides; mesh/material come from the **archetype**
(prefab `*_ArcN` objects copied into the map) - merged in `maps.py`.
Coverage: 99.96% of exports in a 12-package sample (only script `Class` objects fail).

## Assets
* **Textures**: Xbox-tiled DXT; umodel untiles/decodes to PNG correctly. High mips live in
  whichever copy is largest; 207 textures (mostly editor icons) have no mip data in
  any copy. Some `_p` source packages hold 496-byte stubs while maps hold real mips.
* **TextureCube (18)**: umodel has no exporter; WFC cube stores face data natively.
* **Static / skeletal meshes**: umodel `-gltf` works (skin, joints, UVs, tangents,
  real material slot names).
* **Animations**: umodel exports AnimSets only as ActorX `.psa` from CLI ("glTF animation
  could be exported from mesh viewer only"). `psa2gltf.py` converts to glTF using
  umodel's exact conventions: undo MIRROR_MESH (q.y,q.w,p.y negated), swap Y/Z,
  cm->m, conjugate root rotation; constant (untracked) channels dropped. Verified:
  NAV_Idle frame 0 matches mesh rest pose (median error 0).
* **Audio**: `SoundNodeWaveEx` holds an **FMOD FSB4** bank (XMA2 inside). For dialog
  (`WL_DX_*`) and music (`WL_MX_*`) umodel writes zero-filled `.unk` files: the payload
  is 0x8000-aligned inside the export with zero padding, and the export's **last 8
  bytes = BE (absolute offset, size)** of the FSB4. `sounds.py` extracts natively.
  3,745 dialog waves are 200-300 byte stubs with no payload (not in this dump).
  vgmstream decodes all FSB4 -> WAV (24 kHz mono dialog, 48 kHz SFX/music).
* **Materials**: umodel exports MaterialInstanceConstant (`.mat` + `.props.txt`), ignores
  base `Material` ("empty parameters"); texture/parent links come from properties.
* **UI**: GFxMovieInfo/SwfMovie -> Scaleform `.gfx` (umodel `-3rdparty`).
* **FaceFX**: `.fxa` via `-3rdparty`.

## Coalesced.{ini,int,FRA}
int32 header, then (FString path, FString whole-file text) pairs to EOF. String bytes
XOR'd with the 61-byte key `cvnas;dwepo2345098]qw]{}p2039458pseasdfzcvvp;aseiurwefsdcfszd`
(found via autocorrelation peaks at 61k + per-column frequency analysis). Key phase
varies per string (recovered per string by text likelihood); terminators are not XOR'd.
UTF-16 strings use negative length. Community tools (Decrypticon/TFGamesUtil) do the same.

## Level geometry (added in the vertical-slice pass)
* **BSP (`Model`)**: after an empty tagged-property block: Bounds(28), bulk `Vectors`/`Points`
  (elemsize 12), bulk `Nodes` (elemsize **64**: Plane, iVertPool, iSurf, iVertexIndex, u16 ComponentIndex,
  u16 ComponentNodeIndex, ComponentElementIndex, iBack, iFront, iPlane, iCollisionBound, iZone[2],
  NumVertices, NodeFlags, iLeaf[2] — no ZoneMask/iRenderBound), `Surfs` = owner ref + count + 56-byte
  FBspSurf (Material, PolyFlags, pBase, vNormal, vTextureU, vTextureV, iBrushPoly, Actor, Plane,
  ShadowMapScale, LightingChannels), bulk `Verts` (elemsize 24). UV = ((P−pBase)·TexU)/128. Parser: `bsp.py`.
  Only the level Model holds visible brushwork; BRUSH actors' Models are stripped (0 nodes);
  BlockingVolume/Trigger brush Models keep their nodes (convex hulls, local space + actor transform incl. PrePivot).
* **StaticMeshCollectionActor**: after its properties, N × 64-byte big-endian FMatrix LocalToWorld,
  one per `StaticMeshComponents` entry (in order).
* **Placed components only store overrides** (StaticMesh, Materials come from the archetype chain).
* Property names are case-insensitive FNames: e.g. `Brush` is serialized as `BRUSH` — compare names case-insensitively.
* Some actor props record standing relationships (`Base` = the volume/mesh a player start stands on).

## Authored-data resolution rules (targeted evidence pass, 2026-10-01)
* **Effective values / archetypes (CONFIRMED).** Tagged data stores only deltas from the archetype. In this cook every
  export's archetype field is 0 → the archetype is the class default object `<ClassPkg>.Default__<Class>`; a CDO's parent
  is its super-class CDO (super from `schema.json`). `effective.py` walks object → CDO → super CDOs and reports which object
  authored each value. Example: `VEH_SHARED_p.HoverTruck_Physics.DashSpeed 3000` overrides `Default__TnHoverCarSimulationBlueprint` 5000.
* **Enum/bool defaults.** A ByteProperty/enum not serialized anywhere in the chain is 0 (first enum value), e.g.
  `TnAnimNotify_ToggleHidden.Option` absent ⇒ `Toggle_Unhide`; `TnAnimNotify_ToggleVehicleFx.Option` absent ⇒ `Toggle_EnableFx`.
* **StaticMesh section → material (CONFIRMED, `smsections.py`).** Native `FStaticMeshElement` array of LOD 0, preceded by
  its i32 count: `Material i32, EnableCollision u32, OldEnableCollision u32, bEnableShadowCasting u32, FirstIndex,
  NumTriangles, MinVertexIndex, MaxVertexIndex, MaterialIndex, Fragments TArray<(i32,i32)>` (40 + 8·n bytes). FirstIndex
  = 3·Σ previous NumTriangles; empty sections store FirstIndex 0. Validated on 171/171 Streets meshes. Never resolve
  umodel's short glTF material names globally: several packages define the same short name.
* **Cross-package references inside a map.** Streamed sublevels (e.g. `_ART_m`) may place meshes cooked only into the
  persistent `_BASE_m`; look up the persistent package after the sublevel.
* **PrefabInstance (CONFIRMED).** After the tags: `ArchetypeToInstanceMap` = i32 count + (archetype idx, instance idx)
  pairs; the instance is a normal placed actor in the level.
* **Material graphs.** Base `Material` exports keep their full expression graphs in the cook (`matgraph.py`):
  FExpressionInput = {Expression, ExpressionOutputIndex, Mask…}; TextureSample outputs 0 RGB, 1 R, 2 G, 3 B, 4 A.
  StaticSwitchParameter: A = true, B = false; DefaultValue absent = false.
* **SoundCue graphs.** `SoundCue.FirstNode → SoundNodeRoot` (Volume dB, DistanceMin/Max, Priority, Spatialization,
  Category → `SoundMixerCategoryName.CategoryName`, LoopStart/End, optional SoundParameter) → `SoundNodeWaveEvent`
  children (Time s, Volume dB, Pitch, ChildNodes → SoundNodeWaveEx). Vehicle sounds are routed by event name through
  `HmSoundEventSet.SoundEventSet[] {Event, Sound}`.
* **Camera.** `HmCameraStrategySet.Strategies[] {Type (TnXxxCameraStrategyType), Strategy}` → `HmCameraStrategy.Behaviors[]`;
  most behaviors carry a default plus `…ByPCS[]` overrides keyed by sets of player-camera-state classes (`TnPCS_*`).
  Weapons contribute a PCS through `TnWeapon.WeaponPCS`.
* **Clip timing.** Authored `SequenceLength = NumFrames/30`; `psa2gltf` places the last key at `(NumFrames−1)/30`.
  Notify `Time` values are in authored seconds.
* **FColor byte order (CONFIRMED).** Tagged `Color` values are the 4 bytes B,G,R,A (`Engine.Default__HUD.RedColor` = 00 00 FF FF).
  `props.py` returns them as a raw list in that order; `typed_props.py` names them. Reading the list as R,G,B swaps red/blue.
* **FMatrix row order (CONFIRMED).** Tagged `Matrix` values store each row as (W,X,Y,Z); native matrices (StaticMeshCollectionActor,
  StaticLightCollectionActor blocks) are conventional. `typed_props.fix_raw` reorders; `authored.py` fixes DB values on read.
* **StaticLightCollectionActor.** After the tags: N × 64-byte conventional FMatrix LocalToWorld, one per `LightComponents` entry
  (17152 B = 268 × 64 for Streets); identical to each light's (reordered) `CachedParentToWorld`.
* **Struct deltas.** Non-immutable struct properties serialize only fields that differ from the archetype's struct value;
  `authored.effective()` deep-merges them (e.g. TnWorldInfo.DefaultPostProcessSettings, LightComponent.LightingChannels).
* **Texture3D (CLUT).** Native tail after tags: 20-byte bulk header then the top mip, big-endian A8R8G8B8, Xenos tiled-3D
  (xenia Tiled3D addressing; `texture3d.py`). Validated on `ENV_MPCLUT_p.MP_Streets_CLUT` (monotone per axis, tail = 20 + N³·4).
* **ScreenAlpha** is a WFC licensee material root pin used by post-process MaterialEffects (with `bUsesSceneColor`); `matgraph.py` traces it.
* **Simple collision.** `StaticMesh.BodySetup -> RB_BodySetup.AggGeom` (KAggregateGeom): ConvexElems carry `VertexData` (mesh-space UU)
  and authored `FaceTriData` triangle indices; Box/Sphere/Sphyl elems carry a `TM` Matrix (nested; W-first rows like all tagged
  matrices - `authored.py` now fixes nested matrices recursively by schema type).
* **Unset enums/bytes.** A ByteProperty serialized nowhere in an object's archetype chain is 0, i.e. the enum's first value
  (e.g. TnTeamPlayerStart.Team unset = TNTG_Autobots; DefenderTeamIndex unset = 0). Class defaults that set 255 (neutral) are serialized.
* **MaterialFunctions.** `MaterialExpressionFunction.Function -> MaterialFunction` whose expressions live under the function's path
  (InputBlock/OutputBlock IO blocks); WFC masters declare most parameters inside functions.
* **MIC native tail** = cooked compiled material resource: a uniform-expression table of (FName expression class, FName parameter) pairs,
  e.g. `FMaterialUniformExpressionScalarParameter` / `...TextureSetIntermediateParameter`; it reflects the instance's static permutation.
* **TextureSet / TextureSetBlueprint** (licensee): blueprint Textures[] + Intermediates[{Name, Min/MaxSize, GetSizeFrom, Channels[]}];
  intermediates are ordinary Texture2D (DXT5) whose UnpackMin/UnpackMax define per-channel remaps (alpha -1..1 = normal component).

## Milestone-03 format findings (2026-10-02)
* **Compiled particle module stream** (ParticleLODLevel native tail, `pstream.py`): `+24` u8 module count; from `+35` one
  10-byte record per module (`u8 ModuleId`, two raw flag bytes, 5 zero bytes, `u16le` payload offset) separated by 7-byte
  running-count blocks; then `u8 n` + n module indices; then a **float distribution group** (`u32 nF` + nF raw distributions
  of types 1-4) immediately followed by a **vector group** (`u32 nV` + types 7-10). ModuleId indexes the cooked
  `Engine.ParticleModule.EParticleModuleId` enum (PMI_Lifetime=1 ... PMI_SubUVDirect=33). Inside a group, distributions
  follow module order and, per module, its RawDistributionFloat / RawDistributionVector properties. Exact consumption
  verified on 2,290 + 193 LODs (A1_IAC_Base_m, TransGame) with zero leftovers; tagged-module cross-check 12/12 matches.
  Census-proven counts: Gravity / ColorByParameter / Unknown / LocationEmitter carry none, DynamicParameter 4 floats,
  LocationDirect 3 vectors, SubUVDirect 2 vectors, VelocityInheritParent 1 vector; Orbit unresolved.
* **FSB4 sample header** (`fsb4.py`): all 1,929 FSB4 samples in MP_IAC_Streets_BASE_m, A1_IAC_Base_m and TransGame carry
  `loopstart=0, loopend=lengthsamples-1` and no LOOP_* mode bit; codec XMA (mode bit 0x01000000). Bytes from +72 of the
  sample header are a codec tail (kept raw).
* **Scaleform HUD**: `UI_GFxHud_p.Hud_GFX_1` is an uncompressed `GFX` v8 SWF (1120x720 stage, 30 fps). TnHUD data observers
  name `_global.*` AS2 callbacks (CallbackBindingName); the HUD logic is AS2 bytecode in DoAction tags (`as2dis.py`).
* **Destructibles**: HmDestructibleBlueprint -> PieceBlueprints -> StateBlueprints (handle = list index) -> EffectFactories
  + LinkBlueprints (NextStateHandle, TransitionTrigger class). The placed piece cooks one StaticMeshComponent per
  HmStaticMeshDestructionEffect (archetype TextureLightmapMeshTemplate0).
