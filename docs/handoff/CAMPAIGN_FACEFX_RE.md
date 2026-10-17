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
| master bone list | **u32 nBones (14, or 33 for the KON faces)**; per bone: u32 nameIdx, f32 restPos[3], f32 restRot[4] (w,x,y,z), f32 restScale[3], f32 invRestRot[4] (the conjugate of restRot), u32 skeletonBoneIndex (0x7FFFFFFF = unresolved; Trypticon, Omega), f32 weight (1.0 in all 346 bones), u32 nLinks, then nLinks × {**u32 faceGraphNodeIndex** (an index into the compiled face graph's node list, not the name table: 5,281 / 5,281 in range, and the jaw resolves to Eat, Church, Jaw_Open, Jaw_Forward …), u32 boneIndex+1 (all 346 bones), f32 dPos[3] (a delta), f32 rot[4] (the bone's absolute rotation at node value 1; the delta from rest is conj(rest)·rot), f32 dScale[3]}: the bone pose of every face-graph node that moves this bone |

str = u32 length + bytes, no terminator; everything big-endian.

| compiled face graph | **u32 nNodes** (52; Soundwave 42; Skywarp / Starscream / Thundercracker 53; Omega 54; KON 55). Per node: u32 type (0, 4, 6 …), u32 nameIdx, f32 ×4 (min / max-type parameters, roles HYPOTHESIS), u32 0, **u32 nInputLinks, nInputLinks × {u32 inputNode, u32 linkFn, u32 nParams, nParams × f32}** (fn 1 = linear with params m, b, e.g. Omega `BlinkCombiner` = sum of 5 inputs × 1.0; fn 10 with 4 params on the KON faces), **u32 nProps, nProps × {u32 name, u32 type, i32 int, f32 real, u32 nStr, nStr × str}** (Omega `EmissiveBlink`, type 6: Material_Slot_Id 2, Parameter_Name "Emissive_Intensity", so the face graph drives Omega's emissive blink). Then the **node lookup hash table: u32 nBuckets (= nNodes); per bucket u32 hash, u32 n, n × (str name, u32 nodeIndex)**. Proven: every lookup name equals its node's name (19 files) |
| animation groups | u32 groupNameIdx ("Default"), u32 0 (anims), **u32 nGroups after it**; then nGroups × {u32 groupNameIdx, u32 nAnims, nAnims × animation}. 1 group (Dialogue) in most actors; 3 in Starscream (Dialogue, D1_Intro, D1_Outro…) and the KON faces (Dialogue, A2_CINE, A1_Intro): the cinematic groups |
| animation block | u32 animNameIdx, u32 nCurves, nCurves × (u32 nodeNameIdx, u32 0), **i32 −K**, f32 start, f32 end, u32 nCurves, **u32 flag** (1 = keys with stored slopes), f32 end, f32 b, flag × f32, nCurves × u16 keyCount (Σ = K), K × i16 time (t = v × end / 32767), K × i8 value, **if flag: K × (i8 slopeIn, i8 slopeOut)**, **then the trailer: f32 blendIn, f32 blendOut, u32 0, str SoundCue (empty for cinematic curves), str animName, u32 (0 / 1 / 2 / −1)** |
| phoneme map (file end) | **u32 n (42), n × {u32 phonemeId, u32 targetNameIdx, f32 weight}, u32 nTargets (15), nTargets × u32 targetNameIdx** = 572 bytes. **All 22 files end exactly at EOF.** The 15 targets are the phoneme nodes (Eat, If, Ox, Oat, Earth, Size, Church, Fave, Though, Bump, New, Told, Roar, Wet, Cage); weights 0.2 / 0.7 / 0.85 / 1.25 / 2.55. phonemeId is FaceFX's phoneme enum (its exact table is HYPOTHESIS until matched against the FaceFX 1.7 list). 10 distinct tails over the 22 files |

**Walk proof: all 22 files** are walked from the header through every group and animation to the 572-byte tail: **3,616 animations** (3,557 compressed dialog curves + 59 cinematic curves with stored slopes), every K equal to the sum of its key counts. Systems' blocks started at the trailer of the previous animation, so their undecoded "X" is the *next* animation's name index, and their "−K / a == end / b" fields are the header above. Their 74 exceptions are the slope variant and the group breaks.

**Node floats (PROVEN, 1,145 / 1,145 nodes):** (min, 1/min, max, 1/max), with 1 stored where a bound is 0. Phoneme / expression nodes
0..1; head / gaze nodes symmetric (±2, ±2.5, ±4, ±10; −3..5).

**Value scale (PROVEN):** in every one of the 3,616 animations the largest |i8| is exactly 127. Curves are normalised per animation
and **value = i8 / 127 × b**; the header float `b` (never below 1.0, median 1.19) is the animation's peak curve magnitude.

**Timing (measured on 728 dialog lines against their wave durations from the cue tree):**
- `end` ≈ the line's duration (median +0.20 s, p10 −0.14, p90 +0.67: probably the blend-out tail).
- `start` is a lead-in (median −0.27 s; 0 at most).
- Key times are t = i16 × end / 32767 (Systems), so the animation spans [start, end] on the voice's clock, starting with the line.

**Cinematic slopes (strong):** in all 21 measurable slope animations the largest |slope i8| is exactly 127, and the slopes correlate
with finite-difference tangents of the decoded keys (median r 0.83). So **slope = i8 / 127 × the header's extra f32** (the
animation's peak slope; fitted scale / extra f32 median 0.95). slopeIn and slopeOut are stored separately (they differ only at
corners).

