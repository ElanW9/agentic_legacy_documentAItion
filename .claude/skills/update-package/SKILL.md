---
name: update-package
description: Update the doc of a package whose source changed after it was written - move line numbers with update_package, resolve every !changed marker, re-check changed units, document added units, remove deleted ones, validate, and set status draft. Use when check_drift reports CHANGED for a package, or when asked to update a package doc.
---

# Update one package doc after a source change

Input: a package name, e.g. `UTIL_LOG`. Output: the package doc and its unit docs describing the current source, passing validation, and a `state/doc-status.json` entry with status `draft`. Follow CLAUDE.md. Never open `evaluation/`.

The goal is a small diff. Keep everything that is still true, including the reviewer's corrections and answered open questions. A reviewed doc is never rewritten from scratch; for a package with no doc yet, use `document-package`.

## 1. Check the starting point

Run `python -m scripts.check_drift`. The package must be listed as `CHANGED`. If `METADATA` is listed, run `python -m scripts.extract_metadata` first. Never edit `metadata/` by hand.

## 2. Move the line numbers

Run `python -m scripts.update_package <PACKAGE>`, read the report, then run it again with `--write`. The report is your work list:
- **units changed / added / removed**, compared by their source text;
- **facts added / removed**: dependencies, table accesses and risk flags, compared without line numbers;
- **marked**: every citation or line number whose source lines changed. These now end in `!changed` and still carry the old numbers.

If the script says no commit has the documented source, the old version is not in git history. Stop and ask whether to re-document the package with `document-package`.

## 3. Resolve every marker

`python -m scripts.validate_doc` lists each marker as a `changed` error. For each one:
1. Read the cited unit's current code, using the ranges in `metadata/objects.json`.
2. If the claim is still true, give it the correct new line numbers. If it is no longer true, rewrite it from the code, with a citation. If the code it described is gone, remove the claim.
3. Remove the marker.

Never remove a marker without reading the code, and never fix a number by adding the shift you expect.

## 4. Re-read every changed unit in full

A claim can become false while its own lines stay the same: "the only UPDATE in the unit" stops being true when a second UPDATE is added elsewhere. For every unit under "units changed", read its whole current source and check every claim about it: in its subsection, in its unit doc, in tables, and in package-wide sections such as Purpose and Side effects.

## 5. Added and removed units and facts

- **Units added:** document them as in `document-package` step 3: Public API or private units row, subsection, and a unit doc if the unit is complex.
- **Units removed:** delete their rows, subsections and unit doc, and the links to it.
- **Facts added or removed:** add or remove them in Dependencies, Tables touched and Side effects and risks. Then tick off the coverage list as in `document-package` step 5.

## 6. Open questions

- Keep the existing open questions and any answers in them.
- Remove a question only when the code it was about no longer exists, and say so in your report.
- Add a question for everything new that the code does not explain.

## 7. Validate and review

Run `python -m scripts.validate_doc` on the package doc and all its unit docs. Every doc must pass, with no `changed` errors left. Then run the `review-doc` checklist, at least for the changed and added units.

## 8. Record status

Update the entry in `state/doc-status.json` through `scripts.models.DocStatusFile`:
- `source_hash`: the new hash; `update_package --write` already put it in the doc header.
- `status`: `draft`, also when it was `approved`. The change needs a new review.
- `validation_passed`: the last validator result. `updated_at`: now.

Report:
- the update_package summary;
- how many markers you kept with new numbers, rewrote, or removed;
- which claims you rewrote beyond the markers (step 4), so the reviewer knows where to look: most of the diff is moved line numbers;
- units added or removed, open questions added or removed;
- anything you were unsure about.
