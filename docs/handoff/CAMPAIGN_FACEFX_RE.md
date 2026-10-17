# FaceFX .fxa reverse engineering: AssetTools continuation (2026-10-16, in progress)

This continues Systems' first pass (`Rebuild/docs/handoff/CAMPAIGN_FACEFX_FORMAT.md`). Tool: `AssetTools/work/fxa/fxa_parse.py`
(read only on ExtractedAssets; report `work/fxa/fxa_report.json`). All 22 files parse with the layout below, no exceptions, and every
file lands on the same next structure.

## Proven (round trip over all 22 files)

| part | layout |
|---|---|
| header | "FACB", u32 1710, str licensee, str project, u32 1000, u16 1 |
| class table | **u32 nBuckets (10)**; per bucket: **u32 hash, u32 n, n × (str className, u16 classVersion)**. A name hash table: FxAnimCurve and FxPhonemeMap share bucket 109. Class versions: FxActor 3, FxAnim 6, FxMasterBoneList 2, FxName 1, FxAnimCurve 1, the others 0 |
| name table | **u32 nNames, nNames × str** (Trypticon 124 names, ending at 0xA60 exactly). Name indices everywhere below index this table |
| actor header | u32 0, u32 0 (all 22) |
| master bone list | **u32 nBones (14, or 33 for the KON faces)**; per bone: u32 nameIdx, f32 restPos[3], f32 restRot[4] (w,x,y,z), f32 restScale[3], f32 invRestRot[4] (the conjugate of restRot), u32 skeletonBoneIndex (0x7FFFFFFF = unresolved; Trypticon, Omega), f32 weight (1.0 in all 346 bones), u32 nLinks, then nLinks × {u32 nodeNameIdx, u32 boneIndex+1 (all 346 bones), f32 dPos[3], f32 rot[4], f32 dScale[3]}: the per-node bone pose of every face-graph node that moves this bone |

str = u32 length + bytes, no terminator; everything big-endian.

## Next

1. The compiled face graph, which starts right after the bone list with u32 0x34 / 0x35 / 0x36 / 0x2A (node count?), u32 4 (or 0),
   u32 0x0F …: node table, link table, link functions.
2. The animation groups → join Systems' proven animation-block layout, then the value scale, X, b, and the interpolation.
3. The KON 33-bone exceptions.
