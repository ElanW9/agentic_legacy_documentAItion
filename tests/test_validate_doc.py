"""validate_doc.py: one passing doc, and broken variants of it that must each fail for the right reason.

The fixture package lives in tests/fixtures/validate/legacy/ so these tests do not depend on the pilot docs.
"""

import pytest

from scripts import validate_doc
from scripts.extract_metadata import REPO_ROOT, extract
from scripts.validate_doc import Metadata, main, validate

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "validate"
GOOD_DOC = (FIXTURES / "pkg_demo.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def meta():
    return Metadata(*extract(FIXTURES / "legacy"))


def errors(meta, text):
    return [(f.check, f.message) for f in validate(text, "doc.md", meta) if f.severity == "ERROR"]


def broken(old, new, count=1):
    assert GOOD_DOC.count(old) >= count, f"fixture text not found: {old!r}"
    return GOOD_DOC.replace(old, new, count)


def assert_fails(meta, text, check, fragment):
    found = errors(meta, text)
    assert any(c == check and fragment in m for c, m in found), found


def test_good_doc_passes(meta):
    findings = validate(GOOD_DOC, "doc.md", meta)
    assert [f for f in findings if f.severity == "ERROR"] == []
    # The name from the outdated comment is reported, but only as a warning.
    assert {f.message for f in findings} == {"`OLD_ITEMS`: occurs only in a source comment, not as code"}


def test_missing_section(meta):
    assert_fails(meta, broken("## Error handling", "## Errors"), "section", "missing section '## Error handling'")


def test_sections_out_of_order(meta):
    text = broken("## Purpose", "## Open questions\n\n1. moved [PKG_DEMO.GET_QTY:10]\n\n## Purpose")
    assert_fails(meta, text, "section", "out of order")


def test_missing_fixed_subsection(meta):
    assert_fails(meta, broken("### Package cycles", "### Cycles"), "section", "missing subsection '### Package cycles'")


def test_leftover_placeholder(meta):
    assert_fails(meta, broken("### Dynamic SQL\n\nNone found in metadata.", "### Dynamic SQL\n\n{{dynamic sql}}"),
                 "leftover", "placeholder")


def test_unknown_unit_in_citation(meta):
    assert_fails(meta, broken("[PKG_DEMO.ADD_QTY#2:27]", "[PKG_DEMO.ADD_QTYS:27]"),
                 "citation", "unknown id PKG_DEMO.ADD_QTYS")


def test_citation_outside_unit_range(meta):
    assert_fails(meta, broken("[PKG_DEMO.SET_STATUS:6-7]", "[PKG_DEMO.SET_STATUS:6-12]"),
                 "citation", "lines outside PKG_DEMO.SET_STATUS")


def test_overloaded_name_needs_overload_id(meta):
    assert_fails(meta, broken("[PKG_DEMO.ADD_QTY#1:22]", "[PKG_DEMO.ADD_QTY:22]"), "citation", "is overloaded")


def test_bare_package_citation(meta):
    assert_fails(meta, broken("[PKG_DEMO.G_COUNT:3]", "[PKG_DEMO:3]"), "citation", "not the package")


def test_malformed_citation(meta):
    assert_fails(meta, broken("[PKG_DEMO.ADD_QTY#2:27]", "[PKG_DEMO.ADD_QTY#2:line 27]"), "citation", "malformed")


def test_uncited_sentence(meta):
    text = broken("Adds `P_QTY` to `DEMO_ITEMS.QTY` [PKG_DEMO.ADD_QTY#2:27].",
                  "Adds `P_QTY` to `DEMO_ITEMS.QTY` [PKG_DEMO.ADD_QTY#2:27]. It is used by the nightly batch.")
    assert_fails(meta, text, "uncited", "nightly batch")


def test_uncited_open_question(meta):
    text = GOOD_DOC.rstrip() + "\n3. Is the commit intended?\n"
    assert_fails(meta, text, "uncited", "open question without citation")


def test_open_question_without_audience(meta):
    assert_fails(meta, broken("1. Business: What the status", "1. What the status"),
                 "question", "must start with Business: or Technical:")


def test_missing_plain_language_section(meta):
    assert_fails(meta, broken("## In plain language", "## Summary"), "section", "missing section '## In plain language'")


def test_code_in_plain_language_is_a_warning(meta):
    text = broken("Changing an item's status", "Changing `DEMO_ITEMS.STATUS`")
    findings = validate(text, "doc.md", meta)
    assert [f.message for f in findings if f.check == "plain"] == [
        "`code` in the plain-language section; use everyday words"]
    assert not [f for f in findings if f.severity == "ERROR"]


def test_uncited_table_row(meta):
    text = broken(" [PKG_DEMO.SET_STATUS:6] |", " |", count=2)
    assert_fails(meta, text, "uncited", "table row without citation")


def test_table_row_line_outside_unit(meta):
    assert_fails(meta, broken("| `PKG_DEMO.GET_QTY` | 16 |", "| `PKG_DEMO.GET_QTY` | 26 |"),
                 "citation", "line 26-26 is not inside")


def test_unknown_marker_exempts_only_its_clause(meta):
    text = broken("Adds `P_QTY` to `DEMO_ITEMS.QTY` [PKG_DEMO.ADD_QTY#2:27].",
                  "Adds `P_QTY` to `DEMO_ITEMS.QTY`; why: Unknown: needs human input.")
    assert_fails(meta, text, "uncited", "Adds `P_QTY`")


def test_unknown_marker_does_not_skip_line_numbers(meta):
    text = broken("| `PKG_DEMO.GET_QTY` | 16 | WHEN OTHERS | returns NULL; the error is not raised |",
                  "| `PKG_DEMO.GET_QTY` | 26 | WHEN OTHERS | Unknown: needs human input |")
    assert_fails(meta, text, "citation", "line 26-26 is not inside")


def test_invented_dependency_row(meta):
    text = broken("| `PKG_DEMO.SET_STATUS` | `TRG_DEMO_BU` | FIRES_TRIGGER | 5 |",
                  "| `PKG_DEMO.SET_STATUS` | `TRG_DEMO_BU` | FIRES_TRIGGER | 5 |\n"
                  "| `PKG_DEMO.GET_QTY` | `PKG_DEMO.SET_STATUS` | CALL | 14 |")
    assert_fails(meta, text, "dependency", "no CALL edge from PKG_DEMO.GET_QTY to PKG_DEMO.SET_STATUS")


def test_called_by_row_with_wrong_line(meta):
    # Line 21 is inside PKG_DEMO.ADD_QTY#1, so only the edge check catches it.
    text = broken("| `PKG_DEMO.ADD_QTY#1` | `PKG_DEMO.ADD_QTY#2` | 22 |", "| `PKG_DEMO.ADD_QTY#1` | `PKG_DEMO.ADD_QTY#2` | 21 |")
    assert_fails(meta, text, "dependency", "at line 21")


def test_broad_citation_does_not_cover_a_risk_flag(meta, monkeypatch):
    monkeypatch.setattr(validate_doc, "MAX_FLAG_SPAN", 5)  # the fixture body is shorter than the real cap
    text = GOOD_DOC.replace("[PKG_DEMO.SET_STATUS:3-8]", "[PKG_DEMO.SET_STATUS:3]")
    text = text.replace("[PKG_DEMO.SET_STATUS:6-7]", "[PKG_DEMO.SET_STATUS:6]")
    text = text.replace("[PKG_DEMO.SET_STATUS:5-7]", "[PKG_DEMO.SET_STATUS:5]")
    text = text.replace("open work [PKG_DEMO.SET_STATUS:7]", "open work [PKG_DEMO(body):1-30]")
    warnings = [f.message for f in validate(text, "doc.md", meta) if f.check == "coverage"]
    assert warnings == ["COMMIT at tests/fixtures/validate/legacy/packages/pkg_demo.pkb:7 (PKG_DEMO.SET_STATUS) "
                        "is not cited"]
    assert not [f for f in validate(GOOD_DOC, "doc.md", meta) if f.check == "coverage"]


def test_unknown_parameter(meta):
    assert_fails(meta, broken("Adds `P_QTY`", "Adds `P_AMOUNT`"), "reference", "not a parameter")


def test_unknown_table_and_column(meta):
    text = broken("Adds `P_QTY` to `DEMO_ITEMS.QTY`", "Adds `P_QTY` to `DEMO_ITEMS.QUANTITY` in `DEMO_STOCK`")
    assert_fails(meta, text, "reference", "DEMO_ITEMS has no column QUANTITY")
    assert_fails(meta, text, "reference", "`DEMO_STOCK`: not found")


def test_unknown_package_member(meta):
    assert_fails(meta, broken("`PKG_DEMO.G_COUNT` and commits", "`PKG_DEMO.G_TOTAL` and commits"),
                 "reference", "no subprogram or variable PKG_DEMO.G_TOTAL")


def test_comment_only_name_outside_comment_context(meta):
    text = broken("Sets `DEMO_ITEMS.STATUS`", "Sets `OLD_ITEMS` and `DEMO_ITEMS.STATUS`")
    assert_fails(meta, text, "reference", "only in a source comment")


def test_wrong_signature(meta):
    assert_fails(meta, broken("`FUNCTION GET_QTY(P_ID IN NUMBER) RETURN NUMBER`",
                              "`FUNCTION GET_QTY(P_ID IN NUMBER) RETURN VARCHAR2`"), "signature", "GET_QTY")


def test_undocumented_subprogram(meta):
    text = "\n".join(line for line in GOOD_DOC.splitlines() if "GET_QTY" not in line)
    assert_fails(meta, text, "coverage", "PKG_DEMO.GET_QTY is not documented")


def test_cli_with_real_metadata(tmp_path, capsys):
    doc = tmp_path / "set_status.md"
    doc.write_text("""# `PKG_ORDER.SET_STATUS`

## Purpose

Sets `ORDERS.ORD_STATUS` of one order to `P_STATUS` [PKG_ORDER.SET_STATUS:98-104].

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_ORD_ID` | IN | NUMBER | - | selects the order [PKG_ORDER.SET_STATUS:100] |
| `P_STATUS` | IN | NUMBER | - | new status [PKG_ORDER.SET_STATUS:100] |

## Logic walkthrough

1. Updates the order row [PKG_ORDER.SET_STATUS:100].
2. If no row was updated, it calls `PKG_ORDER.WLOG` and returns normally [PKG_ORDER.SET_STATUS:101-103].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `PKG_ORDER.WLOG` | CALL | 102 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `ORDERS` | UPDATE | 100 | STATIC |

## Side effects and risks

The comment at [legacy_code/tables/orders.sql:16] lists status values; their meaning: Unknown: needs human input.

## Error handling

None found in metadata.

## Open questions

1. Business: Should a missing order raise an error? Unknown: needs human input.
""", encoding="utf-8")
    assert main([str(doc)]) == 0
    assert capsys.readouterr().out.startswith("PASS")

    doc.write_text(doc.read_text(encoding="utf-8").replace("[PKG_ORDER.SET_STATUS:100].", "[PKG_ORDER.SET_STATUS:110]."),
                   encoding="utf-8")
    assert main([str(doc)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL") and "L16" in out and "lines outside PKG_ORDER.SET_STATUS" in out
