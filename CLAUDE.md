# AssetTools Claude lane

Project root: F:\Transformers Rebuild\AssetTools. Start a fresh conversation here; subsequently use claude.cmd --continue from this directory. Never resume a legacy conversation from F:\Transformers Rebuild for this lane.

- Write project files only under F:\Transformers Rebuild\AssetTools and F:\Transformers Rebuild\ExtractedAssets (the existing sibling output folder).
- Read F:\Transformers Rebuild\Game Dump in place, read-only. Never modify, rename, move, delete, or copy the dump wholesale.
- Read Rebuild documentation and other reference data in place as needed. Do not write to RE-Workspace, Ghidra projects, or any Rebuild lane.
- Do not duplicate ExtractedAssets or Game Dump, or create links that bypass these write boundaries. Resolve script input/output paths explicitly when running from this root.
- Do not delete or alter old Claude sessions. Do not launch, resume, stop, or coordinate other lanes or their background agents.
- Keep extraction jobs bounded; do not start overlapping full pipelines. Check for an existing extraction job before starting another.
