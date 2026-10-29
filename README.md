# Agentic legacy documentation (proof of concept)

An AI agent documents undocumented legacy Oracle PL/SQL. All code in `legacy_code/` is fictional: an order-to-invoice system with planted traps that AI documentation tends to get wrong.

## How it works

1. **Extract facts.** `scripts/extract_metadata.py` parses `legacy_code/` with regexes (there is no database access) and writes `metadata/*.json`: objects and signatures, dependencies, table usage, and risk flags. Every file is validated through the Pydantic models in `scripts/models/`.
2. **Draft docs.** The agent fills `templates/` for one package at a time, reading the metadata and the source. Every claim cites a unit and line range. Anything it can't establish from the code becomes "Unknown: needs human input".
3. **Validate.** `scripts/validate_doc.py` checks each doc against the metadata: referenced units, parameters and tables must exist, claims need citations, and required sections must be present.
4. **Review.** Docs are reviewed through pull requests. `state/doc-status.json` tracks the status of each package and the hash of its source.
5. **Publish** (later, out of scope). Approved markdown goes to Confluence.

## Repository layout

| Path | Contents |
|------|----------|
| `legacy_code/` | Fictional PL/SQL source. Read-only. |
| `evaluation/` | Answer key. Only used in the retrospective, never during documentation. |
| `metadata/` | Generated JSON facts. |
| `schemas/` | JSON Schemas exported from the Pydantic models. |
| `scripts/`, `scripts/models/` | Extraction, validation, and shared models. |
| `tests/` | pytest tests. |
| `templates/` | Doc templates for packages, procedures, and flows. |
| `glossary/` | Domain terms and naming conventions. |
| `docs/packages/`, `docs/flows/` | Generated documentation. |
| `docs/repo-plan.md` | Inspection findings and design. |
| `state/` | Doc status tracking. |
| `.claude/skills/` | Agent skills. |
| `CLAUDE.md` | Agent rules. |

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration (.env)

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

Then fill in the values in `.env`. Every variable is described in `.env.example`.

- `.env` is git-ignored and must never be committed. You can confirm this with `git check-ignore -v .env`.
- The database variables are for possible future use only. This PoC has no database access.
- When code starts using a new variable, add it to `.env.example` in the same commit.

## Git workflow

- Each step is built on its own branch, `feature/step-<number>-<short-name>`, created from `main`. If the previous step hasn't been merged yet, the branch is created from the previous step's branch instead.
- Make small commits with clear messages.
- Merges into `main` happen only through a reviewed pull request. Never force-push.
- Before every commit, check `git status` to make sure no `.env` or credential file is staged.

## Steps

| Step | Branch | Deliverable |
|------|--------|-------------|
| 0 | `feature/step-0-fake-codebase` | Fictional legacy codebase and answer key |
| 1 | `feature/step-1-inspect-and-plan` | `docs/repo-plan.md` |
| 2 | `feature/step-2-scaffold` | This scaffold |
| 3 | `feature/step-3-metadata-extraction` | Models, extractor, `metadata/`, `schemas/` |
| 3b | `feature/step-3b-spot-check` | Manual verification, fixes, and tests |
| 4 | `feature/step-4-templates-and-glossary` | Templates and glossary stubs |
| 5 | `feature/step-5-agent-rules-and-skills` | `CLAUDE.md` and skills |
| 6 | `feature/step-6-validation` | `validate_doc.py` and tests |
| 7 | `feature/step-7-pilot` | Documentation for the 4 packages |
| 8 | `feature/step-8-retrospective` | `docs/pilot-report.md` |
