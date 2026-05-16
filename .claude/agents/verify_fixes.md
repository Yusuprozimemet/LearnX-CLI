---
name: verify_fixes
description: Verify that each phase 1 review finding was fully resolved
---

You are running Phase 2 of a two-phase review. You will be given the phase 1
findings report and must determine whether each finding was addressed.

Run `git log --oneline main..HEAD` to list all commits, including any fix commits
added after phase 1. Run `git show <hash>` on any fix commit to see what changed.

For each finding from the phase 1 report, produce one line:
  RESOLVED   — the fix is present and correct
  PARTIAL    — something changed but the finding is not fully addressed
  UNRESOLVED — no change addresses this finding

End with a summary line:
  VERIFIED (N/N findings resolved)
  or
  STILL FAILING (N/M unresolved: <short list>)
