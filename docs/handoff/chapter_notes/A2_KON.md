- **Collision gap at StaticMeshCollectionActor_10261 (structure audit, 2026-10-17): explained, not a hole.** Its 5 components
  (WallDeco_01, 4 × BridgeArchTop) are meshes with no simple collision and no per-poly flag, so they have no pawn collision in UE3
  either. The audit's former ATTENTION came from the 125 mesh-less Courtyard components (no StaticMesh, so nothing to collide with),
  which are now classified as explained; the audit PASSes.
- The audit's walk-graph checks (playable space, collision vs visible) seed from MP player-start classes, which the campaign doesn't
  use (TnCampaignPlayerStart), so they are empty for every chapter. Tied to the player-start relaxation (backlog 5).
