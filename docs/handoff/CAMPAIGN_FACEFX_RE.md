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

| compiled face graph | **u32 nNodes** (52; Soundwave 42; Skywarp / Starscream / Thundercracker 53; Omega 54; KON 55). Per node: u32 type (0, 4, 6 …), u32 nameIdx, f32 ×4 (min / max-type parameters, roles HYPOTHESIS), u32 0, **u32 nInputLinks, nInputLinks × {u32 inputNode, u32 linkFn, u32 nParams, nParams × f32}** (fn 1 = linear with params m, b, e.g. Omega `BlinkCombiner` = sum of 5 inputs × 1.0; fn 10 with 4 params on the KON faces), **u32 nProps, nProps × {u32 name, u32 type, i32 int, f32 real, u32 nStr, nStr × str}** (Omega `EmissiveBlink`, type 6: Material_Slot_Id 2, Parameter_Name "Emissive_Intensity", so the face graph drives Omega's emissive blink). Then the **node lookup hash table: u32 nBuckets (= nNodes); per bucket u32 hash, u32 n, n × (str name, u32 nodeIndex)**. Proven: every lookup name equals its node's name (19 files) |
| animation groups | u32 groupNameIdx ("Default"), u32 0 (anims), **u32 nGroups after it**; then nGroups × {u32 groupNameIdx, u32 nAnims, nAnims × animation}. 1 group (Dialogue) in most actors; 3 in Starscream (Dialogue, D1_Intro, D1_Outro…) and the KON faces (Dialogue, A2_CINE, A1_Intro): the cinematic groups |
| animation block | u32 animNameIdx, u32 nCurves, nCurves × (u32 nodeNameIdx, u32 0), **i32 −K**, f32 start, f32 end, u32 nCurves, **u32 flag** (1 = keys with stored slopes), f32 end, f32 b, flag × f32, nCurves × u16 keyCount (Σ = K), K × i16 time (t = v × end / 32767), K × i8 value, **if flag: K × (i8 slopeIn, i8 slopeOut)**, **then the trailer: f32 blendIn, f32 blendOut, u32 0, str SoundCue (empty for cinematic curves), str animName, u32 (0 / 1 / 2 / −1)** |
| phoneme map (file end) | **u32 n (42), n × {u32 phonemeId, u32 targetNameIdx, f32 weight}, u32 nTargets (15), nTargets × u32 targetNameIdx** = 572 bytes. **All 22 files end exactly at EOF.** The 15 targets are the phoneme nodes (Eat, If, Ox, Oat, Earth, Size, Church, Fave, Though, Bump, New, Told, Roar, Wet, Cage); weights 0.2 / 0.7 / 0.85 / 1.25 / 2.55. phonemeId is FaceFX's phoneme enum (its exact table is HYPOTHESIS until matched against the FaceFX 1.7 list). 10 distinct tails over the 22 files |

**Walk proof: all 22 files** are walked from the header through every group and animation to the 572-byte tail: **3,616 animations** (3,557 compressed dialog curves + 59 cinematic curves with stored slopes), every K equal to the sum of its key counts. Systems' blocks started at the trailer of the previous animation, so their undecoded "X" is the *next* animation's name index, and their "−K / a == end / b" fields are the header above. Their 74 exceptions are the slope variant and the group breaks.

**Value scale (HYPOTHESIS, strong):** phoneme, blink and eyebrow curves use i8 0..127, head / gaze curves −127..127, so value = i8 /
127 × the node's range (phonemes 0..1; Gaze_Eye_Yaw node range ±10).

## Exceptions

None left: every byte of all 22 files is accounted for by the layout above. Still undecoded in meaning: the node float roles,
`b`, the extra f32 of slope animations, and the phonemeId table.

## Next

1. The node float roles (min / max per node) to prove the value scale; `b`; the phonemeId table.
3. Interpolation: no slopes are stored except the ZetaPrime case. Compare FaceFX 1.7 Hermite with derived slopes against linear on
   curve shapes; a visual proof on one line (DX_TRPTCN_LK004350).
4. Bone-pose application: rest pose plus the weighted sum of the node deltas from the master bone list links.