**phonemeId table (strong):** the 42 map entries line up with FaceFX's ARPAbet phoneme order. Every vowel and consonant lands on the
matching mouth target, and id 40 (SIL) is the only id without an entry:

| id | phoneme | target | | id | phoneme | target |
|---|---|---|---|---|---|---|
| 0 | IY | Eat | | 21 | TH | Though |
| 1 | IH | If | | 22 | V | Fave |
| 2 | EH | If | | 23 | DH | Though |
| 3 | EY | If | | 24 | M | Bump |
| 4 | AE | If | | 25 | N | New |
| 5 | AA | Ox | | 26 | NG | New |
| 6 | AW | If | | 27 | L | Told |
| 7 | AY | If | | 28 | R | Roar |
| 8 | AH | If | | 29 | W | Wet |
| 9 | AO | Ox | | 30 | Y | Wet |
| 10 | OY | Oat | | 31 | HH | If |
| 11 | OW | Oat | | 32 | B | Bump |
| 12 | UH | Oat | | 33 | D | Told |
| 13 | UW | Oat | | 34 | JH | Church |
| 14 | ER | Earth | | 35 | G | Cage |
| 15 | AX | If | | 36 | P | Bump |
| 16 | S | Size | | 37 | T | Told |
| 17 | SH | Church | | 38 | K | Cage |
| 18 | Z | Size | | 39 | CH | Church |
| 19 | ZH | Church | | 40 | SIL | (none) |
| 20 | F | Fave | | 41 / 42 | SHORTSIL / FLAP | If 0.2 / Told 1.25 |

The phoneme names are not in the executable as strings (the XEX is compressed; the RE image sections hold only the FaceFX class names),
so the names stay a strong hypothesis. The runtime does not need them: animations drive the target nodes directly; the map is only
for generating new lip-sync from audio.

**Interpolation (open):**
- The 3,557 dialog animations store no slopes. FaceFX 1.7 curves are Hermite, so for them the slopes are derived at load / run
  time; linear vs derived Hermite can't be proven from the data alone.
- The 59 cinematic curves store i8 slopeIn / slopeOut per key; their scale (presumably × b / time unit) is still to determine.
- Proposal: evaluate with Hermite and Catmull-Rom-style derived slopes, compare against linear in the visual proof, and pick by eye.

## Exceptions

None left: every byte of all 22 files is accounted for by the layout above. Still undecoded in meaning: the node float roles,
`b`, the extra f32 of slope animations, and the phonemeId table.

## Visual proof, first results (tool `work/fxa/fxa_proof.py`: 30 Hz bone CSVs, jaw vs voice)

- **Timing CONFIRMED:**
  - The summed phoneme-node activity, curves only with no bone math, correlates with the voice RMS envelope at the best lag within
    ±10 frames: median 0.48 (Optimus, 34 lines), 0.43 (BumbleBee, 27), 0.38 (Ratchet, 30).
  - Median best lag −1 / 0 / +1 frame, so curve time 0 is the wave's start and the curve clock runs with the voice.
  - The correlation is moderate because phoneme shapes are not loudness.
