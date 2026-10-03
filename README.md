# AssetTools - WFC asset extraction pipeline

Tooling only. Proprietary output goes to `..\ExtractedAssets` (local reconstruction/testing
from an owned copy; do not redistribute). `..\Game Dump` is only ever opened read-only.

## One command
```powershell
powershell -ExecutionPolicy Bypass -File AssetTools\setup_tools.ps1   # first time: python, umodel, vgmstream, ffmpeg -> AssetTools\bin
AssetTools\bin\py\python.exe AssetTools\run_pipeline.py              # ~3-6 min end to end (movies dominate)
AssetTools\bin\py\python.exe AssetTools\run_pipeline.py --only build_db maps   # partial
```

## Steps (`scripts/wfc/`)
| Step | Script | Output |
|---|---|---|
| inventory | `inventory.py` (+ `ue3pkg.py` native UE3/WFC header, LZO, name/import/export parser) | `manifests/files.json`, `packages.json`, `packages/<pkg>.json`, `inventory.db`, `summary.json` |
| extract | `extract.py` - dedup by original object path, one owner package per object, parallel umodel | `ExtractedAssets/content/<srcpkg>/<group>/<obj>.*`, `manifests/extracted/<phase>.jsonl` + `_status.json` |
| sounds | `sounds.py` - native FSB4 extraction (fixes umodel dialog/music), vgmstream -> WAV | `.fsb` + `.wav`, `extracted/audio_native.jsonl` |
| build_db | `build_db.py` + `props.py` (tagged-property reader) | **`manifests/assets.json`** |
| anims | `psa2gltf.py` | `<AnimSet>.anim.gltf/.bin` beside each `.psa` |
| maps | `maps.py` | `ExtractedAssets/maps/<map>.json`, `manifests/maps.json` |
| config | `coalesced.py` | `ExtractedAssets/config/Coalesced_{ini,int,FRA}/...` + JSON |
| movies | `movies.py` | `ExtractedAssets/movies/*.mkv` + `*.subtitles.json` |
| high_value | `high_value.py` | `manifests/high_value.json`, `docs/HIGH_VALUE_ASSETS.md` |

## Querying
`manifests/inventory.db` (SQLite) tables: `files, packages, package_deps, exports(opath = original path), imports`.
```sql
SELECT package, opath, serial_size FROM exports WHERE class='SkeletalMesh' AND opath LIKE 'TR_Optimus%';
```
`assets.json` record: `id, key, asset_type, class, object_name, object_path, original_package,
owner_package, cooked_copies, extracted[], references{textures,materials,sounds,...},
materials[{ref|candidates, confidence}], parent, skeleton{bone_count,root,signature},
sequences[], preview_skeletal_mesh, compatible_skeletal_meshes/animsets, map_usage[], extraction_status`.

