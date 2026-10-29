"""Dependency graph between units, packages, views, triggers and sequences."""

from enum import StrEnum

from pydantic import Field

from .common import ObjectType, StrictModel


class DependencyKind(StrEnum):
    CALL = "CALL"                    # unit calls a packaged subprogram
    VARIABLE_REF = "VARIABLE_REF"    # unit reads/writes another package's variable or constant
    SEQUENCE_USE = "SEQUENCE_USE"    # seq.NEXTVAL / CURRVAL
    VIEW_SOURCE = "VIEW_SOURCE"      # view selects from table/view
    TRIGGER_ON = "TRIGGER_ON"        # trigger fires on table
    EXTERNAL_CALL = "EXTERNAL_CALL"  # Oracle-supplied package (DBMS_*, UTL_*)


class Dependency(StrictModel):
    source: str
    source_type: ObjectType
    target: str = Field(description="Unit id; base name without #n when the overload is unresolved.")
    target_type: ObjectType
    kind: DependencyKind
    file: str
    line: int
    resolved: bool = Field(default=True, description="False when an overloaded call could not be matched.")


class DependencyGraph(StrictModel):
    parser_version: str
    edges: list[Dependency]
    package_cycles: list[list[str]] = Field(
        default=[], description="Elementary cycles in the package-level call graph."
    )

    def callers_of(self, unit_id: str) -> list[Dependency]:
        base = unit_id.split("#")[0]
        return [
            e for e in self.edges
            if e.kind == DependencyKind.CALL
            and (e.target == unit_id or (not e.resolved and e.target == base))
        ]