- **Bone blend HYPOTHESIS:**
  - Rest ⊕ Σ value × (dPos, slerp(identity, conj(rest)·rot)) moves the jaw by up to 36° (linear) / 49° (Hermite derived slopes)
    on Trypticon LK004350.
  - Jaw angle against the voice: median 0.22 over 21 Optimus lines. Weaker than the curve activity, so the blend (additive
    rotations, sign, clamp) is not yet right.
  - Blend variants on the jaw, 34 Optimus lines, best lag within ±3 frames, with negative node values inverting the rotation:
    product of slerps 0.30, normalised weighted sum (nlerp) 0.30, product with values clamped to [0, 1] 0.30. Jaw angle against
    loudness cannot separate them; the choice needs a visual check on a skinned face (Gameplay's pose hook). Recommendation: the
    nlerp sum (order-independent, cheapest).
- **Interpolation:** linear and derived-Hermite give similar correlation (0.22 vs 0.18). The data can't separate them; the visual
  look (smoothness) decides.

## Visual-proof plan (headless, no game code)

1. **Pick a line:** Trypticon `DX_TRPTCN_LK004350` (25 curves, 8.61 s; wave `content/WL_DX_TRPTCN/DX_TRPTCN_LK004350.wav`, 8.76 s).
2. **Curves:** for each curve, decode keys (t = i16 × end / 32767, v = i8 / 127 × b) and sample at 30 Hz from start to end. Do it
   twice, linear and derived Hermite.
3. **Face graph:** node value = curve value, clamped to [min, max]. Nodes with input links (none in the robots' dialog set, except
   Omega / KON) get Σ linkFn(input); fn 1 = m·x + b.
4. **Bone poses:** for each of the 14 face bones, pose = rest ⊕ Σ over the bone's links (node value × the link's dPos / rot / dScale).
   Translation and scale add; rotation is slerped from identity by the node value. That's the standard FaceFX bone-pose blend
   (HYPOTHESIS until it looks right).
5. **Output:** a CSV per frame (time, 14 bones × pos / quat) plus a plot of jaw-open (C_Face01_Jaw_XF2 rotation) against the wave's
   RMS envelope.
6. **Pass criteria:** the jaw opens when the voice is loud (correlation of jaw angle and envelope > 0.5); silence at the start
   (lead-in) and end; total duration within 0.3 s of the wave.
7. **Then:** Gameplay applies the same evaluation in the skinned pose (after the body anim, override the 14 face bones), and Systems
   syncs the curve clock to the voice playback position.

## Pose hook Gameplay needs (exact spec, so it can be built without a round trip)

**Input:**
- **Skeletal pose** after the body animation: local (parent-space) transforms of all bones of the robot mesh.
- **The actor's FaceFX data:** `fxa_parse.parse_all(<RB_*_FaceFX.fxa>)`. Master bone list: rest pos / rot / scale, skeletonBoneIndex,
  links {node, dPos, rot, dScale}. Face-graph nodes {min, max, links, props}. Animations.
- **Playing animation and time:** name (from InterpTrackFaceFX `FaceFXSeqName` or the dialog line) and t = the voice's playback
  position in seconds, starting at the animation's `start` (negative lead-in).

**Per frame:**
1. **Curves:** each curve's value at t. Keys are t = i16 × end / 32767 and v = i8 / 127 × b. Interpolation is linear (or derived
   Hermite; to choose by eye). Cinematic curves use the stored slopes, i8 / 127 × extra f32.
2. **Node values:** curve value, plus Σ linkFn(input) for nodes with input links (fn 1: m·x + b), clamped to [min, max]. Nodes
   without a curve are 0.
