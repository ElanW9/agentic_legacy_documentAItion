# CLAUDE.md

Placeholder. The full agent rules (principles, constraints, secrets, git workflow, documentation workflow) are written in step 5.

Until then:
- `legacy_code/` is read-only.
- Never read `evaluation/` unless the current step is the retrospective (step 8).
- Never commit `.env` or any credential file.
- Facts about the code come from `metadata/` (deterministic extraction), never from inference.
