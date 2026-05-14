# E2E Test Fixtures

## sample.md

A minimal 3-paragraph document about variables in programming.

**Why it is small:** E2E tests run the real TTS pipeline, which takes 2–4 seconds
per audio segment. A short document keeps the full suite under 3 minutes. The
fixture is intentionally not representative of real user content — it exists only
to exercise the pipeline end-to-end.

**Why this topic:** "What is a variable?" produces a single teaching unit with a
short dialogue. The LLM is mocked (see conftest.py), so the content is fixed and
the test suite is reproducible without a real API key.

**Do not add more content to this file.** If you need to test a different scenario,
add a new fixture file and a separate E2E test module.
