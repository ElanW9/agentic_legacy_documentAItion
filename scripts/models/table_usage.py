"""Which unit reads or writes which table or view."""

from enum import StrEnum
from typing import Literal

from .common import ObjectType, StrictModel


class Operation(StrEnum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MERGE = "MERGE"


class AccessVia(StrEnum):
    STATIC = "STATIC"                    # plain SQL in the source
    DYNAMIC_LITERAL = "DYNAMIC_LITERAL"  # table name found in a string literal used for dynamic SQL


class TableAccess(StrictModel):
    unit_id: str
    unit_type: ObjectType
    relation: str
    relation_type: Literal[ObjectType.TABLE, ObjectType.VIEW]
    operation: Operation
    file: str
    line: int
    via: AccessVia = AccessVia.STATIC


class TableUsage(StrictModel):
    parser_version: str
    accesses: list[TableAccess]
