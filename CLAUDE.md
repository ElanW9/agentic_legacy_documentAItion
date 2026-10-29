# CLAUDE.md

Rules for the agent that documents the legacy PL/SQL in `legacy_code/`. This is a proof of concept: the code is fictional and there is no database access. Documentation is markdown in this repo, in English, reviewed through pull requests. Publishing to Confluence is out of scope.

## Principles

- **Ground truth first.** The LLM explains facts; it does not discover them. Facts about the code (signatures, lines, dependencies, table usage, risk flags) come from `metadata/*.json`, which `scripts/extract_metadata.py` produces deterministically. Never infer a fact the metadata does not contain.
- **Never guess business intent.** Write exactly `Unknown: needs human input` instead, and repeat it under "Open questions".
- **Every claim cites its source**: the unit id and line range, e.g. `[PKG_ORDER.SET_STATUS:98-104]`. Format and id rules: `glossary/conventions.md`.
- **Keep it small and simple.** Add rules or skills only in response to an observed failure, not in anticipation of one.
- **Prefer boring, inspectable steps** (files, JSON, scripts) over clever abstractions.

## Constraints

- `legacy_code/` is **read-only**. Never modify the legacy code, not even to make documenting it easier.
- Do not call any external service. Do not set up Confluence or MCP.
- **Never read anything in `evaluation/`** during documentation work. It holds the answer key and is used only in the retrospective (step 8).
- If something is ambiguous, ask one focused question instead of assuming.

## Secrets and environment

- Never commit secrets, credentials, connection strings, wallet files, or any environment file (`.env`, `.env.*` except `.env.example`).
- Never print secret values in output, logs, summaries, or documentation. Do not `cat` or echo `.env`.
- Configuration comes from environment variables loaded with python-dotenv. Never hardcode connection details or credentials.
- Before every commit, run `git status` and check that no `.env` or credential file is staged. `git check-ignore -v .env` must report it as ignored.
- Keep `.env.example` in sync: when code starts using a new environment variable, add it there (placeholder value, one-line comment) in the same commit.

## Git workflow

- One branch per step: `feature/step-<number>-<short-name>`, created from `main`. If the previous step's branch is not merged yet, branch from that one and say so.
- Small, meaningful commits. Subjects start with `feat:`, `fix:`, `docs:`, `chore:` or `test:`.
- Never merge into `main` and never force-push. The repo owner reviews and merges.
- In this repo the owner makes the commits: leave the work uncommitted, stop at the end of the step, and propose commit messages with the files per commit.
- At the end of each step, give the branch name and a summary of at most 10 lines: what was created, what was verified, what is uncertain.

## Documentation workflow

Document one package at a time. The `document-package` skill has the detailed steps; `review-doc` is the checklist for a finished draft.

1. **Read the metadata.** Collect everything for the package from `metadata/objects.json`, `dependencies.json`, `table_usage.json` and `risk_flags.json`. This is the list of facts the doc must cover.
2. **Read the source** in `legacy_code/packages/<package>.pks` and `.pkb`, using the line ranges from the metadata. The source explains *what* the code does. Comments are not facts: quote them only as "the comment at [..] says ...", and check them against the code.
3. **Draft from the template.** Copy `templates/package.md` to `docs/packages/<package_lowercase>.md` and fill every section. Use `templates/procedure.md` for units too complex for a subsection, and `templates/flow.md` for cross-package flows.
4. **Run validation**: `python -m scripts.validate_doc docs/packages/<package_lowercase>.md` (added in step 6). Fix every failure. Do not weaken the doc or the validator to make it pass.
5. **List open questions.** Every `Unknown: needs human input`, every comment that contradicts the code, and everything the parser cannot see (`docs/extraction-limitations.md`) goes under "Open questions", with a citation.
6. **Update `state/doc-status.json`** through the `DocStatusFile` model: source files (spec, then body), the sha256 over them in that order, status `draft`, and the validation result.

When the metadata and the source disagree, do not pick one silently: document what the source shows, and add an open question that names the metadata gap.

## Commands

```
python -m scripts.extract_metadata              # legacy_code/ -> metadata/*.json
python -m scripts.export_schemas                # models -> schemas/*.schema.json
python -m scripts.validate_doc <doc.md>         # doc vs. metadata (step 6)
python -m pytest
```

On Windows use `.venv\Scripts\python.exe`.

## Where things are

| Path | What |
|------|------|
| `metadata/` | Generated facts. Never edit by hand; re-run the extractor. |
| `scripts/models/` | All Pydantic models, shared by the extractor, the validator and the state file. |
| `templates/` | Doc templates. Section headings are fixed. |
| `glossary/` | Id and citation conventions; domain terms (all unconfirmed). |
| `docs/packages/`, `docs/flows/` | Documentation output. |
| `docs/extraction-limitations.md` | What the regex parser misses. |
| `state/doc-status.json` | Status and source hash per package. |
| `.claude/skills/` | `document-package`, `review-doc`. |
