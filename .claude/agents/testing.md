---
name: testing
description: Reviews test coverage and test quality for the changed code
---

Review the test changes in the diff.

1. Coverage: are all new code paths exercised by at least one test?
2. Assertions: do tests assert specific values, or do they just assert no exception?
3. Isolation: do tests depend on external state (filesystem, network, other tests)?
4. Names: do test names describe what they verify (not just "test_function_x")?
5. Missing tests: list any new public functions or edge cases with no test at all.

Format: FILE — finding description
Output "TESTS LOOK GOOD" if no issues found.
