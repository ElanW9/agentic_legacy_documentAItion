"""Object catalog: packages, subprograms, tables, views, triggers, sequences."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import ObjectType, ParamMode, SourceRef, StrictModel, Visibility


class SourceFile(StrictModel):
    path: str
    sha256: str
    line_count: int


class Parameter(StrictModel):
    name: str
    mode: ParamMode = ParamMode.IN
    datatype: str
    default: str | None = None


class Subprogram(StrictModel):
    unit_id: str = Field(description="PACKAGE.NAME, with #n suffix for overloads (body order).")
    package: str
    name: str
    kind: Literal[ObjectType.PROCEDURE, ObjectType.FUNCTION]
    visibility: Visibility
    overload: int | None = Field(default=None, description="1-based position among same-named units.")
    params: list[Parameter] = []
    return_type: str | None = None
    signature: str
    spec_ref: SourceRef | None = None
    body_ref: SourceRef


class PackageVariable(StrictModel):
    name: str
    datatype: str
    is_constant: bool
    default: str | None = None
    visibility: Visibility
    ref: SourceRef


class Package(StrictModel):
    name: str
    spec_ref: SourceRef | None = None
    body_ref: SourceRef | None = None
    subprograms: list[Subprogram] = []
    variables: list[PackageVariable] = []


class ConstraintKind(StrEnum):
    PRIMARY_KEY = "PRIMARY KEY"
    FOREIGN_KEY = "FOREIGN KEY"
    UNIQUE = "UNIQUE"
    CHECK = "CHECK"


class Column(StrictModel):
    name: str
    datatype: str
    nullable: bool = True
    default: str | None = None
    comment: str | None = None


class Constraint(StrictModel):
    name: str | None = None
    kind: ConstraintKind
    columns: list[str] = []
    ref_table: str | None = None
    ref_columns: list[str] = []
    condition: str | None = None


class Table(StrictModel):
    name: str
    ref: SourceRef
    columns: list[Column]
    constraints: list[Constraint] = []
    comment: str | None = None


class View(StrictModel):
    name: str
    ref: SourceRef
    columns: list[str] = []


class Trigger(StrictModel):
    name: str
    table: str
    timing: Literal["BEFORE", "AFTER", "INSTEAD OF"]
    events: list[Literal["INSERT", "UPDATE", "DELETE"]]
    row_level: bool
    ref: SourceRef


class Sequence(StrictModel):
    name: str
    ref: SourceRef


class ObjectCatalog(StrictModel):
    parser_version: str
    source_root: str
    files: list[SourceFile]
    packages: list[Package]
    tables: list[Table]
    views: list[View]
    triggers: list[Trigger]
    sequences: list[Sequence]

    def subprograms(self) -> list[Subprogram]:
        return [s for p in self.packages for s in p.subprograms]

    def unit_ids(self) -> set[str]:
        """Every id a doc may cite: subprograms, packages, tables, views, triggers, sequences."""
        ids = {s.unit_id for s in self.subprograms()}
        ids |= {p.name for p in self.packages}
        ids |= {t.name for t in self.tables} | {v.name for v in self.views}
        ids |= {t.name for t in self.triggers} | {s.name for s in self.sequences}
        return ids
