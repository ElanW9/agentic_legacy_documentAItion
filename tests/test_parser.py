"""Parser behaviour on small synthetic snippets."""

from scripts.extract_metadata import REPO_ROOT, mask_source
from scripts.models import (
    SCHEMA_ROOTS,
    AccessVia,
    DependencyKind,
    ObjectCatalog,
    RiskKind,
    Visibility,
)

TABLES = """
CREATE TABLE t_main (
  id    NUMBER(10) NOT NULL,
  code  VARCHAR2(2) DEFAULT 'XX',
  CONSTRAINT t_main_pk PRIMARY KEY (id)
);
COMMENT ON COLUMN t_main.code IS 'A=active';
CREATE TABLE t_log (msg VARCHAR2(100));
"""

SPEC = """
CREATE OR REPLACE PACKAGE p AS
  g_state NUMBER;
  PROCEDURE ovl(a IN NUMBER);
  PROCEDURE ovl(a IN NUMBER, b IN NUMBER);
  PROCEDURE run;
END p;
/
"""

BODY = """
CREATE OR REPLACE PACKAGE BODY p AS
  PROCEDURE hidden IS
  BEGIN
    NULL;
  END hidden;

  PROCEDURE ovl(a IN NUMBER) IS
  BEGIN
    ovl(a, 2);
  END ovl;

  PROCEDURE ovl(a IN NUMBER, b IN NUMBER) IS
  BEGIN
    -- UPDATE t_log SET msg = 'in a comment'
    INSERT INTO t_log (msg) VALUES ('DELETE FROM t_main');
  EXCEPTION
    WHEN OTHERS THEN
      NULL;
  END ovl;

  PROCEDURE run IS
  BEGIN
    g_state := 5;
    EXECUTE IMMEDIATE 'SELECT 1 FROM t_main WHERE id = :1' USING g_state;
    ovl(1);
    COMMIT;
  EXCEPTION
    WHEN OTHERS THEN
      ROLLBACK;
      RAISE;
  END run;
END p;
/
"""


def run(extract_snippet):
    return extract_snippet({"tables.sql": TABLES, "p.pks": SPEC, "p.pkb": BODY})


def test_mask_preserves_offsets():
    raw = "a := 'x;--y'; -- c\n/* d\n e */ b;"
    code, clean = mask_source(raw)
    assert len(code) == len(clean) == len(raw)
    assert code.count("\n") == raw.count("\n")
    assert "'x;--y'" in code and "-- c" not in code
    assert ";--" not in clean and "'" in clean


def test_visibility_and_overloads(extract_snippet):
    catalog, graph, _, _ = run(extract_snippet)
    subs = {s.unit_id: s for s in catalog.subprograms()}
    assert set(subs) == {"P.HIDDEN", "P.OVL#1", "P.OVL#2", "P.RUN"}
    assert subs["P.HIDDEN"].visibility == Visibility.PRIVATE
    assert subs["P.OVL#2"].visibility == Visibility.PUBLIC
    calls = {(e.source, e.target) for e in graph.edges if e.kind == DependencyKind.CALL}
    assert ("P.OVL#1", "P.OVL#2") in calls  # resolved by argument count
    assert ("P.RUN", "P.OVL#1") in calls


def test_comments_and_strings_are_not_sql(extract_snippet):
    _, _, usage, _ = run(extract_snippet)
    static = {(a.unit_id, a.operation.value, a.relation) for a in usage.accesses if a.via == AccessVia.STATIC}
    assert static == {("P.OVL#2", "INSERT", "T_LOG")}


def test_dynamic_sql_literal_table(extract_snippet):
    _, _, usage, risks = run(extract_snippet)
    dyn = {(a.unit_id, a.relation) for a in usage.accesses if a.via == AccessVia.DYNAMIC_LITERAL}
    assert dyn == {("P.RUN", "T_MAIN")}
    assert any(f.unit_id == "P.RUN" and f.kind == RiskKind.DYNAMIC_SQL for f in risks.flags)


def test_when_others_classification(extract_snippet):
    _, _, _, risks = run(extract_snippet)
    kinds = {(f.unit_id, f.kind) for f in risks.flags}
    assert ("P.OVL#2", RiskKind.WHEN_OTHERS_SWALLOW) in kinds
    assert ("P.RUN", RiskKind.WHEN_OTHERS_HANDLED) in kinds
    assert ("P.RUN", RiskKind.WHEN_OTHERS_SWALLOW) not in kinds


def test_risk_flags_basic(extract_snippet):
    _, _, _, risks = run(extract_snippet)
    kinds = {(f.unit_id, f.kind) for f in risks.flags}
    assert ("P.RUN", RiskKind.COMMIT) in kinds
    assert ("P.RUN", RiskKind.PACKAGE_STATE) in kinds
    assert ("P.HIDDEN", RiskKind.NO_CALLER) in kinds


def test_column_comment_and_default(extract_snippet):
    # Regression: the schema-prefix regex used to swallow the table name.
    catalog, _, _, _ = run(extract_snippet)
    col = next(c for t in catalog.tables if t.name == "T_MAIN" for c in t.columns if c.name == "CODE")
    assert col.comment == "A=active"
    assert col.default == "'XX'"


def test_output_round_trips_through_models(legacy):
    catalog, graph, usage, risks = legacy
    for model in (catalog, graph, usage, risks):
        assert type(model).model_validate_json(model.model_dump_json()) == model


def test_committed_metadata_is_current(legacy):
    """metadata/objects.json in the repo must match a fresh extraction."""
    catalog = legacy[0]
    on_disk = ObjectCatalog.model_validate_json((REPO_ROOT / "metadata" / "objects.json").read_text("utf-8"))
    assert on_disk == catalog


def test_schemas_exported():
    for name in SCHEMA_ROOTS:
        assert (REPO_ROOT / "schemas" / f"{name}.schema.json").exists()
