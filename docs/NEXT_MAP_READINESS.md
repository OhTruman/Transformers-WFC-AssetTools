# Second MP map after Streets: readiness report (2026-10-03)

This is a report only. No second-map extraction was started.

* **Machine-readable:** `manifests/mp_next_map_readiness.json`, with per-map profiles, metrics, weights and ranking.
* **Generator:** `scripts/wfc/fe_map_catalog.py`.
  * It uses only indexed queries on `inventory.db` and `authored.db` and holds one map's sets at a time.
  * Its working-set guard is 6 GB; the observed peak was 0.05 GB.

## Method
* **Metrics.** Every metric is a CONFIRMED count from cooked data. Each covers the BASE level plus every streamed level (ART,
  AUDIO, shared art/audio).
  * Package completeness: streamed levels referenced vs present.
  * Dependencies: source packages not used by Streets; share of cooked objects also present in Streets.
  * Geometry: StaticMesh and BSP Model bytes vs Streets; SMCA component count.
  * Unique code/state: Kismet nodes, Matinee count, actor/component classes Streets does not use.
  * Movers (`InterpActor`, `StaticInterpActor`, `KActor`) and destructibles.
  * Lighting format: the set of lightmap-related classes compared with Streets.
* **Effort index.**
  * Weighted metrics, each normalised to the candidate maximum:
    * weight 3: new source packages, new classes;
    * weight 2: geometry ratio;
    * weight 1: Kismet, Matinee, movers, destructibles, SMCA components.
  * Penalties:
    * +3 × (1 − object overlap with Streets);
    * +2 if the lightmap format differs;
    * +5 if a streamed level is missing;
    * +2 if the map lacks the six versus modes.
* **What is fact and what is judgment.** The weighting is an analysis choice, so the ranking is a recommendation. The metrics
  themselves are fact.

## Result

| rank | map | effort | new pkgs | overlap | geometry vs Streets | new classes | Kismet | movers | destructibles | lightmap format |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Gorge** (`MP_UND_Gorge_BASE_m`) | 2.91 | 17 | 95.2% | 0.60× | 9 | 91 | 13 InterpActor | 0 | same |
| 2 | Berth | 3.20 | 19 | 95.9% | 0.64× | 12 | 150 | 4 | 9 (+9 components) | same |
| 3 | Complex | 3.25 | 18 | 95.6% | 0.71× | 12 | 124 | 7 | 0 | same |
| 4 | Molten | 3.46 | 16 | 94.2% | 0.87× | 9 | 353 | 4 | 0 | same |
| 5 | Seed of Corruption | 5.47 | 27 | 92.7% | 1.19× | 15 | 575 | 16 | 6 | same |
| 6 | Rust | 6.30 | 24 | 94.1% | 1.02× | 14 | 275 | 8 | 0 | **differs** (light-mapped skeletal meshes) |
| 7 | Orbital Debris | 6.96 | 53 | 88.1% | 1.03× | 19 | 347 | 18 (15 Matinee) | 12 | same |
| 8 | Broken Hope (Escalation only) | 14.57 | 101 | 64.9% | 1.33× | 28 | 1057 | 2 | 100 | differs |
| 9 | Remnant (Escalation only) | 16.51 | 82 | 68.9% | 1.20× | 44 | 1125 | 50 | 94 | differs |

**Streets for reference:**
* geometry: 11.7 MB StaticMesh plus 0.85 MB BSP; 1,953 SMCA components;
* code/state: 70 Kismet nodes, 1 Matinee;
* movers: 4 InterpActor and 8 StaticInterpActor;
* destructibles: 1;
* lighting: 81 `LightMapTexture2D`; 182 point, 83 spot, 2 directional and 1 sky light components.

## Recommendation: Gorge, with Berth as the alternative
**Gorge.**
* **Pipeline fit.** Same packaging as Streets: BASE plus ART plus AUDIO, plus `_LM` and `_LOC` companions. It streams no
  `GLB_Audio_m`. All six versus modes. Same lightmap format: `LightMapTexture2D` only.
* **Size and overlap.**
  * Smallest geometry (0.60× Streets) and fewest Kismet nodes (91).
  * 95.2% of its cooked objects are shared with Streets.
  * 17 new source packages: UND floors/walls/bridges, core floors/mech parts, IAC bridge/turret/spacedome, `TPRO_COR_AmbientMovers_p`,
    the `BL_LVL_MP_UND_GORGE` bank and others.
* **New classes (9):**
  * `InterpActor` ×13: ambient movers (`TPRO_COR_AmbientMovers_p`), a larger set than Streets has;
  * `SkeletalMeshActor`;
  * `LensFlareSource` / `LensFlareComponent` (new render feature);
  * `TnRadialForceVolume`;
  * `PhysicsVolume`, `PostProcessVolume`, `BeastLightEnvironmentVolume`, `TnTransformerBlockingVolume`, plain `PlayerStart`.
  * The radial-force volume and lens flares are the only new runtime semantics. Volumes are data.
* **No destructibles.**

**Berth** is the close second.
* It needs the destructible pipeline for 9 `TnStaticDestructibleActor` (`DES_NEU_Barricade_DSYS_p`). That pipeline was proven on
  Streets' wall panel.
* Other new classes: fog volumes (`FogVolumeConstantDensityInfo`), placed `PointLight` / `SpotLight` actors, and some new Kismet
  classes (`SeqAct_CauseDamage`, `SeqAct_Mixer`).

**Complex and Molten** are small, but both use `HmRoomVolume` / `HmRoomPortal`. That is a native room/portal visibility system
Streets does not use, and its runtime semantics need RE before a faithful render.

**Not recommended next:**
* Orbital Debris: 53 new packages and 15 Matinee sequences.
* Seed: Kismet ×8 Streets and an extra shared-art level.
* Rust: light-mapped skeletal meshes.
* Broken Hope and Remnant: Escalation-only maps with roughly 100 destructibles and an AI/wave state.

## Cheap next steps (not done)
`vs_map.py` takes the map name as its first argument (default `MP_IAC_Streets`), so `vs_map.py MP_UND_Gorge` would be the first
test. The `m04_*` scripts hard-code `MAP = 'MP_IAC_Streets'` and need a parameter first. This report
does not run them; per the brief, no giant second-map extraction is started.
