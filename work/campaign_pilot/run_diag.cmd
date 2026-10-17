@echo off
rem m05 (CSR grid) + structure audit (WFC_AUDIT_CELL=2 m) alone on every campaign chapter, then map_complete / render_index
rem (Integration 2026-10-16). Same rules: CPU, 10 GB cap, hold-aware, outputs under work\campaign_pilot (WFC_VS_ROOT).
setlocal
cd /d "F:\Transformers Rebuild\AssetTools"
set "WFC_PKG_CACHE=10"
set "WFC_AUDIT_CELL=2"
set "WFC_M05_TILE=256"
echo diag start %time% >> work\campaign_pilot\diag.log
for %%M in (A4_ORB A5_TRY D1_ORB D2_COR D3A_IAC D3B_IAC D5_OME) do (
  call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" %%M 10 m05_bsp_default_faces map_structure_audit map_complete map_render_index
  type work\campaign_pilot\%%M_stages.log | findstr " rc " >> work\campaign_pilot\diag.log
  echo diag %%M done %time% >> work\campaign_pilot\diag.log
)
echo diag chain done %time% >> work\campaign_pilot\diag.log
rem retries of m05 (tiled) where the untiled run hit the cap
for %%M in (A1_IAC A3_COR) do (
  call "F:\Transformers Rebuild\AssetTools\work\campaign_pilotun_stages.cmd" %%M 10 m05_bsp_default_faces map_complete map_render_index
  type work\campaign_pilot\%%M_stages.log | findstr " rc " >> work\campaign_pilot\diag.log
  echo diag retry %%M done >> work\campaign_pilot\diag.log
)
echo diag retries done >> work\campaign_pilot\diag.log
