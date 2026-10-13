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

    # ---- batch 1 (2026-10-12; ladder crops for every suspect) ----
    # busy colour: B and up crush blacks / blow white edges and bands; A is faithful
    'content/ENV_AllShader_p/Textures/Ice_crystals_CLR.png': A,
    'content/ENV_AllShader_p/Textures/stains_01_CLR.png': A,
    'content/ENV_AllShader_p_OLD/Templates/Metal_Clr.png': A,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_CeilingDecoA_CLR_TEXSET/ENV_CORE_CeilingDecoA_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_InteriorDoor_CLR_TEXSET/ORB_D1_InteriorDoor_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_SupportDecoB_CLR.png': A,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_SupportDecoB_CLR_TEXSET/ENV_CORE_SupportDecoB_CLR_TEXSET_Color_NormX.png': A,
    # D blows whites / exaggerates grain; C holds
    'content/ENV_ArchiveInterior_p/Courtyard/SimpleFloor_TexSet/SimpleFloor_TexSet_Color_NormX.png': C,
    'content/ENV_ArchiveInterior_p/FaceDeco/FaceDeco1_CLR_TEXSET/FaceDeco1_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Deco_p/Textures/CanyonDeco_A_NoEmis_TEXSET/CanyonDeco_A_NoEmis_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_CanyonDeco_A_CLR.png': C,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_CanyonDeco_A_CLR_TEXSET/ENV_CORE_CanyonDeco_A_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_WallDecoA_CLR.png': C,
    'content/ENV_CORE_Deco_p/Textures/ENV_CORE_WallDecoA_CLR_TEXSET/ENV_CORE_WallDecoA_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_DropShip_p/Doors/ENV_CORE_DSFBDoors_TEXSET/ENV_CORE_DSFBDoors_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Floors_p/Materials/CenterChamberFloorCenterDisc_CLR.png': C,
    # tiling noise turned into polygon cells at every level
    'content/ENV_AllShader_p/Textures/Rust_C_CLR.png': None,
    # FX / shader textures (arcs, fractal, 4 px pixel pattern): the model invents structure
    'content/ENV_AllShader_p/Textures/ElectricArcsElectricArcsElectricArcsElectricArcs.png': None,
    'content/ENV_AllShader_p/Textures/ElectricArcs_512.png': None,
    'content/ENV_AllShader_p/Textures/Pixel_4_CLR.png': None,
    'content/ENV_AllShader_p/Textures/fractalMaps.png': None,

    # ---- batch 2 (2026-10-12; ladder crops for every suspect) ----
    # busy / high-contrast colour (rails, floor tiles, Guts floors, Guardian guns): A is faithful
    'content/ENV_CORE_Floors_p/Materials/CenterChamberFloorRails_CLR.png': A,
    'content/ENV_CORE_Floors_p/Materials/CenterChamberFloorRails_CLR_TEXSET/CenterChamberFloorRails_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/CenterChamberMainFloorRails_CLR.png': A,
    'content/ENV_CORE_Floors_p/Materials/CenterChamberMainFloorRails_CLR_TEXSET/CenterChamberMainFloorRails_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_FloorTileBSP_CLR.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_FloorTileBSP_CLR_TEXSET/ENV_CORE_FloorTileBSP_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_MPFloor_CLR_TEXSET/ENV_CORE_MPFloor_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_COR_GutsFloorA_CLR.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_COR_GutsFloorC_CLR.png': A,
    'content/ENV_CORE_Floors_p/Materials/ENV_COR_GutsFloorC_CLR_TEXSET/ENV_COR_GutsFloorC_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/Sidewalk_CLR_TEXSET/Sidewalk_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Mechparts_p/Materials/ENV_COR_Tracks_CLR_TEXSET/EditorTextureSet_Color_NormX.png': A,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianGuns_CLR.png': A,
    # soft stone: B and up shatter it into bright shards; A holds
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_Tunnel1Slope_CLR_TEXSET/ENV_CORE_Tunnel1Slope_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_Floors_p/Materials/OmegaBridgeSupport_CLR_TEXSET/OmegaBridgeSupport_CLR_TEXSET_Color_NormX.png': A,
    # D blows white rims / rings or exaggerates cells; C holds
    'content/ENV_CORE_Floors_p/Materials/Core_MPFloorMP_CLR.png': C,
    'content/ENV_CORE_Floors_p/Materials/Core_MPFloor_CLR.png': C,
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_MPYFloor_CLR_TEXSET/ENV_CORE_MPYFloor_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_Tunnel1Slope_CLR.png': C,
    'content/ENV_CORE_Floors_p/Materials/ENV_COR_GutsFloorB_CLR.png': C,
    'content/ENV_CORE_Floors_p/Materials/ENV_COR_GutsFloorB_CLR_TEXSET/ENV_COR_GutsFloorB_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Floors_p/Materials/OmegaBridgeSupport_CLR.png': C,
    'content/ENV_CORE_Floors_p/Materials/OmegaBridge_CLR_TEXSET/OmegaBridge_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Platform_p/Textures/ENV_CORE_CanyonGate_A_CLR_TEXSET/ENV_CORE_CanyonGate_A_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Platform_p/Textures/ENV_CORE_CoreIntCenter_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianBase_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianBase_CLR_TEXSET/COR_GuardianBase_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianCenterDisc_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianCenterDisc_CLR_TEXSET/COR_GuardianCenterDisc_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianCore_CLR_TEXSET/COR_GuardianCore_CLR_TEXSET_Color_NormX.png': C,
    # normal: C and D add a grid moire on the flat faces; B is clean
    'content/ENV_CORE_Platform_p/Textures/ENV_CORE_CanyonGate_B_NORM.png': B,
    # normal from a dithered checker: every level turns the dither into woven ridges
    'content/ENV_CORE_Platform_p/Textures/ENV_CORE_CoreIntCenter_NORM.png': None,
    # glow / emissive: the green turns pale
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianCore_EMIS.png': None,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianHeadA_EMIS.png': None,

    # ---- batch 3 (2026-10-13; ladder crops for every suspect) ----
    # busy / high-contrast colour: B and up blow white rims, bars and stripes or turn grit into glitter shards; A is faithful
    'content/ENV_CORE_SeedChamberBoss_p/Materials/HealthCrate_V2_CLR_TEXSET/HealthCrate_V2_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/PROP_NEU_Battery_CLRPROP_NEU_Battery_CLR.png': A,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/PROP_NEU_Battery_CLRPROP_NEU_Battery_CLR_TEXSET/PROP_NEU_Battery_CLRPROP_NEU_Battery_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SeedClawRoot_p/Materials/ENV_CORE_Root_CLR.png': A,
    'content/ENV_CORE_SeedClawRoot_p/Materials/ENV_CORE_Root_CLR_TEXSET/ENV_CORE_Root_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/COR_TNBundleWires_TEXSET/COR_TNBundleWires_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/COR_TNPipeSets_TEXSET/COR_TNPipeSets_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_LaserShield_A_CLR_TEXSET/ENV_CORE_LaserShield_A_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_MRColumnA_CLR_TEXSET/ENV_CORE_MRColumnA_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelFloorPipe_CLR.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelPipeA_CLR_TEXSET/ENV_CORE_TunnelPipeA_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelSupport_B_CLR_TEXSET/ENV_CORE_TunnelSupport_B_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_RoutingPipeAGuts_CLR_TEXSET/ENV_COR_RoutingPipeAGuts_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_RoutingSupportA_CLR_TEXSET/ENV_COR_RoutingSupportA_CLR_TEXSET_Color_NormX.png': A,
    'content/ENV_CORE_SupportColumns_p/Textures/TunnelBundlePipesA_CLR.png': A,
    # D blows white rims / rings or exaggerates cells; C holds (GutsFloorB copies capped as in batch 2)
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianHeadB_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianHeadB_CLR_TEXSET/COR_GuardianHeadB_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/COR_GuardianRails_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/ENV_CORE_ControlPannel_CLR.png': C,
    'content/ENV_CORE_SeedChamberBoss_p/Materials/ENV_CORE_ControlPannel_CLR_TEXSET/ENV_CORE_ControlPannel_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SeedClawRoot_p/Materials/ENV_CORE_RootArm_CLR.png': C,
    'content/ENV_CORE_SeedClawRoot_p/Materials/ENV_CORE_RootArm_CLR_TEXSET/ENV_CORE_RootArm_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_Shader_p/Materials/TPRO_IAC_LiftLock3_TEXSET/TPRO_IAC_LiftLock2_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/Core_CorruptedVineA_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/Core_CorruptedVineA_CLR_TEXSET/Core_CorruptedVineA_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/Core_GutPipeStraightLong_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/Core_GutPipeStraightLong_CLR_TEXSET/Core_GutPipeStraightLong_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_LaserShield_A_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_MRColumnA_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelFloorPipe_CLR_TEXSET/ENV_CORE_TunnelFloorPipe_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelLargePipeA_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelLargePipeA_CLR_TEXSET/ENV_CORE_TunnelLargePipeA_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelPipeA_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelSupport_B_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_GS_SupportAB_CLR_TEXSET/ENV_COR_GS_SupportAB_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_RoutingPipeA_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_RoutingPipeA_CLR_TEXSET/ENV_COR_RoutingPipeA_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_RoutingSupportA_CLR.png': C,
    'content/ENV_CORE_Surfacegun_p/Materials/ENV_COR_EBArm1_CLR.png': C,
    'content/ENV_CORE_Surfacegun_p/Materials/ENV_COR_EBArm1_CLR_TEXSET/ENV_COR_EBArm1_CLR_TEXSET_Color_NormX.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_GutsFloorB_CLRENV_COR_GutsFloorB_CLR.png': C,
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_GutsFloorB_CLRENV_COR_GutsFloorB_CLR_TEXSET/ENV_COR_GutsFloorB_CLRENV_COR_GutsFloorB_CLR_TEXSET_Color_NormX.png': C,
    # painterly rubble turns into polygon cells at every level
    'content/ENV_CORE_Wall_p/ENV_CORE_BSPWall_B_CLR.png': None,
}
REVIEWED = {0, 1, 2, 3}   # batches 0-2: 2026-10-12; 3: 2026-10-13
