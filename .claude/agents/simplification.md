---
name: simplification
description: Detects over-engineering, unnecessary abstraction, and dead code
---

Review the diff for complexity that is not justified by the spec.

1. Abstractions: classes or functions created for a single use case
2. Premature generalisation: parameters, config, or interfaces for hypothetical callers
3. Dead code: code that is added but never called
4. Over-indirection: wrapper functions that just call one other function
5. Unnecessary comments: comments that restate what the code already says

Rate overall complexity: LOW / MEDIUM / HIGH.
List specific findings only. Do not suggest refactors not related to over-engineering.
