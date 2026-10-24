# DLC second-source environment (2026-10-23): source before any AssetTools tool that should see the DLC packs. Every override is opt-in;
# without this file the tools read the Game Dump / ExtractedAssets / manifests exactly as before.
export WFC_COOKED_DIR='F:\Transformers Rebuild\AssetTools\work\dlc\cooked'           # DLC packages (base packages: ue3pkg falls back)
export WFC_EXTRACT_OUT='F:\Transformers Rebuild\AssetTools\out\dlc_content\content'  # umodel content of the DLC packages
export WFC_AUTHORED_EXTRA_DB='F:/Transformers Rebuild/AssetTools/manifests/dlc/authored.db'   # attached behind the base authored.db
export WFC_EXTRA_ASSETS_JSON='F:\Transformers Rebuild\AssetTools\manifests\dlc\assets.json'    # overlays the base assets.json
export WFC_VS_ROOT='F:\Transformers Rebuild\AssetTools\work\dlc_maps\VerticalSlice'  # map outputs (ExtractedAssets untouched)
export PYTHONDONTWRITEBYTECODE=1