## Authored-data query tools (`scripts/wfc/`, read-only against Game Dump)
| Tool | Answers |
|---|---|
| `objtree.py <opath> [--flat]` | recursive typed dump of an object and its in-package sub-objects |
| `effective.py <opath> [--pkg P]` | effective property values through the archetype/CDO chain, with the authoring object |
| `matgraph.py <Material> [--consumers NAME \| --upstream PIN \| --chain]` | material expression graphs, parameter consumers, MIC chains |
| `particles.py <ParticleSystem>` | emitters, required/type-data modules, materials, raw native distribution tables |
| `smsections.py <PKG> <StaticMesh>` | authoritative section → material binding of a cooked mesh copy |
| `authored.py` | Python query layer over `authored.db`: get / effective (archetype chain) / children / refs_to / SoundCue graphs |
| `vs_audio.py [MAP]` | map ambient audio: emitters, Kismet audio zones + reverb presets (MASTER_WET DSP), cues with WAVs, spawn-zone check (`docs/AMBIENT_AUDIO_STREETS.md`) |
| `vs_lighting.py [MAP]` | map lighting: 268 lights with effective props + native placement, global lights, fog, light-channel analysis, character light environments, world post (`docs/LIGHTING_STREETS.md`) |
| `vs_postprocess.py [MAP]` | map post-process: scene chain + effects, governing world settings (deep-merged), CLUT decode/fit, semi-transparent + HUD screen chains, camera PP, fine-aim focus users (`docs/POSTPROCESS_STREETS.md`) |
| `texture3d.py` | Xbox tiled Texture3D (CLUT) decoder |
| `vs_physics.py [MAP]` | map collision/physics: per-trace collision worlds `collision_pawn.glb` / `collision_weapon.glb` (authored simple hulls, flags, sections), volumes, physical materials, world physics, movers, character PhysicsAssets (`docs/PHYSICS_STREETS.md`) |
| `vs_gameplay.py [MAP]` | map MP gameplay: modes (config), starts + spawn clusters, pickups + payloads, objectives per mode with volumes, Kismet graph + mode-dependent visibility, matinee (`docs/GAMEPLAY_STREETS.md`) |
| `vs_navigation.py [MAP]` | map path network: NavigationPoints + ReachSpecs, flags/sizes, connectivity analysis, `navigation.glb` (`docs/NAVIGATION_STREETS.md`) |
| `vs_materials.py [MAP]` | map materials: MIC chains, effective parameters (incl. MaterialFunction params), static-switch defaults, TextureSets, texture files, compiled-resource parameter names (`docs/MATERIALS_STREETS.md`) |
| `vs_character_materials.py` | Optimus robot/vehicle material handoff: authored MP meshes, MIC records, compiled static switches, team colour chain |
| `vs_evidence2.py` | `manifests/vs_evidence_pass2.json` (see `docs/EVIDENCE_PASS2.md`) |
| `vs_props.py [MAP]` | (checkpoint, not in pipeline) authored prop/static-mesh setup, validated vs cooked sections |
| `vs_mapfx.py [MAP]` | decals / particle components of a map with transforms and prefab provenance |
| `vs_evidence.py` | `manifests/vs_evidence.json` targeted slice evidence (see `docs/EVIDENCE_TARGETED_PASS.md`) |
| `pstream.py <PKG> <ParticleSystem prefix>` | **WFC compiled particle module stream decoder**: ModuleId (cooked `EParticleModuleId` enum) per module + every distribution assigned to module/property; `pstream.system()` = tagged summary + decoded modules. Cross-checked by `pstream_validate.py` |
| `fsb4.py` | FSB4 bank / sample-header reader (rate, channels, sample count, loop points, mode flags, raw header) for cooked SoundNodeWaveEx payloads |
| `gfxscan.py <file.gfx> [--grep RX]` / `as2dis.py <file.gfx> <sprite>` | Scaleform GFX/SWF tag scanner (exports, sprites, placements, AS2 constant pools) and ActionScript 2 disassembler |
| `vs_destructibles.py` | `manifests/streets_destructibles.json` (M03, see `docs/EVIDENCE_M03.md`) |
| `vs_pickups.py` | `manifests/streets_pickup_factories.json` + `streets_pickup_fx.json` (M03) |
| `vs_fineaim_hud.py` | `manifests/fineaim_hud.json` (M03) |
| `vs_surface_audio.py` | `manifests/streets_surface_audio.json` (M03) |
| `vs_audio_concurrency.py` | `manifests/vertical_slice_audio_concurrency.json` (M03) |
| `vs_vehicle_loops.py` + `validate_vehicle_loops.py` | `manifests/vehicle_audio_loops.json` (M03) and its header-level validator |
| `m04_bsp.py` / `m04_inventory.py` / `m04_kismet.py` / `m04_complete.py` | **complete MP_IAC_Streets map**: BSP audit, full actor/component inventory + rebuild classification, lighting/mover/prefab audits, Kismet + HUD references, canonical `manifests/mp_iac_streets_complete.json` + `render_index.json` (`docs/MAP_STREETS_COMPLETE.md`) |
| `validate_smca_transforms.py [--before DIR]` | transform-level validation of every StaticMeshCollectionActor component (translation / rotation / signed scale / determinant / bounds vs native + RE table) and the before/after audit |
| `m04_lightmap_atlases.py`, `validate_m04.py` | export missing lightmap atlas PNGs; map-completeness validation (`logs/validate_m04.json`) |
| `validate_m03.py` | cross-manifest validation of the M03 outputs (`logs/validate_m03.json`) |
| `schema.py`, `typed_props.py` | UnrealScript type registry (`manifests/schema.json`) and the schema-driven tag reader |
| `authored_db.py` / `authored_db_safe.py` | global **`manifests/authored.db`** (SQLite, 2.5 GB): `objects` (1,102,518 unique objects with typed props JSON, 0 unparsed), `refs` (2.5 M object references), `types` (schema). Build shards with `authored_db_safe.py --jobs 4 --merge` (one child per package, memory/timeout watchdog, failures in `logs/authored_db_failures.json`) |

See `docs/FORMAT_NOTES.md` (formats), `docs/FIRST_PASS_REPORT.md` (results), `docs/EVIDENCE_TARGETED_PASS.md` (slice evidence).
