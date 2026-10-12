"""Eye review of the HD full pass (hd_full_push.py sheets). Generator data, never hand-edit the pack.

EYE: png -> the highest level the eye accepted ('gen4x_mid_nrm', 'gen4x_mid', 'gen4x') or None (keep the original).
     Textures not listed may use the top level (gen4x_d). A TEXSET pair takes the lower cap of its two halves.
REVIEWED: batches whose every sheet was looked at; only these enter pack/hd_index.json.
"""
A, B, C = 'gen4x', 'gen4x_mid', 'gen4x_mid_nrm'
EYE = {
    'content/ENV_AllShader_p/Textures/Metal_01_TiledNORM.png': None,   # pilot 2026-10-11: diagonal grain -> crumpled foil

    # ---- batch 0 (2026-10-12; ladder crops original | A | B | C | D for every suspect) ----
    # the mid-band boost (B and up) crushes blacks / blows whites on busy high-contrast colour: A is faithful
    'content/CINE_D3B_LevelIntro_p/MegatronShip/PROP_MegatronShip1_TEXSET/PROP_MegatronShip1_TEXSET_Color_NormX.png': A,
    'content/CINE_D3B_LevelIntro_p/MegatronShip/PROP_MegatronShip2_TEXSET/PROP_MegatronShip2_TEXSET_Color_NormX.png': A,
    'content/DES_COR_DropShipGenerator_p/DropshipGenerator_TEXSET/DropshipGenerator_TEXSET_Color_NormX.png': A,
    'content/DES_COR_GlassFloor_p/DES_COR_CorruptFloorGlass_CLR.png': A,
    'content/DES_IAC_Omega_Cover_p/Texture/innerCyberParts_CLR.png': A,
    'content/DES_IAC_Omega_Cover_p/Texture/innerCyberParts_CLR_TEXSET/innerCyberParts_CLR_TEXSET_Color_NormX.png': A,
    'content/DES_NEU_Barricade_p/Texture/innerCyberParts_CLR.png': A,
    'content/DES_NEU_Barricade_p/Texture/innerCyberParts_CLR_TEXSET/innerCyberParts_CLR_TEXSET_Color_NormX.png': A,
    'content/DES_KON_FuelCanisters_p/Textures/FuelCanister_CLR.png': A,
    'content/DES_ORB_Asteroids_p/Textures/SpaceDebris_Large_CLR_TEXSET/SpaceDebris_Large_CLR_TEXSET_Color_NormX.png': A,
    # D blows out whites (stripes) / bleaches a saturated yellow; C holds
    'content/DES_NEU_Valves_p/TPRO_NEU_RocketBarricade_TEXSET/TPRO_NEU_RocketBarricade_TEXSET_Color_NormX.png': C,
    'content/DES_NEU_EBarrel_p/ENV_ebarrel_CLR_Dup.png': C,
    # model turns soft stone into polygon cells; D exaggerates them, C still reads as stone
    'content/DES_ORB_D1_Vent_p/Texture/DES_ORB_Vent_CLR.png': C,
    'content/DES_ORB_D1_Vent_p/Texture/DES_ORB_Vent_CLR_TEXSET/DES_ORB_Vent_CLR_TEXSET_Color_NormX.png': C,
    'content/DES_ORB_MineBall_p/PROP_NEU_MineBall_TEXSET/PROP_NEU_MineBall_TEXSET_Color_NormX.png': C,
    # glow / emissive: even A loses the soft falloff (speckled fringe, hard cracks)
    'content/DES_NEU_EBarrel_p/ENV_ebarrel_GLOW_Dup.png': None,
    'content/DES_COR_GlassFloor_p/DES_COR_CorruptFloorGlass_EMIS.png': None,
    # mask model blurs the 1 px circuit lines away
    'content/DES_IAC_Omega_Cover_p/Texture/innerCyberParts_MASKS.png': None,
    # smooth FX / shader textures: the model invents polygon cells / octagons in gradients
    'content/ENV_AllShader_p/CubeMaps/ENV_Metals_CUBE.png': None,
    'content/ENV_AllShader_p/CubeMaps/GlassCubeMap_Top_r02.png': None,
    'content/ENV_AllShader_p/Energon_River/ElectricArcs_512.png': None,
    'content/ENV_AllShader_p/Rain/halfToneRipples_Alphas.png': None,
    'content/ENV_AllShader_p/Rain/halfToneRipples_r1.png': None,
    'content/ENV_AllShader_p/Textures/Clouds_CLR.png': None,
    'content/ENV_AllShader_p/Textures/DiffClouds_CLR.png': None,
    'content/ENV_AllShader_p/Textures/DiffClouds_CLRElectricArcsElectricArcs.png': None,
    # flat default normal (TEXSET alpha) gains a stripe moire
    'content/ENV_AllShader_p/Textures/DefaultTextureSetC/DefaultTextureSetC_Color_NormX.png': None,
    'content/ENV_AllShader_p/Textures/DefaultTextureSetC/DefaultTextureSetC_Masks_NormY.png': None,
    # flat designer colour: a dark edge appears, nothing gained
    'content/Designer_Materials_p/LightBlue.png': None,
}
REVIEWED = {0}   # batch 0: 2026-10-12
