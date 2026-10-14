"""Eye review of the level E full pass (hd_e_full.py sheets). REJECT: png -> reason (keeps D); REVIEWED_MAPS: maps whose every
E unit was looked at; only these enter push_e_full/pack/hd_index.json (Experimental: E is reviewed 100 %, never sampled).
Rule (2026-10-14, user: "the same texture ... more detail"): E may add wear, cracks, grime, bevels, bolts / rivets inside existing
parts; it is rejected when it invents objects, emblems, labels, faces or text, changes a design element, alters a logo / text, or
turns noise into blobs / cells."""
REJECT = {
    # ---- MP_KON_Molten (2026-10-14; 88 units, all looked at) ----
    'content/DES_IAC_Omega_Cover_p/Texture/innerCyberParts_CLR_TEXSET/innerCyberParts_CLR_TEXSET_Color_NormX.png': 'invents a blue label on a flat panel',
    'content/ENV_CORE_Floors_p/Materials/ENV_CORE_FloorTileBSP_CLR_TEXSET/ENV_CORE_FloorTileBSP_CLR_TEXSET_Color_NormX.png': 'invents glyph markings on a plate',
    'content/ENV_CORE_Platform_p/Textures/ENV_CORE_CanyonGate_B_CLR_TEXSET/ENV_CORE_CanyonGate_B_CLR_TEXSET_Color_NormX.png': 'invents a capsule object in the slot',
    'content/ENV_CORE_SupportColumns_p/Textures/COR_TNBundleWires_TEXSET/COR_TNBundleWires_TEXSET_Color_NormX.png': 'invents a face in the door recess',
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_CORE_TunnelPipeA_CLR_TEXSET/ENV_CORE_TunnelPipeA_CLR_TEXSET_Color_NormX.png': 'invents a round emblem on a flat area',
    'content/ENV_CORE_SupportColumns_p/Textures/ENV_COR_GS_SupportAB_CLR_TEXSET/ENV_COR_GS_SupportAB_CLR_TEXSET_Color_NormX.png': 'invents a padlock-like glyph',
    'content/ENV_CORE_Wall_p/Textures/ENV_CORE_InroomWall_B_CLR_TEXSET/ENV_CORE_InroomWall_B_CLR_TEXSET_Color_NormX.png': 'turns an edge strip into a pipe',
    'content/ENV_CORE_Wall_p/Textures/ENV_Core_CliffWall_B/ENV_Core_CliffWall_B_Color_NormX.png': 'rock turns into blobby organic cells',
    'content/ENV_IAC_SentinelArena_p/Texture/coreRing_CLR_TEXSET/coreRing_CLR_TEXSET_Color_NormX.png': 'invents a plaque on the ring',
    'content/ENV_KON_Architecture_p/Texture/BridgeSupport__01_CLR_TEXSET/BridgeSupport__01_CLR_TEXSET_Color_NormX.png': 'Decepticon logo smeared / redrawn (logos stay exact)',
    'content/ENV_KON_Architecture_p/Texture/Column_01_CLR_TEXSET/Column_01_CLR_TEXSET_Color_NormX.png': 'invents round emblems on the dark base',
    'content/ENV_KON_Deco_p/Texture/BackgroundIsland_03_CLR_TEXSET/BackgroundIsland_03_CLR_TEXSET_Color_NormX.png': 'noisy island turns into blobby craters',
    'content/ENV_KON_Molten_p/Material/ENV_KON_MoltenBurn_TEXSET/ENV_KON_Molten_TEXSET_Color_NormX.png': 'invents gear machinery and glyph text in the molten burn',
    'content/ENV_KON_Molten_p/Material/ENV_KON_Molten_TEXSET/ENV_KON_Molten_TEXSET_Color_NormX.png': 'invents circuit / panel lines on molten rock',
    'content/ENV_KON_PrisonBarge_p/Textures/CeilingDeco_01_CLR_TEXSET/CeilingDeco_01_CLR_TEXSET_Color_NormX.png': 'High Moon logo letters warped (text stays exact)',
    'content/ENV_NEU_Variation_p/ENV_cboard_CLR.png': 'invents a disc object on the circuit board',
    'content/ENV_NEU_Variation_p/ENV_groundblobs_CLR.png': 'ground blobs turn into bubbles',
    # ---- MP_IAC_Streets (2026-10-14; 44 units, all looked at) ----
    'content/ENV_ArchiveInterior_p/ENV_ArchiveWall_CLR_TEXSET/ENV_ArchiveWall_CLR_TEXSET_Color_NormX.png': 'invents a glyph plate in the top band',
    'content/ENV_IAC_BLDS_2_p/Textures/HalfArchInteriors_CLR_TEXSET/EditorTextureSet_Color_NormX.png': 'redraws a dark outline into a curved pipe / trim',
    'content/ENV_IAC_BLDS_2_p/Textures/pillar1_clr_TEXSET/pillar1_clr_TEXSET_Color_NormX.png': 'invents an embossed seal in a flat area',
    'content/ENV_IAC_Deco_1_p/Texture/ChainLinkFence_TEXSET/ChainLinkFence_TEXSET_Color_NormX.png': 'blurs the hub: ring and bolt detail lost',
    'content/ENV_IAC_Ground_p/Texture/ENV_Crater_CLR.png': 'redraws the panel shapes into a new chevron outline',
    'content/ENV_IAC_Train_p/Texture/Train_CLR_TEXSET/Train_CLR_TEXSET_Color_NormX.png': 'adds new panel blocks over the stripes',
    'content/ENV_IAC_TubeRoads_p/Materials/Tubes_Road_CLR_TEXSET/Tubes_Road_CLR_TEXSET_Color_NormX.png': 'invents lettering and a logo on the road tube',
    'content/ENV_NEU_Structures_p/Mid1/ENV_Mid1_Base1_768x2048x2048_CLR_TEXSET/ENV_Mid1_Base1_768x2048x2048_CLR_TEXSET_Color_NormX.png': 'invents markings and a hatch over the arched panels',
}
REVIEWED_MAPS = {'MP_KON_Molten', 'MP_IAC_Streets'}
