Fixed Dify frontend build experiment; not an official Dify release.

This public repository contains only upstream public source, its license, a four-line finish_reason output declaration patch, and CI files. No Dify workflow definitions, resumes, knowledge-base content, credentials, or local service configuration are included.

Manual workflow_dispatch only; no automatic retry. Both official Next and Vinext builds must complete. A successful candidate is saved to the repository owner's GHCR namespace, kept private after explicit visibility verification. This does not deploy anything or claim runtime, typecheck, cost, or 14-node workflow acceptance.

Resource gates: at least 13 GiB available RAM and 11 GiB free disk before building; builder capped at 12 GiB/2 CPUs, one parallel step; stop at 2 GiB disk or 60 minutes. These are conservative proposed gates, not measured minimum requirements.

No Actions cache or uploaded artifacts. Registry availability/permissions may still prevent saving a successfully built image. See UPSTREAM.md and LICENSE.

The source archive was losslessly repacked as tar.xz to fit the browser upload limit. All 8902 paths and file contents were compared byte-for-byte with the original patched ZIP; no source file changed.
Original patched ZIP SHA256: a9a75bd08eeff8de9f4ba54e5c5aed85a5aa458ef6f80f3292aa7ab66d38fef6
Uploaded tar.xz SHA256: 08baec49734f7da83456f64f88c95460385c908e32d9e43d9cbcc8ed33b13447

B03 run 39893589172 failed during Next production compilation with an explicit memory allocation error. No candidate image was generated. B04 then completed both official targets and image generation successfully under a 12 GiB / 2 CPU builder. These are observed successful limits for this run, not measured minimum requirements.

B04 result (2026-10-23): https://github.com/sansyuan97-code/dify-finish-reason-build/actions/runs/39895083851
Build-input commit: d3295e5b0daa1396ee65b9e9e90e6d530d715129
Candidate: ghcr.io/sansyuan97-code/dify-finish-reason-candidate:gh-39895083851
Registry digest: sha256:3ebe4e18ef2894409ecb1b3b82523c463dc7a47afa2aba50e7d22b489eb483f7
The package was initially observed as Public with inherited repository access. Its visibility was explicitly changed to Private and verified on 2026-10-23. No JD, resume, knowledge-base records, user credentials or local configuration were included in the image.
The official build skipped project type validation. Candidate runtime verification, local retrieval, rollback rehearsal, deployment and real 14-node acceptance remain incomplete. No further build was triggered by this documentation update.
