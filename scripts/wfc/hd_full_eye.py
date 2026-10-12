"""Eye review of the HD full pass (hd_full_push.py sheets). Generator data, never hand-edit the pack.

EYE: png -> the highest level the eye accepted ('gen4x_mid_nrm', 'gen4x_mid', 'gen4x') or None (keep the original).
     Textures not listed may use the top level (gen4x_d).
REVIEWED: batches whose every sheet was looked at; only these enter pack/hd_index.json.
"""
EYE = {
    'content/ENV_AllShader_p/Textures/Metal_01_TiledNORM.png': None,   # pilot 2026-10-11: diagonal grain -> crumpled foil
}
REVIEWED = set()
