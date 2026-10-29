---
name: document-package
description: Document one PL/SQL package from legacy_code/ end to end - collect metadata, read the source, draft docs/packages/<package>.md from the template, validate, and update state/doc-status.json. Use when asked to document a package.
---

# Document one package

Input: a package name, e.g. `PKG_ORDER`. Output: `docs/packages/<package_lowercase>.md` that passes validation, plus a `state/doc-status.json` entry. Follow CLAUDE.md. Never open `evaluation/`.

## 1. Collect the facts

From `metadata/`, take every record for the package. Unit ids start with `<PACKAGE>.`; the package itself is `<PACKAGE>`.
- `objects.json`: spec and body ranges, every subprogram (visibility, overload, params, signature, ranges), every variable.
- `dependencies.json`: edges where the package's units are `source` (calls out) or `target` (called by), and `package_cycles` containing the package.
- `table_usage.json`: accesses per unit, with `via`.
- `risk_flags.json`: every flag for the package or its units.

Then follow the `FIRES_TRIGGER` edges and read those triggers' own table usage and flags: their writes are side effects of this package.
Keep this list. Every item must end up in the doc (step 5 checks it).

## 2. Read the source

Read the `.pks` and `.pkb`, one unit at a time, using the metadata ranges. For each unit note what it does, with line numbers: branches, the values it returns, what it raises or swallows, and what it commits.
- A source comment is not a fact. Quote it as "the comment at [ID:line] says ..." and say whether the code agrees.
- If the source shows something the metadata lacks (a call, a table, a flag), document it from the source and add an open question naming the gap. Never edit `metadata/` by hand.

## 3. Draft

Copy `templates/package.md` to `docs/packages/<package_lowercase>.md`.
- Keep every `##` heading, in order. Empty section: `None found in metadata.`
- Copy names, signatures and line numbers from the metadata. Do not retype them from memory.
- Every sentence that states a fact ends with a citation `[ID:start-end]` (`glossary/conventions.md`).
- Describe behaviour, not intent. Purpose, the meaning of a code value or a hardcoded number, and why something exists are `Unknown: needs human input` unless the code itself states it.
- Say "no caller in legacy_code/", never "unused" or "dead".
- A unit with many branches, a COMMIT, or several tables gets its own `docs/packages/<package_lowercase>/<unit_lowercase>.md` from `templates/procedure.md`, linked from the package doc.
- Remove all template comments and `{{placeholders}}`.

## 4. Validate

`python -m scripts.validate_doc docs/packages/<package_lowercase>.md`. Fix the doc and re-run until it passes. If you think the validator is wrong, do not work around it: report it as a validator issue.

## 5. Coverage and open questions

Tick off the list from step 1: every public unit, private unit, variable, edge, table access and risk flag appears in the doc. Then run the `review-doc` checklist.
Under "Open questions", list every `Unknown`, every comment that contradicts the code, every metadata gap, and every limitation from `docs/extraction-limitations.md` that applies (for example, dynamic SQL table names, or callers outside `legacy_code/`).

## 6. Record status

Update `state/doc-status.json` through `scripts.models.DocStatusFile`:
- `source_files`: spec path, then body path.
- `source_hash`: sha256 over the raw bytes of those files, in that order.
- `status`: `draft`. Set `validation_passed` to the last validator result.

Report: doc path, validator result, number of open questions, and anything you were unsure about.
