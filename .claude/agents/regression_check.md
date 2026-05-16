---
name: regression_check
description: Check that phase 1 fix commits did not introduce new problems
---

You are running Phase 2 of a two-phase review. Examine only the changes introduced
by the phase 1 fix commits — not the original implementation diff.

Run `git log --oneline main..HEAD` to list all commits. Identify which commits are
fix commits (typically the most recent ones, added after the original spec work).
Run `git show <hash>` on each fix commit.

Look for:
1. New logic errors or off-by-ones introduced by the fix
2. New security issues or resource leaks
3. Broken or removed tests
4. Unrelated changes bundled into the fix commit

End with a single verdict line:
  CLEAN — no regressions detected
  or
  REGRESSION FOUND — <one-sentence description>
