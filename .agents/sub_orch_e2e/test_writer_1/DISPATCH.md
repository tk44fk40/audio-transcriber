## 2026-08-14T18:52:31Z

You are Test Writer 1 for the E2E Testing Track of audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/test_writer_1

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read these files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/explorer_3/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/explorer_1/analysis.md

Your exclusive write ownership:
1. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/TEST_INFRA.md`
2. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_models.py`
3. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_sanitizer.py`
4. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_normalizer.py`
5. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_postprocess.py`
6. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_timing.py`
7. `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/tests/test_e2e_exporters.py`

Tasks:
1. Write `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/TEST_INFRA.md` per Section 6 of explorer_3 analysis.
2. Implement comprehensive, opaque-box, requirement-driven tests covering Features 1-17 across Tiers 1-2 in the test files above.
3. Every test file MUST:
   - Stay within target <= 200 lines (hard max 300 lines per AGENTS.md).
   - Follow AAA (Arrange-Act-Assert) pattern.
   - Use Google style Japanese docstrings.
   - Have strict type annotations.
   - Run cleanly with `uv run ruff check .` and `uv run ruff format --check .`.
4. Output your progress and handoff report to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/test_writer_1/handoff.md`.
5. Send a completion message back.