3. **Bones** (CONFIRMED by RE from the native code, 2026-10-17: `RE-Workspace/work/handoff/FACEFX_BONE_BLEND_RE.md`, d38c9f4; this
   replaces the earlier nlerp-sum hypothesis). For each master-bone-list bone with a skeletonBoneIndex (0x7FFFFFFF = match by name):
   - Start from P = rest_pos, Acc = R = rest_rot (w, x, y, z).
   - For each link **in stored order**, with v its node value (no clamp in the bone pass; |v| < FLT_EPSILON is skipped):
     - P += v · dPos.
     - Flip R to the pose's hemisphere when |R + Q|² < |R − Q|² (Q = the link's rot); the flip carries over to later links.
     - S = slerp(R, Q, v) if dot(R, Q) ≤ 0.55, else the plain lerp R·(1 − v) + Q·v.
     - Acc = Acc ⊗ (M ⊗ S), where M = the stored `inv_rest_rot`.
   - Normalise Acc once at the end. Scale is not used.
   - **Application is additive** (FXBM_Additive everywhere). Convert FaceFX → UE3 as quat (x, −y, z, w) and vector (x, −y, z); then
     rot = (Q·Qref⁻¹)·animRot and trans += P − Pref on the animated local pose. The earlier "replace" in this spec was wrong.
   - The node clamp to [min, max] in step 2 is the face graph's own clamp (PROVISIONAL: RE did not trace the node evaluation).
   - On DX_OPRIME_LK002649 the product rule and the old nlerp sum differ by at most 0.47° (head) / 0.34° (jaw) per frame, so the blend
     rule does not explain the low jaw-voice correlation on Trypticon. That stays open, as a lip-sync timing or graph question.

**Expected output, one test frame:**
- Optimus `DX_OPRIME_LK002649` (`RB_Optimus_FaceFX.fxa`; start −0.222 s, end 2.869 s; voice wave 1.96 s) at t = 1.0 s. On this line
  the spec blend gives jaw-angle vs voice-envelope correlation 0.53 (linear) / 0.52 (Hermite), jaw up to 6.6° / 7.6°.
- `work/fxa/fxa_proof.py Optimus DX_OPRIME_LK002649` writes the 30 Hz CSV of all 14 bones, linear and Hermite.
  - Reference files: `work/fxa/proof_DX_OPRIME_LK002649_linear.csv` / `_hermite.csv`, regenerated 2026-10-17 with the product rule.
  - Values are FaceFX space, before any additive application or axis conversion: P absolute (rest + Σ v·dPos) and the absolute
    rotation Acc (w, x, y, z). Compare quaternions up to sign (q ≡ −q).
  - The rows are at t = start + k/30, so the "t = 1.0" test row is t = 1.0118.
  - The old nlerp-sum files are kept as `_linear_nlerp.csv` / `_hermite_nlerp.csv`. Those hold delta rotations and delta positions.
  - Gameplay's hook must reproduce the linear row within 1e-4 (positions) / 1e-3 (quaternion components).
- Pass also by eye: the jaw opens on loud syllables (the timing proof above), and the face is neutral during the lead-in and after
  `end`.

**Not needed for the hook:** the phoneme map (generation only), the class / name hash tables (parser internals).

## Rest pose and binding (for Gameplay's hook)

- **Rest-pose files:**
  - `work/fxa/facefx_rest_pose.csv`: the rest pose of every face bone in all 22 actors (346 rows: position, quaternion as stored
    w-first, scale, skeleton bone index).
  - `work/fxa/optimus_face_bone_binding.csv`: the Optimus binding. All 14 bones exist in
    `ExtractedAssets/VerticalSlice/Characters/Optimus/robot.glb` under the same names (glb nodes 7–20), with the .glb bind
    locals beside the FaceFX rest.
- **Mapping from the data (PROVISIONAL, for Gameplay to confirm on the full skeleton):**
  - Units: FaceFX is UE centimetres; the .glb is metres (÷100).
  - The 13 face bones parented to `C_Head01_Face_XF2` match **glb_t = (x, z, −y) / 100** to rounding (eyelids, cheeks, lip corners,
    lips, jaw).
  - Their rest rotation (−1, 0, 0, 0) is identity, i.e. glb (0, 0, 0, 1): FaceFX stores w first, and q and −q are the same rotation.
  - The head bone itself (parented to the neck) matches the glb rotation as (x, z, y, w) up to the sign of q. Its translation's y
    flips sign (a different parent frame), so settle that one bone on the full skeleton.

## Next

1. The visual proof above (a CSV + plot tool in work/fxa).
2. The cinematic slope scale; the phonemeId table.
3. Interpolation: no slopes are stored except the ZetaPrime case. Compare FaceFX 1.7 Hermite with derived slopes against linear on
   curve shapes; a visual proof on one line (DX_TRPTCN_LK004350).
4. Bone-pose application: rest pose plus the weighted sum of the node deltas from the master bone list links.
